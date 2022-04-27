import sys, os
import traceback
from datetime import datetime, timedelta
from decimal import Decimal
import disnake
from disnake.ext import commands, tasks
from disnake.enums import OptionType
from disnake.app_commands import Option
import time
import functools
import aiohttp, asyncio
import json
import random
import numpy as np

import qrcode
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict
import uuid
import aiomysql
from aiomysql.cursors import DictCursor

from web3 import Web3
from web3.middleware import geth_poa_middleware
from ethtoken.abi import EIP20_ABI

from tronpy import AsyncTron
from tronpy.async_contract import AsyncContract, ShieldedTRC20, AsyncContractMethod
from tronpy.providers.async_http import AsyncHTTPProvider
from tronpy.exceptions import AddressNotFound
from tronpy.keys import PrivateKey

# For Solana
from solana.rpc.async_api import AsyncClient as Sol_AsyncClient
from solana.publickey import PublicKey
from solana.rpc.types import TokenAccountOpts
from solana.keypair import Keypair
from solana.transaction import Transaction
from solana.system_program import TransferParams, transfer

from httpx import AsyncClient, Timeout, Limits

from eth_account import Account
import base64

from pywallet import wallet as ethwallet
import ssl
from eth_utils import is_hex_address # Check hex only
from terminaltables import AsciiTable

import store
import cn_addressvalidation

from Bot import get_token_list, num_format_coin, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, RowButton_close_message, RowButton_row_close_any_message, human_format, text_to_num, truncate, seconds_str, encrypt_string, decrypt_string, EMOJI_HOURGLASS_NOT_DONE, alert_if_userlock, MSG_LOCKED_ACCOUNT, EMOJI_MONEYFACE, EMOJI_INFORMATION
from config import config
import redis_utils
from utils import MenuPage

Account.enable_unaudited_hdwallet_features()


class RPCException(Exception):
    def __init__(self, message):
        super(RPCException, self).__init__(message)


