import sys, os
import traceback
from datetime import datetime
from decimal import Decimal
import disnake
from disnake.ext import commands, tasks
from disnake.enums import OptionType
from disnake.app_commands import Option
import time
import functools
import aiohttp, asyncio
import json

import numpy as np

import qrcode
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict
import uuid

from web3 import Web3
from web3.middleware import geth_poa_middleware
from ethtoken.abi import EIP20_ABI

from tronpy import AsyncTron
from tronpy.async_contract import AsyncContract, ShieldedTRC20, AsyncContractMethod
from tronpy.providers.async_http import AsyncHTTPProvider
from tronpy.exceptions import AddressNotFound
from tronpy.keys import PrivateKey

from httpx import AsyncClient, Timeout, Limits

from eth_account import Account

from pywallet import wallet as ethwallet
import ssl
from eth_utils import is_hex_address # Check hex only


import store, utils
import cn_addressvalidation

from Bot import get_token_list, num_format_coin, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, RowButton_close_message, RowButton_row_close_any_message, human_format, text_to_num, truncate, seconds_str, encrypt_string, decrypt_string
from config import config
import redis_utils
from utils import MenuPage

Account.enable_unaudited_hdwallet_features()


class RPCException(Exception):
    def __init__(self, message):
        super(RPCException, self).__init__(message)


