import sys, os
import traceback
from datetime import datetime
from decimal import Decimal
import disnake
from disnake.ext import commands
from disnake.enums import OptionType
from disnake.app_commands import Option
import time
import functools
import aiohttp, asyncio
import json

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

import store, utils
import cn_addressvalidation

from Bot import get_token_list, num_format_coin, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, RowButton_close_message, RowButton_row_close_any_message, human_format, text_to_num, truncate, seconds_str, encrypt_string, decrypt_string
from config import config


Account.enable_unaudited_hdwallet_features()


class Wallet(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    # Create ETH
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
                                print(full_payload)

                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                if method_name == "transfer":
                                    print(res_data)
                                await session.close()
                                decoded_data = json.loads(res_data)
                                if 'result' in decoded_data:
                                    return decoded_data['result']
                                else:
                                    print(decoded_data)
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
                                print(full_payload)
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                if method_name == "transfer":
                                    print(res_data)
                                await session.close()
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
                                await session.close()
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
                        await session.close()
                        decoded_data = json.loads(res_data)
                        return decoded_data
        except asyncio.TimeoutError:
            print('TIMEOUT: COIN: {} - timeout {}'.format(coin.upper(), timeout))
            await logchanbot('TIMEOUT: call_nano COIN: {} - timeout {}'.format(coin.upper(), timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    async def call_xch(self, method_name: str, coin: str, payload: Dict=None) -> Dict:
        import ssl
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
                    print(response)
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        await session.close()
                        decoded_data = json.loads(res_data)
                        return decoded_data
                    else:
                        await logchanbot(f'Call {COIN_NAME} returns {str(response.status)} with method {method_name}')
        except asyncio.TimeoutError:
            print('TIMEOUT: method_name: {} - COIN: {} - timeout {}'.format(method_name, COIN_NAME, timeout))
            await logchanbot('call_doge: method_name: {} - COIN: {} - timeout {}'.format(method_name, COIN_NAME, timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())


    async def call_doge(self, method_name: str, coin: str, payload: str = None) -> Dict:
        timeout = 100
        COIN_NAME = coin.upper()
        headers = {
            'content-type': 'text/plain;',
        }
        if payload is None:
            data = '{"jsonrpc": "1.0", "id":"'+str(uuid.uuid4())+'", "method": "'+method_name+'", "params": [] }'
        else:
            data = '{"jsonrpc": "1.0", "id":"'+str(uuid.uuid4())+'", "method": "'+method_name+'", "params": ['+payload+'] }'
        
        url = getattr(getattr(self.bot.coin_list, COIN_NAME), "daemon_address")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        await session.close()
                        decoded_data = json.loads(res_data)
                        return decoded_data['result']
                    else:
                        await logchanbot(f'Call {COIN_NAME} returns {str(response.status)} with method {method_name}')
        except asyncio.TimeoutError:
            print('TIMEOUT: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin.upper(), timeout))
            await logchanbot('call_doge: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin.upper(), timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    async def sql_get_userwallet(self, userID, coin: str, netname: str, type_coin: str, user_server: str = 'DISCORD', chat_id: int = 0):
        # type_coin: 'ERC-20','TRC-20','TRTL-API','TRTL-SERVICE','BCN','XMR','NANO','BTC','CHIA','OTHER'
        # netname null or None, xDai, MATIC, TRX, BSC
        user_server = user_server.upper()
        COIN_NAME = coin.upper()
        if type_coin.upper() == "ERC-20" and COIN_NAME != netname.upper():
            user_id_erc20 = str(userID) + "_" + type_coin.upper()
        elif type_coin.upper() == "ERC-20" and COIN_NAME == netname.upper():
            user_id_erc20 = str(userID) + "_" + COIN_NAME
        if type_coin.upper() == "TRC-20" and COIN_NAME != netname.upper():
            user_id_erc20 = str(userID) + "_" + type_coin.upper()
        elif type_coin.upper() == "TRC-20" and COIN_NAME == netname.upper():
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


    # TODO: all coin, to register
    # ERC-20, TRC-20, native is one
    # Gas Token like BNB, xDAI, MATIC, TRX will be a different address
    async def sql_register_user(self, userID, coin: str, netname: str, type_coin: str, user_server: str, chat_id: int = 0):
        try:
            COIN_NAME = coin.upper()
            user_server = user_server.upper()
            balance_address = None
            main_address = None

            if type_coin.upper() == "ERC-20" and COIN_NAME != netname.upper():
                user_id_erc20 = str(userID) + "_" + type_coin.upper()
            elif type_coin.upper() == "ERC-20" and COIN_NAME == netname.upper():
                user_id_erc20 = str(userID) + "_" + COIN_NAME
            if type_coin.upper() == "TRC-20" and COIN_NAME != netname.upper():
                user_id_erc20 = str(userID) + "_" + type_coin.upper()
            elif type_coin.upper() == "TRC-20" and COIN_NAME == netname.upper():
                user_id_erc20 = str(userID) + "_" + COIN_NAME

            if type_coin.upper() == "ERC-20":
                # passed test XDAI, MATIC
                w = await self.create_address_eth()
                balance_address = w['address']
            elif type_coin.upper() == "TRC-20":
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
                walletkey = getattr(getattr(self.bot.coin_list, COIN_NAME), "walletkey")
                address_call = await self.call_nano(COIN_NAME, payload='{ "action": "account_create", "wallet": "'+walletkey+'" }')
                reg_address = {}
                reg_address['address'] = address_call['account']
                balance_address = reg_address['address']
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
                            sql = """ INSERT INTO `erc20_user` (`user_id`, `user_id_erc20`, `balance_wallet_address`, `address_ts`, 
                                      `seed`, `create_dump`, `private_key`, `public_key`, `xprivate_key`, `xpublic_key`, 
                                      `user_server`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (str(userID), user_id_erc20, w['address'], int(time.time()), 
                                              encrypt_string(w['seed']), encrypt_string(str(w)), encrypt_string(str(w['private_key'])), w['public_key'], 
                                              encrypt_string(str(w['xprivate_key'])), w['xpublic_key'], user_server))
                            await conn.commit()
                            return {'balance_wallet_address': w['address']}
                        elif netname and netname in ["TRX"]:
                            sql = """ INSERT INTO `trc20_user` (`user_id`, `user_id_trc20`, `balance_wallet_address`, `hex_address`, `address_ts`, 
                                      `private_key`, `public_key`, `user_server`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (str(userID), user_id_erc20, w['base58check_address'], w['hex_address'], int(time.time()), 
                                              encrypt_string(str(w['private_key'])), w['public_key'], user_server))
                            await conn.commit()
                            return {'balance_wallet_address': w['base58check_address']}
                        elif type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                            sql = """ INSERT INTO cn_user_paymentid (`coin_name`, `user_id`, `user_id_coin`, `main_address`, `paymentid`, 
                                      `balance_wallet_address`, `paymentid_ts`, `user_server`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, str(userID), "{}_{}".format(userID, COIN_NAME), main_address, balance_address['payment_id'], 
                                                    balance_address['integrated_address'], int(time.time()), user_server))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['integrated_address']}
                        elif type_coin.upper() == "NANO":
                            sql = """ INSERT INTO `nano_user` (`coin_name`, `user_id`, `user_id_coin`, `balance_wallet_address`, `address_ts`, `user_server`) 
                                      VALUES (%s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, str(userID), "{}_{}".format(userID, COIN_NAME), balance_address['address'], int(time.time()), user_server))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin.upper() == "BTC":
                            sql = """ INSERT INTO `doge_user` (`coin_name`, `user_id`, `user_id_coin`, `balance_wallet_address`, `address_ts`, `privateKey`, `user_server`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, str(userID), "{}_{}".format(userID, COIN_NAME), balance_address['address'], int(time.time()), 
                                                    encrypt_string(balance_address['privateKey']), user_server))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin.upper() == "CHIA":
                            sql = """ INSERT INTO `xch_user` (`coin_name`, `user_id`, `user_id_coin`, `balance_wallet_address`, `address_ts`, `user_server`) 
                                      VALUES (%s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, str(userID), "{}_{}".format(userID, COIN_NAME), balance_address['address'], int(time.time()), user_server))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None


    # TODO: this is for TRC-10, TRC-20, ERC-20 only
    async def http_wallet_getbalance(self, address: str, coin: str, use_url: str=None) -> Dict:
        TOKEN_NAME = coin.upper()
        timeout = 64
        url = config.ftm.default_rpc
        if use_url and use_url != "":
            url = use_url
            # print("fetching from {}".format(use_url))
        if TOKEN_NAME == "BNB" or TOKEN_NAME == "XDAI" or TOKEN_NAME == "MATIC" or TOKEN_NAME == "FTM":
            data = '{"jsonrpc":"2.0","method":"eth_getBalance","params":["'+address+'", "latest"],"id":1}'
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers={'Content-Type': 'application/json'}, json=json.loads(data), timeout=timeout) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            await session.close()
                            decoded_data = json.loads(res_data)
                            if decoded_data and 'result' in decoded_data:
                                return int(decoded_data['result'], 16)
            except asyncio.TimeoutError:
                print('TIMEOUT: get balance {} for {}s'.format(TOKEN_NAME, timeout))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        else:
            token_info = (await get_all_token())[TOKEN_NAME]
            contract = token_info['contract']
            data = '{"jsonrpc":"2.0","method":"eth_call","params":[{"to": "'+contract+'", "data": "0x70a08231000000000000000000000000'+address[2:]+'"}, "latest"],"id":1}'
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers={'Content-Type': 'application/json'}, json=json.loads(data), timeout=timeout) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            await session.close()
                            decoded_data = json.loads(res_data)
                            if decoded_data and 'result' in decoded_data:
                                return int(decoded_data['result'], 16)
            except asyncio.TimeoutError:
                print('TIMEOUT: get balance {} for {}s'.format(TOKEN_NAME, timeout))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        return None


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
            netname = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
            get_deposit = await self.sql_get_userwallet(str(ctx.author.id), COIN_NAME, netname, type_coin, SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await self.sql_register_user(str(ctx.author.id), COIN_NAME, netname, type_coin, SERVER_BOT, 0)
                
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


def setup(bot):
    bot.add_cog(Wallet(bot))