class Faucet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # DB
        self.pool = None

    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=2, maxsize=6, 
                                                       user=config.mysql.user, password=config.mysql.password,
                                                       db=config.mysql.db, cursorclass=DictCursor, autocommit=True)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    async def get_faucet_coin_list(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT `reward_for`, `coin_name`, `reward_amount`
                              FROM `coin_bot_reward_setting` 
                              ORDER BY `coin_name` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0: 
                        return result
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return []

    async def update_faucet_user(self, userId: str, coin_name: str, user_server: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `coin_user_reward_setting` (`user_id`, `coin_name`, `user_server`)
                              VALUES (%s, %s, %s) ON DUPLICATE KEY 
                              UPDATE 
                              `coin_name`=VALUES(`coin_name`)
                              """
                    await cur.execute(sql, (userId, coin_name.upper(), user_server.upper(), ))
                    await conn.commit()
                    return True
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return False
    
    async def get_user_faucet_coin(self, userId: str, user_server: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_user_reward_setting` WHERE `user_id`=%s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, ( userId, user_server.upper() ))
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None

    async def insert_reward(self, userId: str, reward_for: str, reward_amount: float, coin_name: str, reward_time: int, user_server: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `coin_user_reward_list` (`user_id`, `reward_for`, `reward_amount`, `coin_name`, `reward_time`, `user_server`)
                              VALUES (%s, %s, %s, %s, %s, %s)
                              """
                    await cur.execute(sql, (userId, reward_for, reward_amount, coin_name.upper(), reward_time, user_server.upper(), ))
                    await conn.commit()
                    return True
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return False


class WalletAPI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # DB
        self.pool = None

    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=2, maxsize=6, 
                                                       user=config.mysql.user, password=config.mysql.password,
                                                       db=config.mysql.db, cursorclass=DictCursor, autocommit=True)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    async def generate_qr_address(
        self, 
        address: str
    ):
        # return path to image
        # address = wallet['balance_wallet_address']
        # return address if success, else None
        address_path = address.replace('{', '_').replace('}', '_').replace(':', '_').replace('"', "_").replace(',', "_").replace(' ', "_")
        if not os.path.exists(config.storage.path_deposit_qr_create + address_path + ".png"):
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
                img.save(config.storage.path_deposit_qr_create + address_path + ".png")
                return address
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        else:
            return address
        return None

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
            elif type_coin.upper() == "HNT":
                # generate random memo
                from string import ascii_uppercase
                main_address = getattr(getattr(self.bot.coin_list, COIN_NAME), "MainAddress")
                memo = ''.join(random.choice(ascii_uppercase) for i in range(8))
                balance_address = {}
                balance_address['balance_wallet_address'] = "{} MEMO: {}".format(main_address, memo)
                balance_address['address'] = main_address
                balance_address['memo'] = memo
            elif type_coin.upper() == "ADA":
                # get address pool
                address_pools = await store.ada_get_address_pools(50)
                balance_address = {}
                if address_pools:
                    wallet_name = address_pools['wallet_name']
                    addresses = address_pools['addresses']
                    random.shuffle(addresses)
                    balance_address['balance_wallet_address'] = addresses[0]
                    balance_address['address'] = addresses[0]
                    balance_address['wallet_name'] = wallet_name
            elif type_coin.upper() == "SOL":
                balance_address = {}
                kp = Keypair.generate()
                public_key = str(kp.public_key)
                balance_address['balance_wallet_address'] = public_key
                balance_address['secret_key_hex'] = kp.secret_key.hex()
            await self.openConnection()
            async with self.pool.acquire() as conn:
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
                        elif type_coin.upper() == "HNT":
                            sql = """ INSERT INTO `hnt_user` (`coin_name`, `user_id`, `main_address`, `balance_wallet_address`, `memo`, `address_ts`, `user_server`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, str(userID), main_address, balance_address['balance_wallet_address'], memo, int(time.time()), user_server, is_discord_guild))
                            await conn.commit()
                            return balance_address
                        elif type_coin.upper() == "ADA":
                            sql = """ INSERT INTO `ada_user` (`user_id`, `wallet_name`, `balance_wallet_address`, `address_ts`, `user_server`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s);
                                      UPDATE `ada_wallets` SET `used_address`=`used_address`+1 WHERE `wallet_name`=%s LIMIT 1; """
                            await cur.execute(sql, ( str(userID), balance_address['wallet_name'], balance_address['address'], int(time.time()), user_server, is_discord_guild, balance_address['wallet_name'] ))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin.upper() == "SOL":
                            sql = """ INSERT INTO `sol_user` (`user_id`, `balance_wallet_address`, `address_ts`, `secret_key_hex`, `called_Update`, `user_server`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, ( str(userID),  balance_address['balance_wallet_address'], int(time.time()), encrypt_string(balance_address['secret_key_hex']), int(time.time()), user_server, is_discord_guild ))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['balance_wallet_address']}
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
            await self.openConnection()
            async with self.pool.acquire() as conn:
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
                    elif type_coin.upper() == "HNT":
                        sql = """ SELECT * FROM `hnt_user` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server` = %s LIMIT 1 """
                        await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "ADA":
                        sql = """ SELECT * FROM `ada_user` WHERE `user_id`=%s AND `user_server` = %s LIMIT 1 """
                        await cur.execute(sql, (str(userID), user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "SOL":
                        sql = """ SELECT * FROM `sol_user` WHERE `user_id`=%s AND `user_server` = %s LIMIT 1 """
                        await cur.execute(sql, (str(userID), user_server))
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
        COIN_NAME = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
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
                await self.openConnection()
                async with self.pool.acquire() as conn:
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
        user_server = user_server.upper()
        COIN_NAME = coin.upper()
        try:
            comment = user_from
            comment_to = to_address
            payload = f'"{to_address}", {amount}, "{comment}", "{comment_to}", false'
            if COIN_NAME in ["PGO"]:
                payload = f'"{to_address}", {amount}, "{comment}", "{comment_to}"'
            txHash = await self.call_doge('sendtoaddress', COIN_NAME, payload=payload)
            if txHash is not None:
                await self.openConnection()
                async with self.pool.acquire() as conn:
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
                    await self.openConnection()
                    async with self.pool.acquire() as conn:
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
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
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
                                    await self.openConnection()
                                    async with self.pool.acquire() as conn:
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
                        'paymentId': paymentId,
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
                        'paymentId': paymentId,
                        'changeAddress': from_address
                    }
                result = None
                result = await self.call_aiohttp_wallet_xmr_bcn('sendTransaction', COIN_NAME, time_out=time_out, payload=payload)
                if result and 'transactionHash' in result:
                    if is_fee_per_byte != 1:
                        tx_hash = {"transactionHash": result['transactionHash'], "fee": tx_fee}
                    else:
                        tx_hash = {"transactionHash": result['transactionHash'], "fee": result['fee']}
                        tx_fee = float(tx_hash['fee']/10**coin_decimal)
                    try:
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `paymentid`, `date`, `tx_hash`, `user_server`) 
                                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                await cur.execute(sql, (COIN_NAME, user_from, amount, tx_fee, withdraw_fee, coin_decimal, to_address, paymentId, int(time.time()), tx_hash['transactionHash'], user_server))
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
                        'paymentID': paymentId,
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
                        'paymentID': paymentId,
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
                                    await self.openConnection()
                                    async with self.pool.acquire() as conn:
                                        async with conn.cursor() as cur:
                                            sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `paymentid`, `date`, `tx_hash`, `user_server`) 
                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                            await cur.execute(sql, (COIN_NAME, user_from, amount, tx_fee, withdraw_fee, coin_decimal, to_address, paymentId, int(time.time()), tx_hash['transactionHash'], user_server))
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


    async def send_external_hnt(self, user_id: str, wallet_host: str, password: str, from_address: str, payee: str, amount: float, coin_decimal: int, user_server: str, coin: str, withdraw_fee: float, time_out=32):
        COIN_NAME = coin.upper()
        if from_address == payee: return None
        try:
            headers = {
                'Content-Type': 'application/json'
            }
            json_send = {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "wallet_pay",
                "params": {
                    "address": from_address,
                    "payee": payee,
                    "bones": int(amount*10**coin_decimal)
                    #"nonce": 422
                }
            }
            json_unlock = {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "wallet_unlock",
                "params": {
                    "address": from_address,
                    "password": password
                }
            }
            json_check_lock = {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "wallet_is_locked",
                "params": {
                    "address": from_address
                }
            }
            async def call_hnt_wallet(url, headers, json_data, time_out):
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=json_data, timeout=time_out) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            json_resp = decoded_data
                            return json_resp
            # 1] Check if lock
            # 3] Unlock
            try:
                unlock = None
                check_locked = await call_hnt_wallet(wallet_host, headers=headers, json_data=json_check_lock, time_out=time_out)
                print(check_locked)
                if 'result' in check_locked and check_locked['result'] == True:
                    await logchanbot(f'[UNLOCKED] {COIN_NAME}...')
                    unlock = await call_hnt_wallet(wallet_host, headers=headers, json_data=json_unlock, time_out=time_out)
                    print(unlock)
                if unlock is None or (unlock is not None and 'result' in unlock and unlock['result'] == True):
                    sendTx = await call_hnt_wallet(wallet_host, headers=headers, json_data=json_send, time_out=time_out)
                    fee = 0.0
                    if 'result' in sendTx:
                        if 'implicit_burn' in sendTx['result'] and 'fee' in sendTx['result']['implicit_burn']:
                            fee = sendTx['result']['implicit_burn']['fee']/10**coin_decimal
                        elif 'fee' in sendTx['result']:
                            fee = sendTx['result']['fee']/10**coin_decimal
                        try:
                            await self.openConnection()
                            async with self.pool.acquire() as conn:
                                async with conn.cursor() as cur:
                                    sql = """ INSERT INTO hnt_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                    await cur.execute(sql, (COIN_NAME, user_id, amount, fee, withdraw_fee, coin_decimal, payee, int(time.time()), sendTx['result']['hash'], user_server))
                                    await conn.commit()
                                    return sendTx['result']['hash']
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                        # return tx_hash
                else:
                    await logchanbot('[FAILED] send_external_hnt: Failed to unlock wallet...')
                    return None
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def send_external_ada(self, user_id: str, amount: float, coin_decimal: int, user_server: str, coin: str, withdraw_fee: float, to_address: str, time_out=32):
        COIN_NAME = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `ada_wallets` 
                              WHERE `is_for_withdraw`=%s ORDER BY RAND() LIMIT 1 """
                    await cur.execute(sql, ( 1 ))
                    result = await cur.fetchone()
                    if result:
                        ## got wallet setting
                        # check if wallet sync
                        async def fetch_wallet_status(url, timeout):
                            try:
                                headers = {
                                    'Content-Type': 'application/json'
                                }
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(url, headers=headers, timeout=timeout) as response:
                                        res_data = await response.read()
                                        res_data = res_data.decode('utf-8')
                                        decoded_data = json.loads(res_data)
                                        return decoded_data
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            return None
                        fetch_wallet = await fetch_wallet_status(result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'], 8)
                        if fetch_wallet and fetch_wallet['state']['status'] == "ready":
                            # wallet is ready, "syncing" if it is syncing
                            async def send_tx(url: str, to_address: str, amount_atomic: int, timeout: int=90):
                                try:
                                    headers = {
                                        'Content-Type': 'application/json'
                                    }
                                    data_json = {"passphrase": decrypt_string(result['passphrase']), "payments": [{"address": to_address, "amount": {"quantity": amount_atomic, "unit": "lovelace"}}], "withdrawal": "self"}
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(url, headers=headers, json=data_json, timeout=timeout) as response:
                                            if response.status == 202:
                                                res_data = await response.read()
                                                res_data = res_data.decode('utf-8')
                                                decoded_data = json.loads(res_data)
                                                return decoded_data
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                return None
                            sending_tx = await send_tx(result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'] + "/transactions", to_address, int(amount*10**coin_decimal), 90)
                            if "code" in sending_tx and "message" in sending_tx:
                                return sending_tx
                            elif "status" in sending_tx and sending_tx['status'] == "pending":
                                # success
                                # withdraw_fee became: network_fee + withdraw_fee, it is fee_limit
                                network_fee = sending_tx['fee']['quantity']/10**coin_decimal
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
                                    async with conn.cursor() as cur:
                                        sql = """ INSERT INTO `ada_external_tx` (`coin_name`, `asset_name`, `policy_id`, `user_id`, `real_amount`, `real_external_fee`, `network_fee`, `token_decimal`, `to_address`, `input_json`, `output_json`, `hash_id`, `date`, `user_server`) 
                                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                        await cur.execute(sql, ( COIN_NAME, None, None, user_id, amount, network_fee+withdraw_fee, network_fee, coin_decimal, to_address, json.dumps(sending_tx['inputs']), json.dumps(sending_tx['outputs']), sending_tx['id'], int(time.time()), user_server ))
                                        await conn.commit()
                                        return sending_tx
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def send_external_ada_asset(self, user_id: str, amount: float, coin_decimal: int, user_server: str, coin: str, withdraw_fee: float, to_address: str, asset_name: str, policy_id: str, time_out=32):
        COIN_NAME = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `ada_wallets` 
                              WHERE `is_for_withdraw`=%s ORDER BY RAND() LIMIT 1 """
                    await cur.execute(sql, ( 1 ))
                    result = await cur.fetchone()
                    if result:
                        ## got wallet setting
                        # check if wallet sync
                        async def fetch_wallet_status(url, timeout):
                            try:
                                headers = {
                                    'Content-Type': 'application/json'
                                }
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(url, headers=headers, timeout=timeout) as response:
                                        res_data = await response.read()
                                        res_data = res_data.decode('utf-8')
                                        decoded_data = json.loads(res_data)
                                        return decoded_data
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            return None
                        fetch_wallet = await fetch_wallet_status(result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'], 8)
                        if fetch_wallet and fetch_wallet['state']['status'] == "ready":
                            # wallet is ready, "syncing" if it is syncing
                            async def estimate_fee_with_asset(url: str, to_address: str, asset_name: str, policy_id: str, amount_atomic: int, timeout: int=90):
                                try:
                                    headers = {
                                        'Content-Type': 'application/json'
                                    }
                                    data_json = {"payments": [{"address": to_address, "amount": {"quantity": 0, "unit": "lovelace"}, "assets": [{"policy_id": policy_id, "asset_name": asset_name, "quantity": amount_atomic}]}], "withdrawal": "self"}
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(url, headers=headers, json=data_json, timeout=timeout) as response:
                                            if response.status == 202:
                                                res_data = await response.read()
                                                res_data = res_data.decode('utf-8')
                                                decoded_data = json.loads(res_data)
                                                return decoded_data
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                return None
                            async def send_tx(url: str, to_address: str, ada_atomic_amount: int, amount_atomic: int, asset_name: str, policy_id: str, timeout: int=90):
                                try:
                                    headers = {
                                        'Content-Type': 'application/json'
                                    }
                                    data_json = {"passphrase": decrypt_string(result['passphrase']), "payments": [{"address": to_address, "amount": {"quantity": ada_atomic_amount, "unit": "lovelace"}, "assets": [{"policy_id": policy_id, "asset_name": asset_name, "quantity": amount_atomic}]}], "withdrawal": "self"}
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(url, headers=headers, json=data_json, timeout=timeout) as response:
                                            if response.status == 202:
                                                res_data = await response.read()
                                                res_data = res_data.decode('utf-8')
                                                decoded_data = json.loads(res_data)
                                                return decoded_data
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                return None
                            estimate_tx = await estimate_fee_with_asset(result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'] + "/payment-fees", to_address, asset_name, policy_id, int(amount*10**coin_decimal), 10)
                            ada_fee_atomic = None
                            if estimate_tx and "minimum_coins" in estimate_tx:
                                ada_fee_atomic = estimate_tx['minimum_coins'][0]['quantity']
                                sending_tx = await send_tx(result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'] + "/transactions", to_address, ada_fee_atomic, int(amount*10**coin_decimal), asset_name, policy_id, 90)
                                if "code" in sending_tx and "message" in sending_tx:
                                    return sending_tx
                                elif "status" in sending_tx and sending_tx['status'] == "pending":
                                    # success
                                    rows = []
                                    if len(sending_tx['outputs']) > 0:
                                        network_fee = sending_tx['fee']['quantity']/10**6 # Fee in ADA
                                        for each_output in sending_tx['outputs']:
                                            if each_output['address'].upper() == to_address:
                                                # rows.append( () )
                                                pass
                                    data_rows = []
                                    try:
                                        data_rows.append( ( COIN_NAME, asset_name, policy_id, user_id, amount, withdraw_fee, network_fee, coin_decimal, to_address, json.dumps(sending_tx['inputs']), json.dumps(sending_tx['outputs']), sending_tx['id'], int(time.time()), user_server ) )
                                        if getattr(getattr(self.bot.coin_list, COIN_NAME), "withdraw_use_gas_ticker") == 1:
                                            GAS_COIN = getattr(getattr(self.bot.coin_list, COIN_NAME), "gas_ticker")
                                            fee_limit = getattr(getattr(self.bot.coin_list, COIN_NAME), "fee_limit")
                                            fee_limit = fee_limit/20 #  => 2 / 20 = 0.1 ADA # Take care if you adjust fee_limit in DB
                                            # new ADA charge = ADA goes to withdraw wallet + 0.1 ADA
                                            data_rows.append( ( GAS_COIN, None, None, user_id, network_fee+fee_limit+ada_fee_atomic/10**6, 0, network_fee, getattr(getattr(self.bot.coin_list, GAS_COIN), "decimal"), to_address, json.dumps(sending_tx['inputs']), json.dumps(sending_tx['outputs']), sending_tx['id'], int(time.time()), user_server ) )
                                        await self.openConnection()
                                        async with self.pool.acquire() as conn:
                                            async with conn.cursor() as cur:
                                                sql = """ INSERT INTO `ada_external_tx` (`coin_name`, `asset_name`, `policy_id`, `user_id`, `real_amount`, `real_external_fee`, `network_fee`, `token_decimal`, `to_address`, `input_json`, `output_json`, `hash_id`, `date`, `user_server`) 
                                                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                await cur.executemany(sql, data_rows)
                                                await conn.commit()
                                                sending_tx['all_ada_fee'] = network_fee+fee_limit+ada_fee_atomic/10**6
                                                sending_tx['ada_received'] = ada_fee_atomic/10**6
                                                sending_tx['network_fee'] = network_fee
                                                return sending_tx
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot(f'[BUG] send_external_ada_asset: user_id: `{user_id}` failed to insert to DB for withdraw {json.dumps(data_rows)}.')
                            else:
                                print("send_external_ada_asset: cannot get estimated fee for sending asset `{asset_name}`")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def send_external_sol(self, url: str, user_from: str, amount: float, to_address: str, coin: str, coin_decimal: int, tx_fee: float, withdraw_fee: float, user_server: str='DISCORD'):
        async def move_wallet_balance(url: str, receiver: str, atomic_amount: int):
            # url: is endpoint transfer
            try:
                sender = Keypair.from_secret_key(bytes.fromhex(config.sol.MainAddress_key_hex))
                client = Sol_AsyncClient(url)
                txn = Transaction().add(transfer(TransferParams(
                   from_pubkey=sender.public_key, to_pubkey=receiver, lamports=atomic_amount)))
                sending_tx = await client.send_transaction(txn, sender)
                if 'result' in sending_tx:
                    await client.close()
                    return sending_tx['result'] # This is Tx Hash
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return None
        try:
            send_tx = await move_wallet_balance(url, to_address, int(amount*10**coin_decimal))
            if send_tx:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO `sol_external_tx` (`coin_name`, `contract`, `user_id`, `real_amount`, `real_external_fee`, `network_fee`, `txn`, `token_decimal`, `to_address`, `date`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, ( coin.upper(), None, user_from, amount, withdraw_fee, tx_fee, send_tx, coin_decimal, to_address, int(time.time()), user_server ))
                        await conn.commit()
                        return send_tx
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None


class Wallet(commands.Cog):

    def __init__(self, bot):
        self.enable_logchan = True
        self.bot = bot
        self.WalletAPI = WalletAPI(self.bot)
        
        self.botLogChan = None
        
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
        
        # HNT
        self.update_balance_hnt.start()
        self.notify_new_confirmed_hnt.start()
        
        # Swap
        self.swap_pair = {"WRKZ-BWRKZ": 1, "BWRKZ-WRKZ": 1, "WRKZ-XWRKZ": 1, "XWRKZ-WRKZ": 1, "DEGO-WDEGO": 0.001, "WDEGO-DEGO": 1000, "PGO-WPGO": 1, "WPGO-PGO": 1}
        # Donate
        self.donate_to = 386761001808166912 #pluton#8888
        
        # avoid duplicated tx
        self.notified_pending_tx = []
        self.notified_tx = []

        # update ada wallet sync status
        self.update_ada_wallets_sync.start()
        self.notify_new_confirmed_ada.start()
        
        # update sol wallet sync status
        self.update_sol_wallets_sync.start()
        self.unlocked_move_pending_sol.start()

        # DB
        self.pool = None


    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=4, maxsize=8, 
                                                       user=config.mysql.user, password=config.mysql.password,
                                                       db=config.mysql.db, cursorclass=DictCursor, autocommit=True)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    async def user_balance(self, userID: str, coin: str, address: str, coin_family: str, top_block: int, confirmed_depth: int=0, user_server: str = 'DISCORD'):
        # address: TRTL/BCN/XMR = paymentId
        TOKEN_NAME = coin.upper()
        user_server = user_server.upper()
        if top_block is None:
            # If we can not get top block, confirm after 20mn. This is second not number of block
            nos_block = 20*60
        else:
            nos_block = top_block - confirmed_depth
        confirmed_inserted = 30 # 30s for nano
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # moving tip + / -
                    start = time.time()
                    sql = """ SELECT `balance` AS mv_balance FROM `user_balance_mv_data` WHERE `user_id`=%s AND `token_name` = %s AND `user_server` = %s LIMIT 1 """
                    await cur.execute(sql, (userID, TOKEN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        mv_balance = result['mv_balance']
                    else:
                        mv_balance = 0
                    # pending airdrop
                    sql = """ SELECT SUM(real_amount) AS airdropping FROM `discord_airdrop_tmp` WHERE `from_userid`=%s 
                              AND `token_name` = %s AND `status`=%s """
                    await cur.execute(sql, (userID, TOKEN_NAME, "ONGOING"))
                    result = await cur.fetchone()
                    if result:
                        airdropping = result['airdropping']
                    else:
                        airdropping = 0

                    # pending mathtip
                    sql = """ SELECT SUM(real_amount) AS mathtip FROM `discord_mathtip_tmp` WHERE `from_userid`=%s 
                              AND `token_name` = %s AND `status`=%s """
                    await cur.execute(sql, (userID, TOKEN_NAME, "ONGOING"))
                    result = await cur.fetchone()
                    if result:
                        mathtip = result['mathtip']
                    else:
                        mathtip = 0

                    # pending triviatip
                    sql = """ SELECT SUM(real_amount) AS triviatip FROM `discord_triviatip_tmp` WHERE `from_userid`=%s 
                              AND `token_name` = %s AND `status`=%s """
                    await cur.execute(sql, (userID, TOKEN_NAME, "ONGOING"))
                    result = await cur.fetchone()
                    if result:
                        triviatip = result['triviatip']
                    else:
                        triviatip = 0

                    # Expense (negative)
                    sql = """ SELECT SUM(amount_sell) AS open_order FROM open_order WHERE `coin_sell`=%s AND `userid_sell`=%s 
                              AND `status`=%s
                          """
                    await cur.execute(sql, (TOKEN_NAME, userID, 'OPEN'))
                    result = await cur.fetchone()
                    if result:
                        open_order = result['open_order']
                    else:
                        open_order = 0

                    # guild_raffle_entries fee entry
                    sql = """ SELECT SUM(amount) AS raffle_fee FROM guild_raffle_entries WHERE `coin_name`=%s AND `user_id`=%s  
                              AND `user_server`=%s AND `status`=%s
                          """
                    await cur.execute(sql, (TOKEN_NAME, userID, user_server, 'REGISTERED'))
                    result = await cur.fetchone()
                    raffle_fee = 0.0
                    if result and ('raffle_fee' in result) and result['raffle_fee']:
                        raffle_fee = result['raffle_fee']

                    # Each coin
                    if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql = """ SELECT SUM(amount+withdraw_fee) AS tx_expense FROM `cn_external_tx` WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, user_server, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        if top_block is None:
                            sql = """ SELECT SUM(amount) AS incoming_tx FROM `cn_get_transfers` WHERE `payment_id`=%s AND `coin_name` = %s 
                                      AND `amount`>0 AND `time_insert`< %s """
                            await cur.execute(sql, ( address, TOKEN_NAME, int(time.time())-nos_block )) # seconds
                        else:
                            sql = """ SELECT SUM(amount) AS incoming_tx FROM `cn_get_transfers` WHERE `payment_id`=%s AND `coin_name` = %s 
                                      AND `amount`>0 AND `height`< %s """
                            await cur.execute(sql, ( address, TOKEN_NAME, nos_block ))
                        result = await cur.fetchone()
                        if result and result['incoming_tx']:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                    elif coin_family == "BTC":
                        sql = """ SELECT SUM(amount+withdraw_fee) AS tx_expense FROM `doge_external_tx` WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, user_server, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        if TOKEN_NAME not in ["PGO"]:
                            sql = """ SELECT SUM(amount) AS incoming_tx FROM `doge_get_transfers` WHERE `address`=%s AND `coin_name` = %s AND (`category` = %s or `category` = %s) AND `confirmations`>=%s AND `amount`>0 """
                            await cur.execute(sql, (address, TOKEN_NAME, 'receive', 'generate', confirmed_depth))
                            result = await cur.fetchone()
                            if result and result['incoming_tx']:
                                incoming_tx = result['incoming_tx']
                            else:
                                incoming_tx = 0
                        else:
                            sql = """ SELECT SUM(amount) AS incoming_tx FROM `doge_get_transfers` WHERE `address`=%s AND `coin_name` = %s AND `category` = %s AND `confirmations`>=%s AND `amount`>0 """
                            await cur.execute(sql, (address, TOKEN_NAME, 'receive', confirmed_depth))
                            result = await cur.fetchone()
                            if result and result['incoming_tx']:
                                incoming_tx = result['incoming_tx']
                            else:
                                incoming_tx = 0
                    elif coin_family == "NANO":
                        sql = """ SELECT SUM(amount) AS tx_expense FROM `nano_external_tx` WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, user_server, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        sql = """ SELECT SUM(amount) AS incoming_tx FROM `nano_move_deposit` WHERE `user_id`=%s AND `coin_name` = %s 
                                  AND `amount`>0 AND `time_insert`< %s AND `user_server`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, int(time.time())-confirmed_inserted, user_server ))
                        result = await cur.fetchone()
                        if result and result['incoming_tx']:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                    elif coin_family == "CHIA":
                        sql = """ SELECT SUM(amount+withdraw_fee) AS tx_expense FROM `xch_external_tx` WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, user_server, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        if top_block is None:
                            sql = """ SELECT SUM(amount) AS incoming_tx FROM `xch_get_transfers` WHERE `address`=%s AND `coin_name` = %s 
                                      AND `amount`>0 AND `time_insert`< %s """
                            await cur.execute(sql, (address, TOKEN_NAME, nos_block)) # seconds
                        else:
                            sql = """ SELECT SUM(amount) AS incoming_tx FROM `xch_get_transfers` WHERE `address`=%s AND `coin_name` = %s 
                                      AND `amount`>0 AND `height`<%s """
                            await cur.execute(sql, (address, TOKEN_NAME, nos_block))
                        result = await cur.fetchone()
                        if result and result['incoming_tx']:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                    elif coin_family == "ERC-20":
                        # When sending tx out, (negative)
                        sql = """ SELECT SUM(real_amount+real_external_fee) AS tx_expense FROM `erc20_external_tx` 
                                  WHERE `user_id`=%s AND `token_name` = %s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        # in case deposit fee -real_deposit_fee
                        sql = """ SELECT SUM(real_amount-real_deposit_fee) AS incoming_tx FROM `erc20_move_deposit` WHERE `user_id`=%s 
                                  AND `token_name` = %s AND `confirmed_depth`> %s AND `status`=%s """
                        await cur.execute(sql, (userID, TOKEN_NAME, confirmed_depth, "CONFIRMED"))
                        result = await cur.fetchone()
                        if result:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                    elif coin_family == "TRC-20":
                        # When sending tx out, (negative)
                        sql = """ SELECT SUM(real_amount+real_external_fee) AS tx_expense FROM `trc20_external_tx` 
                                  WHERE `user_id`=%s AND `token_name` = %s AND `crediting`=%s AND `sucess`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, "YES", 1 ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        # in case deposit fee -real_deposit_fee
                        sql = """ SELECT SUM(real_amount-real_deposit_fee) AS incoming_tx FROM `trc20_move_deposit` WHERE `user_id`=%s 
                                  AND `token_name` = %s AND `confirmed_depth`> %s AND `status`=%s """
                        await cur.execute(sql, (userID, TOKEN_NAME, confirmed_depth, "CONFIRMED"))
                        result = await cur.fetchone()
                        if result:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                    elif coin_family == "HNT":
                        sql = """ SELECT SUM(amount+withdraw_fee) AS tx_expense FROM `hnt_external_tx` WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, user_server, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        # split address, memo
                        address_memo = address.split()
                        if top_block is None:
                            sql = """ SELECT SUM(amount) AS incoming_tx FROM `hnt_get_transfers` WHERE `address`=%s AND `memo`=%s AND `coin_name` = %s 
                                      AND `amount`>0 AND `time_insert`< %s """
                            await cur.execute(sql, (address_memo[0], address_memo[2], TOKEN_NAME, nos_block)) # TODO: split to address, memo
                        else:
                            sql = """ SELECT SUM(amount) AS incoming_tx FROM `hnt_get_transfers` WHERE `address`=%s AND `memo`=%s AND `coin_name` = %s 
                                      AND `amount`>0 AND `height`<%s """
                            await cur.execute(sql, (address_memo[0], address_memo[2], TOKEN_NAME, nos_block)) # TODO: split to address, memo
                        result = await cur.fetchone()
                        if result and result['incoming_tx']:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                    elif coin_family == "ADA":
                        sql = """ SELECT SUM(real_amount+real_external_fee) AS tx_expense 
                                  FROM `ada_external_tx` 
                                  WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, user_server, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        if top_block is None:
                            sql = """ SELECT SUM(amount) AS incoming_tx 
                                      FROM `ada_get_transfers` WHERE `output_address`=%s AND `direction`=%s AND `coin_name`=%s 
                                      AND `amount`>0 AND `time_insert`< %s """
                            await cur.execute(sql, ( address, "incoming", TOKEN_NAME, nos_block ))
                        else:
                            sql = """ SELECT SUM(amount) AS incoming_tx 
                                      FROM `ada_get_transfers` 
                                      WHERE `output_address`=%s AND `direction`=%s AND `coin_name`=%s 
                                      AND `amount`>0 AND `inserted_at_height`<%s """
                            await cur.execute(sql, ( address, "incoming", TOKEN_NAME, nos_block ))
                        result = await cur.fetchone()
                        if result and result['incoming_tx']:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                    elif coin_family == "SOL" or coin_family == "SPL":
                        # When sending tx out, (negative)
                        sql = """ SELECT SUM(real_amount+real_external_fee) AS tx_expense FROM `sol_external_tx` 
                                  WHERE `user_id`=%s AND `coin_name` = %s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        # in case deposit fee -real_deposit_fee
                        sql = """ SELECT SUM(real_amount-real_deposit_fee) AS incoming_tx FROM `sol_move_deposit` WHERE `user_id`=%s 
                                  AND `token_name` = %s AND `confirmed_depth`> %s AND `status`=%s """
                        await cur.execute(sql, (userID, TOKEN_NAME, confirmed_depth, "CONFIRMED"))
                        result = await cur.fetchone()
                        if result:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                balance = {}
                balance['adjust'] = 0

                balance['mv_balance'] = float("%.6f" % mv_balance) if mv_balance else 0

                balance['airdropping'] = float("%.6f" % airdropping) if airdropping else 0
                balance['mathtip'] = float("%.6f" % mathtip) if mathtip else 0
                balance['triviatip'] = float("%.6f" % triviatip) if triviatip else 0

                balance['tx_expense'] = float("%.6f" % tx_expense) if tx_expense else 0
                balance['incoming_tx'] = float("%.6f" % incoming_tx) if incoming_tx else 0
                
                balance['open_order'] = float("%.6f" % open_order) if open_order else 0
                balance['raffle_fee'] = float("%.6f" % raffle_fee) if raffle_fee else 0

                balance['adjust'] = float("%.6f" % ( balance['mv_balance']+balance['incoming_tx']-balance['airdropping']-balance['mathtip']-balance['triviatip']-balance['tx_expense']-balance['open_order']-balance['raffle_fee'] ))

                # Negative check
                try:
                    if balance['adjust'] < 0:
                        msg_negative = 'Negative balance detected:\nServer:'+user_server+'\nUser: '+userID+'\nToken: '+TOKEN_NAME+'\nBalance: '+str(balance['adjust'])
                        await logchanbot(msg_negative)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                return balance
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    async def swap_coin(self, userId: str, from_coin: str, from_amount: float, from_contract: str, from_decimal: int, to_coin: str, to_amount: float, to_contract: str, to_decimal: int, user_server: str):
        # 1] move to_amount to_coin from "SWAP" to userId
        # 2] move from_amount from_coin from userId to "SWAP"
        currentTs = int(time.time())
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO user_balance_mv 
                              (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`, `real_amount`, `real_amount_usd`, `token_decimal`, `type`, `date`, `user_server`) 
                              VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(32,8)), CAST(%s AS DECIMAL(32,8)), %s, %s, %s, %s);

                              INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                              VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                              UPDATE 
                              `balance`=`balance`+VALUES(`balance`), 
                              `update_date`=VALUES(`update_date`);

                              INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                              VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                              UPDATE 
                              `balance`=`balance`+VALUES(`balance`), 
                              `update_date`=VALUES(`update_date`);


                              INSERT INTO user_balance_mv 
                              (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`, `real_amount`, `real_amount_usd`, `token_decimal`, `type`, `date`, `user_server`) 
                              VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(32,8)), CAST(%s AS DECIMAL(32,8)), %s, %s, %s, %s);

                              INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                              VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                              UPDATE 
                              `balance`=`balance`+VALUES(`balance`), 
                              `update_date`=VALUES(`update_date`);

                              INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                              VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                              UPDATE 
                              `balance`=`balance`+VALUES(`balance`), 
                              `update_date`=VALUES(`update_date`);
                              """
                    await cur.execute(sql, ( to_coin.upper(), to_contract, "SWAP", userId, "SWAP", "SWAP", to_amount, 0.0, to_decimal, "SWAP", currentTs, user_server, "SWAP", to_coin.upper(), user_server, -to_amount, currentTs, userId, to_coin.upper(), user_server, to_amount, currentTs, from_coin.upper(), from_contract, userId, "SWAP", "SWAP", "SWAP", from_amount, 0.0, from_decimal, "SWAP", currentTs, user_server, userId, from_coin.upper(), user_server, -from_amount, currentTs, "SWAP", from_coin.upper(), user_server, from_amount, currentTs ))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    def check_address_erc20(self, address: str):
        if is_hex_address(address):
            return address
        return False

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    # Notify user
    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_spendable_erc20(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            try:
                notify_list = await store.sql_get_pending_notification_users_erc20(SERVER_BOT)
                if len(notify_list) > 0:
                    for each_notify in notify_list:
                        is_notify_failed = False
                        member = self.bot.get_user(int(each_notify['user_id']))
                        if member:
                            if each_notify['txn'] in self.notified_tx: continue
                            msg = "You got a new deposit confirmed: ```" + "Amount: {} {}".format(num_format_coin(each_notify['real_amount'], each_notify['token_name'], each_notify['token_decimal'], False), each_notify['token_name']) + "```"
                            self.notified_tx.append(each_notify['txn'])
                            try:
                                await member.send(msg)
                            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                is_notify_failed = True
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            update_status = await store.sql_updating_pending_move_deposit_erc20(True, is_notify_failed, each_notify['txn'])
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_spendable_trc20(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            try:
                notify_list = await store.sql_get_pending_notification_users_trc20(SERVER_BOT)
                if notify_list and len(notify_list) > 0:
                    for each_notify in notify_list:
                        is_notify_failed = False
                        member = self.bot.get_user(int(each_notify['user_id']))
                        if member:
                            if each_notify['txn'] in self.notified_tx: continue
                            msg = "You got a new deposit confirmed: ```" + "Amount: {} {}".format(num_format_coin(each_notify['real_amount'], each_notify['token_name'], each_notify['token_decimal'], False), each_notify['token_name']) + "```"
                            self.notified_tx.append(each_notify['txn'])
                            try:
                                await member.send(msg)
                            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                is_notify_failed = True
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            update_status = await store.sql_updating_pending_move_deposit_trc20(True, is_notify_failed, each_notify['txn'])
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)

    # Notify user
    @tasks.loop(seconds=60.0)
    async def notify_new_tx_user(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            try:
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
                                                if eachTx['txid'] in self.notified_tx: continue
                                                msg = "You got a new deposit confirmed: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False), eachTx['height']) + "```"
                                                self.notified_tx.append(eachTx['txid'])
                                            else:
                                                if eachTx['txid'] in self.notified_tx: continue
                                                msg = "You got a new deposit confirmed: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False), eachTx['blockhash']) + "```"
                                                self.notified_tx.append(eachTx['txid'])
                                            await user_found.send(msg)
                                        except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
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
                                            except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
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
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def notify_new_tx_user_noconfirmation(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            try:
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

                                        if eachTx['txid'] in self.notified_pending_tx: continue
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
                                                        self.notified_pending_tx.append(eachTx['txid'])
                                                    except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
                                                        pass
                                                    # TODO:
                                                    redis_utils.redis_conn.lpush(key_tx_no_confirmed_sent, tx)
                                                else:
                                                    # try to find if it is guild
                                                    guild_found = self.bot.get_guild(int(user_tx['user_id']))
                                                    if guild_found: user_found = self.bot.get_user(guild_found.owner.id)
                                                    if guild_found and user_found:
                                                        try:
                                                            msg = None
                                                            confirmation_number_txt = "{} needs {} confirmations.".format(eachTx['coin_name'], get_confirm_depth)
                                                            if eachTx['coin_name'] != "BTC":
                                                                msg = "Your guild got a new **pending** deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}\n{}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False), eachTx['height'], confirmation_number_txt) + "```"
                                                            else:
                                                                msg = "Your guild got a new **pending** deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}\n{}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False), eachTx['blockhash'], confirmation_number_txt) + "```"
                                                            await user_found.send(msg)
                                                        except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
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
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_hnt(self):
        time_lap = 20 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM `hnt_get_transfers` WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s """
                        await cur.execute(sql, ( "NO", "NO", SERVER_BOT ))
                        result = await cur.fetchall()
                        if result and len(result) > 0:
                            for eachTx in result:
                                if eachTx['user_id']:
                                    if not eachTx['user_id'].isdigit():
                                        continue
                                    member = self.bot.get_user(int(eachTx['user_id']))
                                    if member is not None:
                                        coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['coin_name']), "decimal")
                                        msg = "You got a new deposit (it could take a few minutes to credit): ```" + "Coin: {}\nTx: {}\nAmount: {}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal, False)) + "```"
                                        try:
                                            await member.send(msg)
                                            sql = """ UPDATE `hnt_get_transfers` SET `notified_confirmation`=%s, `time_notified`=%s WHERE `txid`=%s LIMIT 1 """
                                            await cur.execute(sql, ( "YES", int(time.time()), eachTx['txid'] ))
                                            await conn.commit()
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
                                            sql = """ UPDATE `hnt_get_transfers` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `txid`=%s LIMIT 1 """
                                            await cur.execute(sql, ( "NO", "YES", eachTx['txid'] ))
                                            await conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)

    @tasks.loop(seconds=120.0)
    async def update_balance_hnt(self):
        time_lap = 20 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            timeout = 30
            COIN_NAME = "HNT"
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            try:
                # get height
                try:
                    headers = {
                        'Content-Type': 'application/json',
                    }
                    json_data = {
                        "jsonrpc": "2.0",
                        "id": "1",
                        "method": "block_height"
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(getattr(getattr(self.bot.coin_list, COIN_NAME), "wallet_address"), headers=headers, json=json_data, timeout=timeout) as response:
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                if 'result' in decoded_data:
                                    height = int(decoded_data['result'])
                                    try:
                                        redis_utils.redis_conn.set(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}', str(height))
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                async def fetch_api(url, timeout):
                    try:
                        headers = {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
                        }
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url, headers=headers, timeout=timeout) as response:
                                if response.status == 200:
                                    res_data = await response.read()
                                    res_data = res_data.decode('utf-8')
                                    decoded_data = json.loads(res_data)
                                    return decoded_data
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    return None

                async def get_tx_incoming():
                    try:
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ SELECT * FROM `hnt_get_transfers` """
                                await cur.execute(sql,)
                                result = await cur.fetchall()
                                if result: return result
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    return []
                # Get list of tx from API:
                main_address = getattr(getattr(self.bot.coin_list, COIN_NAME), "MainAddress")
                url = getattr(getattr(self.bot.coin_list, COIN_NAME), "rpchost") + "accounts/"+main_address+"/roles"
                fetch_data = await fetch_api(url, timeout)
                incoming = [] ##payments
                if fetch_data is not None and 'data' in fetch_data:
                    # Check if len data is 0
                    if len(fetch_data['data']) == 0 and 'cursor' in fetch_data:
                        url2 = getattr(getattr(self.bot.coin_list, COIN_NAME), "rpchost") + "accounts/"+main_address+"/roles/?cursor="+fetch_data['cursor']
                        # get with cursor
                        fetch_data_2 = await fetch_api(url2, timeout)
                        if fetch_data_2 is not None and 'data' in fetch_data_2:
                            if len(fetch_data_2['data']) > 0:
                                for each_item in fetch_data_2['data']:
                                    incoming.append(each_item)
                    elif len(fetch_data['data']) > 0 and 'cursor' in fetch_data:
                        for each_item in fetch_data['data']:
                            incoming.append(each_item)
                        url2 = getattr(getattr(self.bot.coin_list, COIN_NAME), "rpchost") + "accounts/"+main_address+"/roles/?cursor="+fetch_data['cursor']
                        # get with cursor
                        fetch_data_2 = await fetch_api(url2, timeout)
                        if fetch_data_2 is not None and 'data' in fetch_data_2:
                            if len(fetch_data_2['data']) > 0:
                                for each_item in fetch_data_2['data']:
                                    incoming.append(each_item)
                    elif len(fetch_data['data']) > 0:
                        for each_item in fetch_data['data']:
                            incoming.append(each_item)
                if len(incoming) > 0:
                    get_incoming_tx = await get_tx_incoming()
                    list_existing_tx = []
                    if len(get_incoming_tx) > 0:
                        list_existing_tx = [each['txid'] for each in get_incoming_tx]
                    for each_tx in incoming:
                        tx_hash = each_tx['hash']
                        if tx_hash in list_existing_tx:
                            # Go to next
                            continue
                        amount = 0.0
                        url_tx = getattr(getattr(self.bot.coin_list, COIN_NAME), "rpchost") + "transactions/" + tx_hash
                        fetch_tx = await fetch_api(url_tx, timeout)
                        if 'data' in fetch_tx:
                            height = fetch_tx['data']['height']
                            blockTime = fetch_tx['data']['time']
                            fee = fetch_tx['data']['fee'] / 10**coin_decimal
                            payer = fetch_tx['data']['payer']
                            if 'payer' in fetch_tx['data'] and fetch_tx['data'] == main_address:
                                continue
                            if 'payments' in fetch_tx['data'] and len(fetch_tx['data']['payments']) > 0:
                                for each_payment in fetch_tx['data']['payments']:
                                    if each_payment['payee'] == main_address:
                                        amount = each_payment['amount'] / 10**coin_decimal
                                        memo = base64.b64decode(each_payment['memo']).decode()
                                        try:
                                            coin_family = "HNT"
                                            user_memo = None
                                            user_id = None
                                            if len(memo) == 8:
                                                user_memo = await store.sql_get_userwallet_by_paymentid("{} MEMO: {}".format(main_address, memo), COIN_NAME, coin_family, SERVER_BOT)
                                                if user_memo is not None and user_memo['user_id']:
                                                    user_id = user_memo['user_id']
                                            await self.openConnection()
                                            async with self.pool.acquire() as conn:
                                                async with conn.cursor() as cur:
                                                    sql = """ INSERT INTO `hnt_get_transfers` (`coin_name`, `user_id`, `txid`, `height`, `timestamp`, 
                                                              `amount`, `fee`, `decimal`, `address`, `memo`, 
                                                              `payer`, `time_insert`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                    await cur.execute(sql, (COIN_NAME, user_id, tx_hash, height, blockTime, amount, fee, 
                                                                            coin_decimal, each_payment['payee'], memo, payer, int(time.time())))
                                                    await conn.commit()
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
                                            await logchanbot(traceback.format_exc())
            except asyncio.TimeoutError:
                print('TIMEOUT: COIN: {} - timeout {}'.format(COIN_NAME, timeout))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_ada(self):
        time_lap = 20 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM `ada_get_transfers` WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s """
                        await cur.execute(sql, ( "NO", "NO", SERVER_BOT ))
                        result = await cur.fetchall()
                        if result and len(result) > 0:
                            for eachTx in result:
                                if eachTx['user_id']:
                                    if not eachTx['user_id'].isdigit():
                                        continue
                                    COIN_NAME = eachTx['coin_name']
                                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                                    if eachTx['user_id'].isdigit() and eachTx['user_server'] == SERVER_BOT:
                                        member = self.bot.get_user(int(eachTx['user_id']))
                                        if member is not None:
                                            msg = "You got a new deposit (it could take a few minutes to credit): ```" + "Coin: {}\nTx: {}\nAmount: {}".format(COIN_NAME, eachTx['hash_id'], num_format_coin(eachTx['amount'], COIN_NAME, coin_decimal, False)) + "```"
                                            try:
                                                await member.send(msg)
                                                sql = """ UPDATE `ada_get_transfers` SET `notified_confirmation`=%s, `time_notified`=%s WHERE `hash_id`=%s AND `coin_name`=%s LIMIT 1 """
                                                await cur.execute(sql, ( "YES", int(time.time()), eachTx['hash_id'], COIN_NAME ))
                                                await conn.commit()
                                            except Exception as e:
                                                traceback.print_exc(file=sys.stdout)
                                                sql = """ UPDATE `ada_get_transfers` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `hash_id`=%s AND `coin_name`=%s LIMIT 1 """
                                                await cur.execute(sql, ( "NO", "YES", eachTx['hash_id'], COIN_NAME ))
                                                await conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)

    @tasks.loop(seconds=30.0)
    async def update_sol_wallets_sync(self):
        time_lap = 30 # seconds
        COIN_NAME = "SOL"
        await self.bot.wait_until_ready()

        async def fetch_getEpochInfo(url: str, timeout: 12):
            data = '{"jsonrpc":"2.0", "method":"getEpochInfo", "id":1}'
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers={'Content-Type': 'application/json'}, json=json.loads(data), timeout=timeout) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            await session.close()
                            decoded_data = json.loads(res_data)
                            if decoded_data and 'result' in decoded_data:
                                return decoded_data['result']
            except asyncio.TimeoutError:
                print('TIMEOUT: getEpochInfo {} for {}s'.format(url, timeout))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return None

        async def fetch_wallet_balance(url: str, address: str):
            # url: is endpoint
            try:
                client = Sol_AsyncClient(url)
                balance = await client.get_balance(PublicKey(address))
                if 'result' in balance:
                    await client.close()
                    return balance['result']
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return None

        async def move_wallet_balance(url: str, sender_hex_key: str, atomic_amount: int):
            # url: is endpoint transfer
            try:
                sender = Keypair.from_secret_key(bytes.fromhex(sender_hex_key))
                receiver_addr = config.sol.MainAddress
                client = Sol_AsyncClient(url)
                txn = Transaction().add(transfer(TransferParams(
                   from_pubkey=sender.public_key, to_pubkey=receiver_addr, lamports=atomic_amount)))
                sending_tx = await client.send_transaction(txn, sender)
                if 'result' in sending_tx:
                    await client.close()
                    return sending_tx['result'] # This is Tx Hash
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return None

        #while True:
        await asyncio.sleep(time_lap)
        # update Height
        try:
            getEpochInfo = await fetch_getEpochInfo(self.bot.erc_node_list['SOL'], 8)
            if getEpochInfo:
                height = getEpochInfo['absoluteSlot']
                try:
                    redis_utils.redis_conn.set(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}', str(height))
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            # If this happen. Sleep and next
            await asyncio.sleep(time_lap)
            #continue

        try:
            lap = int(time.time()) - 3600*2
            last_move = int(time.time()) - 90 # if there is last move, it has to be at least XXs
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `sol_user` WHERE (`called_Update`>%s OR `is_discord_guild`=1) AND `last_move_deposit`<%s """
                    await cur.execute(sql, ( lap, last_move ))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each_addr in result:
                            try:
                                # get deposit balance if it's less than minimum
                                get_balance = await fetch_wallet_balance(self.bot.erc_node_list['SOL'], each_addr['balance_wallet_address'])
                                coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                                real_min_deposit = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_deposit")
                                tx_fee = getattr(getattr(self.bot.coin_list, COIN_NAME), "tx_fee")
                                contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                                real_deposit_fee = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_deposit_fee")
                                if 'context' in get_balance and 'value' in get_balance: 
                                    actual_balance = float(get_balance['value']/10**coin_decimal)
                                    if actual_balance >= real_min_deposit:
                                        # Let's move
                                        remaining = int((actual_balance - tx_fee)*10**coin_decimal)
                                        moving = await move_wallet_balance(self.bot.erc_node_list['SOL'], decrypt_string(each_addr['secret_key_hex']), remaining)
                                        if moving:
                                            await self.openConnection()
                                            async with self.pool.acquire() as conn:
                                                async with conn.cursor() as cur:
                                                    sql = """ INSERT INTO `sol_move_deposit` (`token_name`, `contract`, `user_id`, `balance_wallet_address`, `to_main_address`, `real_amount`, `real_deposit_fee`, `token_decimal`, `txn`, `time_insert`, 
                                                              `user_server`) 
                                                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                                                              UPDATE `sol_user` SET `last_move_deposit`=%s WHERE `balance_wallet_address`=%s LIMIT 1; """
                                                    await cur.execute(sql, ( COIN_NAME, contract, each_addr['user_id'], each_addr['balance_wallet_address'], config.sol.MainAddress, actual_balance - tx_fee, real_deposit_fee, coin_decimal, moving, int(time.time()), SERVER_BOT, int(time.time()), each_addr['balance_wallet_address'] ))
                                                    await conn.commit()
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=30.0)
    async def unlocked_move_pending_sol(self):
        time_lap = 30 # seconds
        COIN_NAME = "SOL"
        await self.bot.wait_until_ready()

        async def fetch_getConfirmedTransaction(url: str, txn: str, timeout: 12):
            json_data = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getConfirmedTransaction",
                        "params": [
                          txn,
                          "json"
                        ]
                    }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers={'Content-Type': 'application/json'}, json=json_data, timeout=timeout) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            await session.close()
                            decoded_data = json.loads(res_data)
                            if decoded_data and 'result' in decoded_data:
                                return decoded_data['result']
            except asyncio.TimeoutError:
                print('TIMEOUT: getConfirmedTransaction {} for {}s'.format(url, timeout))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return None

        time_insert = int(time.time()) - 90
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `sol_move_deposit` WHERE `status`=%s AND `time_insert`<%s """
                    await cur.execute(sql, ( "PENDING", time_insert ))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each_mv in result:
                            fetch_tx = await fetch_getConfirmedTransaction(self.bot.erc_node_list['SOL'], each_mv['txn'], 16)
                            if fetch_tx:
                                get_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                                net_height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                                height = fetch_tx['slot']
                                confirmed_depth = net_height - height
                                status = "FAILED"
                                if fetch_tx['meta']['err'] is None and confirmed_depth > get_confirm_depth:
                                    status = "CONFIRMED"
                                elif fetch_tx['meta']['err'] is not None and confirmed_depth > get_confirm_depth:
                                    status = "FAILED"
                                else:
                                    continue
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
                                    async with conn.cursor() as cur:
                                        sql = """ UPDATE `sol_move_deposit` SET `blockNumber`=%s, `confirmed_depth`=%s, `status`=%s 
                                                  WHERE `txn`=%s LIMIT 1 """
                                        await cur.execute(sql, ( height, confirmed_depth, status, each_mv['txn'] ))
                                        await conn.commit()
                                        ## Notify
                                        if not each_mv['user_id'].isdigit():
                                            continue
                                        COIN_NAME = each_mv['token_name']
                                        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                                        if each_mv['user_id'].isdigit() and each_mv['user_server'] == SERVER_BOT:
                                            member = self.bot.get_user(int(each_mv['user_id']))
                                            if member is not None:
                                                msg = "You got a new deposit (it could take a few minutes to credit): ```" + "Coin: {}\nMoved Tx: {}\nAmount: {}".format(COIN_NAME, each_mv['txn'], num_format_coin(each_mv['real_amount'], COIN_NAME, coin_decimal, False)) + "```"
                                                try:
                                                    await member.send(msg)
                                                    sql = """ UPDATE `sol_move_deposit` SET `notified_confirmation`=%s, `time_notified`=%s WHERE `txn`=%s AND `token_name`=%s LIMIT 1 """
                                                    await cur.execute(sql, ( "YES", int(time.time()), each_mv['txn'], COIN_NAME ))
                                                    await conn.commit()
                                                except Exception as e:
                                                    traceback.print_exc(file=sys.stdout)
                                                    sql = """ UPDATE `sol_move_deposit` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `txn`=%s AND `token_name`=%s LIMIT 1 """
                                                    await cur.execute(sql, ( "NO", "YES", each_mv['txn'], COIN_NAME ))
                                                    await conn.commit()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def update_ada_wallets_sync(self):
        time_lap = 30 # seconds
        await self.bot.wait_until_ready()

        async def fetch_wallet_status(url, timeout):
            try:
                headers = {
                    'Content-Type': 'application/json'
                }
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=timeout) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            return decoded_data
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return None

        while True:
            await asyncio.sleep(time_lap)
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM `ada_wallets` """
                        await cur.execute(sql,)
                        result = await cur.fetchall()
                        if result and len(result) > 0:
                            for each_wallet in result:
                                fetch_wallet = await fetch_wallet_status(each_wallet['wallet_rpc'] + "v2/wallets/" + each_wallet['wallet_id'], 60)
                                if fetch_wallet:
                                    try:
                                        # update height
                                        try:
                                            if each_wallet['wallet_name'] == "withdraw_ada":
                                                height = int(fetch_wallet['tip']['height']['quantity'])
                                                for each_coin in self.bot.coin_name_list:
                                                    if getattr(getattr(self.bot.coin_list, each_coin), "type") == "ADA":
                                                        redis_utils.redis_conn.set(f'{config.redis.prefix+config.redis.daemon_height}{each_coin.upper()}', str(height))
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
                                        await self.openConnection()
                                        async with self.pool.acquire() as conn:
                                            async with conn.cursor() as cur:
                                                sql = """ UPDATE `ada_wallets` SET `status`=%s, `updated`=%s WHERE `wallet_id`=%s LIMIT 1 """
                                                await cur.execute(sql, ( json.dumps(fetch_wallet), int(time.time()), each_wallet['wallet_id'] ))
                                                await conn.commit()
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                # fetch address if Null
                                if each_wallet['addresses'] is None:
                                    fetch_addresses = await fetch_wallet_status(each_wallet['wallet_rpc'] + "v2/wallets/" + each_wallet['wallet_id'] + "/addresses", 60)
                                    if fetch_addresses and len(fetch_addresses) > 0:
                                        addresses = "\n".join([each['id'] for each in fetch_addresses])
                                        try:
                                            await self.openConnection()
                                            async with self.pool.acquire() as conn:
                                                async with conn.cursor() as cur:
                                                    sql = """ UPDATE `ada_wallets` SET `addresses`=%s WHERE `wallet_id`=%s LIMIT 1 """
                                                    await cur.execute(sql, ( addresses, each_wallet['wallet_id'] ))
                                                    await conn.commit()
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
                                # if synced
                                if each_wallet['syncing'] is None and each_wallet['used_address'] > 0:
                                    all_addresses = each_wallet['addresses'].split("\n")
                                    # fetch txes last 48h
                                    time_end = str(datetime.utcnow().isoformat()).split(".")[0] + "Z"
                                    time_start = str((datetime.utcnow() - timedelta(hours=24.0)).isoformat()).split(".")[0] + "Z"
                                    fetch_transactions = await fetch_wallet_status(each_wallet['wallet_rpc'] + "v2/wallets/" + each_wallet['wallet_id'] + "/transactions?start={}&end={}".format(time_start, time_end), 60)
                                    # get transaction already in DB:
                                    existing_hash_ids = []
                                    try:
                                        await self.openConnection()
                                        async with self.pool.acquire() as conn:
                                            async with conn.cursor() as cur:
                                                sql = """ SELECT DISTINCT `hash_id` FROM `ada_get_transfers` """
                                                await cur.execute( sql, )
                                                result = await cur.fetchall()
                                                if result and len(result) > 0:
                                                    existing_hash_ids = [each['hash_id'] for each in result]
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                    if fetch_transactions and len(fetch_transactions) > 0:
                                        data_rows = []
                                        for each_tx in fetch_transactions:
                                            if len(existing_hash_ids) > 0 and each_tx['id'] in existing_hash_ids: continue # skip
                                            try:
                                                if each_tx['status'] == "in_ledger" and each_tx['direction'] == "incoming" and len(each_tx['outputs']) > 0:
                                                    for each_output in each_tx['outputs']:
                                                        if each_output['address'] not in all_addresses: continue # skip this output because no address in...
                                                        COIN_NAME = "ADA"
                                                        coin_family = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                                                        user_tx = await store.sql_get_userwallet_by_paymentid(each_output['address'], COIN_NAME, coin_family, SERVER_BOT)
                                                        # ADA
                                                        data_rows.append( ( user_tx['user_id'], COIN_NAME, each_tx['id'], each_tx['inserted_at']['height']['quantity'], each_tx['direction'], json.dumps(each_tx['inputs']), json.dumps(each_tx['outputs']), each_output['address'], None, None, each_output['amount']['quantity']/10**6, 6, int(time.time()), user_tx['user_server'] ) )
                                                        if each_output['assets'] and len(each_output['assets']) > 0:
                                                            # Asset
                                                            for each_asset in each_output['assets']:
                                                                asset_name = each_asset['asset_name']
                                                                COIN_NAME = None
                                                                for each_coin in self.bot.coin_name_list:
                                                                    if asset_name and getattr(getattr(self.bot.coin_list, each_coin), "type") == "ADA" and getattr(getattr(self.bot.coin_list, each_coin), "header") == asset_name:
                                                                        COIN_NAME = each_coin
                                                                        policyID = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                                                                        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                                                                        data_rows.append( ( user_tx['user_id'], COIN_NAME, each_tx['id'], each_tx['inserted_at']['height']['quantity'], each_tx['direction'], json.dumps(each_tx['inputs']), json.dumps(each_tx['outputs']), each_output['address'], asset_name, policyID, each_asset['quantity']/10**coin_decimal, coin_decimal, int(time.time()), user_tx['user_server'] ) )
                                                                        break
                                            except Exception as e:
                                                traceback.print_exc(file=sys.stdout)
                                        if len(data_rows) > 0:
                                            try:
                                                await self.openConnection()
                                                async with self.pool.acquire() as conn:
                                                    async with conn.cursor() as cur:
                                                        sql = """ INSERT INTO `ada_get_transfers` (`user_id`, `coin_name`, `hash_id`, `inserted_at_height`, `direction`, `input_json`, `output_json`, `output_address`, `asset_name`, `policy_id`, `amount`, `coin_decimal`, `time_insert`, `user_server`) 
                                                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                        await cur.executemany( sql, data_rows )
                                                        await conn.commit()
                                            except Exception as e:
                                                traceback.print_exc(file=sys.stdout)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def update_balance_trtl_api(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
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
                            await self.openConnection()
                            async with self.pool.acquire() as conn:
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
            await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def update_balance_trtl_service(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
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
                            await self.openConnection()
                            async with self.pool.acquire() as conn:
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
            await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def update_balance_xmr(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
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
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
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
            await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def update_balance_btc(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
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
                            await asyncio.sleep(1.0)
                            continue

                        get_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                        get_min_deposit_amount = int(getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_deposit") * 10**coin_decimal)

                        payload = '"*", 100, 0'
                        if COIN_NAME in ["PGO"]:
                            payload = '"*", 200, 0'
                        get_transfers = await self.WalletAPI.call_doge('listtransactions', COIN_NAME, payload=payload)
                        if get_transfers and len(get_transfers) >= 1:
                            try:
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
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
                                                        if COIN_NAME in ["PGO"]:
                                                            # generate from mining
                                                            if tx['category'] == 'receive' and 'generated' not in tx:
                                                                sql = """ INSERT IGNORE INTO `doge_get_transfers` (`coin_name`, `txid`, `blockhash`, `address`, `blocktime`, `amount`, `fee`, `confirmations`, `category`, `time_insert`) 
                                                                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                                await cur.execute(sql, (COIN_NAME, tx['txid'], tx['blockhash'], tx['address'], tx['blocktime'], float(tx['amount']), float(tx['fee']) if 'fee' in tx else None, tx['confirmations'], tx['category'], int(time.time())))
                                                                await conn.commit()
                                                                # Notify Tx
                                                            if (tx['amount'] > 0) and tx['category'] == 'receive' and 'generated' not in tx:
                                                                sql = """ INSERT IGNORE INTO `discord_notify_new_tx` (`coin_name`, `txid`, `payment_id`, `blockhash`, `amount`, `fee`, `decimal`) 
                                                                          VALUES (%s, %s, %s, %s, %s, %s, %s) """
                                                                await cur.execute(sql, (COIN_NAME, tx['txid'], tx['address'], tx['blockhash'], float(tx['amount']), float(tx['fee']) if 'fee' in tx else None, coin_decimal))
                                                                await conn.commit()
                                                        else:
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
                                                if COIN_NAME in ["PGO"] and tx['category'] == 'receive' and 'generated' in tx and tx['amount'] > 0:
                                                    continue
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
            await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def update_balance_chia(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
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
                                    await self.openConnection()
                                    async with self.pool.acquire() as conn:
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
            await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_balance_nano(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
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
                                                    await self.openConnection()
                                                    async with self.pool.acquire() as conn:
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
            await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_balance_erc20(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            try:
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
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def update_balance_trc20(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            try:
                erc_contracts = await self.get_all_contracts("TRC-20", False)
                if len(erc_contracts) > 0:
                    for each_c in erc_contracts:
                        try:
                            type_name = each_c['type']
                            await store.trx_check_minimum_deposit(each_c['coin_name'], type_name, each_c['contract'], each_c['decimal'], each_c['min_move_deposit'], each_c['min_gas_tx'], each_c['fee_limit'], each_c['gas_ticker'], each_c['move_gas_amount'], each_c['chain_id'], each_c['real_deposit_fee'], 7200, SERVER_BOT)
                            pass
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                main_tokens = await self.get_all_contracts("TRC-20", True)
                if len(main_tokens) > 0:
                    for each_c in main_tokens:
                        try:
                            type_name = each_c['type']
                            await store.trx_check_minimum_deposit(each_c['coin_name'], type_name, None, each_c['decimal'], each_c['min_move_deposit'], each_c['min_gas_tx'], each_c['fee_limit'], each_c['gas_ticker'], each_c['move_gas_amount'], each_c['chain_id'], each_c['real_deposit_fee'], 7200, SERVER_BOT)
                            pass
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def unlocked_move_pending_erc20(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            try:
                erc_contracts = await self.get_all_contracts("ERC-20", False)
                depth = max([each['deposit_confirm_depth'] for each in erc_contracts])
                net_names = await self.get_all_net_names()
                net_names = list(net_names.keys())
                if len(net_names) > 0:
                    for each_name in net_names:
                        try:
                            await store.sql_check_pending_move_deposit_erc20(self.bot.erc_node_list[each_name], each_name, depth, 32)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def unlocked_move_pending_trc20(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            try:
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
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def update_balance_address_history_erc20(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            try:
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
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)

    async def send_external_erc20(self, url: str, network: str, user_id: str, to_address: str, amount: float, coin: str, coin_decimal: int, real_withdraw_fee: float, user_server: str, chain_id: str=None, contract: str=None):
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
                    await self.openConnection()
                    async with self.pool.acquire() as conn:
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
        TOKEN_NAME = coin.upper()
        user_server = user_server.upper()

        try:
            _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                       timeout=Timeout(timeout=10, connect=5, read=5))
            TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
            if TOKEN_NAME == "TRX":
                txb = (
                    TronClient.trx.transfer(config.trc.MainAddress, to_address, int(amount*10**6))
                    #.memo("test memo")
                    .fee_limit(int(fee_limit*10**6))
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
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
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
                        txb = await cntr.functions.transfer(to_address, int(amount*10**coin_decimal))
                        txb = txb.with_owner(config.trc.MainAddress).fee_limit(int(fee_limit*10**6))
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
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
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
                            .fee_limit(int(fee_limit*10**6))
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
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
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
            await self.openConnection()
            async with self.pool.acquire() as conn:
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
 
 
    async def generate_qr_address(
        self, 
        address: str
    ):
        User_WalletAPI = WalletAPI(self.bot)
        return await User_WalletAPI.generate_qr_address(address)

    async def sql_get_userwallet(self, userID, coin: str, netname: str, type_coin: str, user_server: str = 'DISCORD', chat_id: int = 0):
        User_WalletAPI = WalletAPI(self.bot)
        return await User_WalletAPI.sql_get_userwallet(userID, coin, netname, type_coin, user_server, chat_id)


    async def sql_register_user(self, userID, coin: str, netname: str, type_coin: str, user_server: str, chat_id: int = 0, is_discord_guild: int=0):
        User_WalletAPI = WalletAPI(self.bot)
        return await User_WalletAPI.sql_register_user(userID, coin, netname, type_coin, user_server, chat_id, is_discord_guild)


    async def get_all_net_names(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
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
            await self.openConnection()
            async with self.pool.acquire() as conn:
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


    async def async_deposit(self, ctx, token: str=None, plain: str=None):
        COIN_NAME = None
        if token is None:
            await ctx.response.send_message(f'{ctx.author.mention}, token name is missing.')
            return
        else:
            COIN_NAME = token.upper()
            # print(self.bot.coin_list)
            if not hasattr(self.bot.coin_list, COIN_NAME):
                await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
                return
            else:
                if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_deposit") == 0:
                    await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** deposit disable.')
                    return
                    
        # Do the job
        try:
            await ctx.response.send_message(f'{ctx.author.mention}, checking your {COIN_NAME} address...', ephemeral=True)
            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
            get_deposit = await self.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            if get_deposit is None:
                get_deposit = await self.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)
                
            wallet_address = get_deposit['balance_wallet_address']
            description = ""
            fee_txt = ""
            token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_note") and len(getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_note")) > 0:
                description = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_note")
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "real_deposit_fee") and getattr(getattr(self.bot.coin_list, COIN_NAME), "real_deposit_fee") > 0:
                real_min_deposit = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_deposit")
                minimum_text = ""
                if real_min_deposit and real_min_deposit > 0:
                    minimum_text = " of {} {}".format(num_format_coin(real_min_deposit, COIN_NAME, coin_decimal, False), token_display)
                fee_txt = " **{} {}** will be deducted from your deposit when it reaches minimum deposit{}.".format(num_format_coin(getattr(getattr(self.bot.coin_list, COIN_NAME), "real_deposit_fee"), COIN_NAME, coin_decimal, False), token_display, minimum_text)
            embed = disnake.Embed(title=f'Deposit for {ctx.author.name}#{ctx.author.discriminator}', description=description + fee_txt, timestamp=datetime.fromtimestamp(int(time.time())))
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            qr_address = wallet_address
            if COIN_NAME == "HNT":
                address_memo = wallet_address.split()
                qr_address = '{"type":"payment","address":"'+address_memo[0]+'","memo":"'+address_memo[2]+'"}'
            try:
                gen_qr_address = await self.generate_qr_address(qr_address)
                address_path = qr_address.replace('{', '_').replace('}', '_').replace(':', '_').replace('"', "_").replace(',', "_").replace(' ', "_")
                embed.set_thumbnail(url=config.storage.deposit_url + address_path + ".png")
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                
            plain_msg = '{}#{} Your deposit address: ```{}```'.format(ctx.author.name, ctx.author.discriminator, wallet_address)
            embed.add_field(name="Your Deposit Address", value="`{}`".format(wallet_address), inline=False)
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link") and len(getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")) > 0:
                embed.add_field(name="Other links", value="[{}]({})".format("Explorer", getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")), inline=False)
            
            if COIN_NAME == "HNT": # put memo and base64
                try:
                    address_memo = wallet_address.split()
                    embed.add_field(name="MEMO", value="```Ascii: {}\nBase64: {}```".format(address_memo[2], base64.b64encode(address_memo[2].encode('ascii')).decode('ascii')), inline=False)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            embed.set_footer(text="Use: deposit plain (for plain text)")
            try:
                if plain and plain.lower() == 'plain' or plain.lower() == 'text':
                    await ctx.edit_original_message(content=plain_msg)
                else:
                    await ctx.edit_original_message(embed=embed)
            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


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
            await ctx.response.send_message(f'{ctx.author.mention}, token name is missing.')
            return
        else:
            COIN_NAME = token.upper()
            if not hasattr(self.bot.coin_list, COIN_NAME):
                await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
                return
            else:
                if getattr(getattr(self.bot.coin_list, COIN_NAME), "is_maintenance") == 1:
                    await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** is currently under maintenance.')
                    return
        # Do the job
        try:
            await ctx.response.send_message(f'{ctx.author.mention}, checking your {COIN_NAME} balance...', ephemeral=True)
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
            embed = disnake.Embed(title=f'Balance for {ctx.author.name}#{ctx.author.discriminator}', timestamp=datetime.fromtimestamp(int(time.time())))
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            try:
                # height can be None
                userdata_balance = await self.user_balance(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
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

            await ctx.edit_original_message(embed=embed)
            # Add update for future call
            try:
                if type_coin == "ERC-20":
                    update_call = await store.sql_update_erc20_user_update_call(str(ctx.author.id))
                elif type_coin == "TRC-10" or type_coin == "TRC-20":
                    update_call = await store.sql_update_trc20_user_update_call(str(ctx.author.id))
                elif type_coin == "SOL" or type_coin == "SPL":
                    update_call = await store.sql_update_sol_user_update_call(str(ctx.author.id))
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
            await ctx.response.send_message(msg)
            return
        else:
            total_all_balance_usd = 0.0
            all_pages = []
            all_names = [each['coin_name'] for each in mytokens]
            total_coins = len(mytokens)
            page = disnake.Embed(title='[ YOUR BALANCE LIST ]',
                                  description="Thank you for using TipBot!",
                                  color=disnake.Color.blue(),
                                  timestamp=datetime.fromtimestamp(int(time.time())), )
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
            await ctx.response.send_message(f"{ctx.author.mention} balance loading...", ephemeral=True)
            for each_token in mytokens:
                try:
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
                            # Add update for future call
                            try:
                                if type_coin == "ERC-20":
                                    update_call = await store.sql_update_erc20_user_update_call(str(ctx.author.id))
                                elif type_coin == "TRC-10" or type_coin == "TRC-20":
                                    update_call = await store.sql_update_trc20_user_update_call(str(ctx.author.id))
                                elif type_coin == "SOL" or type_coin == "SPL":
                                    update_call = await store.sql_update_sol_user_update_call(str(ctx.author.id))
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                        else:
                            height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    if num_coins == 0 or num_coins % per_page == 0:
                        page = disnake.Embed(title='[ YOUR BALANCE LIST ]',
                                             description="Thank you for using TipBot!",
                                             color=disnake.Color.blue(),
                                             timestamp=datetime.fromtimestamp(int(time.time())), )
                        page.set_thumbnail(url=ctx.author.display_avatar)
                        page.set_footer(text="Use the reactions to flip pages.")
                    # height can be None
                    userdata_balance = await self.user_balance(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
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
                                                 timestamp=datetime.fromtimestamp(int(time.time())), )
                            page.set_thumbnail(url=ctx.author.display_avatar)
                            page.set_footer(text="Use the reactions to flip pages.")
                        else:
                            all_pages.append(page)
                            break
                    elif num_coins == total_coins:
                        all_pages.append(page)
                        break
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            # remaining
            if (total_coins - len(zero_tokens)) % per_page > 0:
                all_pages.append(page)
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
                                  timestamp=datetime.fromtimestamp(int(time.time())), )
            # Remove zero from all_names
            if has_none_balance == True:
                msg = f'{ctx.author.mention}, you do not have any balance.'
                await ctx.edit_original_message(content=msg)
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
                try:
                    view=MenuPage(ctx, all_pages, timeout=30)
                    view.message = await ctx.edit_original_message(content=None, embed=all_pages[0], view=view)
                except Exception as e:
                    msg = f'{ctx.author.mention}, internal error when checking /balances. Try again later. If problem still persists, contact TipBot dev.'
                    await ctx.edit_original_message(content=msg)
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(f"[ERROR] /balances with {ctx.author.name}#{ctx.author.discriminator}")


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
        if token.upper() == "ALL":
            await self.async_balances(ctx, None)
        else:
            await self.async_balance(ctx, token)


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
        withdraw_tx_ephemeral = False

        COIN_NAME = token.upper()
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            await ctx.response.send_message(msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "is_maintenance") == 1:
                msg = f'{ctx.author.mention}, **{COIN_NAME}** is currently under maintenance.'
                await ctx.response.send_message(msg)
                return
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_withdraw") != 1:
                msg = f'{ctx.author.mention}, **{COIN_NAME}** withdraw is currently disable.'
                await ctx.response.send_message(msg)
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
                msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
                await ctx.response.send_message(msg)
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
                msg = f'{ctx.author.mention}, **{COIN_NAME}** cannot pull information from network. Try again later.'
                await ctx.response.send_message(msg)
                return
            else:
                try:
                    await ctx.response.send_message(f"{EMOJI_HOURGLASS_NOT_DONE}, checking withdraw for {ctx.author.mention}..", ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    return

                # check if amount is all
                all_amount = False
                if not amount.isdigit() and amount.upper() == "ALL":
                    all_amount = True
                    userdata_balance = await self.user_balance(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                    amount = float(userdata_balance['adjust']) - NetFee
                # If $ is in amount, let's convert to coin/token
                elif "$" in amount[-1] or "$" in amount[0]: # last is $
                    # Check if conversion is allowed for this coin.
                    amount = amount.replace(",", "").replace("$", "")
                    if usd_equivalent_enable == 0:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{COIN_NAME}`."
                        await ctx.edit_original_message(content=msg)
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
                            await ctx.edit_original_message(content=msg)
                            return
                else:
                    amount = amount.replace(",", "")
                    amount = text_to_num(amount)
                    if amount is None:
                        await ctx.edit_original_message(content=f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.')
                        return

                if getattr(getattr(self.bot.coin_list, COIN_NAME), "integer_amount_only") == 1:
                    amount = int(amount)

                # end of check if amount is all
                amount = float(amount)
                userdata_balance = await self.user_balance(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                actual_balance = float(userdata_balance['adjust'])

                # If balance 0, no need to check anything
                if actual_balance <= 0:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please check your **{token_display}** balance.'
                    await ctx.edit_original_message(content=msg)
                    return
                if amount > actual_balance:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to send out {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}.'
                    await ctx.edit_original_message(content=msg)
                    return

                if amount + NetFee > actual_balance:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to send out {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}. You need to leave at least network fee: {num_format_coin(NetFee, COIN_NAME, coin_decimal, False)} {token_display}.'
                    await ctx.edit_original_message(content=msg)
                    return
                elif amount < MinTx or amount > MaxTx:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, transaction cannot be smaller than {num_format_coin(MinTx, COIN_NAME, coin_decimal, False)} {token_display} or bigger than {num_format_coin(MaxTx, COIN_NAME, coin_decimal, False)} {token_display}.'
                    await ctx.edit_original_message(content=msg)
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
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid address:\n`{address}`'
                        await ctx.edit_original_message(content=msg)
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
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return

                    if SendTx:
                        fee_txt = "\nWithdrew fee/node: `{} {}`.".format(num_format_coin(NetFee, COIN_NAME, coin_decimal, False), COIN_NAME)
                        try:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            return
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        try:
                            await logchanbot(f'[{SERVER_BOT}] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} sucessfully withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}')
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
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.ctx.edit_original_message(content=msg)
                        return

                    if SendTx:
                        fee_txt = "\nWithdrew fee/node: `{} {}`.".format(num_format_coin(NetFee, COIN_NAME, coin_decimal, False), COIN_NAME)
                        try:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            return
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        try:
                            await logchanbot(f'[{SERVER_BOT}] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} sucessfully withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}')
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                elif type_coin == "NANO":
                    valid_address = await self.WalletAPI.nano_validate_address(COIN_NAME, address)
                    if not valid_address == True:
                        msg = f"{EMOJI_RED_NO} Address: `{address}` is invalid."
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        if ctx.author.id not in self.bot.TX_IN_PROCESS:
                            self.bot.TX_IN_PROCESS.append(ctx.author.id)
                            try:
                                main_address = getattr(getattr(self.bot.coin_list, COIN_NAME), "MainAddress")
                                SendTx = await self.WalletAPI.send_external_nano(main_address, str(ctx.author.id), amount, address, COIN_NAME, coin_decimal)
                                if SendTx:
                                    fee_txt = "\nWithdrew fee/node: `0.00 {}`.".format(COIN_NAME)
                                    SendTx_hash = SendTx['block']
                                    msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx_hash}`{fee_txt}'
                                    await ctx.edit_original_message(content=msg)
                                    await logchanbot(f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                else:
                                    await logchanbot(f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                            except Exception as e:
                                await logchanbot(traceback.format_exc())
                            self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                        else:
                            # reject and tell to wait
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                            await ctx.edit_original_message(content=msg)
                            return
                elif type_coin == "CHIA":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        SendTx = await self.WalletAPI.send_external_xch(str(ctx.author.id), amount, address, COIN_NAME, coin_decimal, tx_fee, NetFee, SERVER_BOT)
                        if SendTx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(num_format_coin(NetFee, COIN_NAME, coin_decimal, False), COIN_NAME)
                            await logchanbot(f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                        else:
                            await logchanbot(f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
                elif type_coin == "HNT":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        wallet_host = getattr(getattr(self.bot.coin_list, COIN_NAME), "wallet_address")
                        main_address = getattr(getattr(self.bot.coin_list, COIN_NAME), "MainAddress")
                        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                        password = decrypt_string(getattr(getattr(self.bot.coin_list, COIN_NAME), "walletkey"))
                        SendTx = await self.WalletAPI.send_external_hnt(str(ctx.author.id), wallet_host, password, main_address, address, amount, coin_decimal, SERVER_BOT, COIN_NAME, NetFee, 32)
                        if SendTx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(num_format_coin(NetFee, COIN_NAME, coin_decimal, False), COIN_NAME)
                            await logchanbot(f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                        else:
                            await logchanbot(f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
                elif type_coin == "ADA":
                    if not address.startswith("addr1"):
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid address. It should start with `addr1`.'
                        await ctx.edit_original_message(content=msg)
                        return
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        if COIN_NAME == "ADA":
                            self.bot.TX_IN_PROCESS.append(ctx.author.id)
                            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                            fee_limit = getattr(getattr(self.bot.coin_list, COIN_NAME), "fee_limit")
                            # Use fee limit as NetFee
                            SendTx = await self.WalletAPI.send_external_ada(str(ctx.author.id), amount, coin_decimal, SERVER_BOT, COIN_NAME, fee_limit, address, 60)
                            if "status" in SendTx and SendTx['status'] == "pending":
                                tx_hash = SendTx['id']
                                fee = SendTx['fee']['quantity']/10**coin_decimal + fee_limit
                                fee_txt = "\nWithdrew fee/node: `{} {}`.".format(num_format_coin(fee, COIN_NAME, coin_decimal, False), COIN_NAME)
                                await logchanbot(f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{tx_hash}`{fee_txt}'
                                await ctx.edit_original_message(content=msg)
                            elif "code" in SendTx and "message" in SendTx:
                                code = SendTx['code']
                                message = SendTx['message']
                                await logchanbot(f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.```code: {code}\nmessage: {message}```')
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please try again later!'
                                await ctx.edit_original_message(content=msg)
                            else:
                                await logchanbot(f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please try again later!'
                                await ctx.edit_original_message(content=msg)
                            self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                            return
                        else:
                            ## 
                            # Check user's ADA balance.
                            GAS_COIN = None
                            fee_limit = None
                            try:
                                if getattr(getattr(self.bot.coin_list, COIN_NAME), "withdraw_use_gas_ticker") == 1:
                                    # add main token balance to check if enough to withdraw
                                    GAS_COIN = getattr(getattr(self.bot.coin_list, COIN_NAME), "gas_ticker")
                                    fee_limit = getattr(getattr(self.bot.coin_list, COIN_NAME), "fee_limit")
                                    if GAS_COIN:
                                        userdata_balance = await self.user_balance(str(ctx.author.id), GAS_COIN, wallet_address, type_coin, height, getattr(getattr(self.bot.coin_list, GAS_COIN), "deposit_confirm_depth"), SERVER_BOT)
                                        actual_balance = userdata_balance['adjust']
                                        if actual_balance < fee_limit: # use fee_limit to limit ADA
                                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you do not have sufficient {GAS_COIN} to withdraw {COIN_NAME}. You need to have at least a reserved `{fee_limit} {GAS_COIN}`.'
                                            await ctx.edit_original_message(content=msg)
                                            await logchanbot(f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} want to withdraw asset {COIN_NAME} but having only {actual_balance} {GAS_COIN}.')
                                            return
                                    else:
                                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid main token, please report!'
                                        await ctx.edit_original_message(content=msg)
                                        await logchanbot(f'[BUG] {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} invalid main token for {COIN_NAME}.')
                                        return
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, cannot check balance, please try again later!'
                                await ctx.edit_original_message(content=msg)
                                await logchanbot(f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to check balance {ADA_COIN} for asset transfer...')
                                return

                            self.bot.TX_IN_PROCESS.append(ctx.author.id)
                            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                            asset_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "header")
                            policy_id = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                            SendTx = await self.WalletAPI.send_external_ada_asset(str(ctx.author.id), amount, coin_decimal, SERVER_BOT, COIN_NAME, NetFee, address, asset_name, policy_id, 60)
                            if "status" in SendTx and SendTx['status'] == "pending":
                                tx_hash = SendTx['id']
                                gas_coin_msg = ""
                                if GAS_COIN is not None:
                                    gas_coin_msg = " and fee `{} {}` you shall receive additional `{} {}`.".format(num_format_coin(SendTx['network_fee']+fee_limit/20, GAS_COIN, 6, False), GAS_COIN, num_format_coin(SendTx['ada_received'], GAS_COIN, 6, False), GAS_COIN)
                                fee_txt = "\nWithdrew fee/node: `{} {}`{}.".format(num_format_coin(NetFee, COIN_NAME, coin_decimal, False), COIN_NAME, gas_coin_msg)
                                await logchanbot(f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{tx_hash}`{fee_txt}'
                                await ctx.edit_original_message(content=msg)
                            elif "code" in SendTx and "message" in SendTx:
                                code = SendTx['code']
                                message = SendTx['message']
                                await logchanbot(f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.```code: {code}\nmessage: {message}```')
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please try again later!'
                                await ctx.edit_original_message(content=msg)
                            else:
                                await logchanbot(f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please try again later!'
                                await ctx.edit_original_message(content=msg)
                            self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                            return
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
                elif type_coin == "SOL" or type_coin == "SPL":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        tx_fee = getattr(getattr(self.bot.coin_list, COIN_NAME), "tx_fee")
                        SendTx = await self.WalletAPI.send_external_sol(self.bot.erc_node_list['SOL'], str(ctx.author.id), amount, address, COIN_NAME, coin_decimal, tx_fee, NetFee, SERVER_BOT)
                        if SendTx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(num_format_coin(NetFee, COIN_NAME, coin_decimal, False), COIN_NAME)
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        else:
                            await logchanbot(f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
                elif type_coin == "BTC":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        SendTx = await self.WalletAPI.send_external_doge(str(ctx.author.id), amount, address, COIN_NAME, 0, NetFee, SERVER_BOT) # tx_fee=0
                        if SendTx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(num_format_coin(NetFee, COIN_NAME, coin_decimal, False), COIN_NAME)
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        else:
                            await logchanbot(f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
                elif type_coin == "XMR" or type_coin == "TRTL-API" or type_coin == "TRTL-SERVICE" or type_coin == "BCN":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        main_address = getattr(getattr(self.bot.coin_list, COIN_NAME), "MainAddress")
                        mixin = getattr(getattr(self.bot.coin_list, COIN_NAME), "mixin")
                        wallet_address = getattr(getattr(self.bot.coin_list, COIN_NAME), "wallet_address")
                        header = getattr(getattr(self.bot.coin_list, COIN_NAME), "header")
                        is_fee_per_byte = getattr(getattr(self.bot.coin_list, COIN_NAME), "is_fee_per_byte")
                        SendTx = await self.WalletAPI.send_external_xmr(type_coin, main_address, str(ctx.author.id), amount, address, COIN_NAME, coin_decimal, tx_fee, NetFee, is_fee_per_byte, mixin, SERVER_BOT, wallet_address, header, None) # paymentId: None (end)
                        if SendTx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(num_format_coin(NetFee, COIN_NAME, coin_decimal, False), COIN_NAME)
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully executed withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        else:
                            await logchanbot(f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to execute to withdraw {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


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

    @commands.slash_command(
        usage='transfer', 
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option('address', 'address', OptionType.string, required=True)
        ],
        description="withdraw to your external address."
    )
    async def transfer(
        self, 
        ctx,
        amount: str,
        token: str,
        address: str
    ):
        await self.async_withdraw(ctx, amount, token, address)

    @commands.slash_command(
        usage='send', 
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option('address', 'address', OptionType.string, required=True)
        ],
        description="withdraw to your external address."
    )
    async def send(
        self, 
        ctx,
        amount: str,
        token: str,
        address: str
    ):
        await self.async_withdraw(ctx, amount, token, address)
    # End of Withdraw


    # Faucet
    async def async_claim(self, ctx: str, token: str=None):
        faucet = Faucet(self.bot)
        get_user_coin = await faucet.get_user_faucet_coin(str(ctx.author.id), SERVER_BOT)
        list_coins = await faucet.get_faucet_coin_list()
        list_coin_names = list(set([each['coin_name'] for each in list_coins]))
        title_text = " [You haven't set any preferred reward!]"
        if get_user_coin is None:
            title_text = " [You haven't set any preferred reward!]"
        elif get_user_coin and get_user_coin['coin_name']:
            title_text = " [Preferred {}]".format(get_user_coin['coin_name'])
        list_coin_sets = {}
        for each in list_coins:
            if each['reward_for'] not in list_coin_sets:
                list_coin_sets[each['reward_for']] = []
                list_coin_sets[each['reward_for']].append({each['coin_name']: each['reward_amount']})
            else:
                list_coin_sets[each['reward_for']].append({each['coin_name']: each['reward_amount']})
        list_coins_str = ", ".join(list_coin_names)
        if token is None:
            embed = disnake.Embed(title=f'Faucet Claim{title_text}', description=f"```1] Set your reward coin claim with any of this {list_coins_str} with command /claim token_name\n\n2] Vote for TipBot in below links.\n\n```", timestamp=datetime.fromtimestamp(int(time.time())))
            
            for key in ["topgg", "discordbotlist"]:
                reward_list = []
                for each in list_coin_sets[key]:
                    for k, v in each.items():
                        reward_list.append("{}{}".format(v, k))
                reward_list_str = ", ".join(reward_list)
                embed.add_field(name="{}'s reward".format(key), value="Vote at: [{}]({})```{}```".format(key, getattr(config.bot_vote_link, key), reward_list_str), inline=False)
            embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
            try:
                
                if get_user_coin is not None:
                    embed.set_footer(text="Requested by: {}#{} | preferred: {}".format(ctx.author.name, ctx.author.discriminator, get_user_coin['coin_name']))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(embed=embed, view=RowButton_row_close_any_message())
            return
        else:
            COIN_NAME = token.upper()
            if COIN_NAME not in list_coin_names:
                msg = f'{ctx.author.mention}, `{COIN_NAME}` is invalid or does not existed in faucet list!'
                await ctx.response.send_message(msg)
                return
            else:
                # Update user setting faucet
                update = await faucet.update_faucet_user(str(ctx.author.id), COIN_NAME, SERVER_BOT)
                if update:
                    msg = f'{ctx.author.mention}, you updated your preferred claimed reward to `{COIN_NAME}`. This preference applies only for TipBot\'s voting reward.'
                    await ctx.response.send_message(msg)
                else:
                    msg = f'{ctx.author.mention}, internal error!'
                    await ctx.response.send_message(msg)
                return


    @commands.slash_command(
        usage='claim', 
        options=[
            Option('token', 'token', OptionType.string, required=False)
        ],
        description="Faucet claim."
    )
    async def claim(
        self, 
        ctx,
        token: str=None
    ):
        await self.async_claim(ctx, token)


    async def bot_faucet(
        self,
        ctx,
        faucet_coins
    ):
        game_coins = await store.sql_list_game_coins()
        get_game_stat = await store.sql_game_stat(game_coins)
        table_data = [
            ['TICKER', 'Available', 'Claimed / Game']
        ]
        for COIN_NAME in [coinItem.upper() for coinItem in faucet_coins]:
            sum_sub = 0
            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")

            get_deposit = await self.sql_get_userwallet(str(self.bot.user.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await self.sql_register_user(str(self.bot.user.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

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
 
            userdata_balance = await self.user_balance(str(self.bot.user.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
            actual_balance = float(userdata_balance['adjust'])
            sum_sub = float(get_game_stat[COIN_NAME])
 
            balance_actual = num_format_coin(actual_balance, COIN_NAME, coin_decimal, False)
            get_claimed_count = await store.sql_faucet_sum_count_claimed(COIN_NAME)
            sub_claim = num_format_coin(float(get_claimed_count['claimed']) + sum_sub, COIN_NAME, coin_decimal, False) if get_claimed_count['count'] > 0 else f"0.00{COIN_NAME}"
            if actual_balance != 0:
                table_data.append([COIN_NAME, balance_actual, sub_claim])
            else:
                table_data.append([COIN_NAME, '0', sub_claim])
        table = AsciiTable(table_data)
        table.padding_left = 0
        table.padding_right = 0
        return table.table


    async def take_action(
        self,
        ctx,
        info: str=None
    ):
        await self.bot_log()
        faucet_simu = False
        # bot check in the first place
        if ctx.author.bot == True:
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} (Bot) using **take** {ctx.guild.name} / {ctx.guild.id}')
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, Bot is not allowed using this."
            await ctx.response.send_message(msg)
            return

        if ctx.author.id in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
            await ctx.response.send_message(msg)
            return

        try:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing /take ...'
            await ctx.response.send_message(msg)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(f"{EMOJI_INFORMATION} {ctx.author.mention}, failed to message /take ...", ephemeral=True)
            return

        COIN_NAME = random.choice(self.bot.faucet_coins)
        if info and info.upper() != "INFO":
            COIN_NAME = info.upper()
            if not hasattr(self.bot.coin_list, COIN_NAME):
                msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
                await ctx.edit_original_message(content=msg)
                return
            elif COIN_NAME  not in self.bot.faucet_coins:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, {COIN_NAME} not available for faucet."
                await ctx.edit_original_message(content=msg)
                return

        total_claimed = '{:,.0f}'.format(await store.sql_faucet_count_all())
        if info and info.upper() == "INFO":
            remaining = await self.bot_faucet(ctx, self.bot.faucet_coins) or ''
            msg = f'{ctx.author.mention} Faucet balance:\n```{remaining}```Total user claims: **{total_claimed}** times. Tip me if you want to feed these faucets. Use /claim to vote TipBot and get reward.'
            await ctx.edit_original_message(content=msg)
            return

        claim_interval = config.faucet.interval
        half_claim_interval = int(config.faucet.interval / 2)

        serverinfo = None
        extra_take_text = ""
        try: 
            # check if bot channel is set:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo and serverinfo['botchan'] and ctx.channel.id != int(serverinfo['botchan']):
                try:
                    botChan = self.bot.get_channel(int(serverinfo['botchan']))
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, {botChan.mention} is the bot channel!!!'
                    await ctx.edit_original_message(content=msg)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                # add penalty:
                try:
                    faucet_penalty = await store.sql_faucet_penalty_checkuser(str(ctx.author.id), True, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                return
            if serverinfo and serverinfo['enable_faucet'] == "NO":
                if self.enable_logchan:
                    await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **take** in {ctx.guild.name} / {ctx.guild.id} which is disable.')
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, **Faucet** in this guild is disable."
                await ctx.edit_original_message(content=msg)
                return
            elif serverinfo and serverinfo['enable_faucet'] == "YES" and serverinfo['faucet_channel'] is not None and serverinfo['faucet_coin'] is not None:
                extra_take_text = " Additional reward:\n\n1) you can also do /faucet in <#{}> which funded by the guild.".format(serverinfo['faucet_channel'])
                if serverinfo['vote_reward_amount'] and serverinfo['vote_reward_channel']:
                    extra_take_text += "\n2) [Vote {} at top.gg](https://top.gg/servers/{}/vote) for {} {} each time.".format(ctx.guild.name, ctx.guild.id, serverinfo['vote_reward_amount'], serverinfo['vote_reward_coin'])
                
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # end of bot channel check

        # check user claim:
        try:
            if info is None:
                check_claimed = await store.sql_faucet_checkuser(str(ctx.author.id), SERVER_BOT)
                if check_claimed is not None:
                    if int(time.time()) - check_claimed['claimed_at'] <= claim_interval*3600:
                        time_waiting = seconds_str(claim_interval*3600 - int(time.time()) + check_claimed['claimed_at'])
                        user_claims = await store.sql_faucet_count_user(str(ctx.author.id))
                        number_user_claimed = '{:,.0f}'.format(user_claims)
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention} You just claimed within last {claim_interval}h. Waiting time {time_waiting} for next **take**. Total user claims: **{total_claimed}** times. You have claimed: **{number_user_claimed}** time(s). Tip me if you want to feed these faucets. Use /claim to vote TipBot and get reward.{extra_take_text}'
                        await ctx.edit_original_message(content=msg)
                        return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        # offline can not take
        if ctx.author.status == disnake.Status.offline:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention} Offline status cannot claim faucet."
            await ctx.edit_original_message(content=msg)
            return

        # check if account locked
        account_lock = await alert_if_userlock(ctx, 'take')
        if account_lock:
            msg = f"{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}"
            await ctx.edit_original_message(content=msg)
            return
        # end of check if account locked

        # check if user create account less than 3 days
        try:
            account_created = ctx.author.created_at
            if (datetime.utcnow().astimezone() - account_created).total_seconds() <= config.faucet.account_age_to_claim:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using /take. Alternatively, vote for TipBot to get reward `/claim`.{extra_take_text}"
                await ctx.edit_original_message(content=msg)
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        try:
            # check penalty:
            try:
                faucet_penalty = await store.sql_faucet_penalty_checkuser(str(ctx.author.id), False, SERVER_BOT)
                if faucet_penalty and not info:
                    if half_claim_interval*3600 - int(time.time()) + int(faucet_penalty['penalty_at']) > 0:
                        time_waiting = seconds_str(half_claim_interval*3600 - int(time.time()) + int(faucet_penalty['penalty_at']))
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention} You claimed in a wrong channel within last {str(half_claim_interval)}h. Waiting time {time_waiting} for next **take** and be sure to be the right channel set by the guild. Use /claim to vote TipBot and get reward.{extra_take_text}'
                        await ctx.edit_original_message(content=msg)
                        return
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            return

        net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
        contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")

        get_deposit = await self.sql_get_userwallet(str(self.bot.user.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await self.sql_register_user(str(self.bot.user.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

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

        userdata_balance = await self.user_balance(str(self.bot.user.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])

        amount = random.uniform(getattr(getattr(self.bot.coin_list, COIN_NAME), "faucet_min"), getattr(getattr(self.bot.coin_list, COIN_NAME), "faucet_max"))
        trunc_num = 4
        if coin_decimal >= 8:
            trunc_num = 8
        elif coin_decimal >= 4:
            trunc_num = 4
        elif coin_decimal >= 2:
            trunc_num = 2
        else:
            trunc_num = 6
        amount = truncate(float(amount), trunc_num)
        if amount == 0:
            amount_msg_zero = 'Get 0 random amount requested faucet by: {}#{}'.format(ctx.author.name, ctx.author.discriminator)
            await logchanbot(amount_msg_zero)
            return

        if amount > actual_balance and not info:
            msg = f'{ctx.author.mention} Please try again later. Bot runs out of **{COIN_NAME}**'
            await ctx.edit_original_message(content=msg)
            return

        tip = None
        if ctx.author.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.author.id)
        else:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return
        try:
            if not info:
                amount_in_usd = 0.0
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
                        amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                tip = await store.sql_user_balance_mv_single(str(self.bot.user.id), str(ctx.author.id), str(ctx.guild.id), str(ctx.channel.id), amount, COIN_NAME, "FAUCET", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                try:
                    faucet_add = await store.sql_faucet_add(str(ctx.author.id), str(ctx.guild.id), COIN_NAME, amount, coin_decimal, SERVER_BOT)
                    msg = f'{EMOJI_MONEYFACE} {ctx.author.mention}, you got a random faucet {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}. Use /claim to vote TipBot and get reward.{extra_take_text}'
                    await ctx.edit_original_message(content=msg)
                    await logchanbot(f'[Discord] User {ctx.author.name}#{ctx.author.discriminator} claimed faucet {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME} in guild {ctx.guild.name}/{ctx.guild.id}')
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            else:
                try:
                    msg = f"Simulated faucet {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}. This is a test only. Use without **ticker** to do real faucet claim. Use /claim to vote TipBot and get reward."
                    await ctx.edit_original_message(content=msg)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        self.bot.TX_IN_PROCESS.remove(ctx.author.id)


    @commands.guild_only()
    @commands.slash_command(usage="take <info>",
                            options=[
                                Option('info', 'info', OptionType.string, required=False)
                            ],
                            description="Claim a random coin faucet.")
    async def take(
        self, 
        ctx,
        info: str=None
    ):
        await self.take_action(ctx, info)
    # End of Faucet

    # Donate
    @commands.slash_command(
        usage='donate', 
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True)
        ],
        description="Donate to TipBot's dev team"
    )
    async def donate(
        self, 
        ctx,
        amount: str,
        token: str
        
    ):
        COIN_NAME = token.upper()
        # Token name check
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            await ctx.response.send_message(msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_tip") != 1:
                msg = f'{ctx.author.mention}, **{COIN_NAME}** tipping is disable.'
                await ctx.response.send_message(msg)
                return
        # End token name check
        net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
        contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
        token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")

        MinTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
        MaxTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")

        try:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing donation check...'
            await ctx.response.send_message(msg)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(f"{EMOJI_INFORMATION} {ctx.author.mention}, failed to send a donation message...", ephemeral=True)
            return

        User_WalletAPI = WalletAPI(self.bot)

        get_deposit = await User_WalletAPI.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await User_WalletAPI.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']

        # Check if tx in progress
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return

        height = None
        try:
            if type_coin in ["ERC-20", "TRC-20"]:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
            else:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        # check if amount is all
        all_amount = False
        if not amount.isdigit() and amount.upper() == "ALL":
            all_amount = True
            userdata_balance = await self.user_balance(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
            amount = float(userdata_balance['adjust'])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]: # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            if usd_equivalent_enable == 0:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{COIN_NAME}`."
                await ctx.edit_original_message(content=msg)
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
                    await ctx.edit_original_message(content=msg)
                    return
        else:
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.'
                await ctx.edit_original_message(content=msg)
                return
        # end of check if amount is all
        userdata_balance = await self.user_balance(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])
        donate_factor = 100
        if amount <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
            await ctx.edit_original_message(content=msg)
            return
        elif amount > MaxTip*donate_factor or amount < MinTip/donate_factor:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, transactions (donate) cannot be bigger than **{num_format_coin(MaxTip*donate_factor, COIN_NAME, coin_decimal, False)} {token_display}** or smaller than **{num_format_coin(MinTip/donate_factor, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to donate **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return

        # check queue
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention} {EMOJI_HOURGLASS_NOT_DONE} You have another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return

        equivalent_usd = ""
        amount_in_usd = 0.0
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
                amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                if amount_in_usd > 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
        if ctx.author.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.author.id)
            try:
                donate = await store.sql_user_balance_mv_single(str(ctx.author.id), str(self.donate_to), "DONATE", "DONATE", amount, COIN_NAME, "DONATE", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                if donate:
                    msg = f'{ctx.author.mention}, thank you for donate {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.'
                    await ctx.edit_original_message(content=msg)
                    await logchanbot(f'[DONATE] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} donated {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}{equivalent_usd}.')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
            self.bot.TX_IN_PROCESS.remove(ctx.author.id)
        else:
            msg = f'{EMOJI_ERROR} {ctx.author.mention} {EMOJI_HOURGLASS_NOT_DONE}, you have another tx in progress.'
            await ctx.edit_original_message(content=msg)
    # End of Donate

    # Swap
    @commands.slash_command(
        usage='swap', 
        options=[
            Option('from_amount', 'from_amount', OptionType.string, required=True),
            Option('from_token', 'from_token', OptionType.string, required=True),
            Option('to_token', 'to_token', OptionType.string, required=True)
        ],
        description="Swap between supported token/coin."
    )
    async def swap(
        self, 
        ctx,
        from_amount: str,
        from_token: str,
        to_token: str
        
    ):
        FROM_COIN = from_token.upper()
        TO_COIN = to_token.upper()
        PAIR_NAME = FROM_COIN + "-" + TO_COIN
        if PAIR_NAME not in self.swap_pair:
            msg = f'{EMOJI_RED_NO}, {ctx.author.mention} `{PAIR_NAME}` is not available.'
            await ctx.response.send_message(msg)
            return
        else:
            amount = from_amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.'
                await ctx.response.send_message(msg)
            else:
                if amount <= 0:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
                    await ctx.response.send_message(msg)
                    return

                try:
                    msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing swap check...'
                    await ctx.response.send_message(msg)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await ctx.response.send_message(f"{EMOJI_INFORMATION} {ctx.author.mention}, failed to swap check message...", ephemeral=True)
                    return

                amount = float(amount)
                to_amount = amount * self.swap_pair[PAIR_NAME]
                net_name = getattr(getattr(self.bot.coin_list, FROM_COIN), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, FROM_COIN), "type")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, FROM_COIN), "deposit_confirm_depth")
                coin_decimal = getattr(getattr(self.bot.coin_list, FROM_COIN), "decimal")
                MinTip = getattr(getattr(self.bot.coin_list, FROM_COIN), "real_min_tip")
                MaxTip = getattr(getattr(self.bot.coin_list, FROM_COIN), "real_max_tip")
                token_display = getattr(getattr(self.bot.coin_list, FROM_COIN), "display_name")
                contract = getattr(getattr(self.bot.coin_list, FROM_COIN), "contract")
                to_contract = getattr(getattr(self.bot.coin_list, TO_COIN), "contract")
                to_coin_decimal = getattr(getattr(self.bot.coin_list, TO_COIN), "decimal")
                User_WalletAPI = WalletAPI(self.bot)
                get_deposit = await User_WalletAPI.sql_get_userwallet(str(ctx.author.id), FROM_COIN, net_name, type_coin, SERVER_BOT, 0)
                if get_deposit is None:
                    get_deposit = await User_WalletAPI.sql_register_user(str(ctx.author.id), FROM_COIN, net_name, type_coin, SERVER_BOT, 0, 0)

                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']

                # Check if tx in progress
                if ctx.author.id in self.bot.TX_IN_PROCESS:
                    msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
                    await ctx.edit_original_message(content=msg)
                    return

                height = None
                try:
                    if type_coin in ["ERC-20", "TRC-20"]:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                    else:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{FROM_COIN}').decode())
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                userdata_balance = await self.user_balance(str(ctx.author.id), FROM_COIN, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                actual_balance = float(userdata_balance['adjust'])

                if amount > MaxTip or amount < MinTip:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, swap cannot be bigger than **{num_format_coin(MaxTip, FROM_COIN, coin_decimal, False)} {token_display}** or smaller than **{num_format_coin(MinTip, FROM_COIN, coin_decimal, False)} {token_display}**.'
                    await ctx.edit_original_message(content=msg)
                    return
                elif amount > actual_balance:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to swap **{num_format_coin(amount, FROM_COIN, coin_decimal, False)} {token_display}**.'
                    await ctx.redit_original_message(content=msg)
                    return
                if ctx.author.id not in self.bot.TX_IN_PROCESS:
                    self.bot.TX_IN_PROCESS.append(ctx.author.id)
                    try:
                        swap = await self.swap_coin(str(ctx.author.id), FROM_COIN, amount, contract, coin_decimal, TO_COIN, to_amount, to_contract, to_coin_decimal, SERVER_BOT)
                        if swap:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, swapped from `{num_format_coin(amount, FROM_COIN, coin_decimal, False)} {FROM_COIN} to {num_format_coin(to_amount, TO_COIN, to_coin_decimal, False)} {TO_COIN}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} swapped from `{num_format_coin(amount, FROM_COIN, coin_decimal, False)} {FROM_COIN} to {num_format_coin(to_amount, TO_COIN, to_coin_decimal, False)} {TO_COIN}`.')
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                    self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                else:
                    msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
                    await ctx.edit_original_message(content=msg)
                    return
    # End of Swap


def setup(bot):
    bot.add_cog(Wallet(bot))
    bot.add_cog(WalletAPI(bot))