class WalletAPI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        



    # ERC-20, TRC-20, native is one
    # Gas Token like BNB, xDAI, MATIC, TRX will be a different address
    async def sql_register_user(self, userID, coin: str, netname: str, type_coin: str, user_server: str, chat_id: int = 0, is_discord_guild: int=0):
        try:
            COIN_NAME = coin.upper()
            user_server = user_server.upper()
            balance_address = None
            main_address = None

            if type_coin.upper() == "ERC-20" and COIN_NAME != netname.upper():
                user_id_erc20 = str(userID) + "_" + type_coin.upper()
                type_coin_user = "ERC-20"
            elif type_coin.upper() == "ERC-20" and COIN_NAME == netname.upper():
                user_id_erc20 = str(userID) + "_" + COIN_NAME
                type_coin_user = COIN_NAME
            if type_coin.upper() in ["TRC-20", "TRC-10"] and COIN_NAME != netname.upper():
                type_coin = "TRC-20"
                type_coin_user = "TRC-20"
                user_id_erc20 = str(userID) + "_" + type_coin.upper()
            elif type_coin.upper() in ["TRC-20", "TRC-10"] and COIN_NAME == netname.upper():
                user_id_erc20 = str(userID) + "_" + COIN_NAME
                type_coin_user = "TRX"

            if type_coin.upper() == "ERC-20":
                # passed test XDAI, MATIC
                w = await self.create_address_eth()
                balance_address = w['address']
            elif type_coin.upper() in ["TRC-20", "TRC-10"]:
                # passed test TRX, USDT
                w = await self.create_address_trx()
                balance_address = w
            elif type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN"]:
                # passed test WRKZ, DEGO
                main_address = getattr(getattr(self.bot.coin_list, COIN_NAME), "MainAddress")
                get_prefix_char = getattr(getattr(self.bot.coin_list, COIN_NAME), "get_prefix_char")
                get_prefix = getattr(getattr(self.bot.coin_list, COIN_NAME), "get_prefix")
                get_addrlen = getattr(getattr(self.bot.coin_list, COIN_NAME), "get_addrlen")
                balance_address = {}
                balance_address['payment_id'] = cn_addressvalidation.paymentid()
                balance_address['integrated_address'] = cn_addressvalidation.cn_make_integrated(main_address, get_prefix_char, get_prefix, get_addrlen, balance_address['payment_id'])['integrated_address']
            elif type_coin.upper() == "XMR":
                # passed test WOW
                main_address = getattr(getattr(self.bot.coin_list, COIN_NAME), "MainAddress")
                balance_address = await self.make_integrated_address_xmr(main_address, COIN_NAME)
            elif type_coin.upper() == "NANO":
                walletkey = decrypt_string(getattr(getattr(self.bot.coin_list, COIN_NAME), "walletkey"))
                balance_address = await self.call_nano(COIN_NAME, payload='{ "action": "account_create", "wallet": "'+walletkey+'" }')
            elif type_coin.upper() == "BTC":
                # passed test PGO, XMY
                naming = config.redis.prefix + "_"+user_server+"_" + str(userID)
                payload = f'"{naming}"'
                address_call = await self.call_doge('getnewaddress', COIN_NAME, payload=payload)
                reg_address = {}
                reg_address['address'] = address_call
                payload = f'"{address_call}"'
                key_call = await self.call_doge('dumpprivkey', COIN_NAME, payload=payload)
                reg_address['privateKey'] = key_call
                if reg_address['address'] and reg_address['privateKey']:
                    balance_address = reg_address
            elif type_coin.upper() == "CHIA":
                # passed test XFX
                payload = {'wallet_id': 1, 'new_address': True}
                try:
                    address_call = await self.call_xch('get_next_address', COIN_NAME, payload=payload)
                    if 'success' in address_call and address_call['address']:
                        balance_address = address_call
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)

            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        if netname and netname not in ["TRX"]:
                            sql = """ INSERT INTO `erc20_user` (`user_id`, `user_id_erc20`, `type`, `balance_wallet_address`, `address_ts`, 
                                      `seed`, `create_dump`, `private_key`, `public_key`, `xprivate_key`, `xpublic_key`, 
                                      `called_Update`, `user_server`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (str(userID), user_id_erc20, type_coin_user, w['address'], int(time.time()), 
                                              encrypt_string(w['seed']), encrypt_string(str(w)), encrypt_string(str(w['private_key'])), w['public_key'], 
                                              encrypt_string(str(w['xprivate_key'])), w['xpublic_key'], int(time.time()), user_server, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': w['address']}
                        elif netname and netname in ["TRX"]:
                            sql = """ INSERT INTO `trc20_user` (`user_id`, `user_id_trc20`, `type`, `balance_wallet_address`, `hex_address`, `address_ts`, 
                                      `private_key`, `public_key`, `called_Update`, `user_server`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (str(userID), user_id_erc20, type_coin_user, w['base58check_address'], w['hex_address'], int(time.time()), 
                                              encrypt_string(str(w['private_key'])), w['public_key'], int(time.time()), user_server, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': w['base58check_address']}
                        elif type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                            sql = """ INSERT INTO cn_user_paymentid (`coin_name`, `user_id`, `user_id_coin`, `main_address`, `paymentid`, 
                                      `balance_wallet_address`, `paymentid_ts`, `user_server`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, str(userID), "{}_{}".format(userID, COIN_NAME), main_address, balance_address['payment_id'], 
                                                    balance_address['integrated_address'], int(time.time()), user_server, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['integrated_address'], 'paymentid': balance_address['payment_id']}
                        elif type_coin.upper() == "NANO":
                            sql = """ INSERT INTO `nano_user` (`coin_name`, `user_id`, `user_id_coin`, `balance_wallet_address`, `address_ts`, `user_server`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, str(userID), "{}_{}".format(userID, COIN_NAME), balance_address['account'], int(time.time()), user_server, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['account']}
                        elif type_coin.upper() == "BTC":
                            sql = """ INSERT INTO `doge_user` (`coin_name`, `user_id`, `user_id_coin`, `balance_wallet_address`, `address_ts`, `privateKey`, `user_server`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, str(userID), "{}_{}".format(userID, COIN_NAME), balance_address['address'], int(time.time()), 
                                                    encrypt_string(balance_address['privateKey']), user_server, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin.upper() == "CHIA":
                            sql = """ INSERT INTO `xch_user` (`coin_name`, `user_id`, `user_id_coin`, `balance_wallet_address`, `address_ts`, `user_server`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, str(userID), "{}_{}".format(userID, COIN_NAME), balance_address['address'], int(time.time()), user_server, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    async def sql_get_userwallet(self, userID, coin: str, netname: str, type_coin: str, user_server: str = 'DISCORD', chat_id: int = 0):
        # netname null or None, xDai, MATIC, TRX, BSC
        user_server = user_server.upper()
        COIN_NAME = coin.upper()
        if type_coin.upper() == "ERC-20" and COIN_NAME != netname.upper():
            user_id_erc20 = str(userID) + "_" + type_coin.upper()
        elif type_coin.upper() == "ERC-20" and COIN_NAME == netname.upper():
            user_id_erc20 = str(userID) + "_" + COIN_NAME
        if type_coin.upper() in ["TRC-20", "TRC-10"] and COIN_NAME != netname.upper():
            type_coin = "TRC-20"
            user_id_erc20 = str(userID) + "_" + type_coin.upper()
        elif type_coin.upper() in ["TRC-20", "TRC-10"] and COIN_NAME == netname.upper():
            user_id_erc20 = str(userID) + "_" + COIN_NAME
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if netname and netname not in ["TRX"]:
                        sql = """ SELECT * FROM `erc20_user` WHERE `user_id`=%s 
                                  AND `user_id_erc20`=%s AND `user_server` = %s LIMIT 1 """
                        await cur.execute(sql, (str(userID), user_id_erc20, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif netname and netname in ["TRX"]:
                        sql = """ SELECT * FROM `trc20_user` WHERE `user_id`=%s 
                                  AND `user_id_trc20`=%s AND `user_server` = %s LIMIT 1 """
                        await cur.execute(sql, (str(userID), user_id_erc20, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql = """ SELECT * FROM `cn_user_paymentid` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server` = %s LIMIT 1 """
                        await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "NANO":
                        sql = """ SELECT * FROM `nano_user` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server` = %s LIMIT 1 """
                        await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "BTC":
                        sql = """ SELECT * FROM `doge_user` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server` = %s LIMIT 1 """
                        await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "CHIA":
                        sql = """ SELECT * FROM `xch_user` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server` = %s LIMIT 1 """
                        await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                        result = await cur.fetchone()
                        if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None


    async def call_nano(self, coin: str, payload: str) -> Dict:
        timeout = 100
        COIN_NAME = coin.upper()
        url = getattr(getattr(self.bot.coin_list, COIN_NAME), "rpchost")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        decoded_data = json.loads(res_data)
                        return decoded_data
        except asyncio.TimeoutError:
            print('TIMEOUT: COIN: {} - timeout {}'.format(coin.upper(), timeout))
            await logchanbot('TIMEOUT: call_nano COIN: {} - timeout {}'.format(coin.upper(), timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def nano_get_wallet_balance_elements(self, coin: str) -> str:
        COIN_NAME = coin.upper()
        walletkey = decrypt_string(getattr(getattr(self.bot.coin_list, COIN_NAME), "walletkey"))
        get_wallet_balance = await self.call_nano(COIN_NAME, payload='{ "action": "wallet_balances", "wallet": "'+walletkey+'" }')
        if get_wallet_balance and 'balances' in get_wallet_balance:
            return get_wallet_balance['balances']
        return None

    async def nano_sendtoaddress(self, source: str, to_address: str, atomic_amount: int, coin: str) -> str:
        COIN_NAME = coin.upper()
        walletkey = decrypt_string(getattr(getattr(self.bot.coin_list, COIN_NAME), "walletkey"))
        payload = '{ "action": "send", "wallet": "'+walletkey+'", "source": "'+source+'", "destination": "'+to_address+'", "amount": "'+str(atomic_amount)+'" }'
        sending = await self.call_nano(COIN_NAME, payload=payload)
        if sending and 'block' in sending:
            return sending
        return None

    async def nano_validate_address(self, coin: str, account: str) -> str:
        COIN_NAME = coin.upper()
        valid_address = await self.call_nano(COIN_NAME, payload='{ "action": "validate_account_number", "account": "'+account+'" }')
        if valid_address and valid_address['valid'] == "1":
            return True
        return None

    async def send_external_nano(self, main_address: str, user_from: str, amount: float, to_address: str, coin: str, coin_decimal):
        global pool
        COIN_NAME = coin.upper()
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    tx_hash = await self.nano_sendtoaddress(main_address, to_address, int(Decimal(amount)*10**coin_decimal), COIN_NAME)
                    if tx_hash:
                        updateTime = int(time.time())
                        async with conn.cursor() as cur: 
                            sql = """ INSERT INTO nano_external_tx (`coin_name`, `user_id`, `amount`, `decimal`, `to_address`, `date`, `tx_hash`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, user_from, amount, coin_decimal, to_address, int(time.time()), tx_hash['block'],))
                            await conn.commit()
                            return tx_hash
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None


    async def call_xch(self, method_name: str, coin: str, payload: Dict=None) -> Dict:
        timeout = 100
        COIN_NAME = coin.upper()

        headers = {
            'Content-Type': 'application/json',
        }
        if payload is None:
            data = '{}'
        else:
            data = payload
        url = getattr(getattr(self.bot.coin_list, COIN_NAME), "rpchost") + '/' + method_name.lower()
        try:
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(getattr(getattr(self.bot.coin_list, COIN_NAME), "cert_path"), getattr(getattr(self.bot.coin_list, COIN_NAME), "key_path"))
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
                async with session.post(url, json=data, headers=headers, timeout=timeout, ssl=ssl_context) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        decoded_data = json.loads(res_data)
                        return decoded_data
                    else:
                        print(f'Call {COIN_NAME} returns {str(response.status)} with method {method_name}')
        except asyncio.TimeoutError:
            print('TIMEOUT: method_name: {} - COIN: {} - timeout {}'.format(method_name, COIN_NAME, timeout))
            await logchanbot('call_doge: method_name: {} - COIN: {} - timeout {}'.format(method_name, COIN_NAME, timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())


    async def send_external_xch(self, user_from: str, amount: float, to_address: str, coin: str, coin_decimal: int, tx_fee: float, withdraw_fee: float, user_server: str='DISCORD'):
        global pool
        COIN_NAME = coin.upper()
        try:
            payload = {
                "wallet_id": 1,
                "amount": int(amount*10**coin_decimal),
                "address": to_address,
                "fee": int(tx_fee*10**coin_decimal)
            }
            result = await self.call_xch('send_transaction', COIN_NAME, payload=payload)
            if result:
                result['tx_hash'] = result['transaction']
                result['transaction_id'] = result['transaction_id']
                await store.openConnection()
                async with store.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        async with conn.cursor() as cur: 
                            sql = """ INSERT INTO xch_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, user_from, amount, float(result['tx_hash']['fee_amount']/10**coin_decimal), withdraw_fee, coin_decimal, to_address, int(time.time()), result['tx_hash']['name'], user_server,))
                            await conn.commit()
                            return result['tx_hash']['name']
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None


    async def call_doge(self, method_name: str, coin: str, payload: str = None) -> Dict:
        timeout = 64
        COIN_NAME = coin.upper()
        headers = {
            'content-type': 'text/plain;',
        }
        if payload is None:
            data = '{"jsonrpc": "1.0", "id":"'+str(uuid.uuid4())+'", "method": "'+method_name+'", "params": [] }'
        else:
            data = '{"jsonrpc": "1.0", "id":"'+str(uuid.uuid4())+'", "method": "'+method_name+'", "params": ['+payload+'] }'
        
        url = getattr(getattr(self.bot.coin_list, COIN_NAME), "daemon_address")
        # print(url, method_name)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        decoded_data = json.loads(res_data)
                        return decoded_data['result']
                    else:
                        print(f'Call {COIN_NAME} returns {str(response.status)} with method {method_name}')
                        print(data)
                        print(url)
        except asyncio.TimeoutError:
            print('TIMEOUT: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin.upper(), timeout))
            await logchanbot('call_doge: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin.upper(), timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    async def send_external_doge(self, user_from: str, amount: float, to_address: str, coin: str, tx_fee: float, withdraw_fee: float, user_server: str):
        global pool
        user_server = user_server.upper()
        COIN_NAME = coin.upper()
        try:
            comment = user_from
            comment_to = to_address
            payload = f'"{to_address}", {amount}, "{comment}", "{comment_to}", false'
            if COIN_NAME in ["PGO"]:
                payload = f'"{to_address}", {amount}, "{comment}", "{comment_to}"'
            txHash = await self.call_doge('sendtoaddress', COIN_NAME, payload=payload)
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO doge_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `to_address`, `date`, `tx_hash`, `user_server`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (COIN_NAME, user_from, amount, tx_fee, withdraw_fee, to_address, int(time.time()), txHash, user_server))
                    await conn.commit()
                    return txHash
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return False


    async def make_integrated_address_xmr(self, address: str, coin: str, paymentid: str = None):
        COIN_NAME = coin.upper()
        if paymentid:
            try:
                value = int(paymentid, 16)
            except ValueError:
                return False
        else:
            paymentid = cn_addressvalidation.paymentid(8)

        if COIN_NAME == "LTHN":
            payload = {
                "payment_id": {} or paymentid
            }
            address_ia = await self.call_aiohttp_wallet_xmr_bcn('make_integrated_address', COIN_NAME, payload=payload)
            if address_ia: return address_ia
            return None
        else:
            payload = {
                "standard_address" : address,
                "payment_id": {} or paymentid
            }
            address_ia = await self.call_aiohttp_wallet_xmr_bcn('make_integrated_address', COIN_NAME, payload=payload)
            if address_ia: return address_ia
            return None

    async def create_address_eth(self):
        def create_eth_wallet():
            seed = ethwallet.generate_mnemonic()
            w = ethwallet.create_wallet(network="ETH", seed=seed, children=1)
            return w

        wallet_eth = functools.partial(create_eth_wallet)
        create_wallet = await self.bot.loop.run_in_executor(None, wallet_eth)
        return create_wallet

    async def create_address_trx(self):
        try:
            _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                       timeout=Timeout(timeout=10, connect=5, read=5))
            TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
            create_wallet = TronClient.generate_address()
            await TronClient.close()
            return create_wallet
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    def check_address_erc20(self, address: str):
        if is_hex_address(address):
            return address
        return False


    async def call_aiohttp_wallet_xmr_bcn(self, method_name: str, coin: str, time_out: int = None, payload: Dict = None) -> Dict:
        COIN_NAME = coin.upper()
        coin_family = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        full_payload = {
            'params': payload or {},
            'jsonrpc': '2.0',
            'id': str(uuid.uuid4()),
            'method': f'{method_name}'
        }
        url = getattr(getattr(self.bot.coin_list, COIN_NAME), "wallet_address")
        timeout = time_out or 60
        if method_name == "save" or method_name == "store":
            timeout = 300
        elif method_name == "sendTransaction":
            timeout = 180
        elif method_name == "createAddress" or method_name == "getSpendKeys":
            timeout = 60
        try:
            if COIN_NAME == "LTHN":
                # Copied from XMR below
                try:
                    async with aiohttp.ClientSession(headers={'Content-Type': 'application/json'}) as session:
                        async with session.post(url, json=full_payload, timeout=timeout) as response:
                            # sometimes => "message": "Not enough unlocked money" for checking fee
                            if method_name == "split_integrated_address":
                                # we return all data including error
                                if response.status == 200:
                                    res_data = await response.read()
                                    res_data = res_data.decode('utf-8')
                                    decoded_data = json.loads(res_data)
                                    return decoded_data
                            elif method_name == "transfer":
                                print('{} - transfer'.format(COIN_NAME))

                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                if method_name == "transfer":
                                    print(res_data)
                                
                                decoded_data = json.loads(res_data)
                                if 'result' in decoded_data:
                                    return decoded_data['result']
                                else:
                                    return None
                except asyncio.TimeoutError:
                    await logchanbot('call_aiohttp_wallet: method_name: {} COIN_NAME {} - timeout {}\nfull_payload:\n{}'.format(method_name, COIN_NAME, timeout, json.dumps(payload)))
                    print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method_name, COIN_NAME, timeout))
                    return None
                except Exception:
                    await logchanbot(traceback.format_exc())
                    return None
            elif coin_family == "XMR":
                try:
                    async with aiohttp.ClientSession(headers={'Content-Type': 'application/json'}) as session:
                        async with session.post(url, json=full_payload, timeout=timeout) as response:
                            # sometimes => "message": "Not enough unlocked money" for checking fee
                            if method_name == "transfer":
                                print('{} - transfer'.format(COIN_NAME))
                                # print(full_payload)
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                if method_name == "transfer":
                                    print(res_data)
                                
                                decoded_data = json.loads(res_data)
                                if 'result' in decoded_data:
                                    return decoded_data['result']
                                else:
                                    return None
                except asyncio.TimeoutError:
                    await logchanbot('call_aiohttp_wallet: method_name: {} COIN_NAME {} - timeout {}\nfull_payload:\n{}'.format(method_name, COIN_NAME, timeout, json.dumps(payload)))
                    print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method_name, COIN_NAME, timeout))
                    return None
                except Exception:
                    await logchanbot(traceback.format_exc())
                    return None
            elif coin_family in ["TRTL-SERVICE", "BCN"]:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, json=full_payload, timeout=timeout) as response:
                            if response.status == 200 or response.status == 201:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                
                                decoded_data = json.loads(res_data)
                                if 'result' in decoded_data:
                                    return decoded_data['result']
                                else:
                                    await logchanbot(str(res_data))
                                    return None
                            else:
                                await logchanbot(str(response))
                                return None
                except asyncio.TimeoutError:
                    await logchanbot('call_aiohttp_wallet: {} COIN_NAME {} - timeout {}\nfull_payload:\n{}'.format(method_name, COIN_NAME, timeout, json.dumps(payload)))
                    print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method_name, COIN_NAME, timeout))
                    return None
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                    return None
        except asyncio.TimeoutError:
            await logchanbot('call_aiohttp_wallet: method_name: {} - coin_family: {} - timeout {}'.format(method_name, coin_family, timeout))
            print('TIMEOUT: method_name: {} - coin_family: {} - timeout {}'.format(method_name, coin_family, timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())


    async def send_external_xmr(self, type_coin: str, from_address: str, user_from: str, amount: float, to_address: str, coin: str, coin_decimal: int, tx_fee: float, withdraw_fee: float, is_fee_per_byte: int, get_mixin: int, user_server: str, wallet_api_url: str=None, wallet_api_header: str=None, paymentId: str=None):
        global pool
        COIN_NAME = coin.upper()
        user_server = user_server.upper()
        time_out = 32
        if COIN_NAME == "DEGO":
            time_out = 120
        try:
            if type_coin == "XMR":
                acc_index = 0
                payload = {
                    "destinations": [{'amount': int(amount*10**coin_decimal), 'address': to_address}],
                    "account_index": acc_index,
                    "subaddr_indices": [],
                    "priority": 1,
                    "unlock_time": 0,
                    "get_tx_key": True,
                    "get_tx_hex": False,
                    "get_tx_metadata": False
                }
                if COIN_NAME == "UPX":
                    payload = {
                        "destinations": [{'amount': int(amount*10**coin_decimal), 'address': to_address}],
                        "account_index": acc_index,
                        "subaddr_indices": [],
                        "ring_size": 11,
                        "get_tx_key": True,
                        "get_tx_hex": False,
                        "get_tx_metadata": False
                    }
                result = await self.call_aiohttp_wallet_xmr_bcn('transfer', COIN_NAME, time_out=time_out, payload=payload)
                if result and 'tx_hash' in result and 'tx_key' in result:
                    await store.openConnection()
                    async with store.pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `tx_key`, `user_server`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, user_from, amount, tx_fee, withdraw_fee, coin_decimal, to_address, int(time.time()), result['tx_hash'], result['tx_key'], user_server,))
                            await conn.commit()
                            return result['tx_hash']
            elif (type_coin == "TRTL-SERVICE" or type_coin == "BCN") and paymentId is None:
                if is_fee_per_byte != 1:
                    payload = {
                        'addresses': [from_address],
                        'transfers': [{
                            "amount": int(amount*10**coin_decimal),
                            "address": to_address
                        }],
                        'fee': int(tx_fee*10**coin_decimal),
                        'anonymity': get_mixin
                    }
                else:
                    payload = {
                        'addresses': [from_address],
                        'transfers': [{
                            "amount": int(amount*10**coin_decimal),
                            "address": to_address
                        }],
                        'anonymity': get_mixin
                    }
                result = await self.call_aiohttp_wallet_xmr_bcn('sendTransaction', COIN_NAME, time_out=time_out, payload=payload)
                if result and 'transactionHash' in result:
                    if is_fee_per_byte != 1:
                        tx_hash = {"transactionHash": result['transactionHash'], "fee": tx_fee}
                    else:
                        tx_hash = {"transactionHash": result['transactionHash'], "fee": result['fee']}
                        tx_fee = float(tx_hash['fee']/10**coin_decimal)
                    try:
                        await store.openConnection()
                        async with store.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                await cur.execute(sql, (COIN_NAME, user_from, amount, tx_fee, withdraw_fee, coin_decimal, to_address, int(time.time()), tx_hash['transactionHash'], user_server))
                                await conn.commit()
                                return tx_hash['transactionHash']
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
            elif type_coin == "TRTL-API" and paymentId is None:
                if is_fee_per_byte != 1:
                    json_data = {
                        "destinations": [{"address": to_address, "amount": int(amount*10**coin_decimal)}],
                        "mixin": get_mixin,
                        "fee": int(tx_fee*10**coin_decimal),
                        "sourceAddresses": [
                            from_address
                        ],
                        "paymentID": "",
                        "changeAddress": from_address
                    }
                else:
                    json_data = {
                        "destinations": [{"address": to_address, "amount": int(amount*10**coin_decimal)}],
                        "mixin": get_mixin,
                        "sourceAddresses": [
                            from_address
                        ],
                        "paymentID": "",
                        "changeAddress": from_address
                    }
                method = "/transactions/send/advanced"
                try:
                    headers = {
                        'X-API-KEY': wallet_api_header,
                        'Content-Type': 'application/json'
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(wallet_api_url + method, headers=headers, json=json_data, timeout=time_out) as response:
                            json_resp = await response.json()
                            if response.status == 200 or response.status == 201:
                                if is_fee_per_byte != 1:
                                    tx_hash = {"transactionHash": json_resp['transactionHash'], "fee": tx_fee}
                                else:
                                    tx_hash = {"transactionHash": json_resp['transactionHash'], "fee": json_resp['fee']}
                                    tx_fee = float(tx_hash['fee']/10**coin_decimal)
                                try:
                                    await store.openConnection()
                                    async with store.pool.acquire() as conn:
                                        async with conn.cursor() as cur:
                                            sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                            await cur.execute(sql, (COIN_NAME, user_from, amount, tx_fee, withdraw_fee, coin_decimal, to_address, int(time.time()), tx_hash['transactionHash'], user_server))
                                            await conn.commit()
                                            return tx_hash['transactionHash']
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            elif 'errorMessage' in json_resp:
                                raise RPCException(json_resp['errorMessage'])
                            else:
                                await logchanbot('walletapi_send_transaction: {} response: {}'.format(method, response))
                except asyncio.TimeoutError:
                    await logchanbot('walletapi_send_transaction: TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method, COIN_NAME, time_out))
            elif (type_coin == "TRTL-SERVICE" or type_coin == "BCN") and paymentId is not None:
                if COIN_NAME == "DEGO":
                    time_out = 300
                if is_fee_per_byte != 1:
                    payload = {
                        'addresses': [from_address],
                        'transfers': [{
                            "amount": int(amount*10**coin_decimal),
                            "address": to_address
                        }],
                        'fee': int(tx_fee*10**coin_decimal),
                        'anonymity': get_mixin,
                        'paymentId': paymentid,
                        'changeAddress': from_address
                    }
                else:
                    payload = {
                        'addresses': [from_address],
                        'transfers': [{
                            "amount": int(amount*10**coin_decimal),
                            "address": to_address
                        }],
                        'anonymity': get_mixin,
                        'paymentId': paymentid,
                        'changeAddress': from_address
                    }
                result = None
                result = await rpc_client.call_aiohttp_wallet_xmr_bcn('sendTransaction', COIN_NAME, time_out=time_out, payload=payload)
                if result and 'transactionHash' in result:
                    if is_fee_per_byte != 1:
                        tx_hash = {"transactionHash": result['transactionHash'], "fee": tx_fee}
                    else:
                        tx_hash = {"transactionHash": result['transactionHash'], "fee": result['fee']}
                        tx_fee = float(tx_hash['fee']/10**coin_decimal)
                    try:
                        await store.openConnection()
                        async with store.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `paymentid`, `date`, `tx_hash`, `user_server`) 
                                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                await cur.execute(sql, (COIN_NAME, user_from, amount, tx_fee, withdraw_fee, coin_decimal, to_address, paymentid, int(time.time()), tx_hash['transactionHash'], user_server))
                                await conn.commit()
                                return tx_hash['transactionHash']
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
            elif type_coin == "TRTL-API" and paymentId is not None:
                if is_fee_per_byte != 1:
                    json_data = {
                        'sourceAddresses': [from_address],
                        'destinations': [{
                            "amount": int(amount*10**coin_decimal),
                            "address": to_address
                        }],
                        'fee': int(tx_fee*10**coin_decimal),
                        'mixin': get_mixin,
                        'paymentID': paymentid,
                        'changeAddress': from_address
                    }
                else:
                    json_data = {
                        'sourceAddresses': [from_address],
                        'destinations': [{
                            "amount": int(amount*10**coin_decimal),
                            "address": to_address
                        }],
                        'mixin': get_mixin,
                        'paymentID': paymentid,
                        'changeAddress': from_address
                    }
                method = "/transactions/send/advanced"
                try:
                    headers = {
                        'X-API-KEY': wallet_api_header,
                        'Content-Type': 'application/json'
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(wallet_api_url + method, headers=headers, json=json_data, timeout=time_out) as response:
                            json_resp = await response.json()
                            if response.status == 200 or response.status == 201:
                                if is_fee_per_byte != 1:
                                    tx_hash = {"transactionHash": json_resp['transactionHash'], "fee": tx_fee}
                                else:
                                    tx_hash = {"transactionHash": json_resp['transactionHash'], "fee": json_resp['fee']}
                                    tx_fee = float(tx_hash['fee']/10**coin_decimal)
                                try:
                                    await store.openConnection()
                                    async with store.pool.acquire() as conn:
                                        async with conn.cursor() as cur:
                                            sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `paymentid`, `date`, `tx_hash`, `user_server`) 
                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                            await cur.execute(sql, (COIN_NAME, user_from, amount, tx_fee, withdraw_fee, coin_decimal, to_address, paymentid, int(time.time()), tx_hash['transactionHash'], user_server))
                                            await conn.commit()
                                            return tx_hash['transactionHash']
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            elif 'errorMessage' in json_resp:
                                raise RPCException(json_resp['errorMessage'])
                except asyncio.TimeoutError:
                    await logchanbot('walletapi_send_transaction_id: TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method, COIN_NAME, time_out))
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None


class Wallet(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.WalletAPI = WalletAPI(self.bot)
        
        redis_utils.openRedis()
        self.notify_new_tx_user_noconfirmation.start()
        self.notify_new_tx_user.start()

        # nano, banano
        self.update_balance_nano.start()
        # TRTL-API
        self.update_balance_trtl_api.start()
        # TRTL-SERVICE
        self.update_balance_trtl_service.start()
        # XMR
        self.update_balance_xmr.start()
        # BTC
        self.update_balance_btc.start()
        # CHIA
        self.update_balance_chia.start()
        # ERC-20
        self.update_balance_erc20.start()
        self.unlocked_move_pending_erc20.start()
        self.update_balance_address_history_erc20.start()
        self.notify_new_confirmed_spendable_erc20.start()
        
        # TRC-20
        self.update_balance_trc20.start()
        self.unlocked_move_pending_trc20.start()
        self.notify_new_confirmed_spendable_trc20.start()


    # Notify user
    @tasks.loop(seconds=15.0)
    async def notify_new_confirmed_spendable_erc20(self):
        await asyncio.sleep(3.0)
        try:
            notify_list = await store.sql_get_pending_notification_users_erc20(SERVER_BOT)
            if len(notify_list) > 0:
                for each_notify in notify_list:
                    is_notify_failed = False
                    member = self.bot.get_user(int(each_notify['user_id']))
                    if member:
                        msg = "You got a new deposit confirmed: ```" + "Amount: {} {}".format(num_format_coin(each_notify['real_amount'], each_notify['token_name'], each_notify['token_decimal'], False), each_notify['token_name']) + "```"
                        try:
                            await member.send(msg)
                        except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                            is_notify_failed = True
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        update_status = await store.sql_updating_pending_move_deposit_erc20(True, is_notify_failed, each_notify['txn'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @tasks.loop(seconds=15.0)
    async def notify_new_confirmed_spendable_trc20(self):
        await asyncio.sleep(3.0)
        try:
            notify_list = await store.sql_get_pending_notification_users_trc20(SERVER_BOT)
            if notify_list and len(notify_list) > 0:
                for each_notify in notify_list:
                    is_notify_failed = False
                    member = self.bot.get_user(int(each_notify['user_id']))
                    if member:
                        msg = "You got a new deposit confirmed: ```" + "Amount: {} {}".format(num_format_coin(each_notify['real_amount'], each_notify['token_name'], each_notify['token_decimal'], False), each_notify['token_name']) + "```"
                        try:
                            await member.send(msg)
                        except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                            is_notify_failed = True
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        update_status = await store.sql_updating_pending_move_deposit_trc20(True, is_notify_failed, each_notify['txn'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    # Notify user
    @tasks.loop(seconds=15.0)
    async def notify_new_tx_user(self):
        await asyncio.sleep(5.0)
        await self.bot.wait_until_ready()

        pending_tx = await store.sql_get_new_tx_table('NO', 'NO')
        if len(pending_tx) > 0:
            # let's notify_new_tx_user
            for eachTx in pending_tx:
                try:
                    COIN_NAME = eachTx['coin_name']
                    coin_family = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR", "BTC", "CHIA", "NANO"]:
                        user_tx = await store.sql_get_userwallet_by_paymentid(eachTx['payment_id'], eachTx['coin_name'], coin_family, SERVER_BOT)
                        if user_tx:
                            user_found = self.bot.get_user(int(user_tx['user_id']))
                            if user_found:
                                is_notify_failed = False
                                try:
                                    msg = None
                                    if coin_family == "NANO":
                                        msg = "You got a new deposit: ```" + "Coin: {}\nAmount: {}".format(eachTx['coin_name'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False)) + "```"   
                                    elif coin_family != "BTC":
                                        msg = "You got a new deposit confirmed: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False), eachTx['height']) + "```"                         
                                    else:
                                        msg = "You got a new deposit confirmed: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False), eachTx['blockhash']) + "```"
                                    await user_found.send(msg)
                                except (discord.Forbidden, discord.errors.Forbidden, discord.errors.HTTPException) as e:
                                    is_notify_failed = True
                                    pass
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                update_notify_tx = await store.sql_update_notify_tx_table(eachTx['payment_id'], user_tx['user_id'], user_found.name, 'YES', 'NO' if is_notify_failed == False else 'YES')
                            else:
                                # try to find if it is guild
                                guild_found = self.bot.get_guild(int(user_tx['user_id']))
                                if guild_found: user_found = self.bot.get_user(guild_found.owner.id)
                                if guild_found and user_found:
                                    is_notify_failed = False
                                    try:
                                        msg = None
                                        if coin_family == "NANO":
                                            msg = "Your guild `{}` got a new deposit: ```" + "Coin: {}\nAmount: {}".format(guild_found.name, eachTx['coin_name'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False)) + "```"   
                                        elif coin_family != "BTC":
                                            msg = "Your guild `{}` got a new deposit confirmed: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}".format(guild_found.name, eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False), eachTx['height']) + "```"                         
                                        else:
                                            msg = "Your guild `{}` got a new deposit confirmed: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}".format(guild_found.name, eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False), eachTx['blockhash']) + "```"
                                        await user_found.send(msg)
                                    except (discord.Forbidden, discord.errors.Forbidden, discord.errors.HTTPException) as e:
                                        is_notify_failed = True
                                        pass
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot(traceback.format_exc())
                                    update_notify_tx = await store.sql_update_notify_tx_table(eachTx['payment_id'], user_tx['user_id'], guild_found.name, 'YES', 'NO' if is_notify_failed == False else 'YES')
                                else:
                                    #print('Can not find user id {} to notification tx: {}'.format(user_tx['user_id'], eachTx['txid']))
                                    pass
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)


    @tasks.loop(seconds=10.0)
    async def notify_new_tx_user_noconfirmation(self):
        await asyncio.sleep(5.0)
        await self.bot.wait_until_ready()

        if config.notify_new_tx.enable_new_no_confirm == 1:
            key_tx_new = config.redis.prefix_new_tx + 'NOCONFIRM'
            key_tx_no_confirmed_sent = config.redis.prefix_new_tx + 'NOCONFIRM:SENT'
            try:
                if redis_utils.redis_conn.llen(key_tx_new) > 0:
                    list_new_tx = redis_utils.redis_conn.lrange(key_tx_new, 0, -1)
                    list_new_tx_sent = redis_utils.redis_conn.lrange(key_tx_no_confirmed_sent, 0, -1) # byte list with b'xxx'
                    # Unique the list
                    list_new_tx = np.unique(list_new_tx).tolist()
                    list_new_tx_sent = np.unique(list_new_tx_sent).tolist()
                    for tx in list_new_tx:
                        try:
                            if tx not in list_new_tx_sent:
                                tx = tx.decode() # decode byte from b'xxx to xxx
                                key_tx_json = config.redis.prefix_new_tx + tx
                                eachTx = None
                                try:
                                    if redis_utils.redis_conn.exists(key_tx_json): eachTx = json.loads(redis_utils.redis_conn.get(key_tx_json).decode())
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                if eachTx is None: continue

                                COIN_NAME = eachTx['coin_name']
                                coin_family = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                                if eachTx and coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR", "BTC", "CHIA"]:
                                    get_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                                    user_tx = await store.sql_get_userwallet_by_paymentid(eachTx['payment_id'], eachTx['coin_name'], coin_family, SERVER_BOT)
                                    if user_tx:
                                        user_found = self.bot.get_user(int(user_tx['user_id']))
                                        if user_found:
                                            try:
                                                msg = None
                                                confirmation_number_txt = "{} needs {} confirmations.".format(eachTx['coin_name'], get_confirm_depth)
                                                if coin_family != "BTC":
                                                    msg = "You got a new **pending** deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}\n{}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False), eachTx['height'], confirmation_number_txt) + "```"
                                                else:
                                                    msg = "You got a new **pending** deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}\n{}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False), eachTx['blockhash'], confirmation_number_txt) + "```"
                                                await user_found.send(msg)
                                            except (discord.Forbidden, discord.errors.Forbidden, discord.errors.HTTPException) as e:
                                                pass
                                            # TODO:
                                            redis_utils.redis_conn.lpush(key_tx_no_confirmed_sent, tx)
                                        else:
                                            # try to find if it is guild
                                            guild_found = self.bot.get_guild(int(user_tx['user_id']))
                                            if guild_found: user_found =self.bot.get_user(guild_found.owner.id)
                                            if guild_found and user_found:
                                                try:
                                                    msg = None
                                                    confirmation_number_txt = "{} needs {} confirmations.".format(eachTx['coin_name'], get_confirm_depth)
                                                    if eachTx['coin_name'] != "BTC":
                                                        msg = "Your guild got a new **pending** deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}\n{}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False), eachTx['height'], confirmation_number_txt) + "```"
                                                    else:
                                                        msg = "Your guild got a new **pending** deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}\n{}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False), eachTx['blockhash'], confirmation_number_txt) + "```"
                                                    await user_found.send(msg)
                                                except (discord.Forbidden, discord.errors.Forbidden, discord.errors.HTTPException) as e:
                                                    pass
                                                except Exception as e:
                                                    traceback.print_exc(file=sys.stdout)
                                                redis_utils.redis_conn.lpush(key_tx_no_confirmed_sent, tx)
                                            else:
                                                # print('Can not find user id {} to notification **pending** tx: {}'.format(user_tx['user_id'], eachTx['txid']))
                                                pass
                                else:
                                    redis_utils.redis_conn.lpush(key_tx_no_confirmed_sent, tx)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)


    @tasks.loop(seconds=20.0)
    async def update_balance_trtl_api(self):
        await asyncio.sleep(5.0)
        try:
            # async def trtl_api_get_transfers(self, url: str, key: str, coin: str, height_start: int = None, height_end: int = None):
            list_trtl_api = await store.get_coin_settings("TRTL-API")
            if len(list_trtl_api) > 0:
                list_coins = [each['coin_name'].upper() for each in list_trtl_api]
                for COIN_NAME in list_coins:
                    # print(f"Check balance {COIN_NAME}")
                    gettopblock = await self.gettopblock(COIN_NAME, time_out=32)
                    height = int(gettopblock['block_header']['height'])
                    try:
                        redis_utils.redis_conn.set(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}', str(height))
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)

                    url = getattr(getattr(self.bot.coin_list, COIN_NAME), "wallet_address")
                    key = getattr(getattr(self.bot.coin_list, COIN_NAME), "header")
                    get_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    get_min_deposit_amount = int(getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_deposit") * 10**coin_decimal)
                    
                    get_transfers = await self.trtl_api_get_transfers(url, key, COIN_NAME, height - 2000, height)
                    list_balance_user = {}
                    if get_transfers and len(get_transfers) >= 1:
                        await store.openConnection()
                        async with store.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ SELECT * FROM `cn_get_transfers` WHERE `coin_name` = %s """
                                await cur.execute(sql, (COIN_NAME,))
                                result = await cur.fetchall()
                                d = [i['txid'] for i in result]
                                # print('=================='+COIN_NAME+'===========')
                                # print(d)
                                # print('=================='+COIN_NAME+'===========')
                                for tx in get_transfers:
                                    # Could be one block has two or more tx with different payment ID
                                    # add to balance only confirmation depth meet
                                    if len(tx['transfers']) > 0 and height >= int(tx['blockHeight']) + get_confirm_depth and tx['transfers'][0]['amount'] >= get_min_deposit_amount and 'paymentID' in tx:
                                        if 'paymentID' in tx and tx['paymentID'] in list_balance_user:
                                            if tx['transfers'][0]['amount'] > 0:
                                                list_balance_user[tx['paymentID']] += tx['transfers'][0]['amount']
                                        elif 'paymentID' in tx and tx['paymentID'] not in list_balance_user:
                                            if tx['transfers'][0]['amount'] > 0:
                                                list_balance_user[tx['paymentID']] = tx['transfers'][0]['amount']
                                        try:
                                            if tx['hash'] not in d:
                                                addresses = tx['transfers']
                                                address = ''
                                                for each_add in addresses:
                                                    if len(each_add['address']) > 0: address = each_add['address']
                                                    break

                                                sql = """ INSERT IGNORE INTO `cn_get_transfers` (`coin_name`, `txid`, `payment_id`, `height`, `timestamp`, `amount`, `fee`, `decimal`, `address`, time_insert) 
                                                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                await cur.execute(sql, (COIN_NAME, tx['hash'], tx['paymentID'], tx['blockHeight'], tx['timestamp'], float(int(tx['transfers'][0]['amount'])/10**coin_decimal), float(int(tx['fee'])/10**coin_decimal), coin_decimal, address, int(time.time())))
                                                await conn.commit()
                                                # add to notification list also
                                                sql = """ INSERT IGNORE INTO `discord_notify_new_tx` (`coin_name`, `txid`, `payment_id`, `height`, `amount`, `fee`, `decimal`) 
                                                          VALUES (%s, %s, %s, %s, %s, %s, %s) """
                                                await cur.execute(sql, (COIN_NAME, tx['hash'], tx['paymentID'], tx['blockHeight'], float(int(tx['transfers'][0]['amount'])/10**coin_decimal), float(int(tx['fee'])/10**coin_decimal), coin_decimal))
                                                await conn.commit()
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
                                    elif len(tx['transfers']) > 0 and height < int(tx['blockHeight']) + get_confirm_depth and tx['transfers'][0]['amount'] >= get_min_deposit_amount and 'paymentID' in tx:
                                        # add notify to redis and alert deposit. Can be clean later?
                                        if config.notify_new_tx.enable_new_no_confirm == 1:
                                            key_tx_new = config.redis.prefix_new_tx + 'NOCONFIRM'
                                            key_tx_json = config.redis.prefix_new_tx + tx['hash']
                                            try:
                                                if redis_utils.redis_conn.llen(key_tx_new) > 0:
                                                    list_new_tx = redis_utils.redis_conn.lrange(key_tx_new, 0, -1)
                                                    if list_new_tx and len(list_new_tx) > 0 and tx['hash'].encode() not in list_new_tx:
                                                        redis_utils.redis_conn.lpush(key_tx_new, tx['hash'])
                                                        redis_utils.redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['hash'], 'payment_id': tx['paymentID'], 'height': tx['blockHeight'], 'amount': float(int(tx['transfers'][0]['amount'])/10**coin_decimal), 'fee': float(int(tx['fee'])/10**coin_decimal), 'decimal': coin_decimal}), ex=86400)
                                                elif redis_utils.redis_conn.llen(key_tx_new) == 0:
                                                    redis_utils.redis_conn.lpush(key_tx_new, tx['hash'])
                                                    redis_utils.redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['hash'], 'payment_id': tx['paymentID'], 'height': tx['blockHeight'], 'amount': float(int(tx['transfers'][0]['amount'])/10**coin_decimal), 'fee': float(int(tx['fee'])/10**coin_decimal), 'decimal': coin_decimal}), ex=86400)
                                            except Exception as e:
                                                traceback.print_exc(file=sys.stdout)
                                # TODO: update balance cache
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @tasks.loop(seconds=20.0)
    async def update_balance_trtl_service(self):
        await asyncio.sleep(5.0)
        try:
            list_trtl_service = await store.get_coin_settings("TRTL-SERVICE")
            list_bcn_service = await store.get_coin_settings("BCN")
            if len(list_trtl_service+list_bcn_service) > 0:
                list_coins = [each['coin_name'].upper() for each in list_trtl_service+list_bcn_service]
                for COIN_NAME in list_coins:
                    # print(f"Check balance {COIN_NAME}")
                    gettopblock = await self.gettopblock(COIN_NAME, time_out=32)
                    height = int(gettopblock['block_header']['height'])
                    try:
                        redis_utils.redis_conn.set(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}', str(height))
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)

                    url = getattr(getattr(self.bot.coin_list, COIN_NAME), "wallet_address")
                    get_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    get_min_deposit_amount = int(getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_deposit") * 10**coin_decimal)
                    
                    get_transfers = await self.trtl_service_getTransactions(url, COIN_NAME, height - 2000, height)
                    list_balance_user = {}
                    if get_transfers and len(get_transfers) >= 1:
                        await store.openConnection()
                        async with store.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ SELECT * FROM `cn_get_transfers` WHERE `coin_name` = %s """
                                await cur.execute(sql, (COIN_NAME,))
                                result = await cur.fetchall()
                                d = [i['txid'] for i in result]
                                # print('=================='+COIN_NAME+'===========')
                                # print(d)
                                # print('=================='+COIN_NAME+'===========')
                                for txes in get_transfers:
                                    tx_in_block = txes['transactions']
                                    for tx in tx_in_block:
                                        # Could be one block has two or more tx with different payment ID
                                        # add to balance only confirmation depth meet
                                        if height >= int(tx['blockIndex']) + get_confirm_depth and tx['amount'] >= get_min_deposit_amount and 'paymentId' in tx:
                                            if 'paymentId' in tx and tx['paymentId'] in list_balance_user:
                                                if tx['amount'] > 0: list_balance_user[tx['paymentId']] += tx['amount']
                                            elif 'paymentId' in tx and tx['paymentId'] not in list_balance_user:
                                                if tx['amount'] > 0: list_balance_user[tx['paymentId']] = tx['amount']
                                            try:
                                                if tx['transactionHash'] not in d:
                                                    addresses = tx['transfers']
                                                    address = ''
                                                    for each_add in addresses:
                                                        if len(each_add['address']) > 0: address = each_add['address']
                                                        break
                                                        
                                                    sql = """ INSERT IGNORE INTO `cn_get_transfers` (`coin_name`, `txid`, `payment_id`, `height`, `timestamp`, `amount`, `fee`, `decimal`, `address`, time_insert) 
                                                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                    await cur.execute(sql, (COIN_NAME, tx['transactionHash'], tx['paymentId'], tx['blockIndex'], tx['timestamp'], float(tx['amount']/10**coin_decimal), float(tx['fee']/10**coin_decimal), coin_decimal, address, int(time.time())))
                                                    await conn.commit()
                                                    # add to notification list also
                                                    sql = """ INSERT IGNORE INTO `discord_notify_new_tx` (`coin_name`, `txid`, `payment_id`, `height`, `amount`, `fee`, `decimal`) 
                                                              VALUES (%s, %s, %s, %s, %s, %s, %s) """
                                                    await cur.execute(sql, (COIN_NAME, tx['transactionHash'], tx['paymentId'], tx['blockIndex'], float(tx['amount']/10**coin_decimal), float(tx['fee']/10**coin_decimal), coin_decimal))
                                                    await conn.commit()
                                            except Exception as e:
                                                traceback.print_exc(file=sys.stdout)
                                        elif height < int(tx['blockIndex']) + get_confirm_depth and tx['amount'] >= get_min_deposit_amount and 'paymentId' in tx:
                                            # add notify to redis and alert deposit. Can be clean later?
                                            if config.notify_new_tx.enable_new_no_confirm == 1:
                                                key_tx_new = config.redis.prefix_new_tx + 'NOCONFIRM'
                                                key_tx_json = config.redis.prefix_new_tx + tx['transactionHash']
                                                try:
                                                    if redis_utils.redis_conn.llen(key_tx_new) > 0:
                                                        list_new_tx = redis_utils.redis_conn.lrange(key_tx_new, 0, -1)
                                                        if list_new_tx and len(list_new_tx) > 0 and tx['transactionHash'].encode() not in list_new_tx:
                                                            redis_utils.redis_conn.lpush(key_tx_new, tx['transactionHash'])
                                                            redis_utils.redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['transactionHash'], 'payment_id': tx['paymentId'], 'height': tx['blockIndex'], 'amount': float(tx['amount']/10**coin_decimal), 'fee': tx['fee'], 'decimal': coin_decimal}), ex=86400)
                                                    elif redis_utils.redis_conn.llen(key_tx_new) == 0:
                                                        redis_utils.redis_conn.lpush(key_tx_new, tx['transactionHash'])
                                                        redis_utils.redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['transactionHash'], 'payment_id': tx['paymentId'], 'height': tx['blockIndex'], 'amount': float(tx['amount']/10**coin_decimal), 'fee': tx['fee'], 'decimal': coin_decimal}), ex=86400)
                                                except Exception as e:
                                                    traceback.print_exc(file=sys.stdout)
                    # TODO: update user balance
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @tasks.loop(seconds=20.0)
    async def update_balance_xmr(self):
        await asyncio.sleep(5.0)
        try:
            list_xmr_api = await store.get_coin_settings("XMR")
            if len(list_xmr_api) > 0:
                list_coins = [each['coin_name'].upper() for each in list_xmr_api]
                for COIN_NAME in list_coins:
                    # print(f"Check balance {COIN_NAME}")
                    gettopblock = await self.gettopblock(COIN_NAME, time_out=32)
                    height = int(gettopblock['block_header']['height'])
                    try:
                        redis_utils.redis_conn.set(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}', str(height))
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)

                    url = getattr(getattr(self.bot.coin_list, COIN_NAME), "wallet_address")
                    get_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    get_min_deposit_amount = int(getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_deposit") * 10**coin_decimal)

                    payload = {
                        "in" : True,
                        "out": True,
                        "pending": False,
                        "failed": False,
                        "pool": False,
                        "filter_by_height": True,
                        "min_height": height - 2000,
                        "max_height": height
                    }
                    
                    get_transfers = await self.WalletAPI.call_aiohttp_wallet_xmr_bcn('get_transfers', COIN_NAME, payload=payload)
                    if get_transfers and len(get_transfers) >= 1 and 'in' in get_transfers:
                        try:
                            await store.openConnection()
                            async with store.pool.acquire() as conn:
                                async with conn.cursor() as cur:
                                    sql = """ SELECT * FROM `cn_get_transfers` WHERE `coin_name` = %s """
                                    await cur.execute(sql, (COIN_NAME,))
                                    result = await cur.fetchall()
                                    d = [i['txid'] for i in result]
                                    # print('=================='+COIN_NAME+'===========')
                                    # print(d)
                                    # print('=================='+COIN_NAME+'===========')
                                    list_balance_user = {}
                                    for tx in get_transfers['in']:
                                        # add to balance only confirmation depth meet
                                        if height >= int(tx['height']) + get_confirm_depth and tx['amount'] >= get_min_deposit_amount and 'payment_id' in tx:
                                            if 'payment_id' in tx and tx['payment_id'] in list_balance_user:
                                                list_balance_user[tx['payment_id']] += tx['amount']
                                            elif 'payment_id' in tx and tx['payment_id'] not in list_balance_user:
                                                list_balance_user[tx['payment_id']] = tx['amount']
                                            try:
                                                if tx['txid'] not in d:
                                                    tx_address = tx['address'] if COIN_NAME != "LTHN" else getattr(getattr(self.bot.coin_list, COIN_NAME), "MainAddress")
                                                    sql = """ INSERT IGNORE INTO `cn_get_transfers` (`coin_name`, `in_out`, `txid`, `payment_id`, `height`, `timestamp`, `amount`, `fee`, `decimal`, `address`, time_insert) 
                                                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                    await cur.execute(sql, (COIN_NAME, tx['type'].upper(), tx['txid'], tx['payment_id'], tx['height'], tx['timestamp'], float(tx['amount']/10**coin_decimal), float(tx['fee']/10**coin_decimal), coin_decimal, tx_address, int(time.time())))
                                                    await conn.commit()
                                                    # add to notification list also
                                                    sql = """ INSERT IGNORE INTO `discord_notify_new_tx` (`coin_name`, `txid`, `payment_id`, `height`, `amount`, `fee`, `decimal`) 
                                                              VALUES (%s, %s, %s, %s, %s, %s, %s) """
                                                    await cur.execute(sql, (COIN_NAME, tx['txid'], tx['payment_id'], tx['height'], float(tx['amount']/10**coin_decimal), float(tx['fee']/10**coin_decimal), coin_decimal))
                                                    await conn.commit()
                                            except Exception as e:
                                                traceback.print_exc(file=sys.stdout)
                                        elif height < int(tx['height']) + get_confirm_depth and tx['amount'] >= get_min_deposit_amount and 'payment_id' in tx:
                                            # add notify to redis and alert deposit. Can be clean later?
                                            if config.notify_new_tx.enable_new_no_confirm == 1:
                                                key_tx_new = config.redis.prefix_new_tx + 'NOCONFIRM'
                                                key_tx_json = config.redis.prefix_new_tx + tx['txid']
                                                try:
                                                    if redis_utils.redis_conn.llen(key_tx_new) > 0:
                                                        list_new_tx = redis_utils.redis_conn.lrange(key_tx_new, 0, -1)
                                                        if list_new_tx and len(list_new_tx) > 0 and tx['txid'].encode() not in list_new_tx:
                                                            redis_utils.redis_conn.lpush(key_tx_new, tx['txid'])
                                                            redis_utils.redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['txid'], 'payment_id': tx['payment_id'], 'height': tx['height'], 'amount': float(tx['amount']/10**coin_decimal), 'fee': float(tx['fee']/10**coin_decimal), 'decimal': coin_decimal}), ex=86400)
                                                    elif redis_utils.redis_conn.llen(key_tx_new) == 0:
                                                        redis_utils.redis_conn.lpush(key_tx_new, tx['txid'])
                                                        redis_utils.redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['txid'], 'payment_id': tx['payment_id'], 'height': tx['height'], 'amount': float(tx['amount']/10**coin_decimal), 'fee': float(tx['fee']/10**coin_decimal), 'decimal': coin_decimal}), ex=86400)
                                                except Exception as e:
                                                    traceback.print_exc(file=sys.stdout)
                                    # TODO: update user balance
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @tasks.loop(seconds=10.0)
    async def update_balance_btc(self):
        await asyncio.sleep(5.0)
        try:
            # async def trtl_api_get_transfers(self, url: str, key: str, coin: str, height_start: int = None, height_end: int = None):
            list_btc_api = await store.get_coin_settings("BTC")
            if len(list_btc_api) > 0:
                list_coins = [each['coin_name'].upper() for each in list_btc_api]
                for COIN_NAME in list_coins:
                    # print(f"Check balance {COIN_NAME}")
                    gettopblock = await self.WalletAPI.call_doge('getblockchaininfo', COIN_NAME)
                    height = int(gettopblock['blocks'])
                    try:
                        redis_utils.redis_conn.set(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}', str(height))
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        print("sleep 5s")
                        await asyncio.sleep(5.0)
                        continue

                    get_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    get_min_deposit_amount = int(getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_deposit") * 10**coin_decimal)

                    payload = '"*", 100, 0'
                    get_transfers = await self.WalletAPI.call_doge('listtransactions', COIN_NAME, payload=payload)
                    if get_transfers and len(get_transfers) >= 1:
                        try:
                            await store.openConnection()
                            async with store.pool.acquire() as conn:
                                async with conn.cursor() as cur:
                                    sql = """ SELECT * FROM `doge_get_transfers` WHERE `coin_name` = %s AND `category` IN (%s, %s) """
                                    await cur.execute(sql, (COIN_NAME, 'receive', 'send'))
                                    result = await cur.fetchall()
                                    d = [i['txid'] for i in result]
                                    # print('=================='+COIN_NAME+'===========')
                                    # print(d)
                                    # print('=================='+COIN_NAME+'===========')
                                    list_balance_user = {}
                                    for tx in get_transfers:
                                        # add to balance only confirmation depth meet
                                        if get_confirm_depth <= int(tx['confirmations']) and tx['amount'] >= get_min_deposit_amount:
                                            if 'address' in tx and tx['address'] in list_balance_user and tx['amount'] > 0:
                                                list_balance_user[tx['address']] += tx['amount']
                                            elif 'address' in tx and tx['address'] not in list_balance_user and tx['amount'] > 0:
                                                list_balance_user[tx['address']] = tx['amount']
                                            try:
                                                if tx['txid'] not in d:
                                                    # generate from mining
                                                    if tx['category'] == "receive" or tx['category'] == "generate":
                                                        sql = """ INSERT IGNORE INTO `doge_get_transfers` (`coin_name`, `txid`, `blockhash`, `address`, `blocktime`, `amount`, `fee`, `confirmations`, `category`, `time_insert`) 
                                                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                        await cur.execute(sql, (COIN_NAME, tx['txid'], tx['blockhash'], tx['address'], tx['blocktime'], float(tx['amount']), float(tx['fee']) if 'fee' in tx else None, tx['confirmations'], tx['category'], int(time.time())))
                                                        await conn.commit()
                                                    # add to notification list also, doge payment_id = address
                                                    if (tx['amount'] > 0) and tx['category'] == 'receive':
                                                        sql = """ INSERT IGNORE INTO `discord_notify_new_tx` (`coin_name`, `txid`, `payment_id`, `blockhash`, `amount`, `fee`, `decimal`) 
                                                                  VALUES (%s, %s, %s, %s, %s, %s, %s) """
                                                        await cur.execute(sql, (COIN_NAME, tx['txid'], tx['address'], tx['blockhash'], float(tx['amount']), float(tx['fee']) if 'fee' in tx else None, coin_decimal))
                                                        await conn.commit()
                                            except Exception as e:
                                                traceback.print_exc(file=sys.stdout)
                                        if get_confirm_depth > int(tx['confirmations']) > 0 and tx['amount'] >= get_min_deposit_amount:
                                            # add notify to redis and alert deposit. Can be clean later?
                                            if config.notify_new_tx.enable_new_no_confirm == 1:
                                                key_tx_new = config.redis.prefix_new_tx + 'NOCONFIRM'
                                                key_tx_json = config.redis.prefix_new_tx + tx['txid']
                                                try:
                                                    if redis_utils.redis_conn.llen(key_tx_new) > 0:
                                                        list_new_tx = redis_utils.redis_conn.lrange(key_tx_new, 0, -1)
                                                        if list_new_tx and len(list_new_tx) > 0 and tx['txid'].encode() not in list_new_tx:
                                                            redis_utils.redis_conn.lpush(key_tx_new, tx['txid'])
                                                            redis_utils.redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['txid'], 'payment_id': tx['address'], 'blockhash': tx['blockhash'], 'amount': tx['amount'], 'decimal': coin_decimal}), ex=86400)
                                                    elif redis_utils.redis_conn.llen(key_tx_new) == 0:
                                                        redis_utils.redis_conn.lpush(key_tx_new, tx['txid'])
                                                        redis_utils.redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['txid'], 'payment_id': tx['address'], 'blockhash': tx['blockhash'], 'amount': tx['amount'], 'decimal': coin_decimal}), ex=86400)
                                                except Exception as e:
                                                    traceback.print_exc(file=sys.stdout)
                                    # TODO: update balance cache
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    await asyncio.sleep(3.0)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)



    @tasks.loop(seconds=20.0)
    async def update_balance_chia(self):
        await asyncio.sleep(5.0)
        try:
            list_chia_api = await store.get_coin_settings("CHIA")
            if len(list_chia_api) > 0:
                list_coins = [each['coin_name'].upper() for each in list_chia_api]
                for COIN_NAME in list_coins:
                    # print(f"Check balance {COIN_NAME}")
                    gettopblock = await self.gettopblock(COIN_NAME, time_out=32)
                    height = int(gettopblock['height'])
                    try:
                        redis_utils.redis_conn.set(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}', str(height))
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)

                    get_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    get_min_deposit_amount = int(getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_deposit") * 10**coin_decimal)

                    payload = {'wallet_id': 1}
                    list_tx = await self.WalletAPI.call_xch('get_transactions', COIN_NAME, payload=payload)
                    if 'success' in list_tx and list_tx['transactions'] and len(list_tx['transactions']) > 0:
                        get_transfers =  list_tx['transactions']
                        if get_transfers and len(get_transfers) >= 1:
                            try:
                                await store.openConnection()
                                async with store.pool.acquire() as conn:
                                    async with conn.cursor() as cur:
                                        sql = """ SELECT * FROM `xch_get_transfers` WHERE `coin_name` = %s  """
                                        await cur.execute(sql, (COIN_NAME))
                                        result = await cur.fetchall()
                                        d = [i['txid'] for i in result]
                                        # print('=================='+COIN_NAME+'===========')
                                        # print(d)
                                        # print('=================='+COIN_NAME+'===========')
                                        list_balance_user = {}
                                        for tx in get_transfers:
                                            # add to balance only confirmation depth meet
                                            if height >= get_confirm_depth + int(tx['confirmed_at_height']) and tx['amount'] >= get_min_deposit_amount:
                                                if 'to_address' in tx and tx['to_address'] in list_balance_user and tx['amount'] > 0:
                                                    list_balance_user[tx['to_address']] += tx['amount']
                                                elif 'to_address' in tx and tx['to_address'] not in list_balance_user and tx['amount'] > 0:
                                                    list_balance_user[tx['to_address']] = tx['amount']
                                                try:
                                                    if tx['name'] not in d:
                                                        # receive
                                                        if len(tx['sent_to']) == 0:
                                                            sql = """ INSERT IGNORE INTO `xch_get_transfers` (`coin_name`, `txid`, `height`, `timestamp`, `address`, `amount`, `fee`, `decimal`, `time_insert`) 
                                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                            await cur.execute(sql, (COIN_NAME, tx['name'], tx['confirmed_at_height'], tx['created_at_time'],
                                                                                    tx['to_address'], float(tx['amount']/10**coin_decimal), float(tx['fee_amount']/10**coin_decimal), coin_decimal, int(time.time())))
                                                            await conn.commit()
                                                        # add to notification list also, doge payment_id = address
                                                        if (tx['amount'] > 0) and len(tx['sent_to']) == 0:
                                                            sql = """ INSERT IGNORE INTO `discord_notify_new_tx` (`coin_name`, `txid`, `payment_id`, `blockhash`, `height`, `amount`, `fee`, `decimal`) 
                                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                                                            await cur.execute(sql, (COIN_NAME, tx['name'], tx['to_address'], tx['name'], int(tx['confirmed_at_height']), 
                                                                                    float(tx['amount']/10**coin_decimal), float(tx['fee_amount']/10**coin_decimal), coin_decimal))
                                                            await conn.commit()
                                                except Exception as e:
                                                    traceback.print_exc(file=sys.stdout)
                                            if height < get_confirm_depth + int(tx['confirmed_at_height']) and tx['amount'] >= get_min_deposit_amount:
                                                # add notify to redis and alert deposit. Can be clean later?
                                                if config.notify_new_tx.enable_new_no_confirm == 1:
                                                    key_tx_new = config.redis.prefix_new_tx + 'NOCONFIRM'
                                                    key_tx_json = config.redis.prefix_new_tx + tx['name']
                                                    try:
                                                        if redis_utils.redis_conn.llen(key_tx_new) > 0:
                                                            list_new_tx = redis_utils.redis_conn.lrange(key_tx_new, 0, -1)
                                                            if list_new_tx and len(list_new_tx) > 0 and tx['name'].encode() not in list_new_tx:
                                                                redis_utils.redis_conn.lpush(key_tx_new, tx['name'])
                                                                redis_utils.redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['name'], 'payment_id': tx['to_address'], 'height': tx['confirmed_at_height'], 'amount': float(tx['amount']/10**coin_decimal), 'decimal': coin_decimal}), ex=86400)
                                                        elif redis_utils.redis_conn.llen(key_tx_new) == 0:
                                                            redis_utils.redis_conn.lpush(key_tx_new, tx['name'])
                                                            redis_utils.redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['name'], 'payment_id': tx['to_address'], 'height': tx['confirmed_at_height'], 'amount': float(tx['amount']/10**coin_decimal), 'decimal': coin_decimal}), ex=86400)
                                                    except Exception as e:
                                                        traceback.print_exc(file=sys.stdout)
                                        # TODO: update balance users
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @tasks.loop(seconds=20.0)
    async def update_balance_nano(self):
        await asyncio.sleep(5.0)
        try:
            updated = 0
            list_nano = await store.get_coin_settings("NANO")
            if len(list_nano) > 0:
                list_coins = [each['coin_name'].upper() for each in list_nano]
                for COIN_NAME in list_coins:
                    # print(f"Check balance {COIN_NAME}")
                    start = time.time()
                    timeout = 16
                    try:
                        gettopblock = await self.WalletAPI.call_nano(COIN_NAME, payload='{ "action": "block_count" }')
                        if gettopblock and 'count' in gettopblock:
                            height = int(gettopblock['count'])
                            # store in redis
                            try:                                
                                redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{COIN_NAME}', str(height))
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    get_balance = await self.WalletAPI.nano_get_wallet_balance_elements(COIN_NAME)
                    all_user_info = await store.sql_nano_get_user_wallets(COIN_NAME)
                    all_deposit_address = {}
                    all_deposit_address_keys = []
                    if len(all_user_info) > 0:
                        all_deposit_address_keys = [each['balance_wallet_address'] for each in all_user_info]
                        for each in all_user_info:
                            all_deposit_address[each['balance_wallet_address']] = each
                    if get_balance and len(get_balance) > 0:
                        for address, balance in get_balance.items():
                            try:
                                # if bigger than minimum deposit, and no pending and the address is in user database addresses
                                real_min_deposit = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_deposit")
                                coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                                if float(int(balance['balance'])/10**coin_decimal) >= real_min_deposit and float(int(balance['pending'])/10**coin_decimal) == 0 and address in all_deposit_address_keys:
                                    # let's move balance to main_address
                                    try:
                                        main_address = getattr(getattr(self.bot.coin_list, COIN_NAME), "MainAddress")
                                        move_to_deposit = await self.WalletAPI.nano_sendtoaddress(address, main_address, int(balance['balance']), COIN_NAME) # atomic
                                        # add to DB
                                        if move_to_deposit:
                                            try:
                                                await store.openConnection()
                                                async with store.pool.acquire() as conn:
                                                    async with conn.cursor() as cur:
                                                        sql = """ INSERT INTO nano_move_deposit (`coin_name`, `user_id`, `balance_wallet_address`, `to_main_address`, `amount`, `decimal`, `block`, `time_insert`) 
                                                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                                                        await cur.execute(sql, (COIN_NAME, all_deposit_address[address]['user_id'], address, main_address, float(int(balance['balance'])/10**coin_decimal), coin_decimal, move_to_deposit['block'], int(time.time()), ))
                                                        await conn.commit()
                                                        updated += 1
                                                        # add to notification list also
                                                        # txid = new block ID
                                                        # payment_id = deposit address
                                                        sql = """ INSERT IGNORE INTO discord_notify_new_tx (`coin_name`, `txid`, `payment_id`, `amount`, `decimal`) 
                                                                  VALUES (%s, %s, %s, %s, %s) """
                                                        await cur.execute(sql, (COIN_NAME, move_to_deposit['block'], address, float(int(balance['balance'])/10**coin_decimal), coin_decimal,))
                                                        await conn.commit()
                                            except Exception as e:
                                                traceback.print_exc(file=sys.stdout)
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                    end = time.time()
                    # print('Done update balance: '+ COIN_NAME+ ' updated *'+str(updated)+'* duration (s): '+str(end - start))
                    await asyncio.sleep(4.0)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @tasks.loop(seconds=20.0)
    async def update_balance_erc20(self):
        await asyncio.sleep(5.0)
        erc_contracts = await self.get_all_contracts("ERC-20", False)
        if len(erc_contracts) > 0:
            for each_c in erc_contracts:
                try:
                    await store.sql_check_minimum_deposit_erc20(self.bot.erc_node_list[each_c['net_name']], each_c['net_name'], each_c['coin_name'], each_c['contract'], each_c['decimal'], each_c['min_move_deposit'], each_c['min_gas_tx'], each_c['gas_ticker'], each_c['move_gas_amount'], each_c['chain_id'], each_c['real_deposit_fee'], 7200)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        main_tokens = await self.get_all_contracts("ERC-20", True)
        if len(main_tokens) > 0:
            for each_c in main_tokens:
                try:
                    await store.sql_check_minimum_deposit_erc20(self.bot.erc_node_list[each_c['net_name']], each_c['net_name'], each_c['coin_name'], None, each_c['decimal'], each_c['min_move_deposit'], each_c['min_gas_tx'], each_c['gas_ticker'], each_c['move_gas_amount'], each_c['chain_id'], each_c['real_deposit_fee'], 7200)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)


    @tasks.loop(seconds=20.0)
    async def update_balance_trc20(self):
        await asyncio.sleep(5.0)
        erc_contracts = await self.get_all_contracts("TRC-20", False)
        if len(erc_contracts) > 0:
            for each_c in erc_contracts:
                try:
                    type_name = each_c['type']
                    await store.trx_check_minimum_deposit(each_c['coin_name'], type_name, each_c['contract'], each_c['decimal'], each_c['min_move_deposit'], each_c['min_gas_tx'], each_c['gas_ticker'], each_c['move_gas_amount'], each_c['chain_id'], each_c['real_deposit_fee'], 7200, SERVER_BOT)
                    pass
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        main_tokens = await self.get_all_contracts("TRC-20", True)
        if len(main_tokens) > 0:
            for each_c in main_tokens:
                try:
                    type_name = each_c['type']
                    await store.trx_check_minimum_deposit(each_c['coin_name'], type_name, None, each_c['decimal'], each_c['min_move_deposit'], each_c['min_gas_tx'], each_c['gas_ticker'], each_c['move_gas_amount'], each_c['chain_id'], each_c['real_deposit_fee'], 7200, SERVER_BOT)
                    pass
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)


    @tasks.loop(seconds=20.0)
    async def unlocked_move_pending_erc20(self):
        await asyncio.sleep(5.0)
        erc_contracts = await self.get_all_contracts("ERC-20", False)
        depth = max([each['deposit_confirm_depth'] for each in erc_contracts])
        net_names = await self.get_all_net_names()
        net_names = list(net_names.keys())
        if len(net_names) > 0:
            for each_name in net_names:
                try:
                    await store.sql_check_pending_move_deposit_erc20(self.bot.erc_node_list[each_name], each_name, depth)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)


    @tasks.loop(seconds=10.0)
    async def unlocked_move_pending_trc20(self):
        await asyncio.sleep(5.0)
        trc_contracts = await self.get_all_contracts("TRC-20", False)
        depth = max([each['deposit_confirm_depth'] for each in trc_contracts])
        net_names = await self.get_all_net_names_tron()
        net_names = list(net_names.keys())

        if len(net_names) > 0:
            for each_name in net_names:
                try:
                    await store.sql_check_pending_move_deposit_trc20(each_name, depth, "PENDING")
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)


    @tasks.loop(seconds=20.0)
    async def update_balance_address_history_erc20(self):
        await asyncio.sleep(5.0)
        erc_contracts = await self.get_all_contracts("ERC-20", False)
        depth = max([each['deposit_confirm_depth'] for each in erc_contracts])
        net_names = await self.get_all_net_names()
        net_names = list(net_names.keys())
        if len(net_names) > 0:
            for each_name in net_names:
                try:
                    get_recent_tx = await store.get_monit_scanning_contract_balance_address_erc20(each_name, 7200)
                    if get_recent_tx and len(get_recent_tx) > 0:
                        tx_update_call = []
                        for each_tx in get_recent_tx:
                            to_addr = "0x" + each_tx['to_addr'][26:]
                            tx_update_call.append((each_tx['blockTime'], to_addr))
                        if len(tx_update_call) > 0:
                            update_call = await store.sql_update_erc_user_update_call_many_erc20(tx_update_call)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)



    async def send_external_erc20(self, url: str, network: str, user_id: str, to_address: str, amount: float, coin: str, coin_decimal: int, real_withdraw_fee: float, user_server: str, chain_id: str=None, contract: str=None):
        global pool
        TOKEN_NAME = coin.upper()
        user_server = user_server.upper()

        try:
            # HTTPProvider:
            w3 = Web3(Web3.HTTPProvider(url))
            signed_txn = None
            sent_tx = None
            if contract is None:
                # Main Token
                if network == "MATIC":
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config.eth.MainAddress), 'pending')
                else:
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config.eth.MainAddress))
                # get gas price
                gasPrice = w3.eth.gasPrice

                estimateGas = w3.eth.estimateGas({'to': w3.toChecksumAddress(to_address), 'from': w3.toChecksumAddress(config.eth.MainAddress), 'value':  int(amount * 10**coin_decimal)})

                atomic_amount = int(amount * 10**18)
                transaction = {
                        'from': w3.toChecksumAddress(config.eth.MainAddress),
                        'to': w3.toChecksumAddress(to_address),
                        'value': atomic_amount,
                        'nonce': nonce,
                        'gasPrice': gasPrice,
                        'gas': estimateGas,
                        'chainId': chain_id
                    }
                try:
                    signed_txn = w3.eth.account.sign_transaction(transaction, private_key=config.eth.MainAddress_key)
                    # send Transaction for gas:
                    sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            else:
                # Token ERC-20
                # inject the poa compatibility middleware to the innermost layer
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)

                unicorns = w3.eth.contract(address=w3.toChecksumAddress(contract), abi=EIP20_ABI)
                if network == "MATIC":
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config.eth.MainAddress), 'pending')
                else:
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config.eth.MainAddress))

                unicorn_txn = unicorns.functions.transfer(
                    w3.toChecksumAddress(to_address),
                    int(amount * 10**coin_decimal) # amount to send
                 ).buildTransaction({
                    'from': w3.toChecksumAddress(config.eth.MainAddress),
                    'gasPrice': w3.eth.gasPrice,
                    'nonce': nonce,
                    'chainId': chain_id
                 })

                acct = Account.from_mnemonic(
                    mnemonic=config.eth.MainAddress_seed)
                signed_txn = w3.eth.account.signTransaction(unicorn_txn, private_key=acct.key)
                sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
            if signed_txn and sent_tx:
                # Add to SQL
                try:
                    await store.openConnection()
                    async with store.pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            sql = """ INSERT INTO `erc20_external_tx` (`token_name`, `contract`, `user_id`, `real_amount`, 
                                      `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, 
                                      `user_server`, `network`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (TOKEN_NAME, contract, user_id, amount, real_withdraw_fee, coin_decimal, 
                                                    to_address, int(time.time()), sent_tx.hex(), user_server, network))
                            await conn.commit()
                            return sent_tx.hex()
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())


    async def send_external_trc20(self, user_id: str, to_address: str, amount: float, coin: str, coin_decimal: int, real_withdraw_fee: float, user_server: str, fee_limit: float, trc_type: str, contract: str=None):
        global pool
        TOKEN_NAME = coin.upper()
        user_server = user_server.upper()

        try:
            _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                       timeout=Timeout(timeout=10, connect=5, read=5))
            TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
            if TOKEN_NAME == "TRX":
                txb = (
                    TronClient.trx.transfer(config.trc.MainAddress, to_address, int(amount*10**coin_decimal))
                    #.memo("test memo")
                    .fee_limit(int(fee_limit*10**coin_decimal))
                )
                txn = await txb.build()
                priv_key = PrivateKey(bytes.fromhex(config.trc.MainAddress_key))
                txn_ret = await txn.sign(priv_key).broadcast()
                try:
                    in_block = await txn_ret.wait()
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                await TronClient.close()
                if txn_ret and in_block:
                    # Add to SQL
                    try:
                        await store.openConnection()
                        async with store.pool.acquire() as conn:
                            await conn.ping(reconnect=True)
                            async with conn.cursor() as cur:
                                sql = """ INSERT INTO trc20_external_tx (`token_name`, `contract`, `user_id`, `real_amount`, 
                                          `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, `user_server`) 
                                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                await cur.execute(sql, (TOKEN_NAME, contract, user_id, amount, real_withdraw_fee, coin_decimal, 
                                                        to_address, int(time.time()), txn_ret['txid'], user_server))
                                await conn.commit()
                                return txn_ret['txid']
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
            else:
                if trc_type == "TRC-20":
                    try:
                        cntr = await TronClient.get_contract(contract)
                        precision = await cntr.functions.decimals()
                        ## TODO: alert if balance below threshold
                        ## balance = await cntr.functions.balanceOf(config.trc.MainAddress) / 10**precision
                        txb = await cntr.functions.transfer(to_address, int(amount*10**6))
                        txb = txb.with_owner(config.trc.MainAddress).fee_limit(int(fee_limit*10**coin_decimal))
                        txn = await txb.build()
                        priv_key = PrivateKey(bytes.fromhex(config.trc.MainAddress_key))
                        txn_ret = await txn.sign(priv_key).broadcast()
                        in_block = None
                        try:
                            in_block = await txn_ret.wait()
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        await TronClient.close()
                        if txn_ret and in_block:
                            # Add to SQL
                            try:
                                await store.openConnection()
                                async with store.pool.acquire() as conn:
                                    await conn.ping(reconnect=True)
                                    async with conn.cursor() as cur:
                                        sql = """ INSERT INTO trc20_external_tx (`token_name`, `contract`, `user_id`, `real_amount`, 
                                                  `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, `user_server`) 
                                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                        await cur.execute(sql, (TOKEN_NAME, contract, user_id, amount, real_withdraw_fee, coin_decimal, 
                                                                to_address, int(time.time()), txn_ret['txid'], user_server))
                                        await conn.commit()
                                        return txn_ret['txid']
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                                await logchanbot(traceback.format_exc())
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                elif trc_type == "TRC-10":
                    try:
                        precision = 10**coin_decimal
                        txb = (
                            TronClient.trx.asset_transfer(
                                config.trc.MainAddress, to_address, int(precision*amount), token_id=int(contract)
                            )
                            .fee_limit(int(fee_limit*10**coin_decimal))
                        )
                        txn = await txb.build()
                        priv_key = PrivateKey(bytes.fromhex(config.trc.MainAddress_key))
                        txn_ret = await txn.sign(priv_key).broadcast()

                        in_block = None
                        try:
                            in_block = await txn_ret.wait()
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        await TronClient.close()
                        if txn_ret and in_block:
                            # Add to SQL
                            try:
                                await store.openConnection()
                                async with store.pool.acquire() as conn:
                                    await conn.ping(reconnect=True)
                                    async with conn.cursor() as cur:
                                        sql = """ INSERT INTO trc20_external_tx (`token_name`, `contract`, `user_id`, `real_amount`, 
                                                  `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, `user_server`) 
                                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                        await cur.execute(sql, (TOKEN_NAME, str(contract), user_id, amount, real_withdraw_fee, coin_decimal, 
                                                                to_address, int(time.time()), txn_ret['txid'], user_server))
                                        await conn.commit()
                                        return txn_ret['txid']
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                                await logchanbot(traceback.format_exc())
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False


    async def trtl_api_get_transfers(self, url: str, key: str, coin: str, height_start: int = None, height_end: int = None):
        time_out = 30
        method = "/transactions"
        headers = {
            'X-API-KEY': key,
            'Content-Type': 'application/json'
        }
        if (height_start is None) or (height_end is None):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url + method, headers=headers, timeout=time_out) as response:
                        json_resp = await response.json()
                        if response.status == 200 or response.status == 201:
                            return json_resp['transactions']
                        elif 'errorMessage' in json_resp:
                            raise RPCException(json_resp['errorMessage'])
            except asyncio.TimeoutError:
                await logchanbot('trtl_api_get_transfers: TIMEOUT: {} - coin {} timeout {}'.format(method, coin, time_out))
            except Exception as e:
                await logchanbot('trtl_api_get_transfers: '+ str(traceback.format_exc()))
        elif height_start and height_end:
            method += '/' + str(height_start) + '/' + str(height_end)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url + method, headers=headers, timeout=time_out) as response:
                        json_resp = await response.json()
                        if response.status == 200 or response.status == 201:
                            return json_resp['transactions']
                        elif 'errorMessage' in json_resp:
                            raise RPCException(json_resp['errorMessage'])
            except asyncio.TimeoutError:
                await logchanbot('trtl_api_get_transfers: TIMEOUT: {} - coin {} timeout {}'.format(method, coin, time_out))
            except Exception as e:
                await logchanbot('trtl_api_get_transfers: ' + str(traceback.format_exc()))


    async def trtl_service_getTransactions(self, url: str, coin: str, firstBlockIndex: int=2000000, blockCount: int= 200000):
        COIN_NAME = coin.upper()
        time_out = 64
        payload = {
            'firstBlockIndex': firstBlockIndex if firstBlockIndex > 0 else 1,
            'blockCount': blockCount,
            }
        result = await self.WalletAPI.call_aiohttp_wallet_xmr_bcn('getTransactions', COIN_NAME, time_out=time_out, payload=payload)
        if result and 'items' in result:
            return result['items']
        return []


    # Mostly for BCN/XMR
    async def call_daemon(self, get_daemon_rpc_url: str, method_name: str, coin: str, time_out: int = None, payload: Dict = None) -> Dict:
        full_payload = {
            'params': payload or {},
            'jsonrpc': '2.0',
            'id': str(uuid.uuid4()),
            'method': f'{method_name}'
        }
        timeout = time_out or 16
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(get_daemon_rpc_url + '/json_rpc', json=full_payload, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.json()
                        if res_data and 'result' in res_data:
                            return res_data['result']
                        else:
                            return res_data
        except asyncio.TimeoutError:
            await logchanbot('call_daemon: method: {} COIN_NAME {} - timeout {}'.format(method_name, coin.upper(), time_out))
            return None
        except Exception:
            traceback.print_exc(file=sys.stdout)
            return None


    async def gettopblock(self, coin: str, time_out: int = None):
        COIN_NAME = coin.upper()
        coin_family = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        get_daemon_rpc_url = getattr(getattr(self.bot.coin_list, COIN_NAME), "daemon_address")
        result = None
        timeout = time_out or 32

        if COIN_NAME in ["LTHN"] or coin_family in ["BCN", "TRTL-API", "TRTL-SERVICE"]:
            method_name = "getblockcount"
            full_payload = {
                'params': {},
                'jsonrpc': '2.0',
                'id': str(uuid.uuid4()),
                'method': f'{method_name}'
            }
            try:
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(get_daemon_rpc_url + '/json_rpc', json=full_payload, timeout=timeout) as response:
                        if response.status == 200:
                            res_data = await response.json()
                            result = None
                            if res_data and 'result' in res_data:
                                result = res_data['result']
                            else:
                                result = res_data
                            if result:
                                full_payload = {
                                    'jsonrpc': '2.0',
                                    'method': 'getblockheaderbyheight',
                                    'params': {'height': result['count'] - 1}
                                }
                                try:
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(get_daemon_rpc_url + '/json_rpc', json=full_payload, timeout=timeout) as response:
                                            if response.status == 200:
                                                res_data = await response.json()
                                                return res_data['result']
                                except asyncio.TimeoutError:
                                    traceback.print_exc(file=sys.stdout)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            return None
            except asyncio.TimeoutError:
                await logchanbot('gettopblock: method: {} COIN_NAME {} - timeout {}'.format(method_name, coin.upper(), time_out))
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None
        elif coin_family == "XMR":
            method_name = "get_block_count"
            full_payload = {
                'params': {},
                'jsonrpc': '2.0',
                'id': str(uuid.uuid4()),
                'method': f'{method_name}'
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(get_daemon_rpc_url + '/json_rpc', json=full_payload, timeout=timeout) as response:
                        if response.status == 200:
                            try:
                                res_data = await response.json()
                            except Exception:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                res_data = json.loads(res_data)
                            result = None
                            if res_data and 'result' in res_data:
                                result = res_data['result']
                            else:
                                result = res_data
                            if result:
                                full_payload = {
                                    'jsonrpc': '2.0',
                                    'method': 'get_block_header_by_height',
                                    'params': {'height': result['count'] - 1}
                                }
                                try:
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(get_daemon_rpc_url + '/json_rpc', json=full_payload, timeout=timeout) as response:
                                            if response.status == 200:
                                                res_data = await response.json()
                                                if res_data and 'result' in res_data:
                                                    return res_data['result']
                                                else:
                                                    return res_data
                                except asyncio.TimeoutError:
                                    await logchanbot('gettopblock: method: {} COIN_NAME {} - timeout {}'.format('get_block_count', COIN_NAME, time_out))
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            return None
            except asyncio.TimeoutError:
                await logchanbot('gettopblock: method: {} COIN_NAME {} - timeout {}'.format(method_name, coin.upper(), time_out))
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None
        elif coin_family == "CHIA":
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(getattr(getattr(self.bot.coin_list, COIN_NAME), "cert_path"), getattr(getattr(self.bot.coin_list, COIN_NAME), "key_path"))
            url = getattr(getattr(self.bot.coin_list, COIN_NAME), "daemon_address") + '/get_blockchain_state'
            try:
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
                    async with session.post(url, timeout=timeout, json={}, ssl=ssl_context) as response:
                        if response.status == 200:
                            res_data = await response.json()
                            return res_data['blockchain_state']['peak']
            except asyncio.TimeoutError:
                await logchanbot('gettopblock: method: {} COIN_NAME {} - timeout {}'.format("get_blockchain_state", coin.upper(), time_out))
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None


    async def get_all_contracts(self, type_token: str, main_token: bool=False):
        # type_token: ERC-20, TRC-20
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if main_token == False:
                        sql = """ SELECT * FROM `coin_settings` WHERE `type`=%s AND `contract` IS NOT NULL AND `net_name` IS NOT NULL """
                        await cur.execute(sql, (type_token,))
                        result = await cur.fetchall()
                        if result and len(result) > 0: return result
                    else:
                        sql = """ SELECT * FROM `coin_settings` WHERE `type`=%s AND `contract` IS NULL AND `net_name` IS NOT NULL """
                        await cur.execute(sql, (type_token,))
                        result = await cur.fetchall()
                        if result and len(result) > 0: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []
 
 
    async def sql_get_userwallet(self, userID, coin: str, netname: str, type_coin: str, user_server: str = 'DISCORD', chat_id: int = 0):
        User_WalletAPI = WalletAPI(self.bot)
        return await User_WalletAPI.sql_get_userwallet(userID, coin, netname, type_coin, user_server, chat_id)


    async def sql_register_user(self, userID, coin: str, netname: str, type_coin: str, user_server: str, chat_id: int = 0, is_discord_guild: int=0):
        User_WalletAPI = WalletAPI(self.bot)
        return await User_WalletAPI.sql_register_user(userID, coin, netname, type_coin, user_server, chat_id, is_discord_guild)


    async def get_all_net_names(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_ethscan_setting` WHERE `enable`=%s """
                    await cur.execute(sql, (1,))
                    result = await cur.fetchall()
                    net_names = {}
                    if result and len(result) > 0:
                        for each in result:
                            net_names[each['net_name']] = each
                        return net_names
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return {}


    async def get_all_net_names_tron(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_tronscan_setting` WHERE `enable`=%s """
                    await cur.execute(sql, (1,))
                    result = await cur.fetchall()
                    net_names = {}
                    if result and len(result) > 0:
                        for each in result:
                            net_names[each['net_name']] = each
                        return net_names
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return {}

    async def generate_qr_address(
        self, 
        address: str
    ):
        # return path to image
        # address = wallet['balance_wallet_address']
        # return address if success, else None
        if not os.path.exists(config.storage.path_deposit_qr_create + address + ".png"):
            try:
                # do some QR code
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=2,
                )
                qr.add_data(address)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                img = img.resize((256, 256))
                img.save(config.storage.path_deposit_qr_create + address + ".png")
                return address
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        else:
            return address
        return None


    async def async_deposit(self, ctx, token: str=None, plain: str=None):
        COIN_NAME = None
        if token is None:
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(f'{ctx.author.mention}, token name is missing.')
            else:
                await ctx.reply(f'{ctx.author.mention}, token name is missing.')
            return
        else:
            COIN_NAME = token.upper()
            # print(self.bot.coin_list)
            if not hasattr(self.bot.coin_list, COIN_NAME):
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
                else:
                    await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
                return
            else:
                if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_deposit") == 0:
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** deposit disable.')
                    else:
                        await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** deposit disable.')
                    return
                    
        # Do the job
        try:
            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
            get_deposit = await self.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await self.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)
                
            wallet_address = get_deposit['balance_wallet_address']
            description = ""
            fee_txt = ""
            token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_note") and len(getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_note")) > 0:
                description = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_note")
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "real_deposit_fee") and getattr(getattr(self.bot.coin_list, COIN_NAME), "real_deposit_fee") > 0:
                fee_txt = " **{} {}** will be deducted from your deposit when it reaches minimum.".format(getattr(getattr(self.bot.coin_list, COIN_NAME), "real_deposit_fee"), token_display)
            embed = disnake.Embed(title=f'Deposit for {ctx.author.name}#{ctx.author.discriminator}', description=description + fee_txt, timestamp=datetime.utcnow())
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            try:
                gen_qr_address = await self.generate_qr_address(wallet_address)
                embed.set_thumbnail(url=config.storage.deposit_url + wallet_address + ".png")
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            plain_msg = '{}#{} Your deposit address: ```{}```'.format(ctx.author.name, ctx.author.discriminator, wallet_address)
            embed.add_field(name="Your Deposit Address", value="`{}`".format(wallet_address), inline=False)
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link") and len(getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")) > 0:
                embed.add_field(name="Other links", value="[{}]({})".format("Explorer", getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")), inline=False)
            embed.set_footer(text="Use: deposit plain (for plain text)")
            try:
                # Try DM first
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    if plain and plain.lower() == 'plain' or plain.lower() == 'text':
                        await ctx.response.send_message(plain_msg, ephemeral=True)
                    else:
                        await ctx.response.send_message(embed=embed, ephemeral=True)
                else:
                    if plain and plain.lower() == 'plain' or plain.lower() == 'text':
                        msg = await ctx.reply(plain_msg, view=RowButton_close_message())
                        await store.add_discord_bot_message(str(msg.id), "DM" if isinstance(ctx.channel, disnake.DMChannel) else str(ctx.guild.id), str(ctx.author.id))
                    else:
                        msg = await ctx.reply(embed=embed, view=RowButton_close_message())
                        await store.add_discord_bot_message(str(msg.id), "DM" if isinstance(ctx.channel, disnake.DMChannel) else str(ctx.guild.id), str(ctx.author.id))
            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.command(
        usage='deposit <token> [plain/embed]', 
        aliases=['deposit'],
        description="Get your wallet deposit address."
    )
    async def _deposit(
        self, 
        ctx, 
        token: str,
        plain: str = 'embed'
    ):
        await self.async_deposit(ctx, token, plain)


    @commands.slash_command(
        usage='deposit <token> [plain/embed]', 
        options=[
            Option('token', 'token', OptionType.string, required=True),
            Option('plain', 'plain', OptionType.string, required=False)
        ],
        description="Get your wallet deposit address."
    )
    async def deposit(
        self, 
        ctx, 
        token: str,
        plain: str = 'embed'
    ):
        await self.async_deposit(ctx, token, plain)
    # End of deposit


    # Balance
    async def async_balance(self, ctx, token: str=None):
        COIN_NAME = None
        if token is None:
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(f'{ctx.author.mention}, token name is missing.')
            else:
                await ctx.reply(f'{ctx.author.mention}, token name is missing.')
            return
        else:
            COIN_NAME = token.upper()
            if not hasattr(self.bot.coin_list, COIN_NAME):
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
                else:
                    await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
                return
            else:
                if getattr(getattr(self.bot.coin_list, COIN_NAME), "is_maintenance") == 1:
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** is currently under maintenance.')
                    else:
                        await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** is currently under maintenance.')
                    return
        # Do the job
        try:
            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")

            get_deposit = await self.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await self.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']

            height = None
            try:
                if type_coin in ["ERC-20", "TRC-20"]:
                    height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                else:
                    height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

            description = ""
            token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
            embed = disnake.Embed(title=f'Balance for {ctx.author.name}#{ctx.author.discriminator}', timestamp=datetime.utcnow())
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            try:
                # height can be None
                userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                total_balance = userdata_balance['adjust']
                equivalent_usd = ""
                if usd_equivalent_enable == 1:
                    native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                    COIN_NAME_FOR_PRICE = COIN_NAME
                    if native_token_name:
                        COIN_NAME_FOR_PRICE = native_token_name
                    per_unit = None
                    if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                        id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                    else:
                        per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
                    if per_unit and per_unit > 0:
                        total_in_usd = float(Decimal(total_balance) * Decimal(per_unit))
                        if total_in_usd >= 0.01:
                            equivalent_usd = " ~ {:,.2f}$".format(total_in_usd)
                        elif total_in_usd >= 0.0001:
                            equivalent_usd = " ~ {:,.4f}$".format(total_in_usd)
                embed.add_field(name="Token/Coin {}{}".format(token_display, equivalent_usd), value="```Available: {} {}```".format(num_format_coin(total_balance, COIN_NAME, coin_decimal, False), token_display), inline=False)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(embed=embed)
            else:
                await ctx.reply(embed=embed)
            # Add update for future call
            try:
                if type_coin == "ERC-20":
                    update_call = await store.sql_update_erc20_user_update_call(str(ctx.author.id))
                elif type_coin == "TRC-10" or type_coin == "TRC-20":
                    update_call = await store.sql_update_trc20_user_update_call(str(ctx.author.id))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    # Balances
    async def async_balances(self, ctx, tokens: str=None):
        COIN_NAME = None
        mytokens = []
        zero_tokens = []
        unknown_tokens = []
        has_none_balance = True
        if tokens is None:
            # do all coins/token which is not under maintenance
            mytokens = await store.get_coin_settings(coin_type=None)
        else:
            # get list of coin/token from tokens
            get_tokens = await store.get_coin_settings(coin_type=None)
            token_list = None
            if "," in tokens:
                token_list = tokens.upper().split(",")
            elif ";" in tokens:
                token_list = tokens.upper().split(",")
            elif "." in tokens:
                token_list = tokens.upper().split(",")
            elif " " in tokens:
                token_list = tokens.upper().split()
            else:
                # one token
                token_list = [tokens.upper().strip()]
            if token_list and len(token_list) > 0:
                token_list = list(set(token_list))
                for each_token in token_list:
                    try:
                        if getattr(self.bot.coin_list, each_token):
                            mytokens.append(getattr(self.bot.coin_list, each_token))
                    except Exception as e:
                        unknown_tokens.append(each_token)

        if len(mytokens) == 0:
            msg = f'{ctx.author.mention}, no token or not exist.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        else:
            total_all_balance_usd = 0.0
            all_pages = []
            all_names = [each['coin_name'] for each in mytokens]
            total_coins = len(mytokens)
            page = disnake.Embed(title='[ YOUR BALANCE LIST ]',
                                  description="Thank you for using TipBot!",
                                  color=disnake.Color.blue(),
                                  timestamp=datetime.utcnow(), )
            page.add_field(name="Coin/Tokens: [{}]".format(len(all_names)), 
                           value="```"+", ".join(all_names)+"```", inline=False)
            if len(unknown_tokens) > 0:
                unknown_tokens = list(set(unknown_tokens))
                page.add_field(name="Unknown Tokens: {}".format(len(unknown_tokens)), 
                               value="```"+", ".join(unknown_tokens)+"```", inline=False)
            page.set_thumbnail(url=ctx.author.display_avatar)
            page.set_footer(text="Use the reactions to flip pages.")
            all_pages.append(page)
            num_coins = 0
            per_page = 8
            if type(ctx) != disnake.ApplicationCommandInteraction:
                tmp_msg = await ctx.reply("Loading...")
            for each_token in mytokens:
                COIN_NAME = each_token['coin_name']
                type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
                usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")

                get_deposit = await self.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                if get_deposit is None:
                    get_deposit = await self.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)
                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']

                height = None
                try:
                    if type_coin in ["ERC-20", "TRC-20"]:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                    else:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)

                if num_coins == 0 or num_coins % per_page == 0:
                    page = disnake.Embed(title='[ YOUR BALANCE LIST ]',
                                         description="Thank you for using TipBot!",
                                         color=disnake.Color.blue(),
                                         timestamp=datetime.utcnow(), )
                    page.set_thumbnail(url=ctx.author.display_avatar)
                    page.set_footer(text="Use the reactions to flip pages.")
                # height can be None
                userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                total_balance = userdata_balance['adjust']
                if total_balance == 0:
                    zero_tokens.append(COIN_NAME)
                    continue
                elif total_balance > 0:
                    has_none_balance = False
                equivalent_usd = ""
                if usd_equivalent_enable == 1:
                    native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                    COIN_NAME_FOR_PRICE = COIN_NAME
                    if native_token_name:
                        COIN_NAME_FOR_PRICE = native_token_name
                    per_unit = None
                    if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                        id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                    else:
                        per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
                    if per_unit and per_unit > 0:
                        total_in_usd = float(Decimal(total_balance) * Decimal(per_unit))
                        total_all_balance_usd += total_in_usd
                        if total_in_usd >= 0.01:
                            equivalent_usd = " ~ {:,.2f}$".format(total_in_usd)
                        elif total_in_usd >= 0.0001:
                            equivalent_usd = " ~ {:,.4f}$".format(total_in_usd)
                         
                page.add_field(name="{}{}".format(token_display, equivalent_usd) , value="```{}```".format(num_format_coin(total_balance, COIN_NAME, coin_decimal, False)), inline=True)
                num_coins += 1
                if num_coins > 0 and num_coins % per_page == 0:
                    all_pages.append(page)
                    if num_coins < total_coins:
                        page = disnake.Embed(title='[ YOUR BALANCE LIST ]',
                                             description="Thank you for using TipBot!",
                                             color=disnake.Color.blue(),
                                             timestamp=datetime.utcnow(), )
                        page.set_thumbnail(url=ctx.author.display_avatar)
                        page.set_footer(text="Use the reactions to flip pages.")
                    else:
                        all_pages.append(page)
                        break
                elif num_coins == total_coins:
                    all_pages.append(page)
                    break

            # Replace first page
            if total_all_balance_usd > 0.01:
                total_all_balance_usd = "Having ~ {:,.2f}$".format(total_all_balance_usd)
            elif total_all_balance_usd > 0.0001:
                total_all_balance_usd = "Having ~ {:,.4f}$".format(total_all_balance_usd)
            else:
                total_all_balance_usd = "Thank you for using TipBot!"
            page = disnake.Embed(title='[ YOUR BALANCE LIST ]',
                                  description=f"`{total_all_balance_usd}`",
                                  color=disnake.Color.blue(),
                                  timestamp=datetime.utcnow(), )
            # Remove zero from all_names
            if has_none_balance == True:
                msg = f'{ctx.author.mention}, you do not have any balance.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
            else:
                all_names = [each for each in all_names if each not in zero_tokens]
                page.add_field(name="Coin/Tokens: [{}]".format(len(all_names)), 
                               value="```"+", ".join(all_names)+"```", inline=False)
                if len(unknown_tokens) > 0:
                    unknown_tokens = list(set(unknown_tokens))
                    page.add_field(name="Unknown Tokens: {}".format(len(unknown_tokens)), 
                                   value="```"+", ".join(unknown_tokens)+"```", inline=False)
                if len(zero_tokens) > 0:
                    zero_tokens = list(set(zero_tokens))
                    page.add_field(name="Zero Balances: [{}]".format(len(zero_tokens)), 
                                   value="```"+", ".join(zero_tokens)+"```", inline=False)
                page.set_thumbnail(url=ctx.author.display_avatar)
                page.set_footer(text="Use the reactions to flip pages.")
                all_pages[0] = page

                view = MenuPage(ctx, all_pages, timeout=30)
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    view.message = await ctx.response.send_message(embed=all_pages[0], view=view)
                else:
                    await tmp_msg.delete()
                    view.message = await ctx.reply(content=None, embed=all_pages[0], view=view)


    @commands.command(
        usage='balance <token>', 
        aliases=['balance', 'bal'],
        description="Get your token's balance."
    )
    async def _balance(
        self, 
        ctx, 
        token: str
    ):
        await self.async_balance(ctx, token)


    @commands.slash_command(
        usage='balance <token>', 
        options=[
            Option('token', 'token', OptionType.string, required=True)
        ],
        description="Get your token's balance."
    )
    async def balance(
        self, 
        ctx, 
        token: str
    ):
        await self.async_balance(ctx, token)


    @commands.command(
        usage='balances', 
        aliases=['balances', 'bals'],
        description="Get all your token's balance."
    )
    async def _balances(
        self, 
        ctx, 
        *, 
        tokens: str=None
    ):
        await self.async_balances(ctx, tokens)


    @commands.slash_command(
        usage='balances', 
        options=[
            Option('tokens', 'tokens', OptionType.string, required=False)
        ],
        description="Get all your token's balance."
    )
    async def balances(
        self, 
        ctx,
        tokens: str=None
    ):
        await self.async_balances(ctx, tokens)
    # End of Balance


    # Withdraw
    async def async_withdraw(self, ctx, amount: str, token: str, address: str):
        COIN_NAME = token.upper()
        if not hasattr(self.bot.coin_list, COIN_NAME):
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
            else:
                await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
            return
        else:
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "is_maintenance") == 1:
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** is currently under maintenance.')
                else:
                    await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** is currently under maintenance.')
                return
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_withdraw") != 1:
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** withdraw is currently disable.')
                else:
                    await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** withdraw is currently disable.')
                return
        # Do the job
        try:
            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            MinTx = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tx")
            MaxTx = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tx")
            NetFee = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_withdraw_fee")
            tx_fee = getattr(getattr(self.bot.coin_list, COIN_NAME), "tx_fee")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")

            if tx_fee is None:
                tx_fee = NetFee
            token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
            fee_limit = getattr(getattr(self.bot.coin_list, COIN_NAME), "fee_limit")
            get_deposit = await self.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await self.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']

            # Check if tx in progress
            if ctx.author.id in self.bot.TX_IN_PROCESS:
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
                else:
                    await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                    msg = await ctx.reply(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
                return

            height = None
            try:
                if type_coin in ["ERC-20", "TRC-20"]:
                    height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                else:
                    height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            if height is None:
                await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** cannot pull information from network. Try again later.')
                return
            else:
                # check if amount is all
                all_amount = False
                if not amount.isdigit() and amount.upper() == "ALL":
                    all_amount = True
                    userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), TOKEN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                    amount = float(userdata_balance['adjust']) - NetFee
                # If $ is in amount, let's convert to coin/token
                elif "$" in amount[-1] or "$" in amount[0]: # last is $
                    # Check if conversion is allowed for this coin.
                    amount = amount.replace(",", "").replace("$", "")
                    if usd_equivalent_enable == 0:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{COIN_NAME}`."
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return
                    else:
                        native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                        COIN_NAME_FOR_PRICE = COIN_NAME
                        if native_token_name:
                            COIN_NAME_FOR_PRICE = native_token_name
                        per_unit = None
                        if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                            id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                            per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                        else:
                            per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
                        if per_unit and per_unit > 0:
                            amount = float(Decimal(amount) / Decimal(per_unit))
                        else:
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method.'
                            if type(ctx) == disnake.ApplicationCommandInteraction:
                                await ctx.response.send_message(msg)
                            else:
                                await ctx.reply(msg)
                            return
                else:
                    amount = amount.replace(",", "")
                    amount = text_to_num(amount)
                    if amount is None:
                        await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.')
                        return

                # end of check if amount is all
                amount = float(amount)
                userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                actual_balance = float(userdata_balance['adjust'])

                # If balance 0, no need to check anything
                if actual_balance <= 0:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention} Please check your **{token_display}** balance.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg, ephemeral=True)
                    else:
                        await ctx.reply(msg)
                    return
                if amount > actual_balance:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send out {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg, ephemeral=True)
                    else:
                        await ctx.reply(msg)
                    return

                if amount + NetFee > actual_balance:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send out {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}. You need to leave at least network fee: {num_format_coin(NetFee, COIN_NAME, coin_decimal, False)} {token_display}.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg, ephemeral=True)
                    else:
                        await ctx.reply(msg)
                    return
                elif amount < MinTx or amount > MaxTx:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be smaller than {num_format_coin(MinTx, COIN_NAME, coin_decimal, False)} {token_display} or bigger than {num_format_coin(MaxTx, COIN_NAME, coin_decimal, False)} {token_display}.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg, ephemeral=True)
                    else:
                        await ctx.reply(msg)
                    return

                equivalent_usd = ""
                total_in_usd = 0.0
                per_unit = None
                if usd_equivalent_enable == 1:
                    native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                    COIN_NAME_FOR_PRICE = COIN_NAME
                    if native_token_name:
                        COIN_NAME_FOR_PRICE = native_token_name
                    if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                        id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                    else:
                        per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
                    if per_unit and per_unit > 0:
                        total_in_usd = float(Decimal(amount) * Decimal(per_unit))
                        if total_in_usd >= 0.0001:
                            equivalent_usd = " ~ {:,.4f} USD".format(total_in_usd)

                if type_coin in ["ERC-20"]:
                    # Check address
                    valid_address = self.check_address_erc20(address)
                    valid = False
                    if valid_address and valid_address.upper() == address.upper():
                        valid = True
                    else:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n`{address}`'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return

                    SendTx = None
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        try:
                            url = self.bot.erc_node_list[net_name]
                            chain_id = getattr(getattr(self.bot.coin_list, COIN_NAME), "chain_id")
                            SendTx = await self.send_external_erc20(url, net_name, str(ctx.author.id), address, amount, COIN_NAME, coin_decimal, NetFee, SERVER_BOT, chain_id, contract)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot(traceback.format_exc())
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish.'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg, ephemeral=True)
                        else:
                            await ctx.reply(msg)
                        return

                    if SendTx:
                        try:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} You withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx}`'
                            if type(ctx) == disnake.ApplicationCommandInteraction:
                                await ctx.response.send_message(msg, ephemeral=True)
                            else:
                                await ctx.reply(msg)
                            return
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        try:
                            await logchanbot(f'[{SERVER_BOT}] A user {ctx.author.name}#{ctx.author.discriminator} sucessfully withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}')
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                elif type_coin in ["TRC-20", "TRC-10"]:
                    # TODO: validate address
                    SendTx = None
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        try:
                            SendTx = await self.send_external_trc20(str(ctx.author.id), address, amount, COIN_NAME, coin_decimal, NetFee, SERVER_BOT, fee_limit, type_coin, contract)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot(traceback.format_exc())
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish.'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg, ephemeral=True)
                        else:
                            await ctx.reply(msg)
                        return

                    if SendTx:
                        try:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} You withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx}`'
                            if type(ctx) == disnake.ApplicationCommandInteraction:
                                await ctx.response.send_message(msg, ephemeral=True)
                            else:
                                await ctx.reply(msg)
                            return
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        try:
                            await logchanbot(f'[{SERVER_BOT}] A user {ctx.author.name}#{ctx.author.discriminator} sucessfully withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}')
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                elif type_coin == "NANO":
                    valid_address = await self.WalletAPI.nano_validate_address(COIN_NAME, address)
                    if not valid_address == True:
                        msg = f"{EMOJI_RED_NO} Address: `{address}` is invalid."
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg, ephemeral=True)
                        else:
                            await ctx.reply(msg)
                        return
                    else:
                        try:
                            main_address = getattr(getattr(self.bot.coin_list, COIN_NAME), "MainAddress")
                            SendTx = await self.WalletAPI.send_external_nano(main_address, str(ctx.author.id), amount, address, COIN_NAME, coin_decimal)
                            if SendTx:
                                SendTx_hash = SendTx['block']
                                msg = f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx_hash}`'
                                if type(ctx) == disnake.ApplicationCommandInteraction:
                                    await ctx.response.send_message(msg, ephemeral=True)
                                else:
                                    await ctx.reply(msg)
                                await logchanbot(f'A user successfully executed withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                            else:
                                await logchanbot(f'A user failed to execute withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                elif type_coin == "CHIA":
                    SendTx = await self.WalletAPI.send_external_xch(str(ctx.author.id), amount, address, COIN_NAME, coin_decimal, tx_fee, NetFee, SERVER_BOT)
                    if SendTx:
                        await logchanbot(f'A user successfully executed send {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        msg = f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx}`'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg, ephemeral=True)
                        else:
                            await ctx.reply(msg)
                    else:
                        await logchanbot(f'A user failed to execute to withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                elif type_coin == "BTC":
                    SendTx = await self.WalletAPI.send_external_doge(str(ctx.author.id), amount, address, COIN_NAME, 0, NetFee, SERVER_BOT) # tx_fee=0
                    if SendTx:
                        msg = f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx}`'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg, ephemeral=True)
                        else:
                            await ctx.reply(msg)
                        await logchanbot(f'A user successfully executed withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                    else:
                        await logchanbot(f'A user failed to execute to withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                elif type_coin == "XMR" or type_coin == "TRTL-API" or type_coin == "TRTL-SERVICE" or type_coin == "BCN":
                    main_address = getattr(getattr(self.bot.coin_list, COIN_NAME), "MainAddress")
                    mixin = getattr(getattr(self.bot.coin_list, COIN_NAME), "mixin")
                    wallet_address = getattr(getattr(self.bot.coin_list, COIN_NAME), "wallet_address")
                    header = getattr(getattr(self.bot.coin_list, COIN_NAME), "header")
                    is_fee_per_byte = getattr(getattr(self.bot.coin_list, COIN_NAME), "is_fee_per_byte")
                    SendTx = await self.WalletAPI.send_external_xmr(type_coin, main_address, str(ctx.author.id), amount, address, COIN_NAME, coin_decimal, tx_fee, NetFee, is_fee_per_byte, mixin, SERVER_BOT, wallet_address, header, None) # paymentId: None (end)
                    if SendTx:
                        msg = f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx}`'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg, ephemeral=True)
                        else:
                            await ctx.reply(msg)
                        await logchanbot(f'A user successfully executed withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                    else:
                        await logchanbot(f'A user failed to execute to withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.command(
        usage='withdraw <amount> <coin/token> <address>', 
        aliases=['withdraw', 'send'],
        description="withdraw to your external address."
    )
    async def _withdraw(
        self, 
        ctx,
        amount: str,
        token: str,
        address: str
    ):
        await self.async_withdraw(ctx, amount, token, address)


    @commands.slash_command(
        usage='withdraw', 
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option('address', 'address', OptionType.string, required=True)
        ],
        description="withdraw to your external address."
    )
    async def withdraw(
        self, 
        ctx,
        amount: str,
        token: str,
        address: str
    ):
        await self.async_withdraw(ctx, amount, token, address)
    # End of Balance

def setup(bot):
    bot.add_cog(Wallet(bot))
    bot.add_cog(WalletAPI(bot))