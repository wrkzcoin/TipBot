import traceback, sys, os
import disnake
from discord_webhook import DiscordWebhook
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.utils.markdown import text, bold, italic, code, pre, quote_html, escape_md
from aiogram.utils.markdown import markdown_decoration as markdown
from aiogram.types import ParseMode, InputMediaPhoto, InputMediaVideo, ChatActions
from aiogram.utils import exceptions, executor

from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup

import aiohttp, asyncio, json
import aiomysql
from aiomysql.cursors import DictCursor
import random
import uuid

from attrdict import AttrDict
import qrcode
import time
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
import math

from mnemonic import Mnemonic
from pytezos.crypto.key import Key as XtzKey
from pytezos import pytezos

from bip_utils import Bip39SeedGenerator, Bip44Coins, Bip44
import near_api

import xrpl
from xrpl.asyncio.account import get_latest_transaction, get_account_transactions, get_account_payment_transactions
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.asyncio.ledger import get_fee
from xrpl.models.transactions import Payment
from xrpl.asyncio.transaction import safe_sign_transaction, send_reliable_submission
from xrpl.asyncio.ledger import get_latest_validated_ledger_sequence
from xrpl.asyncio.account import get_next_valid_seq_number

# Stellar
from stellar_sdk import (
    AiohttpClient,
    Asset,
    Keypair as Stella_Keypair,
    Network,
    ServerAsync,
    TransactionBuilder,
    parse_transaction_envelope_from_xdr
)

from pywallet import wallet as ethwallet
import ssl
from eth_utils import is_hex_address  # Check hex only
from terminaltables import AsciiTable

from typing import List, Dict
from decimal import Decimal
from cachetools import TTLCache
from sqlitedict import SqliteDict

from config import load_config

from cogs.wallet import WalletAPI
import store
import cn_addressvalidation
from Bot import decrypt_string, encrypt_string, num_format_coin, text_to_num,\
    log_to_channel

# Configure logging
logging.basicConfig(level=logging.INFO)
config = load_config()
withdraw_tx = TTLCache(maxsize=2048, ttl=60.0) # key = user_id + coin => time

# Initialize bot and dispatcher
bot = Bot(token=config['telegram']['token_id'])
storage = MemoryStorage()
dp = Dispatcher(bot, storage=MemoryStorage())

QUEUE_MSG = []
SERVER_BOT = "TELEGRAM"
TX_IN_PROGRESS = []
MIN_MSG_TO_SAVE = 2

pool_netmon = None


def truncate(number, digits) -> float:
    stepper = Decimal(pow(10.0, digits))
    return math.trunc(stepper * Decimal(number)) / stepper

async def logchanbot(content: str):
    try:
        webhook = DiscordWebhook(
            url=config['discord']['webhook_default_url'],
            content=f'{disnake.utils.escape_markdown(content)}'
        )
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

class RPCException(Exception):
    def __init__(self, message):
        super(RPCException, self).__init__(message)

async def openConnection_node_monitor():
    global pool_netmon
    try:
        if pool_netmon is None:
            pool_netmon = await aiomysql.create_pool(
                host=config['mysql_node_monitor']['host'], port=3306,
                minsize=1, maxsize=2,
                user=config['mysql_node_monitor']['user'],
                password=config['mysql_node_monitor']['password'],
                db=config['mysql_node_monitor']['db'], cursorclass=DictCursor
            )
    except:
        print("ERROR: Unexpected error: Could not connect to MySql instance.")
        traceback.print_exc(file=sys.stdout)

async def handle_best_node(network: str):
    global pool_netmon
    table = ""
    if network.upper() == "TRX":
        table = "chain_trx"
    try:
        await openConnection_node_monitor()
        async with pool_netmon.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT id, url, name, duration, MAX(height) as height
                          FROM `""" + table + """`
                          GROUP BY url ORDER BY height DESC LIMIT 10 """
                await cur.execute(sql, )
                nodes = await cur.fetchall()
                if nodes and len(nodes) > 1:
                    # Check which one has low fetch time
                    url = nodes[0]['url']
                    fetch_time = nodes[0]['duration']
                    for each_node in nodes:
                        if fetch_time > each_node['duration']:
                            url = each_node['url']
                    return url
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

class WalletTG:
    # init method or constructor 
    def __init__(self):
        # DB
        self.pool = None
        self.coin_list = None
        self.coin_list_name = None

        self.token_hints = None
        self.token_hint_names = None

        self.coin_paprika_id_list = None
        self.coin_paprika_symbol_list = None

        self.cache_kv_db_test = SqliteDict(config['cache']['temp_leveldb_gen'], tablename="test", flag='r')
        self.cache_kv_db_general = SqliteDict(config['cache']['temp_leveldb_gen'], tablename="general", flag='r')
        self.cache_kv_db_block = SqliteDict(config['cache']['temp_leveldb_gen'], tablename="block", flag='r')

        self.erc_node_list = {
            "FTM": config['default_endpoints']['ftm'],
            "BSC": config['default_endpoints']['bsc'],
            "MATIC": config['default_endpoints']['matic'],
            "xDai": config['default_endpoints']['xdai'],
            "ETH": config['default_endpoints']['eth'],
            "TLOS": config['default_endpoints']['tlos'],
            "AVAX": config['default_endpoints']['avax'],
            "TRX": config['Tron_Node']['fullnode'],
            "SOL": config['default_endpoints']['sol'],
            "CELO": config['default_endpoints']['celo'],
            "ONE": config['default_endpoints']['one']
        }

    def get_cache_kv(self, table: str, key: str):
        try:
            if table.lower() == "test":
                return self.cache_kv_db_test[key.upper()]
            elif table.lower() == "general":
                return self.cache_kv_db_general[key.upper()]
            elif table.lower() == "block":
                return self.cache_kv_db_block[key.upper()]
        except KeyError:
            pass
        return None

    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(
                    host=config['mysql']['host'], port=3306, minsize=2, maxsize=4,
                    user=config['mysql']['user'], password=config['mysql']['password'],
                    db=config['mysql']['db'], cursorclass=DictCursor, autocommit=True
                )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    async def update_user_balance_call(self, user_id: str, type_coin: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if type_coin.upper() == "ERC-20":
                        sql = """ UPDATE `erc20_user` SET `called_Update`=%s WHERE `user_id`=%s """
                    elif type_coin.upper() == "TRC-10" or type_coin.upper() == "TRC-20":
                        sql = """ UPDATE `trc20_user` SET `called_Update`=%s WHERE `user_id`=%s """
                    elif type_coin.upper() == "SOL" or type_coin.upper() == "SPL":
                        sql = """ UPDATE `sol_user` SET `called_Update`=%s WHERE `user_id`=%s """
                    elif type_coin.upper() == "XTZ":
                        sql = """ UPDATE `tezos_user` SET `called_Update`=%s WHERE `user_id`=%s """
                    elif type_coin.upper() == "NEO":
                        sql = """ UPDATE `neo_user` SET `called_Update`=%s WHERE `user_id`=%s """
                    elif type_coin.upper() == "NEAR":
                        sql = """ UPDATE `near_user` SET `called_Update`=%s WHERE `user_id`=%s """
                    else:
                        return
                    await cur.execute(sql, (int(time.time()), user_id))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("utils " +str(traceback.format_exc()))
        return None

    async def insert_messages(self, msg_list):
        if len(msg_list) == 0: return
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `telegram_messages` 
                    (`message_id`, `text`, `date`, `from_username`, `from_user_id`, `chat_id`, `chat_title`, `chat_username`, `chat_type`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.executemany(sql, msg_list)
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    async def get_messages(self, chat_id: str, time_int: int, num_user: int = None):
        lapDuration = int(time.time()) - time_int
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    list_talker = []
                    if num_user is None:
                        sql = """ SELECT DISTINCT `from_username` FROM `telegram_messages` 
                                  WHERE `chat_id`=%s AND `date`>%s """
                        await cur.execute(sql, (chat_id, lapDuration))
                        result = await cur.fetchall()
                        if result:
                            for item in result:
                                if item['from_username'] not in list_talker:
                                    list_talker.append(item['from_username'])
                    else:
                        sql = """ SELECT `from_username` FROM `telegram_messages` WHERE `chat_id`=%s 
                                  GROUP BY `from_username` ORDER BY max(`date`) DESC LIMIT %s """
                        await cur.execute(sql, (chat_id, num_user))
                        result = await cur.fetchall()
                        if result:
                            for item in result:
                                if item['from_username'] not in list_talker:
                                    list_talker.append(item['from_username'])
                    return list_talker
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []

    async def sql_get_new_tx_table(
        self, notified: str = 'NO', failed_notify: str = 'NO',
        user_server: str = SERVER_BOT
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `discord_notify_new_tx` 
                    WHERE `notified`=%s AND `failed_notify`=%s AND `user_server`=%s
                    """
                    await cur.execute(sql, (notified, failed_notify, user_server))
                    result = await cur.fetchall()
                    return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []

    async def get_coin_paprika_list(self):
        if self.coin_paprika_id_list is None or self.coin_paprika_symbol_list is None:
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM `coin_paprika_list` """
                        await cur.execute(sql, ())
                        result = await cur.fetchall()
                        if result and len(result) > 0:
                            id_list = {}
                            symbol_list = {}
                            for each_item in result:
                                id_list[each_item['id']] = each_item  # key example: btc-bitcoin
                                symbol_list[each_item['symbol'].upper()] = each_item  # key example: BTC
                            self.coin_paprika_id_list = id_list
                            self.coin_paprika_symbol_list = symbol_list
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    # Call: await self.get_coin_setting()
    async def get_coin_setting(self):
        if self.coin_list is None:
            await self.get_token_hints()
            await self.get_coin_paprika_list()
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        coin_list = {}
                        coin_list_name = []
                        sql = """ SELECT * FROM `coin_settings` WHERE `enable_telegram`=1 """
                        await cur.execute(sql, )
                        result = await cur.fetchall()
                        if result and len(result) > 0:
                            for each in result:
                                coin_list[each['coin_name']] = each
                                coin_list_name.append(each['coin_name'])
                            self.coin_list = AttrDict(coin_list)
                            self.coin_list_name = coin_list_name
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    async def get_token_hints(self):
        if self.token_hints is None:
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM `coin_alias_price` """
                        await cur.execute(sql, ())
                        result = await cur.fetchall()
                        if result and len(result) > 0:
                            hints = {}
                            hint_names = {}
                            for each_item in result:
                                hints[each_item['ticker']] = each_item
                                hint_names[each_item['name'].upper()] = each_item
                            self.token_hints = hints
                            self.token_hint_names = hint_names
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    async def generate_qr_address(
            self,
            address: str
    ):
        # return path to image
        # address = wallet['balance_wallet_address']
        # return address if success, else None
        address_path = address.replace('{', '_').replace('}', '_').replace(
            ':', '_').replace('"', "_").replace(',', "_").replace(' ', "_")
        if not os.path.exists(config['storage']['path_deposit_qr_create'] + address_path + ".png"):
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
                img.save(config['storage']['path_deposit_qr_create'] + address_path + ".png")
                return address
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        else:
            return address
        return None

    # ERC-20, TRC-20, native is one
    # Gas Token like BNB, xDAI, MATIC, TRX will be a different address
    async def sql_register_user(
        self, user_id, coin: str, netname: str, type_coin: str, user_server: str,
        chat_id: int = 0, is_discord_guild: int = 0
    ):
        await self.get_coin_setting()
        try:
            coin_name = coin.upper()
            user_server = user_server.upper()
            balance_address = None
            main_address = None

            if type_coin.upper() == "ERC-20" and coin_name != netname.upper():
                user_id_erc20 = str(user_id) + "_" + type_coin.upper()
                type_coin_user = "ERC-20"
            elif type_coin.upper() == "ERC-20" and coin_name == netname.upper():
                user_id_erc20 = str(user_id) + "_" + coin_name
                type_coin_user = coin_name
            if type_coin.upper() in ["TRC-20", "TRC-10"] and coin_name != netname.upper():
                type_coin = "TRC-20"
                type_coin_user = "TRC-20"
                user_id_erc20 = str(user_id) + "_" + type_coin.upper()
            elif type_coin.upper() in ["TRC-20", "TRC-10"] and coin_name == netname.upper():
                user_id_erc20 = str(user_id) + "_" + coin_name
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
                main_address = getattr(getattr(self.coin_list, coin_name), "MainAddress")
                get_prefix_char = getattr(getattr(self.coin_list, coin_name), "get_prefix_char")
                get_prefix = getattr(getattr(self.coin_list, coin_name), "get_prefix")
                get_addrlen = getattr(getattr(self.coin_list, coin_name), "get_addrlen")
                balance_address = {}
                balance_address['payment_id'] = cn_addressvalidation.paymentid()
                balance_address['integrated_address'] = \
                    cn_addressvalidation.cn_make_integrated(main_address, get_prefix_char, get_prefix, get_addrlen,
                                                            balance_address['payment_id'])['integrated_address']
            elif type_coin.upper() == "XMR":
                # passed test WOW
                main_address = getattr(getattr(self.coin_list, coin_name), "MainAddress")
                balance_address = await self.make_integrated_address_xmr(main_address, coin_name)
            elif type_coin.upper() == "NANO":
                walletkey = decrypt_string(getattr(getattr(self.coin_list, coin_name), "walletkey"))
                balance_address = await self.call_nano(coin_name,
                                                       payload='{ "action": "account_create", "wallet": "' + walletkey + '" }')
            elif type_coin.upper() == "BTC":
                # passed test PGO, XMY
                naming = config['kv_db']['prefix'] + "_" + user_server + "_" + str(user_id)
                payload = f'"{naming}"'
                address_call = await self.call_doge('getnewaddress', coin_name, payload=payload)
                reg_address = {}
                reg_address['address'] = address_call
                payload = f'"{address_call}"'
                key_call = await self.call_doge('dumpprivkey', coin_name, payload=payload)
                reg_address['privateKey'] = key_call
                if reg_address['address'] and reg_address['privateKey']:
                    balance_address = reg_address
            elif type_coin.upper() == "CHIA":
                # passed test XFX
                payload = {'wallet_id': 1, 'new_address': True}
                try:
                    address_call = await self.call_xch('get_next_address', coin_name, payload=payload)
                    if 'success' in address_call and address_call['address']:
                        balance_address = address_call
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            elif type_coin.upper() == "HNT":
                # generate random memo
                from string import ascii_uppercase
                main_address = getattr(getattr(self.coin_list, coin_name), "MainAddress")
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
                            `called_Update`, `user_server`, `chat_id`, `is_discord_guild`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            await cur.execute(sql, (
                                str(user_id), user_id_erc20, type_coin_user, w['address'], int(time.time()),
                                encrypt_string(w['seed']), encrypt_string(str(w)),
                                encrypt_string(str(w['private_key'])),
                                w['public_key'],
                                encrypt_string(str(w['xprivate_key'])), w['xpublic_key'], int(time.time()), user_server,
                                chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': w['address']}
                        elif netname and netname in ["TRX"]:
                            sql = """ INSERT INTO `trc20_user` (`user_id`, `user_id_trc20`, `type`, `balance_wallet_address`, `hex_address`, `address_ts`, 
                            `private_key`, `public_key`, `called_Update`, `user_server`, `chat_id`, `is_discord_guild`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            await cur.execute(sql, (
                                str(user_id), user_id_erc20, type_coin_user, w['base58check_address'], w['hex_address'],
                                int(time.time()),
                                encrypt_string(str(w['private_key'])), w['public_key'], int(time.time()), user_server,
                                chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': w['base58check_address']}
                        elif type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                            sql = """ INSERT INTO cn_user_paymentid (`coin_name`, `user_id`, `user_id_coin`, `main_address`, `paymentid`, 
                            `balance_wallet_address`, `paymentid_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            await cur.execute(sql, (
                                coin_name, str(user_id), "{}_{}".format(user_id, coin_name), main_address,
                                balance_address['payment_id'],
                                balance_address['integrated_address'], int(time.time()), user_server, chat_id,
                                is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['integrated_address'],
                                    'paymentid': balance_address['payment_id']}
                        elif type_coin.upper() == "NANO":
                            sql = """ INSERT INTO `nano_user` (`coin_name`, `user_id`, `user_id_coin`, `balance_wallet_address`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                                coin_name, str(user_id), "{}_{}".format(user_id, coin_name), balance_address['account'],
                                int(time.time()), user_server, chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['account']}
                        elif type_coin.upper() == "BTC":
                            sql = """ INSERT INTO `doge_user` 
                            (`coin_name`, `user_id`, `user_id_coin`, `balance_wallet_address`, `address_ts`, `privateKey`, 
                            `user_server`, `chat_id`, `is_discord_guild`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            await cur.execute(sql, (
                                coin_name, str(user_id), "{}_{}".format(user_id, coin_name), balance_address['address'],
                                int(time.time()),
                                encrypt_string(balance_address['privateKey']), user_server, chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin.upper() == "CHIA":
                            sql = """ INSERT INTO `xch_user` 
                            (`coin_name`, `user_id`, `user_id_coin`, `balance_wallet_address`, `address_ts`, `user_server`, 
                            `chat_id`, `is_discord_guild`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            await cur.execute(sql, (
                                coin_name, str(user_id), "{}_{}".format(user_id, coin_name), balance_address['address'],
                                int(time.time()), user_server, chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin.upper() == "HNT":
                            sql = """ INSERT INTO `hnt_user` 
                            (`coin_name`, `user_id`, `main_address`, `balance_wallet_address`, `memo`, `address_ts`, 
                            `user_server`, `chat_id`, `is_discord_guild`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            await cur.execute(sql, (
                                coin_name, str(user_id), main_address, balance_address['balance_wallet_address'], memo,
                                int(time.time()), user_server, chat_id, is_discord_guild))
                            await conn.commit()
                            return balance_address
                        elif type_coin.upper() == "ADA":
                            sql = """ INSERT INTO `ada_user` 
                            (`user_id`, `wallet_name`, `balance_wallet_address`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s);
                            UPDATE `ada_wallets` SET `used_address`=`used_address`+1 WHERE `wallet_name`=%s LIMIT 1;
                            """
                            await cur.execute(sql, (
                                str(user_id), balance_address['wallet_name'], balance_address['address'],
                                int(time.time()),
                                user_server, chat_id, is_discord_guild, balance_address['wallet_name']))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin.upper() == "SOL":
                            sql = """ INSERT INTO `sol_user` 
                            (`user_id`, `balance_wallet_address`, `address_ts`, `secret_key_hex`, `called_Update`, 
                            `user_server`, `chat_id`, `is_discord_guild`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            await cur.execute(sql, (
                                str(user_id), balance_address['balance_wallet_address'], int(time.time()),
                                encrypt_string(balance_address['secret_key_hex']), int(time.time()), user_server,
                                chat_id,
                                is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['balance_wallet_address']}
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    async def sql_get_userwallet(
        self, user_id, coin: str, netname: str, type_coin: str, user_server: str = SERVER_BOT,
        chat_id: int = None
    ):
        # netname null or None, xDai, MATIC, TRX, BSC
        user_server = user_server.upper()
        coin_name = coin.upper()
        if type_coin.upper() == "ERC-20" and coin_name != netname.upper():
            user_id_erc20 = str(user_id) + "_" + type_coin.upper()
        elif type_coin.upper() == "ERC-20" and coin_name == netname.upper():
            user_id_erc20 = str(user_id) + "_" + coin_name
        if type_coin.upper() in ["TRC-20", "TRC-10"] and coin_name != netname.upper():
            type_coin = "TRC-20"
            user_id_erc20 = str(user_id) + "_" + type_coin.upper()
        elif type_coin.upper() in ["TRC-20", "TRC-10"] and coin_name == netname.upper():
            user_id_erc20 = str(user_id) + "_" + coin_name
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if netname and netname not in ["TRX"]:
                        sql = """ SELECT * FROM `erc20_user` WHERE `user_id`=%s 
                                  AND `user_id_erc20`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_id_erc20, user_server))
                        result = await cur.fetchone()
                        if result:
                            # update chat_id
                            if chat_id is not None:
                                try:
                                    sql = """ UPDATE `erc20_user` SET `chat_id`=%s 
                                    WHERE `user_id`=%s AND `user_server`=%s
                                    """
                                    await cur.execute(sql, (chat_id, str(user_id), user_server))
                                    await conn.commit()
                                except Exception as e:
                                    pass
                            return result
                    elif netname and netname in ["TRX"]:
                        sql = """ SELECT * FROM `trc20_user` WHERE `user_id`=%s 
                                  AND `user_id_trc20`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_id_erc20, user_server))
                        result = await cur.fetchone()
                        if result:
                            # update chat_id
                            if chat_id is not None:
                                try:
                                    sql = """ UPDATE `trc20_user` SET `chat_id`=%s 
                                    WHERE `user_id`=%s AND `user_server`=%s
                                    """
                                    await cur.execute(sql, (chat_id, str(user_id), user_server))
                                    await conn.commit()
                                except Exception as e:
                                    pass
                            return result
                    elif type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql = """ SELECT * FROM `cn_user_paymentid` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result:
                            # update chat_id
                            if chat_id is not None:
                                try:
                                    sql = """ UPDATE `cn_user_paymentid` SET `chat_id`=%s 
                                    WHERE `user_id`=%s AND `user_server`=%s
                                    """
                                    await cur.execute(sql, (chat_id, str(user_id), user_server))
                                    await conn.commit()
                                except Exception as e:
                                    pass
                            return result
                    elif type_coin.upper() == "NANO":
                        sql = """ SELECT * FROM `nano_user` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result:
                            # update chat_id
                            if chat_id is not None:
                                try:
                                    sql = """ UPDATE `nano_user` SET `chat_id`=%s WHERE `user_id`=%s AND `user_server`=%s """
                                    await cur.execute(sql, (chat_id, str(user_id), user_server))
                                    await conn.commit()
                                except Exception as e:
                                    pass
                            return result
                    elif type_coin.upper() == "BTC":
                        sql = """ SELECT * FROM `doge_user` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result:
                            # update chat_id
                            if chat_id is not None:
                                try:
                                    sql = """ UPDATE `doge_user` SET `chat_id`=%s WHERE `user_id`=%s AND `user_server`=%s """
                                    await cur.execute(sql, (chat_id, str(user_id), user_server))
                                    await conn.commit()
                                except Exception as e:
                                    pass
                            return result
                    elif type_coin.upper() == "CHIA":
                        sql = """ SELECT * FROM `xch_user` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result:
                            # update chat_id
                            if chat_id is not None:
                                try:
                                    sql = """ UPDATE `xch_user` SET `chat_id`=%s WHERE `user_id`=%s AND `user_server`=%s """
                                    await cur.execute(sql, (chat_id, str(user_id), user_server))
                                    await conn.commit()
                                except Exception as e:
                                    pass
                            return result
                    elif type_coin.upper() == "HNT":
                        sql = """ SELECT * FROM `hnt_user` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result:
                            # update chat_id
                            if chat_id is not None:
                                try:
                                    sql = """ UPDATE `hnt_user` SET `chat_id`=%s WHERE `user_id`=%s AND `user_server`=%s """
                                    await cur.execute(sql, (chat_id, str(user_id), user_server))
                                    await conn.commit()
                                except Exception as e:
                                    pass
                            return result
                    elif type_coin.upper() == "ADA":
                        sql = """ SELECT * FROM `ada_user` WHERE `user_id`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_server))
                        result = await cur.fetchone()
                        if result:
                            # update chat_id
                            if chat_id is not None:
                                try:
                                    sql = """ UPDATE `ada_user` SET `chat_id`=%s WHERE `user_id`=%s AND `user_server`=%s """
                                    await cur.execute(sql, (chat_id, str(user_id), user_server))
                                    await conn.commit()
                                except Exception as e:
                                    pass
                            return result
                    elif type_coin.upper() == "SOL":
                        sql = """ SELECT * FROM `sol_user` WHERE `user_id`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_server))
                        result = await cur.fetchone()
                        if result:
                            # update chat_id
                            if chat_id is not None:
                                try:
                                    sql = """ UPDATE `ada_user` SET `chat_id`=%s WHERE `user_id`=%s AND `user_server`=%s """
                                    await cur.execute(sql, (chat_id, str(user_id), user_server))
                                    await conn.commit()
                                except Exception as e:
                                    pass
                            return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    async def call_nano(self, coin: str, payload: str) -> Dict:
        await self.get_coin_setting()
        timeout = 100
        coin_name = coin.upper()
        url = getattr(getattr(self.coin_list, coin_name), "rpchost")
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
        await self.get_coin_setting()
        coin_name = coin.upper()
        walletkey = decrypt_string(getattr(getattr(self.coin_list, coin_name), "walletkey"))
        get_wallet_balance = await self.call_nano(coin_name,
                                                  payload='{ "action": "wallet_balances", "wallet": "' + walletkey + '" }')
        if get_wallet_balance and 'balances' in get_wallet_balance:
            return get_wallet_balance['balances']
        return None

    async def nano_sendtoaddress(self, source: str, to_address: str, atomic_amount: int, coin: str) -> str:
        await self.get_coin_setting()
        coin_name = coin.upper()
        walletkey = decrypt_string(getattr(getattr(self.coin_list, coin_name), "walletkey"))
        payload = '{ "action": "send", "wallet": "' + walletkey + '", "source": "' + source + '", "destination": "' + to_address + '", "amount": "' + str(
            atomic_amount) + '" }'
        sending = await self.call_nano(coin_name, payload=payload)
        if sending and 'block' in sending:
            return sending
        return None

    async def nano_validate_address(self, coin: str, account: str) -> str:
        coin_name = coin.upper()
        valid_address = await self.call_nano(coin_name,
                                             payload='{ "action": "validate_account_number", "account": "' + account + '" }')
        if valid_address and valid_address['valid'] == "1":
            return True
        return None

    async def send_external_nano(
        self, main_address: str, user_from: str, amount: float, 
        to_address: str, coin: str, coin_decimal
    ):
        coin_name = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    tx_hash = await self.nano_sendtoaddress(
                        main_address, to_address, int(Decimal(amount) * 10 ** coin_decimal), coin_name
                    )
                    if tx_hash:
                        updateTime = int(time.time())
                        async with conn.cursor() as cur:
                            sql = """ INSERT INTO nano_external_tx (`coin_name`, `user_id`, `amount`, 
                            `decimal`, `to_address`, `date`, `tx_hash`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """
                            await cur.execute(sql, (
                                coin_name, user_from, amount, coin_decimal, to_address, int(time.time()),
                                tx_hash['block'],))
                            await conn.commit()
                            return tx_hash
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None

    async def call_xch(self, method_name: str, coin: str, payload: Dict = None) -> Dict:
        await self.get_coin_setting()
        timeout = 100
        coin_name = coin.upper()

        headers = {
            'Content-Type': 'application/json',
        }
        if payload is None:
            data = '{}'
        else:
            data = payload
        url = getattr(getattr(self.coin_list, coin_name), "rpchost") + '/' + method_name.lower()
        try:
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(getattr(getattr(self.coin_list, coin_name), "cert_path"),
                                        getattr(getattr(self.coin_list, coin_name), "key_path"))
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
                async with session.post(url, json=data, headers=headers, timeout=timeout, ssl=ssl_context) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        decoded_data = json.loads(res_data)
                        return decoded_data
                    else:
                        print(f'Call {coin_name} returns {str(response.status)} with method {method_name}')
        except asyncio.TimeoutError:
            print('TIMEOUT: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin_name, timeout))
            await logchanbot(
                'call_doge: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin_name, timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    async def send_external_xch(
        self, user_from: str, amount: float, to_address: str, coin: str, coin_decimal: int,
        tx_fee: float, withdraw_fee: float, user_server: str = 'DISCORD'
    ):
        coin_name = coin.upper()
        try:
            payload = {
                "wallet_id": 1,
                "amount": int(amount * 10 ** coin_decimal),
                "address": to_address,
                "fee": int(tx_fee * 10 ** coin_decimal)
            }
            result = await self.call_xch('send_transaction', coin_name, payload=payload)
            if result:
                result['tx_hash'] = result['transaction']
                result['transaction_id'] = result['transaction_id']
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        async with conn.cursor() as cur:
                            sql = """ INSERT INTO xch_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, 
                            `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            await cur.execute(sql, (
                                coin_name, user_from, amount,
                                float(result['tx_hash']['fee_amount'] / 10 ** coin_decimal),
                                withdraw_fee, coin_decimal, to_address, int(time.time()), result['tx_hash']['name'],
                                user_server,))
                            await conn.commit()
                            return result['tx_hash']['name']
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None

    async def call_doge(self, method_name: str, coin: str, payload: str = None) -> Dict:
        await self.get_coin_setting()
        timeout = 64
        coin_name = coin.upper()
        headers = {
            'content-type': 'text/plain;',
        }
        if payload is None:
            data = '{"jsonrpc": "1.0", "id":"' + str(
                uuid.uuid4()) + '", "method": "' + method_name + '", "params": [] }'
        else:
            data = '{"jsonrpc": "1.0", "id":"' + str(
                uuid.uuid4()) + '", "method": "' + method_name + '", "params": [' + payload + '] }'

        url = getattr(getattr(self.coin_list, coin_name), "daemon_address")
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
                        print(f'Call {coin_name} returns {str(response.status)} with method {method_name}')
                        print(data)
                        print(url)
        except asyncio.TimeoutError:
            print('TIMEOUT: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin.upper(), timeout))
            await logchanbot(
                'call_doge: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin.upper(), timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    async def send_external_doge(
        self, user_from: str, amount: float, to_address: str, coin: str, tx_fee: float,
        withdraw_fee: float, user_server: str
    ):
        user_server = user_server.upper()
        coin_name = coin.upper()
        try:
            comment = user_from
            comment_to = to_address
            payload = f'"{to_address}", {amount}, "{comment}", "{comment_to}", false'
            if coin_name in ["PGO"]:
                payload = f'"{to_address}", {amount}, "{comment}", "{comment_to}"'
            txHash = await self.call_doge('sendtoaddress', coin_name, payload=payload)
            if txHash is not None:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO `doge_external_tx` (`coin_name`, `user_id`, `amount`, 
                        `tx_fee`, `withdraw_fee`, `to_address`, `date`, `tx_hash`, `user_server`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        await cur.execute(sql, (
                            coin_name, user_from, amount, tx_fee, withdraw_fee, to_address, 
                            int(time.time()), txHash, user_server)
                        )
                        await conn.commit()
                        return txHash
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return False

    async def make_integrated_address_xmr(self, address: str, coin: str, paymentid: str = None):
        coin_name = coin.upper()
        if paymentid:
            try:
                value = int(paymentid, 16)
            except ValueError:
                return False
        else:
            paymentid = cn_addressvalidation.paymentid(8)

        if coin_name == "LTHN":
            payload = {
                "payment_id": {} or paymentid
            }
            address_ia = await self.call_aiohttp_wallet_xmr_bcn('make_integrated_address', coin_name, payload=payload)
            if address_ia: return address_ia
            return None
        else:
            payload = {
                "standard_address": address,
                "payment_id": {} or paymentid
            }
            address_ia = await self.call_aiohttp_wallet_xmr_bcn('make_integrated_address', coin_name, payload=payload)
            if address_ia: return address_ia
            return None

    async def create_address_eth(self):
        seed = ethwallet.generate_mnemonic()
        w = ethwallet.create_wallet(network="ETH", seed=seed, children=1)
        return w

    async def create_address_trx(self):
        try:
            tron_node = await handle_best_node("TRX")
            _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                       timeout=Timeout(timeout=10, connect=5, read=5))
            TronClient = AsyncTron(provider=AsyncHTTPProvider(tron_node, client=_http_client))
            create_wallet = TronClient.generate_address()
            await TronClient.close()
            return create_wallet
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    def check_address_erc20(self, address: str):
        if is_hex_address(address):
            return address
        return False

    async def call_aiohttp_wallet_xmr_bcn(
        self, method_name: str, coin: str, time_out: int = None,
        payload: Dict = None
    ) -> Dict:
        await self.get_coin_setting()
        coin_name = coin.upper()
        coin_family = getattr(getattr(self.coin_list, coin_name), "type")
        full_payload = {
            'params': payload or {},
            'jsonrpc': '2.0',
            'id': str(uuid.uuid4()),
            'method': f'{method_name}'
        }
        url = getattr(getattr(self.coin_list, coin_name), "wallet_address")
        timeout = time_out or 60
        if method_name == "save" or method_name == "store":
            timeout = 300
        elif method_name == "sendTransaction":
            timeout = 180
        elif method_name == "createAddress" or method_name == "getSpendKeys":
            timeout = 60
        try:
            if coin_name == "LTHN":
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
                                print('{} - transfer'.format(coin_name))

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
                    await logchanbot(
                        'call_aiohttp_wallet: method_name: {} coin_name {} - timeout {}\nfull_payload:\n{}'.format(
                            method_name, coin_name, timeout, json.dumps(payload)))
                    print('TIMEOUT: {} coin_name {} - timeout {}'.format(method_name, coin_name, timeout))
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
                                print('{} - transfer'.format(coin_name))
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
                    await logchanbot(
                        'call_aiohttp_wallet: method_name: {} coin_name {} - timeout {}\nfull_payload:\n{}'.format(
                            method_name, coin_name, timeout, json.dumps(payload)))
                    print('TIMEOUT: {} coin_name {} - timeout {}'.format(method_name, coin_name, timeout))
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
                    await logchanbot(
                        'call_aiohttp_wallet: {} coin_name {} - timeout {}\nfull_payload:\n{}'.format(
                            method_name, coin_name, timeout, json.dumps(payload))
                    )
                    print('TIMEOUT: {} coin_name {} - timeout {}'.format(method_name, coin_name, timeout))
                    return None
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                    return None
        except asyncio.TimeoutError:
            await logchanbot(
                'call_aiohttp_wallet: method_name: {} - coin_family: {} - timeout {}'.format(
                    method_name, coin_family, timeout)
            )
            print('TIMEOUT: method_name: {} - coin_family: {} - timeout {}'.format(method_name, coin_family, timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    async def send_external_xmr(
        self, type_coin: str, from_address: str, user_from: str, amount: float, to_address: str,
        coin: str, coin_decimal: int, tx_fee: float, withdraw_fee: float, is_fee_per_byte: int,
        get_mixin: int, user_server: str, wallet_api_url: str = None,
        wallet_api_header: str = None, paymentId: str = None
    ):
        coin_name = coin.upper()
        user_server = user_server.upper()
        time_out = 32
        if coin_name == "DEGO":
            time_out = 120
        try:
            if type_coin == "XMR":
                acc_index = 0
                payload = {
                    "destinations": [{'amount': int(amount * 10 ** coin_decimal), 'address': to_address}],
                    "account_index": acc_index,
                    "subaddr_indices": [],
                    "priority": 1,
                    "unlock_time": 0,
                    "get_tx_key": True,
                    "get_tx_hex": False,
                    "get_tx_metadata": False
                }
                if coin_name == "UPX":
                    payload = {
                        "destinations": [{'amount': int(amount * 10 ** coin_decimal), 'address': to_address}],
                        "account_index": acc_index,
                        "subaddr_indices": [],
                        "ring_size": 11,
                        "get_tx_key": True,
                        "get_tx_hex": False,
                        "get_tx_metadata": False
                    }
                result = await self.call_aiohttp_wallet_xmr_bcn(
                    'transfer', coin_name, time_out=time_out, payload=payload
                )
                if result and 'tx_hash' in result and 'tx_key' in result:
                    await self.openConnection()
                    async with self.pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, 
                            `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `tx_key`, `user_server`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            await cur.execute(sql, (
                                coin_name, user_from, amount, tx_fee, withdraw_fee, coin_decimal, to_address,
                                int(time.time()), result['tx_hash'], result['tx_key'], user_server,)
                            )
                            await conn.commit()
                            return result['tx_hash']
            elif (type_coin == "TRTL-SERVICE" or type_coin == "BCN") and paymentId is None:
                if is_fee_per_byte != 1:
                    payload = {
                        'addresses': [from_address],
                        'transfers': [{
                            "amount": int(amount * 10 ** coin_decimal),
                            "address": to_address
                        }],
                        'fee': int(tx_fee * 10 ** coin_decimal),
                        'anonymity': get_mixin
                    }
                else:
                    payload = {
                        'addresses': [from_address],
                        'transfers': [{
                            "amount": int(amount * 10 ** coin_decimal),
                            "address": to_address
                        }],
                        'anonymity': get_mixin
                    }
                result = await self.call_aiohttp_wallet_xmr_bcn(
                    'sendTransaction', coin_name, time_out=time_out,
                    payload=payload
                )
                if result and 'transactionHash' in result:
                    if is_fee_per_byte != 1:
                        tx_hash = {"transactionHash": result['transactionHash'], "fee": tx_fee}
                    else:
                        tx_hash = {"transactionHash": result['transactionHash'], "fee": result['fee']}
                        tx_fee = float(tx_hash['fee'] / 10 ** coin_decimal)
                    try:
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ INSERT INTO `cn_external_tx` 
                                (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, 
                                `to_address`, `date`, `tx_hash`, `user_server`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                await cur.execute(sql, (
                                    coin_name, user_from, amount, tx_fee, withdraw_fee, coin_decimal, to_address,
                                    int(time.time()), tx_hash['transactionHash'], user_server))
                                await conn.commit()
                                return tx_hash['transactionHash']
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
            elif type_coin == "TRTL-API" and paymentId is None:
                if is_fee_per_byte != 1:
                    json_data = {
                        "destinations": [{"address": to_address, "amount": int(amount * 10 ** coin_decimal)}],
                        "mixin": get_mixin,
                        "fee": int(tx_fee * 10 ** coin_decimal),
                        "sourceAddresses": [
                            from_address
                        ],
                        "paymentID": "",
                        "changeAddress": from_address
                    }
                else:
                    json_data = {
                        "destinations": [{"address": to_address, "amount": int(amount * 10 ** coin_decimal)}],
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
                        async with session.post(wallet_api_url + method, headers=headers, json=json_data,
                                                timeout=time_out) as response:
                            json_resp = await response.json()
                            if response.status == 200 or response.status == 201:
                                if is_fee_per_byte != 1:
                                    tx_hash = {"transactionHash": json_resp['transactionHash'], "fee": tx_fee}
                                else:
                                    tx_hash = {"transactionHash": json_resp['transactionHash'], "fee": json_resp['fee']}
                                    tx_fee = float(tx_hash['fee'] / 10 ** coin_decimal)
                                try:
                                    await self.openConnection()
                                    async with self.pool.acquire() as conn:
                                        async with conn.cursor() as cur:
                                            sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, 
                                            `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, 
                                            `date`, `tx_hash`, `user_server`) 
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                            await cur.execute(sql, (
                                                coin_name, user_from, amount, tx_fee, withdraw_fee, coin_decimal,
                                                to_address, int(time.time()), tx_hash['transactionHash'], 
                                                user_server)
                                            )
                                            await conn.commit()
                                            return tx_hash['transactionHash']
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            elif 'errorMessage' in json_resp:
                                raise RPCException(json_resp['errorMessage'])
                            else:
                                await logchanbot('walletapi_send_transaction: {} response: {}'.format(
                                    method, response)
                                )
                except asyncio.TimeoutError:
                    await logchanbot(
                        'walletapi_send_transaction: TIMEOUT: {} coin_name {} - timeout {}'.format(
                            method, coin_name, time_out)
                        )
            elif (type_coin == "TRTL-SERVICE" or type_coin == "BCN") and paymentId is not None:
                if coin_name == "DEGO":
                    time_out = 300
                if is_fee_per_byte != 1:
                    payload = {
                        'addresses': [from_address],
                        'transfers': [{
                            "amount": int(amount * 10 ** coin_decimal),
                            "address": to_address
                        }],
                        'fee': int(tx_fee * 10 ** coin_decimal),
                        'anonymity': get_mixin,
                        'paymentId': paymentId,
                        'changeAddress': from_address
                    }
                else:
                    payload = {
                        'addresses': [from_address],
                        'transfers': [{
                            "amount": int(amount * 10 ** coin_decimal),
                            "address": to_address
                        }],
                        'anonymity': get_mixin,
                        'paymentId': paymentId,
                        'changeAddress': from_address
                    }
                result = None
                result = await self.call_aiohttp_wallet_xmr_bcn(
                    'sendTransaction', coin_name, time_out=time_out, payload=payload
                )
                if result and 'transactionHash' in result:
                    if is_fee_per_byte != 1:
                        tx_hash = {"transactionHash": result['transactionHash'], "fee": tx_fee}
                    else:
                        tx_hash = {"transactionHash": result['transactionHash'], "fee": result['fee']}
                        tx_fee = float(tx_hash['fee'] / 10 ** coin_decimal)
                    try:
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, 
                                `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, 
                                `paymentid`, `date`, `tx_hash`, `user_server`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                await cur.execute(sql, (
                                    coin_name, user_from, amount, tx_fee, withdraw_fee, 
                                    coin_decimal, to_address, paymentId,
                                    int(time.time()), tx_hash['transactionHash'],
                                    user_server)
                                )
                                await conn.commit()
                                return tx_hash['transactionHash']
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
            elif type_coin == "TRTL-API" and paymentId is not None:
                if is_fee_per_byte != 1:
                    json_data = {
                        'sourceAddresses': [from_address],
                        'destinations': [{
                            "amount": int(amount * 10 ** coin_decimal),
                            "address": to_address
                        }],
                        'fee': int(tx_fee * 10 ** coin_decimal),
                        'mixin': get_mixin,
                        'paymentID': paymentId,
                        'changeAddress': from_address
                    }
                else:
                    json_data = {
                        'sourceAddresses': [from_address],
                        'destinations': [{
                            "amount": int(amount * 10 ** coin_decimal),
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
                        async with session.post(wallet_api_url + method, headers=headers, json=json_data,
                                                timeout=time_out) as response:
                            json_resp = await response.json()
                            if response.status == 200 or response.status == 201:
                                if is_fee_per_byte != 1:
                                    tx_hash = {"transactionHash": json_resp['transactionHash'], "fee": tx_fee}
                                else:
                                    tx_hash = {"transactionHash": json_resp['transactionHash'], "fee": json_resp['fee']}
                                    tx_fee = float(tx_hash['fee'] / 10 ** coin_decimal)
                                try:
                                    await self.openConnection()
                                    async with self.pool.acquire() as conn:
                                        async with conn.cursor() as cur:
                                            sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, 
                                            `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, 
                                            `paymentid`, `date`, `tx_hash`, `user_server`) 
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                            await cur.execute(sql, (
                                                coin_name, user_from, amount, tx_fee, withdraw_fee, coin_decimal,
                                                to_address, paymentId, int(time.time()), tx_hash['transactionHash'],
                                                user_server)
                                            )
                                            await conn.commit()
                                            return tx_hash['transactionHash']
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            elif 'errorMessage' in json_resp:
                                raise RPCException(json_resp['errorMessage'])
                except asyncio.TimeoutError:
                    await logchanbot(
                        'walletapi_send_transaction_id: TIMEOUT: {} coin_name {} - timeout {}'.format(
                            method, coin_name, time_out)
                    )
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None

    async def send_external_hnt(
        self, user_id: str, wallet_host: str, password: str, from_address: str, payee: str,
        amount: float, coin_decimal: int, user_server: str, coin: str, withdraw_fee: float,
        time_out=32
    ):
        coin_name = coin.upper()
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
                    "bones": int(amount * 10 ** coin_decimal)
                    # "nonce": 422
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
                check_locked = await call_hnt_wallet(
                    wallet_host, headers=headers, json_data=json_check_lock, time_out=time_out
                )
                print(check_locked)
                if 'result' in check_locked and check_locked['result'] == True:
                    await logchanbot(f'[UNLOCKED] {coin_name}...')
                    unlock = await call_hnt_wallet(wallet_host, headers=headers, json_data=json_unlock,
                                                   time_out=time_out)
                    print(unlock)
                if unlock is None or (unlock is not None and 'result' in unlock and unlock['result'] == True):
                    send_tx = await call_hnt_wallet(wallet_host, headers=headers, json_data=json_send, time_out=time_out)
                    fee = 0.0
                    if 'result' in send_tx:
                        if 'implicit_burn' in send_tx['result'] and 'fee' in send_tx['result']['implicit_burn']:
                            fee = send_tx['result']['implicit_burn']['fee'] / 10 ** coin_decimal
                        elif 'fee' in send_tx['result']:
                            fee = send_tx['result']['fee'] / 10 ** coin_decimal
                        try:
                            await self.openConnection()
                            async with self.pool.acquire() as conn:
                                async with conn.cursor() as cur:
                                    sql = """ INSERT INTO hnt_external_tx (`coin_name`, `user_id`, 
                                    `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `date`, 
                                    `tx_hash`, `user_server`) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                    await cur.execute(sql, (
                                        coin_name, user_id, amount, fee, withdraw_fee, coin_decimal, payee,
                                        int(time.time()), send_tx['result']['hash'], user_server))
                                    await conn.commit()
                                    return send_tx['result']['hash']
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

    async def send_external_ada(
        self, user_id: str, amount: float, coin_decimal: int, user_server: str, coin: str,
        withdraw_fee: float, to_address: str, time_out=32
    ):
        coin_name = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `ada_wallets` 
                              WHERE `is_for_withdraw`=%s ORDER BY RAND() LIMIT 1 """
                    await cur.execute(sql, (1))
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

                        fetch_wallet = await fetch_wallet_status(
                            result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'], 8)
                        if fetch_wallet and fetch_wallet['state']['status'] == "ready":
                            # wallet is ready, "syncing" if it is syncing
                            async def send_tx(url: str, to_address: str, amount_atomic: int, timeout: int = 90):
                                try:
                                    headers = {
                                        'Content-Type': 'application/json'
                                    }
                                    data_json = {"passphrase": decrypt_string(result['passphrase']), "payments": [
                                        {"address": to_address,
                                         "amount": {"quantity": amount_atomic, "unit": "lovelace"}}],
                                                 "withdrawal": "self"}
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(
                                            url, headers=headers, json=data_json,
                                            timeout=timeout
                                        ) as response:
                                            if response.status == 202:
                                                res_data = await response.read()
                                                res_data = res_data.decode('utf-8')
                                                decoded_data = json.loads(res_data)
                                                return decoded_data
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                return None

                            sending_tx = await send_tx(
                                result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'] + "/transactions",
                                to_address, int(amount * 10 ** coin_decimal), 90)
                            if "code" in sending_tx and "message" in sending_tx:
                                return sending_tx
                            elif "status" in sending_tx and sending_tx['status'] == "pending":
                                # success
                                # withdraw_fee became: network_fee + withdraw_fee, it is fee_limit
                                network_fee = sending_tx['fee']['quantity'] / 10 ** coin_decimal
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
                                    async with conn.cursor() as cur:
                                        sql = """ INSERT INTO `ada_external_tx` (`coin_name`, `asset_name`, 
                                        `policy_id`, `user_id`, `real_amount`, `real_external_fee`, 
                                        `network_fee`, `token_decimal`, `to_address`, `input_json`, 
                                        `output_json`, `hash_id`, `date`, `user_server`) 
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                        await cur.execute(sql, (
                                            coin_name, None, None, user_id, amount, network_fee + withdraw_fee,
                                            network_fee,
                                            coin_decimal, to_address, json.dumps(sending_tx['inputs']),
                                            json.dumps(sending_tx['outputs']), sending_tx['id'], int(time.time()),
                                            user_server)
                                        )
                                        await conn.commit()
                                        return sending_tx
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def send_external_ada_asset(
        self, user_id: str, amount: float, coin_decimal: int, user_server: str, coin: str,
        withdraw_fee: float, to_address: str, asset_name: str, policy_id: str,
        time_out=32
    ):
        coin_name = coin.upper()
        try:
            await self.get_coin_setting()
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `ada_wallets` 
                              WHERE `is_for_withdraw`=%s ORDER BY RAND() LIMIT 1 """
                    await cur.execute(sql, (1))
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

                        fetch_wallet = await fetch_wallet_status(
                            result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'], 8)
                        if fetch_wallet and fetch_wallet['state']['status'] == "ready":
                            # wallet is ready, "syncing" if it is syncing
                            async def estimate_fee_with_asset(
                                url: str, to_address: str, asset_name: str,
                                policy_id: str, amount_atomic: int, timeout: int = 90
                            ):
                                try:
                                    headers = {
                                        'Content-Type': 'application/json'
                                    }
                                    data_json = {"payments": [
                                        {"address": to_address, "amount": {"quantity": 0, "unit": "lovelace"},
                                         "assets": [{"policy_id": policy_id, "asset_name": asset_name,
                                                     "quantity": amount_atomic}]}], "withdrawal": "self"}
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(url, headers=headers, json=data_json,
                                                                timeout=timeout) as response:
                                            if response.status == 202:
                                                res_data = await response.read()
                                                res_data = res_data.decode('utf-8')
                                                decoded_data = json.loads(res_data)
                                                return decoded_data
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                return None

                            async def send_tx(
                                url: str, to_address: str, ada_atomic_amount: int, amount_atomic: int,
                                asset_name: str, policy_id: str, timeout: int = 90
                            ):
                                try:
                                    headers = {
                                        'Content-Type': 'application/json'
                                    }
                                    data_json = {"passphrase": decrypt_string(result['passphrase']), "payments": [
                                        {"address": to_address,
                                         "amount": {"quantity": ada_atomic_amount, "unit": "lovelace"}, "assets": [
                                            {"policy_id": policy_id, "asset_name": asset_name,
                                             "quantity": amount_atomic}]}], "withdrawal": "self"}
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(url, headers=headers, json=data_json,
                                                                timeout=timeout) as response:
                                            if response.status == 202:
                                                res_data = await response.read()
                                                res_data = res_data.decode('utf-8')
                                                decoded_data = json.loads(res_data)
                                                return decoded_data
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                return None

                            estimate_tx = await estimate_fee_with_asset(
                                result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'] + "/payment-fees",
                                to_address, asset_name, policy_id, int(amount * 10 ** coin_decimal), 10)
                            ada_fee_atomic = None
                            if estimate_tx and "minimum_coins" in estimate_tx:
                                ada_fee_atomic = estimate_tx['minimum_coins'][0]['quantity']
                                sending_tx = await send_tx(
                                    result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'] + "/transactions",
                                    to_address, ada_fee_atomic, int(amount * 10 ** coin_decimal), asset_name, policy_id,
                                    90)
                                if "code" in sending_tx and "message" in sending_tx:
                                    return sending_tx
                                elif "status" in sending_tx and sending_tx['status'] == "pending":
                                    # success
                                    rows = []
                                    if len(sending_tx['outputs']) > 0:
                                        network_fee = sending_tx['fee']['quantity'] / 10 ** 6  # Fee in ADA
                                        for each_output in sending_tx['outputs']:
                                            if each_output['address'].upper() == to_address:
                                                # rows.append( () )
                                                pass
                                    data_rows = []
                                    try:
                                        data_rows.append((
                                            coin_name, asset_name, policy_id, user_id, amount,
                                            withdraw_fee, network_fee, coin_decimal, to_address,
                                            json.dumps(sending_tx['inputs']),
                                            json.dumps(sending_tx['outputs']), sending_tx['id'],
                                            int(time.time()), user_server)
                                        )
                                        if getattr(getattr(self.coin_list, coin_name), "withdraw_use_gas_ticker") == 1:
                                            GAS_COIN = getattr(getattr(self.coin_list, coin_name), "gas_ticker")
                                            fee_limit = getattr(getattr(self.coin_list, coin_name), "fee_limit")
                                            fee_limit = fee_limit / 20  # => 2 / 20 = 0.1 ADA # Take care if you adjust fee_limit in DB
                                            # new ADA charge = ADA goes to withdraw wallet + 0.1 ADA
                                            data_rows.append((
                                                GAS_COIN, None, None, user_id,
                                                network_fee + fee_limit + ada_fee_atomic / 10 ** 6, 0,
                                                network_fee,
                                                getattr(getattr(self.coin_list, GAS_COIN), "decimal"),
                                                to_address, json.dumps(sending_tx['inputs']),
                                                json.dumps(sending_tx['outputs']), sending_tx['id'],
                                                int(time.time()), user_server
                                            ))
                                        await self.openConnection()
                                        async with self.pool.acquire() as conn:
                                            async with conn.cursor() as cur:
                                                sql = """ INSERT INTO `ada_external_tx` (`coin_name`, 
                                                `asset_name`, `policy_id`, `user_id`, `real_amount`, 
                                                `real_external_fee`, `network_fee`, `token_decimal`, 
                                                `to_address`, `input_json`, `output_json`, `hash_id`, 
                                                `date`, `user_server`) 
                                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                await cur.executemany(sql, data_rows)
                                                await conn.commit()
                                                sending_tx['all_ada_fee'] = network_fee + fee_limit + ada_fee_atomic / 10 ** 6
                                                sending_tx['ada_received'] = ada_fee_atomic / 10 ** 6
                                                sending_tx['network_fee'] = network_fee
                                                return sending_tx
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot(
                                            f"[BUG] send_external_ada_asset: user_id: `{user_id}` failed to insert to DB for withdraw "\
                                            f"{json.dumps(data_rows)}."
                                        )
                            else:
                                print(
                                    "send_external_ada_asset: cannot get estimated fee for sending asset `{asset_name}`")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def send_external_sol(
        self, url: str, user_from: str, amount: float, to_address: str, coin: str,
        coin_decimal: int, tx_fee: float, withdraw_fee: float, user_server: str = 'DISCORD'
    ):
        async def move_wallet_balance(url: str, receiver: str, atomic_amount: int):
            # url: is endpoint transfer
            try:
                sender = Keypair.from_secret_key(bytes.fromhex(config['sol']['MainAddress_key_hex']))
                client = Sol_AsyncClient(url)
                txn = Transaction().add(transfer(TransferParams(
                    from_pubkey=sender.public_key, to_pubkey=receiver, lamports=atomic_amount)))
                sending_tx = await client.send_transaction(txn, sender)
                if 'result' in sending_tx:
                    await client.close()
                    return sending_tx['result']  # This is Tx Hash
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return None

        try:
            send_tx = await move_wallet_balance(url, to_address, int(amount * 10 ** coin_decimal))
            if send_tx:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO `sol_external_tx` (`coin_name`, `contract`, `user_id`, 
                        `real_amount`, `real_external_fee`, `network_fee`, `txn`, `token_decimal`, 
                        `to_address`, `date`, `user_server`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (
                            coin.upper(), None, user_from, amount, withdraw_fee, tx_fee, send_tx, coin_decimal,
                            to_address,
                            int(time.time()), user_server))
                        await conn.commit()
                        return send_tx
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    async def send_external_erc20(
        self, url: str, network: str, user_id: str, to_address: str, amount: float, coin: str,
        coin_decimal: int, real_withdraw_fee: float, user_server: str, chain_id: str = None,
        contract: str = None
    ):
        token_name = coin.upper()
        user_server = user_server.upper()

        try:
            # HTTPProvider:
            w3 = Web3(Web3.HTTPProvider(url))
            signed_txn = None
            sent_tx = None
            if contract is None:
                # Main Token
                if network == "MATIC":
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config['eth']['MainAddress']), 'pending')
                else:
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config['eth']['MainAddress']))
                # get gas price
                gasPrice = w3.eth.gasPrice

                estimateGas = w3.eth.estimateGas(
                    {'to': w3.toChecksumAddress(to_address), 'from': w3.toChecksumAddress(config['eth']['MainAddress']),
                     'value': int(amount * 10 ** coin_decimal)})

                atomic_amount = int(amount * 10 ** 18)
                transaction = {
                    'from': w3.toChecksumAddress(config['eth']['MainAddress']),
                    'to': w3.toChecksumAddress(to_address),
                    'value': atomic_amount,
                    'nonce': nonce,
                    'gasPrice': gasPrice,
                    'gas': estimateGas,
                    'chainId': chain_id
                }
                try:
                    signed_txn = w3.eth.account.sign_transaction(transaction, private_key=config['eth']['MainAddress_key'])
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
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config['eth']['MainAddress']), 'pending')
                else:
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config['eth']['MainAddress']))

                unicorn_txn = unicorns.functions.transfer(
                    w3.toChecksumAddress(to_address),
                    int(amount * 10 ** coin_decimal)  # amount to send
                ).buildTransaction({
                    'from': w3.toChecksumAddress(config['eth']['MainAddress']),
                    'gasPrice': w3.eth.gasPrice,
                    'nonce': nonce,
                    'chainId': chain_id
                })

                acct = Account.from_mnemonic(
                    mnemonic=config['eth']['MainAddress_seed'])
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
                            `user_server`, `network`)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql,(
                                token_name, contract, user_id, amount, real_withdraw_fee, coin_decimal,
                                to_address, int(time.time()), sent_tx.hex(), user_server, network)
                            )
                            await conn.commit()
                            return sent_tx.hex()
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    async def send_external_trc20(
        self, user_id: str, to_address: str, amount: float, coin: str, coin_decimal: int,
        real_withdraw_fee: float, user_server: str, fee_limit: float, trc_type: str,
        contract: str = None
    ):
        token_name = coin.upper()
        user_server = user_server.upper()

        try:
            tron_node = await handle_best_node("TRX")
            _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                       timeout=Timeout(timeout=10, connect=5, read=5))
            TronClient = AsyncTron(provider=AsyncHTTPProvider(tron_node, client=_http_client))
            if token_name == "TRX":
                txb = (
                    TronClient.trx.transfer(config['trc']['MainAddress'], to_address, int(amount * 10 ** 6))
                    # .memo("test memo")
                    .fee_limit(int(fee_limit * 10 ** 6))
                )
                txn = await txb.build()
                priv_key = PrivateKey(bytes.fromhex(config['trc']['MainAddress_key']))
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
                                sql = """ INSERT INTO trc20_external_tx (`token_name`, `contract`, `user_id`, 
                                `real_amount`, `real_external_fee`, `token_decimal`, `to_address`, `date`, 
                                `txn`, `user_server`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                await cur.execute(sql, (
                                    token_name, contract, user_id, amount, real_withdraw_fee, coin_decimal,
                                    to_address, int(time.time()), txn_ret['txid'], user_server)
                                )
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
                        ## balance = await cntr.functions.balanceOf(config['trc']['MainAddress']) / 10**precision
                        txb = await cntr.functions.transfer(to_address, int(amount * 10 ** coin_decimal))
                        txb = txb.with_owner(config['trc']['MainAddress']).fee_limit(int(fee_limit * 10 ** 6))
                        txn = await txb.build()
                        priv_key = PrivateKey(bytes.fromhex(config['trc']['MainAddress_key']))
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
                                        await cur.execute(sql, (
                                            token_name, contract, user_id, amount, real_withdraw_fee, coin_decimal,
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
                        precision = 10 ** coin_decimal
                        txb = (
                            TronClient.trx.asset_transfer(
                                config['trc']['MainAddress'], to_address, int(precision * amount), token_id=int(contract)
                            )
                            .fee_limit(int(fee_limit * 10 ** 6))
                        )
                        txn = await txb.build()
                        priv_key = PrivateKey(bytes.fromhex(config['trc']['MainAddress_key']))
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
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        """
                                        await cur.execute(sql, (
                                            token_name, str(contract), user_id, amount, real_withdraw_fee, coin_decimal,
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

    ### For Wallet
    async def check_withdraw_coin_address(self, coin_family: str, address: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    result = None
                    if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql = """ SELECT * FROM `cn_user_paymentid` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "CHIA":
                        sql = """ SELECT * FROM `xch_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "BTC":
                        # if doge family, address is paymentid
                        sql = """ SELECT * FROM `doge_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "NANO":
                        # if doge family, address is paymentid
                        sql = """ SELECT * FROM `nano_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "HNT":
                        # if doge family, address is paymentid
                        sql = """ SELECT * FROM `hnt_user` WHERE `main_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "ADA":
                        # if ADA family, address is paymentid
                        sql = """ SELECT * FROM `ada_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "SOL":
                        # if SOL family, address is paymentid
                        sql = """ SELECT * FROM `sol_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "ERC-20":
                        sql = """ SELECT * FROM `erc20_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "TRC-20":
                        sql = """ SELECT * FROM `trc20_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return result

    async def user_balance(
        self, user_id: str, coin: str, address: str, coin_family: str, top_block: int,
        confirmed_depth: int = 0, user_server: str = SERVER_BOT
    ):
        # address: TRTL/BCN/XMR = paymentId
        token_name = coin.upper()
        user_server = user_server.upper()
        if top_block is None:
            # If we can not get top block, confirm after 20mn. This is second not number of block
            nos_block = 20 * 60
        else:
            nos_block = top_block - confirmed_depth
        confirmed_inserted = 30  # 30s for nano
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # moving tip + / -
                    sql = """
                            SELECT 
                            (SELECT IFNULL((SELECT `balance`  
                            FROM `user_balance_mv_data` 
                            WHERE `user_id`=%s AND `token_name`=%s AND `user_server`=%s LIMIT 1), 0))

                            - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                            FROM `discord_airdrop_tmp` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                            FROM `discord_mathtip_tmp` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                            FROM `discord_triviatip_tmp` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`amount_sell`)  
                            FROM `open_order` 
                            WHERE `coin_sell`=%s AND `userid_sell`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`amount`)  
                            FROM `guild_raffle_entries` 
                            WHERE `coin_name`=%s AND `user_id`=%s AND `user_server`=%s AND `status`=%s), 0))
                          """
                    query_param = [user_id, token_name, user_server,
                                   user_id, token_name, "ONGOING",
                                   user_id, token_name, "ONGOING",
                                   user_id, token_name, "ONGOING",
                                   token_name, user_id, "OPEN",
                                   token_name, user_id, user_server, "REGISTERED"]
                    if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql += """
                            - (SELECT IFNULL((SELECT SUM(amount+withdraw_fee)  
                            FROM `cn_external_tx` 
                            WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s AND `crediting`=%s), 0))
                            """
                        query_param += [user_id, token_name, user_server, "YES"]
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount) FROM `cn_get_transfers` WHERE `payment_id`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `time_insert`< %s AND `user_server`=%s), 0))
                            """
                            query_param += [address, token_name, int(time.time()) - nos_block, user_server]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount) FROM `cn_get_transfers` 
                            WHERE `payment_id`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `height`< %s AND `user_server`=%s), 0))
                            """
                            query_param += [address, token_name, nos_block, user_server]
                    elif coin_family == "BTC":
                        sql += """
                            - (SELECT IFNULL((SELECT SUM(amount+withdraw_fee)  
                            FROM `doge_external_tx` 
                            WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s AND `crediting`=%s), 0))
                            """
                        query_param += [user_id, token_name, user_server, "YES"]
                        if token_name not in ["PGO"]:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(`amount`) 
                            FROM `doge_get_transfers` 
                            WHERE `address`=%s AND `coin_name`=%s 
                            AND (`category` = %s or `category` = %s) 
                            AND `confirmations`>=%s AND `amount`>0), 0))
                            """
                            query_param += [address, token_name, 'receive', 'generate', confirmed_depth]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `doge_get_transfers` 
                            WHERE `address`=%s AND `coin_name`=%s AND `category` = %s 
                            AND `confirmations`>=%s AND `amount`>0), 0))
                            """
                            query_param += [address, token_name, 'receive', confirmed_depth]
                    elif coin_family == "NEO":
                        sql += """
                            - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                            FROM `neo_external_tx` 
                            WHERE `user_id`=%s AND `coin_name`=%s 
                            AND `user_server`=%s AND `crediting`=%s), 0))
                               """
                        query_param += [user_id, token_name, user_server, "YES"]
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(`amount`)  
                            FROM `neo_get_transfers` 
                            WHERE `address`=%s 
                            AND `coin_name`=%s AND `category` = %s 
                            AND `time_insert`<=%s AND `amount`>0), 0))
                                   """
                            query_param += [address, token_name, 'received', int(time.time()) - nos_block]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(`amount`)  
                            FROM `neo_get_transfers` 
                            WHERE `address`=%s 
                            AND `coin_name`=%s AND `category` = %s 
                            AND `confirmations`<=%s AND `amount`>0), 0))
                                   """
                            query_param += [address, token_name, 'received', nos_block]
                    elif coin_family == "NEAR":
                        sql += """
                            - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                            FROM `near_external_tx` 
                            WHERE `user_id`=%s AND `token_name`=%s 
                            AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount-real_deposit_fee) 
                            FROM `near_move_deposit` 
                            WHERE `balance_wallet_address`=%s 
                            AND `user_id`=%s AND `token_name`=%s 
                            AND `time_insert`<=%s AND `amount`>0), 0))
                            """
                            query_param += [address, user_id, token_name, int(time.time()) - nos_block]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount-real_deposit_fee)  
                            FROM `near_move_deposit` 
                            WHERE `balance_wallet_address`=%s 
                            AND `user_id`=%s AND `token_name`=%s 
                            AND `confirmations`<=%s AND `amount`>0), 0))
                            """
                            query_param += [address, user_id, token_name, nos_block]
                    elif coin_family == "NANO":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(`amount`)  
                        FROM `nano_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]

                        sql += """
                        + (SELECT IFNULL((SELECT SUM(amount)  
                        FROM `nano_move_deposit` WHERE `user_id`=%s 
                        AND `coin_name`=%s 
                        AND `amount`>0 AND `time_insert`< %s AND `user_server`=%s), 0))
                        """
                        query_param += [user_id, token_name, int(time.time()) - confirmed_inserted, user_server]
                    elif coin_family == "CHIA":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(amount+withdraw_fee)  
                        FROM `xch_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]

                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(`amount`)  
                            FROM `xch_get_transfers` 
                            WHERE `address`=%s AND `coin_name`=%s AND `amount`>0 
                            AND `time_insert`< %s), 0))
                            """
                            query_param += [address, token_name, nos_block]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(`amount`)  
                            FROM `xch_get_transfers` 
                            WHERE `address`=%s AND `coin_name`=%s AND `amount`>0 AND `height`<%s), 0))
                            """
                            query_param += [address, token_name, nos_block]
                    elif coin_family == "ERC-20":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                        FROM `erc20_external_tx` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        sql += """
                        + (SELECT IFNULL((SELECT SUM(real_amount-real_deposit_fee)  
                        FROM `erc20_move_deposit` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `confirmed_depth`> %s AND `user_server`=%s AND `status`=%s), 0))
                        """
                        query_param += [user_id, token_name, confirmed_depth, user_server, "CONFIRMED"]
                    elif coin_family == "XTZ":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                        FROM `tezos_external_tx` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        sql += """
                        + (SELECT IFNULL((SELECT SUM(real_amount-real_deposit_fee)  
                        FROM `tezos_move_deposit` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `confirmed_depth`> %s AND `user_server`=%s 
                        AND `status`=%s), 0))
                        """
                        query_param += [user_id, token_name, 0, user_server, "CONFIRMED"]
                    elif coin_family == "ZIL":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                        FROM `zil_external_tx` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        sql += """
                        + (SELECT IFNULL((SELECT SUM(real_amount-real_deposit_fee)  
                        FROM `zil_move_deposit` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `confirmed_depth`> %s AND `user_server`=%s AND `status`=%s), 0))
                        """
                        query_param += [user_id, token_name, 0, user_server, "CONFIRMED"]
                    elif coin_family == "VET":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                        FROM `vet_external_tx` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        sql += """
                        + (SELECT IFNULL((SELECT SUM(real_amount-real_deposit_fee)  
                        FROM `vet_move_deposit` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `confirmed_depth`> %s AND `user_server`=%s AND `status`=%s), 0))
                        """
                        query_param += [user_id, token_name, 0, user_server, "CONFIRMED"]
                    elif coin_family == "TRC-20":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                        FROM `trc20_external_tx` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s AND `sucess`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES", 1]
                        
                        sql += """
                        + (SELECT IFNULL((SELECT SUM(real_amount-real_deposit_fee)  
                        FROM `trc20_move_deposit` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `confirmed_depth`> %s AND `user_server`=%s AND `status`=%s), 0))
                        """
                        query_param += [user_id, token_name, confirmed_depth, user_server, "CONFIRMED"]
                    elif coin_family == "HNT":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(amount+withdraw_fee)  
                        FROM `hnt_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        address_memo = address.split()
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `hnt_get_transfers` 
                            WHERE `address`=%s AND `memo`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `time_insert`< %s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, nos_block, user_server]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `hnt_get_transfers` 
                            WHERE `address`=%s AND `memo`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, nos_block, user_server]

                    elif coin_family == "XRP":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(amount+tx_fee)  
                        FROM `xrp_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `xrp_get_transfers` 
                            WHERE `destination_tag`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `time_insert`< %s AND `user_server`=%s), 0))
                            """
                            query_param += [address, token_name, nos_block, user_server]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `xrp_get_transfers` 
                            WHERE `destination_tag`=%s AND `coin_name`=%s AND `amount`>0 AND `height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address, token_name, nos_block, user_server]
                    elif coin_family == "XLM":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(amount+withdraw_fee)  
                        FROM `xlm_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        address_memo = address.split()
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                                      FROM `xlm_get_transfers` 
                                      WHERE `address`=%s AND `memo`=%s 
                                      AND `coin_name`=%s AND `amount`>0 
                                      AND `time_insert`< %s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, nos_block, user_server]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `xlm_get_transfers` 
                            WHERE `address`=%s AND `memo`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, nos_block, user_server]
                    elif coin_family == "ADA":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                        FROM `ada_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount) 
                            FROM `ada_get_transfers` WHERE `output_address`=%s AND `direction`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `time_insert`< %s AND `user_server`=%s), 0))
                            """
                            query_param += [address, "incoming", token_name, nos_block, user_server]

                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount) 
                            FROM `ada_get_transfers` 
                            WHERE `output_address`=%s AND `direction`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `inserted_at_height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address, "incoming", token_name, nos_block, user_server]
                    elif coin_family == "SOL" or coin_family == "SPL":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                        FROM `sol_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        sql += """
                        + (SELECT IFNULL((SELECT SUM(real_amount-real_deposit_fee)  
                        FROM `sol_move_deposit` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `confirmed_depth`> %s AND `user_server`=%s AND `status`=%s), 0))
                        """
                        query_param += [user_id, token_name, confirmed_depth, user_server, "CONFIRMED"]
                    sql += """ AS mv_balance"""
                    await cur.execute(sql, tuple(query_param))
                    result = await cur.fetchone()
                    if result:
                        mv_balance = result['mv_balance']
                    else:
                        mv_balance = 0
                balance = {}
                try:
                    balance['adjust'] = 0
                    balance['mv_balance'] = float("%.6f" % mv_balance) if mv_balance else 0
                    balance['adjust'] = float("%.6f" % balance['mv_balance'])
                except Exception:
                    print("issue user_balance coin name: {}".format(token_name))
                    traceback.print_exc(file=sys.stdout)
                # Negative check
                try:
                    if balance['adjust'] < 0:
                        msg_negative = 'Negative balance detected:\nServer:' + user_server + '\nUser: ' + user_id + '\nToken: ' + token_name + '\nBalance: ' + str(
                            balance['adjust'])
                        await logchanbot(msg_negative)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                return balance
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("telegram user_balance " +str(traceback.format_exc()))

    async def swap_coin(
        self, userId: str, from_coin: str, from_amount: float, from_contract: str, from_decimal: int,
        to_coin: str, to_amount: float, to_contract: str, to_decimal: int, user_server: str
    ):
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
                    await cur.execute(sql, (
                        to_coin.upper(), to_contract, "SWAP", userId, "SWAP", "SWAP", to_amount, 0.0, to_decimal,
                        "SWAP",
                        currentTs, user_server, "SWAP", to_coin.upper(), user_server, -to_amount, currentTs, userId,
                        to_coin.upper(), user_server, to_amount, currentTs, from_coin.upper(), from_contract, userId,
                        "SWAP", "SWAP", "SWAP", from_amount, 0.0, from_decimal, "SWAP", currentTs, user_server, userId,
                        from_coin.upper(), user_server, -from_amount, currentTs, "SWAP", from_coin.upper(), user_server,
                        from_amount, currentTs))
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

    async def check_xlm_asset(
        self, url: str, asset_name: str, issuer: str, to_address: str, user_id: str,
        user_server: str
    ):
        found = False
        try:
            async with ServerAsync(
                    horizon_url=url, client=AiohttpClient()
            ) as server:
                account = await server.accounts().account_id(to_address).call()
                if 'balances' in account and len(account['balances']) > 0:
                    for each_balance in account['balances']:
                        if 'asset_code' in each_balance and 'asset_issuer' in each_balance and \
                            each_balance['asset_code'] == asset_name and issuer == each_balance['asset_issuer']:
                            found = True
                            break
        except Exception:
            await logchanbot(
                f"[{user_server}] [XLM]: Failed /withdraw by {user_id}. Account not found for address: "\
                f"{to_address} / asset_name: {asset_name}."
            )
        return found

    async def send_external_xlm(
        self, url: str, withdraw_keypair: str, user_id: str, amount: float, to_address: str,
        coin_decimal: int, user_server: str, coin: str, withdraw_fee: float,
        asset_ticker: str = None, asset_issuer: str = None, time_out=32
    ):
        coin_name = coin.upper()
        asset_sending = Asset.native()
        if coin_name != "XLM":
            asset_sending = Asset(asset_ticker, asset_issuer)
        tipbot_keypair = Stella_Keypair.from_secret(withdraw_keypair)
        async with ServerAsync(
                horizon_url=url, client=AiohttpClient()
        ) as server:
            tipbot_account = await server.load_account(tipbot_keypair.public_key)
            base_fee = 50000
            transaction = (
                TransactionBuilder(
                    source_account=tipbot_account,
                    network_passphrase=Network.PUBLIC_NETWORK_PASSPHRASE,
                    base_fee=base_fee,
                )
                # .add_text_memo("Hello, Stellar!")
                .append_payment_op(to_address, asset_sending, str(truncate(amount, 6)))
                .set_timeout(30)
                .build()
            )
            transaction.sign(tipbot_keypair)
            response = await server.submit_transaction(transaction)
            # print(response)
            fee = float(response['fee_charged']) / 10000000
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO xlm_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, 
                        `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (
                        coin_name, user_id, amount, fee, withdraw_fee, coin_decimal, to_address, int(time.time()),
                        response['hash'], user_server))
                        await conn.commit()
                        return response['hash']
            except Exception:
                await logchanbot("wallet send_external_xlm " + str(traceback.format_exc()))
                traceback.print_exc(file=sys.stdout)
        return None

@dp.message_handler(commands='start')
async def start_cmd_handler(message: types.Message):
    if message.chat.type != "private":
        return

    keyboard_markup = types.ReplyKeyboardMarkup(row_width=3)
    # default row_width is 3, so here we can omit it actually
    # kept for clearness
    await message.reply(
        "Hello, Welcome to TipBot!\nAvailable command: /balance, /withdraw, /tip, /deposit, /coinlist, /about",
        reply_markup=keyboard_markup)

@dp.message_handler(commands='about')
async def start_cmd_handler(message: types.Message):
    reply_text = text(
        bold("Thank you for checking:\n"),
        markdown.link("⚆ Twitter BotTipsTweet", "https://twitter.com/BotTipsTweet"),
        "\n",
        markdown.link("⚆ Discord", "https://chat.wrkz.work"),
        "\n",
        markdown.link("⚆ Telegram", "https://t.me/wrkzcoinchat"),
        "\n",
        "⚆ Run by TipBot Team"
    )
    await message.reply(reply_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    return

@dp.message_handler(commands='coinlist')
async def start_cmd_handler(message: types.Message):
    WalletAPI = WalletTG()
    await WalletAPI.get_coin_setting()
    coin_list_name = ", ".join(WalletAPI.coin_list_name)
    message_text = text(bold('INFO COIN LIST:'),
                        markdown.pre(f"{coin_list_name}"))
    await message.reply(message_text,
                        parse_mode=ParseMode.MARKDOWN_V2)
    return

@dp.message_handler(commands='deposit')
async def start_cmd_handler(message: types.Message):
    content = ' '.join(message.text.split())
    args = content.split(" ")
    if message.chat.type != "private":
        reply_text = "Please do via direct message with me!"
        await message.reply(reply_text)
        return

    if message.from_user.username is None:
        reply_text = "I can not get your username. Please set!"
        await message.reply(reply_text)
        return

    WalletAPI = WalletTG()
    await WalletAPI.get_coin_setting()

    if len(args) != 2:
        ## Form
        await Form_Deposit.coin_name.set()
        message_text = text(bold('PICK COIN FROM LIST:'),
                            markdown.pre(", ".join(WalletAPI.coin_list_name)))
        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        coin_name = args[1].upper()
        if not hasattr(WalletAPI.coin_list, coin_name):
            message_text = text(bold('ERROR:'),
                                markdown.pre(f"{coin_name} does not exist with us."))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
            return
        else:
            if getattr(getattr(WalletAPI.coin_list, coin_name), "is_maintenance") == 1:
                message_text = text(bold('ERROR:'),
                                    markdown.pre(f"{coin_name} is currently under maintenance."))
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return
            ############
            tg_user = message.from_user.username
            chat_id = message.chat.id
            net_name = getattr(getattr(WalletAPI.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(WalletAPI.coin_list, coin_name), "type")
            contract = getattr(getattr(WalletAPI.coin_list, coin_name), "contract")
            explorer_link = getattr(getattr(WalletAPI.coin_list, coin_name), "explorer_link")
            deposit_note = getattr(getattr(WalletAPI.coin_list, coin_name), "deposit_note")

            get_deposit = await WalletAPI.sql_get_userwallet(
                tg_user, coin_name, net_name, type_coin, SERVER_BOT, message.chat.id
            )
            if get_deposit is None:
                get_deposit = await WalletAPI.sql_register_user(
                    tg_user, coin_name, net_name, type_coin, SERVER_BOT, chat_id, 0
                )
            message_text = text(markdown.bold(f"DEPOSIT {coin_name} INFO:\n") + \
                                markdown.pre("Deposit:       " + get_deposit['balance_wallet_address'])
                                )
            if deposit_note:
                message_text += text(bold('NOTE:'),
                                     markdown.pre(deposit_note))

            keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
            if explorer_link is not None and explorer_link.startswith("http"):
                keyboard_markup.add(
                    # url buttons have no callback data
                    types.InlineKeyboardButton('Explorer Link', url=explorer_link),
                )
            else:
                keyboard_markup = None

            # message_text += text(markdown.link("Link to Explorer", explorer_link))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True,
                                reply_markup=keyboard_markup)
            await WalletAPI.update_user_balance_call(tg_user, type_coin)


class Form_Balance(StatesGroup):
    coin_name = State()  # Will be represented in storage as 'Form_Balance:coin_name'


class Form_Deposit(StatesGroup):
    coin_name = State()  # Will be represented in storage as 'Form_Deposit:coin_name'


@dp.message_handler(state=Form_Deposit.coin_name)
async def process_deposit_coin_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['coin_name'] = message.text.upper()
        WalletAPI = WalletTG()
        await WalletAPI.get_coin_setting()
        if data['coin_name'].upper() == "CANCEL":
            message_text = text(bold('CANCELLED:'),
                                markdown.pre(f"Action cancelled. Thank you!"))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
        elif data['coin_name'].upper() not in WalletAPI.coin_list_name + ["ALL"]:
            message_text = text(bold('PICK COIN FROM LIST:'),
                                markdown.pre(", ".join(WalletAPI.coin_list_name)))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            coin_name = data['coin_name']
            if getattr(getattr(WalletAPI.coin_list, coin_name), "is_maintenance") == 1 \
                    or getattr(getattr(WalletAPI.coin_list, coin_name), "enable_deposit") != 1:
                message_text = text(bold('ERROR:'),
                                    markdown.pre(f"{coin_name} is currently under maintenance or disable deposit."))
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                ############
                tg_user = message.from_user.username
                chat_id = message.chat.id
                net_name = getattr(getattr(WalletAPI.coin_list, coin_name), "net_name")
                type_coin = getattr(getattr(WalletAPI.coin_list, coin_name), "type")
                contract = getattr(getattr(WalletAPI.coin_list, coin_name), "contract")
                explorer_link = getattr(getattr(WalletAPI.coin_list, coin_name), "explorer_link")
                deposit_note = getattr(getattr(WalletAPI.coin_list, coin_name), "deposit_note")

                get_deposit = await WalletAPI.sql_get_userwallet(
                    tg_user, coin_name, net_name, type_coin, SERVER_BOT, message.chat.id
                )
                if get_deposit is None:
                    get_deposit = await WalletAPI.sql_register_user(
                        tg_user, coin_name, net_name, type_coin, SERVER_BOT, chat_id, 0
                    )
                message_text = text(markdown.bold(f"DEPOSIT {coin_name} INFO:\n") + \
                                    markdown.pre("Deposit:       " + get_deposit['balance_wallet_address'])
                                    )
                if deposit_note:
                    message_text += text(bold('NOTE:'),
                                         markdown.pre(deposit_note))

                keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
                if explorer_link is not None and explorer_link.startswith("http"):
                    keyboard_markup.add(
                        # url buttons have no callback data
                        types.InlineKeyboardButton('Explorer Link', url=explorer_link),
                    )
                else:
                    keyboard_markup = None

                # message_text += text(markdown.link("Link to Explorer", explorer_link))
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True,
                                    reply_markup=keyboard_markup)
                await WalletAPI.update_user_balance_call(tg_user, type_coin)
        await state.finish()


@dp.message_handler(state=Form_Balance.coin_name)
async def process_coin_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['coin_name'] = message.text.upper()
        WalletAPI = WalletTG()
        await WalletAPI.get_coin_setting()
        if data['coin_name'].upper() == "CANCEL":
            message_text = text(bold('CANCELLED:'),
                                markdown.pre(f"Action cancelled. Thank you!"))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
            await state.finish()
            return
        elif data['coin_name'].upper() not in WalletAPI.coin_list_name + ["ALL"]:
            message_text = text(bold('PICK COIN FROM LIST (or ALL):'),
                                markdown.pre(", ".join(WalletAPI.coin_list_name)))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            coin_name = data['coin_name']
            #######
            has_none_balance = True
            zero_tokens = []
            unknown_tokens = []
            tg_user = message.from_user.username
            chat_id = message.chat.id
            list_coin_balances = {}
            if coin_name in ["LIST", "ALL"]:
                coin_list = WalletAPI.coin_list_name
            else:
                coin_list = [coin_name]
            for each in coin_list:
                coin_name = each.upper()
                if coin_name in WalletAPI.coin_list_name:
                    type_coin = getattr(getattr(WalletAPI.coin_list, coin_name), "type")
                    net_name = getattr(getattr(WalletAPI.coin_list, coin_name), "net_name")
                    deposit_confirm_depth = getattr(getattr(WalletAPI.coin_list, coin_name), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(WalletAPI.coin_list, coin_name), "decimal")
                    token_display = getattr(getattr(WalletAPI.coin_list, coin_name), "display_name")
                    usd_equivalent_enable = getattr(getattr(WalletAPI.coin_list, coin_name), "usd_equivalent_enable")

                    get_deposit = await WalletAPI.sql_get_userwallet(
                        tg_user, coin_name, net_name, type_coin, SERVER_BOT, message.chat.id
                    )
                    if get_deposit is None:
                        get_deposit = await WalletAPI.sql_register_user(
                            tg_user, coin_name, net_name, type_coin, SERVER_BOT, chat_id, 0
                        )
                    wallet_address = get_deposit['balance_wallet_address']
                    if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        wallet_address = get_deposit['paymentid']
                    height = None
                    try:
                        await WalletAPI.update_user_balance_call(tg_user, type_coin)

                        if type_coin in ["ERC-20", "TRC-20"]:
                            height = WalletAPI.get_cache_kv(
                                "block",
                                f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{net_name}"
                            )
                        elif type_coin in ["XLM", "NEO", "VITE"]:
                            height = WalletAPI.get_cache_kv(
                                "block",
                                f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{type_coin}"
                            )
                        else:
                            height = WalletAPI.get_cache_kv(
                                "block",
                                f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{coin_name}"
                            )
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    userdata_balance = await WalletAPI.user_balance(
                        tg_user, coin_name, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT
                    )
                    total_balance = userdata_balance['adjust']
                    if total_balance == 0:
                        zero_tokens.append(coin_name)
                        continue
                    elif total_balance > 0:
                        has_none_balance = False
                        list_coin_balances[coin_name] = num_format_coin(total_balance, coin_name, coin_decimal, False)
                else:
                    unknown_tokens.append(coin_name)

            if has_none_balance == True:
                coin_text = ""
                if len(coin_list) == 1: coin_text = "{} ".format(coin_name)
                message_text = text(bold('ERROR:'), markdown.pre(f"You don't have any {coin_text}balance."))
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                balance_list = []
                for k, v in list_coin_balances.items():
                    balance_list.append("{}: {}".format(k, v))
                message_text = text(bold('BALANCE:'), markdown.pre("\n".join(balance_list)))
                if len(zero_tokens) > 0:
                    message_text += text(bold('ZERO BALANCE:'), markdown.pre(", ".join(zero_tokens)))
                if len(unknown_tokens) > 0:
                    message_text += text(bold('UNKNOWN COIN/TOKEN:'), markdown.pre(", ".join(unknown_tokens)))
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
            await state.finish()

@dp.message_handler(commands='balance')
async def start_cmd_handler(message: types.Message):
    content = ' '.join(message.text.split())
    args = content.split(" ")
    if message.chat.type != "private":
        reply_text = "Please do via direct message with me!"
        await message.reply(reply_text)
        return

    if message.from_user.username is None:
        reply_text = "I can not get your username. Please set!"
        await message.reply(reply_text)
        return

    WalletAPI = WalletTG()
    await WalletAPI.get_coin_setting()

    if len(args) < 2:
        ## Form
        await Form_Balance.coin_name.set()
        message_text = text(
            bold('PICK COIN FROM LIST (or ALL):'),
            markdown.pre(", ".join(WalletAPI.coin_list_name))
        )
        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)

    elif len(args) >= 2:
        has_none_balance = True
        zero_tokens = []
        unknown_tokens = []
        tg_user = message.from_user.username
        chat_id = message.chat.id
        list_coin_balances = {}
        if args[1].upper() in ["LIST", "ALL"]:
            coin_list = WalletAPI.coin_list_name
        else:
            coin_list = args[1:]
        for each in coin_list:
            coin_name = each.upper()
            if coin_name in WalletAPI.coin_list_name:
                type_coin = getattr(getattr(WalletAPI.coin_list, coin_name), "type")
                net_name = getattr(getattr(WalletAPI.coin_list, coin_name), "net_name")
                deposit_confirm_depth = getattr(getattr(WalletAPI.coin_list, coin_name), "deposit_confirm_depth")
                coin_decimal = getattr(getattr(WalletAPI.coin_list, coin_name), "decimal")
                token_display = getattr(getattr(WalletAPI.coin_list, coin_name), "display_name")
                usd_equivalent_enable = getattr(getattr(WalletAPI.coin_list, coin_name), "usd_equivalent_enable")

                get_deposit = await WalletAPI.sql_get_userwallet(
                    tg_user, coin_name, net_name, type_coin, SERVER_BOT, message.chat.id
                )
                if get_deposit is None:
                    get_deposit = await WalletAPI.sql_register_user(
                        tg_user, coin_name, net_name, type_coin, SERVER_BOT, chat_id, 0
                    )
                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                height = None
                try:
                    await WalletAPI.update_user_balance_call(tg_user, type_coin)
                    if type_coin in ["ERC-20", "TRC-20"]:
                        height = WalletAPI.get_cache_kv(
                            "block",
                            f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{net_name}"
                        )
                    elif type_coin in ["XLM", "NEO", "VITE"]:
                        height = WalletAPI.get_cache_kv(
                            "block",
                            f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{type_coin}"
                        )
                    else:
                        height = WalletAPI.get_cache_kv(
                            "block",
                            f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{coin_name}"
                        )
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                userdata_balance = await WalletAPI.user_balance(
                    tg_user, coin_name, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT
                )
                total_balance = userdata_balance['adjust']
                if total_balance == 0:
                    zero_tokens.append(coin_name)
                    continue
                elif total_balance > 0:
                    has_none_balance = False
                    list_coin_balances[coin_name] = num_format_coin(total_balance, coin_name, coin_decimal, False)
            else:
                unknown_tokens.append(coin_name)

        if has_none_balance == True:
            coin_text = ""
            if len(coin_list) == 1: coin_text = "{} ".format(coin_name)
            message_text = text(bold('ERROR:'), markdown.pre(f"You don't have any {coin_text}balance."))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
            return
        else:
            balance_list = []
            for k, v in list_coin_balances.items():
                balance_list.append("{}: {}".format(k, v))
            message_text = text(bold('BALANCE:'), markdown.pre("\n".join(balance_list)))
            if len(zero_tokens) > 0:
                message_text += text(bold('ZERO BALANCE:'), markdown.pre(", ".join(zero_tokens)))
            if len(unknown_tokens) > 0:
                message_text += text(bold('UNKNOWN COIN/TOKEN:'), markdown.pre(", ".join(unknown_tokens)))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
            return

@dp.message_handler(commands='tip')
async def start_cmd_handler(message: types.Message):
    if message.from_user.username is None:
        reply_text = "I can not get your username. Please set!"
        await message.reply(reply_text)
        return

    content = ' '.join(message.text.split())
    args = content.split(" ")
    # there could be more than one receivers
    # Example /tip 10 doge @mention_1 @mention_2 @mention_3 ....ddfd @mention_4 last text

    receivers = []
    no_wallet_receivers = []
    last_receiver = ""
    comment = ""

    WalletAPI = WalletTG()
    await WalletAPI.get_coin_setting()
    try:
        if len(args) < 3:
            message_text = text(bold('ERROR:'), markdown.pre("Please use /tip amount coin @telegramuser"))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
            return
        elif len(args) == 3:
            if message.reply_to_message and message.reply_to_message.from_user.username:
                pass
            else:
                message_text = text(bold('ERROR:'), markdown.pre("Please use /tip amount coin @telegramuser"))
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return

        amount = args[1].replace(",", "")
        coin_name = args[2].upper()
        chat_id = message.chat.id
        if not hasattr(WalletAPI.coin_list, coin_name):
            message_text = text(bold('ERROR:'),
                                markdown.pre(f"{coin_name} does not exist with us."))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
            return
        else:
            net_name = getattr(getattr(WalletAPI.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(WalletAPI.coin_list, coin_name), "type")
            token_display = getattr(getattr(WalletAPI.coin_list, coin_name), "display_name")
            contract = getattr(getattr(WalletAPI.coin_list, coin_name), "contract")
            coin_decimal = getattr(getattr(WalletAPI.coin_list, coin_name), "decimal")
            deposit_confirm_depth = getattr(getattr(WalletAPI.coin_list, coin_name), "deposit_confirm_depth")

            MinTip = getattr(getattr(WalletAPI.coin_list, coin_name), "real_min_tip")
            MaxTip = getattr(getattr(WalletAPI.coin_list, coin_name), "real_max_tip")
            usd_equivalent_enable = getattr(getattr(WalletAPI.coin_list, coin_name), "usd_equivalent_enable")

            wallet_address = None
            get_tipper = await WalletAPI.sql_get_userwallet(
                message.from_user.username, coin_name, net_name, type_coin, SERVER_BOT, None
            )
            if get_tipper is None:
                message_text = text(bold('ERROR:'), markdown.pre(
                    f"You do not have a wallet with me yet. Please try /deposit {coin_name} in direct message with me."))
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return
            else:
                wallet_address = get_tipper['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_tipper['paymentid']

            if getattr(getattr(WalletAPI.coin_list, coin_name), "is_maintenance") == 1:
                message_text = text(bold('ERROR:'),
                                    markdown.pre(f"{coin_name} is currently under maintenance."))
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return
            if getattr(getattr(WalletAPI.coin_list, coin_name), "enable_tip") != 1:
                message_text = text(bold('ERROR:'),
                                    markdown.pre(f"{coin_name} tipping is currently disable."))
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return

            ## Check amount
            height = None
            try:
                if type_coin in ["ERC-20", "TRC-20"]:
                    height = WalletAPI.get_cache_kv(
                        "block",
                        f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{net_name}"
                    )
                elif type_coin in ["XLM", "NEO", "VITE"]:
                    height = WalletAPI.get_cache_kv(
                        "block",
                        f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{type_coin}"
                    )
                else:
                    height = WalletAPI.get_cache_kv(
                        "block",
                        f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{coin_name}"
                    )
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            all_amount = False
            if not amount.isdigit() and amount.upper() == "ALL":
                all_amount = True
                userdata_balance = await store.sql_user_balance_single(
                    message.from_user.username, coin_name,
                    wallet_address, type_coin, height,
                    deposit_confirm_depth, SERVER_BOT
                )
                amount = float(userdata_balance['adjust'])
            else:
                amount = amount.replace(",", "")
                amount = text_to_num(amount)
                if amount is None:
                    message_text = text(bold('ERROR:'),
                                        markdown.pre(f"Invalid given amount."))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    return
            # end of check if amount is all
            ######
            # /tip amount coin @mention @mention...                 
            if len(args) > 3:
                for each in args[3:]:
                    if each.startswith("@"):
                        last_receiver = each
                        tg_user = each[1:]  # remove first @
                        if len(tg_user) == 0:
                            continue
                        if not tg_user.replace('_', '').replace(',', '').isalnum:
                            no_wallet_receivers.append(tg_user)
                        else:
                            # Check user in wallet
                            tg_user = tg_user.replace(',', '')
                            if len(tg_user) < 5:
                                no_wallet_receivers.append(tg_user)
                            else:
                                # m = await bot.get_chat_member(chat_id, tg_user)
                                # print(m)
                                get_deposit = await WalletAPI.sql_get_userwallet(
                                    tg_user, coin_name, net_name, type_coin, SERVER_BOT, None
                                )
                                if get_deposit is None and tg_user.lower() != "teletip_bot":
                                    no_wallet_receivers.append(tg_user)
                                elif tg_user.lower() == "teletip_bot" or get_deposit is not None:
                                    receivers.append(tg_user)
            # Check if reply to
            if message.reply_to_message and message.reply_to_message.from_user.username and message.reply_to_message.from_user.username not in receivers:
                receivers.append(message.reply_to_message.from_user.username)
            # Unique: receivers
            receivers = set(list(receivers))
            # Remove author if exist
            if len(receivers) > 0 and message.from_user.username in receivers:
                receivers.remove(message.from_user.username)

            if len(receivers) == 0:
                message_text = text(bold('ERROR:'),
                                    markdown.pre(f"There is no one tip to."))
                if len(no_wallet_receivers) > 0:
                    message_text += text(bold('USER NO WALLET:'),
                                         markdown.pre("{}".format(", ".join(no_wallet_receivers))))
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return
            else:
                userdata_balance = await store.sql_user_balance_single(
                    message.from_user.username, coin_name,
                    wallet_address, type_coin, height,
                    deposit_confirm_depth, SERVER_BOT
                )
                actual_balance = float(userdata_balance['adjust'])
                try:
                    comment = message.text.split(last_receiver)[-1].strip()
                except Exception as e:
                    pass

                if amount <= 0:
                    message_text = text(bold('ERROR:'),
                                        markdown.pre(f"Please get more {token_display}."))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    return

                if amount < MinTip or amount > MaxTip:
                    message_text = text(
                        bold('ERROR:'),
                        markdown.pre(f"Transactions cannot be smaller than {num_format_coin(MinTip, coin_name, coin_decimal, False)} "\
                            f"{token_display} or bigger than {num_format_coin(MaxTip, coin_name, coin_decimal, False)} {token_display}"
                        )
                    )
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    return
                elif amount * len(receivers) > actual_balance:
                    message_text = text(bold('ERROR:'),
                                        markdown.pre(
                                            f"Insufficient balance to tip total of {num_format_coin(amount * len(receivers), coin_name, coin_decimal, False)} {token_display}."))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    return
                # start checking to tip

                if message.from_user.username not in TX_IN_PROGRESS:
                    TX_IN_PROGRESS.append(message.from_user.username)
                    try:
                        equivalent_usd = ""
                        amount_in_usd = 0.0
                        if usd_equivalent_enable == 1:
                            native_token_name = getattr(getattr(WalletAPI.coin_list, coin_name), "native_token_name")
                            COIN_NAME_FOR_PRICE = coin_name
                            if native_token_name:
                                COIN_NAME_FOR_PRICE = native_token_name
                            if COIN_NAME_FOR_PRICE in WalletAPI.token_hints:
                                id = WalletAPI.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                                per_unit = WalletAPI.coin_paprika_id_list[id]['price_usd']
                            else:
                                per_unit = WalletAPI.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
                            if per_unit and per_unit > 0:
                                amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                                if amount_in_usd > 0.0001:
                                    equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
                        tiptype = "TIP"
                        if len(receivers) > 1:
                            tiptype = "TIPS"
                        tips = await store.sql_user_balance_mv_multiple(
                            message.from_user.username, receivers,
                            str(chat_id), str(chat_id), float(amount),
                            coin_name, tiptype, coin_decimal, SERVER_BOT,
                            contract, float(amount_in_usd), None
                        )
                        message_text = text(bold(
                            'TIPPED: {} {}{}'.format(num_format_coin(amount, coin_name, coin_decimal, False), coin_name,
                                                     equivalent_usd)),
                            markdown.pre("{}".format(", ".join(receivers))))
                        if len(no_wallet_receivers) > 0:
                            message_text += text(
                                bold('USER NO WALLET:'),
                                markdown.pre("{}".format(", ".join(no_wallet_receivers)))
                            )
                        if len(comment) > 0:
                            message_text += text(
                                bold('COMMENT:'),
                                markdown.pre(comment)
                            )
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                        # Try to DM users
                        for user_to in receivers:
                            try:
                                get_each_receiver = await WalletAPI.sql_get_userwallet(
                                    user_to, coin_name, net_name,
                                    type_coin, SERVER_BOT, None
                                )
                                if get_each_receiver is not None and get_each_receiver['chat_id']:
                                    to_user = get_each_receiver['chat_id']
                                    to_message_text = text(
                                        bold(f"You got a tip from "),
                                        escape_md("@{}".format(message.from_user.username)),
                                        markdown.pre("Amount: {} {}".format(
                                            num_format_coin(amount, coin_name, coin_decimal, False),
                                            coin_name)
                                        )
                                    )
                                    if to_user:
                                        try:
                                            if user_to == "teletip_bot":
                                                await logchanbot(
                                                    f"[{SERVER_BOT}] A user tipped {num_format_coin(amount, coin_name, coin_decimal, False)} "\
                                                    f"{coin_name} to {user_to}"
                                                )
                                            else:
                                                await bot.send_message(
                                                    chat_id=to_user, text=to_message_text,
                                                    parse_mode=ParseMode.MARKDOWN_V2
                                                )
                                        except exceptions.BotBlocked:
                                            await logchanbot(f"[{SERVER_BOT}] {coin_name} Target [ID]: blocked by user {user_to}")
                                        except exceptions.ChatNotFound:
                                            await logchanbot(f"{SERVER_BOT} Target [ID:{to_user}]: invalid user ID")
                                        except exceptions.RetryAfter as e:
                                            await logchanbot(
                                                f"{SERVER_BOT} Target [ID:{to_user}]: Flood limit is exceeded. Sleep {e.timeout} seconds.")
                                            await asyncio.sleep(e.timeout)
                                            await bot.send_message(chat_id=to_user, text=to_message_text,
                                                                   parse_mode=ParseMode.MARKDOWN_V2)  # Recursive call
                                        except exceptions.UserDeactivated:
                                            await logchanbot(f"{SERVER_BOT} Target [ID:{to_user}]: user is deactivated")
                                        except exceptions.TelegramAPIError:
                                            await logchanbot(f"{SERVER_BOT} Target [ID:{to_user}]: failed")
                                        except Exception as e:
                                            await logchanbot(traceback.print_exc(file=sys.stdout))
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                    TX_IN_PROGRESS.remove(message.from_user.username)
                else:
                    message_text = text(bold('ERROR:'),
                                        markdown.pre("You have another tx in process. Please wait it to finish."))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

@dp.message_handler(commands='withdraw')
async def start_cmd_handler(message: types.Message):
    if message.from_user.username is None:
        message_text = text(bold('ERROR:'), markdown.pre("I can not get your username. Please set!"))
        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
        return

    if message.chat.type != "private":
        reply_text = "Please do via direct message with me!"
        await message.reply(reply_text)
        return

    send_all = False
    content = ' '.join(message.text.split())
    args = content.split(" ")
    if len(args) != 4:
        message_text = text(bold('ERROR:'),
                            markdown.pre("Please use /withdraw amount coin address"))
        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
        return

    amount = args[1].replace(",", "")
    coin_name = args[2].upper()
    address = args[3]
    WalletAPI = WalletTG()
    await WalletAPI.get_coin_setting()
    if not hasattr(WalletAPI.coin_list, coin_name):
        message_text = text(bold('ERROR:'),
                            markdown.pre(f"{coin_name} does not exist with us."))
        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
        return
    else:
        if getattr(getattr(WalletAPI.coin_list, coin_name), "is_maintenance") == 1:
            message_text = text(bold('ERROR:'),
                                markdown.pre(f"{coin_name} is currently under maintenance."))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
            return
        if getattr(getattr(WalletAPI.coin_list, coin_name), "enable_withdraw") != 1:
            message_text = text(bold('ERROR:'),
                                markdown.pre(f"{coin_name} withdraw is currently disable."))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
            return
        ######
        tg_user = message.from_user.username
        chat_id = message.chat.id
        net_name = getattr(getattr(WalletAPI.coin_list, coin_name), "net_name")
        type_coin = getattr(getattr(WalletAPI.coin_list, coin_name), "type")
        deposit_confirm_depth = getattr(getattr(WalletAPI.coin_list, coin_name), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(WalletAPI.coin_list, coin_name), "decimal")
        MinTx = getattr(getattr(WalletAPI.coin_list, coin_name), "real_min_tx")
        MaxTx = getattr(getattr(WalletAPI.coin_list, coin_name), "real_max_tx")
        NetFee = getattr(getattr(WalletAPI.coin_list, coin_name), "real_withdraw_fee")
        tx_fee = getattr(getattr(WalletAPI.coin_list, coin_name), "tx_fee")
        usd_equivalent_enable = getattr(getattr(WalletAPI.coin_list, coin_name), "usd_equivalent_enable")
        try:
            check_exist = await WalletAPI.check_withdraw_coin_address(type_coin, address)
            if check_exist is not None:
                message_text = text(
                    bold('ERROR:'),
                    markdown.pre(f"You cannot withdraw to this address: {address}.")
                )
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        if tx_fee is None:
            tx_fee = NetFee
        token_display = getattr(getattr(WalletAPI.coin_list, coin_name), "display_name")
        contract = getattr(getattr(WalletAPI.coin_list, coin_name), "contract")
        fee_limit = getattr(getattr(WalletAPI.coin_list, coin_name), "fee_limit")
        get_deposit = await WalletAPI.sql_get_userwallet(
            tg_user, coin_name, net_name, type_coin, SERVER_BOT, message.chat.id
        )
        if get_deposit is None:
            get_deposit = await WalletAPI.sql_register_user(
                tg_user, coin_name, net_name, type_coin, SERVER_BOT, chat_id, 0
            )

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']

        # Check if tx in progress
        if tg_user in TX_IN_PROGRESS:
            message_text = text(bold('ERROR:'),
                                markdown.pre(f"You have another tx in progress.."))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
            return

        height = None
        try:
            if type_coin in ["ERC-20", "TRC-20"]:
                height = WalletAPI.get_cache_kv(
                    "block",
                    f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{net_name}"
                )
            elif type_coin in ["XLM", "NEO", "VITE"]:
                height = WalletAPI.get_cache_kv(
                    "block",
                    f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{type_coin}"
                )
            else:
                height = WalletAPI.get_cache_kv(
                    "block",
                    f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{coin_name}"
                )

        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if height is None:
            message_text = text(
                bold('ERROR:'),
                markdown.pre(f"INFO {coin_name}, I cannot pull information from network. Try again later.")
            )
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
            return
        else:
            # check if amount is all
            all_amount = False
            if not amount.isdigit() and amount.upper() == "ALL":
                all_amount = True
                userdata_balance = await WalletAPI.user_balance(
                    tg_user, coin_name, wallet_address, type_coin, height,
                    deposit_confirm_depth, SERVER_BOT
                )
                amount = float(userdata_balance['adjust']) - NetFee
            else:
                amount = amount.replace(",", "")
                amount = text_to_num(amount)
                if amount is None:
                    message_text = text(
                        bold('ERROR:'),
                        markdown.pre(f"Invalid given amount.")
                    )
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    return

            if getattr(getattr(WalletAPI.coin_list, coin_name), "integer_amount_only") == 1:
                amount = int(amount)

            # end of check if amount is all
            amount = float(amount)
            userdata_balance = await WalletAPI.user_balance(
                tg_user, coin_name, wallet_address, type_coin, height,
                deposit_confirm_depth, SERVER_BOT
            )
            actual_balance = float(userdata_balance['adjust'])

            # If balance 0, no need to check anything
            if actual_balance <= 0:
                message_text = text(
                    bold('ERROR:'),
                    markdown.pre(f"please check your {token_display} balance.")
                )
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return
            if amount > actual_balance:
                message_text = text(
                    bold('ERROR:'),
                    markdown.pre(f"Insufficient balance to send out {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}.")
                )
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return

            if amount + NetFee > actual_balance:
                message_text = text(
                    bold('ERROR:'),
                    markdown.pre(f"Insufficient balance to send out {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}."\
                        f" You need to leave at least network fee: {num_format_coin(NetFee, coin_name, coin_decimal, False)} {token_display}."
                    )
                )
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return
            elif amount < MinTx or amount > MaxTx:
                message_text = text(
                    bold('ERROR:'),
                    markdown.pre(f"Transaction cannot be smaller than {num_format_coin(MinTx, coin_name, coin_decimal, False)} {token_display} "\
                        f"or bigger than {num_format_coin(MaxTx, coin_name, coin_decimal, False)} {token_display}."
                    )
                )
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return

            try:
                key_withdraw = tg_user + "_" + coin_name
                if key_withdraw in withdraw_tx:
                    msg = "You recently executed a withdraw of this coin/token {coin_name}. "\
                        "Waiting a few seconds more and re-try."
                    message_text = text(bold('ERROR:'),
                                        markdown.pre(msg))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    return
                else:
                    withdraw_tx[key_withdraw] = int(time.time())
            except Exception:
                pass

            equivalent_usd = ""
            total_in_usd = 0.0
            if usd_equivalent_enable == 1:
                native_token_name = getattr(getattr(WalletAPI.coin_list, coin_name), "native_token_name")
                COIN_NAME_FOR_PRICE = coin_name
                if native_token_name:
                    COIN_NAME_FOR_PRICE = native_token_name
                if COIN_NAME_FOR_PRICE in WalletAPI.token_hints:
                    id = WalletAPI.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                    per_unit = WalletAPI.coin_paprika_id_list[id]['price_usd']
                else:
                    per_unit = WalletAPI.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
                if per_unit and per_unit > 0:
                    total_in_usd = float(Decimal(amount) * Decimal(per_unit))
                    if total_in_usd >= 0.0001:
                        equivalent_usd = " ~ {:,.4f} USD".format(total_in_usd)

            if type_coin in ["ERC-20"]:
                # Check address
                valid_address = WalletAPI.check_address_erc20(address)
                valid = False
                if valid_address and valid_address.upper() == address.upper():
                    valid = True
                else:
                    message_text = text(bold('ERROR:'),
                                        markdown.pre(f"Invalid address:\n{address}"))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    return

                send_tx = None
                if tg_user not in TX_IN_PROGRESS:
                    TX_IN_PROGRESS.append(tg_user)
                    try:
                        url = WalletAPI.erc_node_list[net_name]
                        chain_id = getattr(getattr(WalletAPI.coin_list, coin_name), "chain_id")
                        send_tx = await WalletAPI.send_external_erc20(
                            url, net_name, tg_user, address, amount, coin_name,
                            coin_decimal, NetFee, SERVER_BOT, chain_id,
                            contract
                        )
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                    WalletAPI.remove(tg_user)
                else:
                    message_text = text(bold('ERROR:'),
                                        markdown.pre("You have another tx in process. Please wait it to finish."))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    return

                if send_tx:
                    fee_txt = "\nWithdrew fee/node: {} {}.".format(
                        num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                    try:
                        msg = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to {address}.\nTransaction hash: {send_tx}{fee_txt}'
                        message_text = text(bold('COMPLETED:'),
                                            markdown.pre(msg))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    try:
                        await log_to_channel(
                            "withdraw",
                            f"[{SERVER_BOT}] User {tg_user} sucessfully withdrew "\
                            f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                            f"{token_display}{equivalent_usd}"
                        )
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                return
            elif type_coin in ["TRC-20", "TRC-10"]:
                # TODO: validate address
                send_tx = None
                if tg_user not in TX_IN_PROGRESS:
                    TX_IN_PROGRESS.append(tg_user)
                    try:
                        send_tx = await WalletAPI.send_external_trc20(
                            tg_user, address, amount, coin_name, coin_decimal,
                            NetFee, SERVER_BOT, fee_limit, type_coin, contract
                        )
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                    TX_IN_PROGRESS.remove(tg_user)
                else:
                    message_text = text(bold('ERROR:'),
                                        markdown.pre("You have another tx in process. Please wait it to finish."))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    return

                if send_tx:
                    fee_txt = "\nWithdrew fee/node: {} {}.".format(
                        num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                    try:
                        msg = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to {address}.\nTransaction hash: {send_tx}{fee_txt}'
                        message_text = text(bold('COMPLETED:'),
                                            markdown.pre(msg))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    try:
                        await log_to_channel(
                            "withdraw",
                            f"[{SERVER_BOT}] User {tg_user} sucessfully withdrew "\
                            f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                            f"{token_display}{equivalent_usd}"
                        )
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                return
            elif type_coin == "NANO":
                valid_address = await WalletAPI.nano_validate_address(coin_name, address)
                if not valid_address == True:
                    msg = f"Address: {address} is invalid."
                    message_text = text(bold('ERROR:'),
                                        markdown.pre(msg))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    return
                else:
                    if tg_user not in TX_IN_PROGRESS:
                        TX_IN_PROGRESS.append(tg_user)
                        try:
                            main_address = getattr(getattr(WalletAPI.coin_list, coin_name), "MainAddress")
                            send_tx = await WalletAPI.send_external_nano(
                                main_address, tg_user, amount, address,
                                coin_name, coin_decimal
                            )
                            if send_tx:
                                fee_txt = "\nWithdrew fee/node: 0.00 {}.".format(coin_name)
                                send_tx_hash = send_tx['block']
                                msg = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to {address}.\nTransaction hash: {send_tx_hash}{fee_txt}'
                                message_text = text(bold('COMPLETED:'),
                                                    markdown.pre(msg))
                                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                                await log_to_channel(
                                    "withdraw",
                                    f"[{SERVER_BOT}] User {tg_user} successfully withdrew "\
                                    f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                                    f"{token_display}{equivalent_usd}."
                                )
                            else:
                                await log_to_channel(
                                    "withdraw",
                                    f"[{SERVER_BOT}] [FAILED] User {tg_user} failed to withdraw "\
                                    f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                                    f"{token_display}{equivalent_usd}."
                                )
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                        TX_IN_PROGRESS.remove(tg_user)
                    else:
                        message_text = text(bold('ERROR:'),
                                            markdown.pre("You have another tx in process. Please wait it to finish."))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    return
            elif type_coin == "CHIA":
                if tg_user not in TX_IN_PROGRESS:
                    TX_IN_PROGRESS.append(tg_user)
                    send_tx = await WalletAPI.send_external_xch(
                        tg_user, amount, address, coin_name, coin_decimal, tx_fee, NetFee, SERVER_BOT
                    )
                    if send_tx:
                        fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                            num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                        await log_to_channel(
                            "withdraw",
                            f"[{SERVER_BOT}] User {tg_user} successfully withdrew "\
                            f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                            f"{token_display}{equivalent_usd}."
                        )
                        msg = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to {address}.\nTransaction hash: {send_tx}{fee_txt}'
                        message_text = text(bold('COMPLETED:'),
                                            markdown.pre(msg))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    else:
                        await log_to_channel(
                            "withdraw",
                            f"[{SERVER_BOT}] [FAILED] User {tg_user} failed to withdraw "\
                            f"{num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}."
                        )
                    TX_IN_PROGRESS.remove(tg_user)
                else:
                    message_text = text(bold('ERROR:'),
                                        markdown.pre("You have another tx in process. Please wait it to finish."))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return
            elif type_coin == "HNT":
                if tg_user not in TX_IN_PROGRESS:
                    TX_IN_PROGRESS.append(tg_user)
                    wallet_host = getattr(getattr(WalletAPI.coin_list, coin_name), "wallet_address")
                    main_address = getattr(getattr(WalletAPI.coin_list, coin_name), "MainAddress")
                    coin_decimal = getattr(getattr(WalletAPI.coin_list, coin_name), "decimal")
                    password = decrypt_string(getattr(getattr(WalletAPI.coin_list, coin_name), "walletkey"))
                    send_tx = await WalletAPI.send_external_hnt(
                        tg_user, wallet_host, password, main_address, address,
                        amount, coin_decimal, SERVER_BOT, coin_name, NetFee, 32
                    )
                    if send_tx:
                        fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                            num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                        await log_to_channel(
                            "withdraw",
                            f"[{SERVER_BOT}] User {tg_user} successfully withdrew "\
                            f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                            f"{token_display}{equivalent_usd}."
                        )
                        msg = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to {address}.\nTransaction hash: {send_tx}{fee_txt}'
                        message_text = text(bold('COMPLETED:'),
                                            markdown.pre(msg))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    else:
                        await log_to_channel(
                            "withdraw",
                            f"[{SERVER_BOT}] [FAILED] User {tg_user} failed to withdraw "\
                            f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                            f"{token_display}{equivalent_usd}."
                        )
                    TX_IN_PROGRESS.remove(tg_user)
                else:
                    # reject and tell to wait
                    message_text = text(bold('ERROR:'),
                                        markdown.pre("You have another tx in process. Please wait it to finish."))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return
            elif type_coin == "XLM":
                url = getattr(getattr(WalletAPI.coin_list, coin_name), "http_address")
                main_address = getattr(getattr(WalletAPI.coin_list, coin_name), "MainAddress")
                if address == main_address:
                    # can not send
                    msg = f'You cannot send to this address `{address}`.'
                    message_text = text(bold('ERROR:'),
                                        markdown.pre(msg))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    return
                if coin_name != "XLM":  # in case of asset
                    issuer = getattr(getattr(WalletAPI.coin_list, coin_name), "contract")
                    asset_code = getattr(getattr(WalletAPI.coin_list, coin_name), "header")
                    check_asset = await WalletAPI.check_xlm_asset(url, asset_code, issuer, address, tg_user, SERVER_BOT)
                    if check_asset is False:
                        msg = f'You cannot send to this address `{address}`. The destination account may not trust the asset you are attempting to send!'
                        message_text = text(bold('ERROR:'),
                                            markdown.pre(msg))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                        return
                if tg_user not in TX_IN_PROGRESS:
                    TX_IN_PROGRESS.append(tg_user)
                    wallet_host = getattr(getattr(WalletAPI.coin_list, coin_name), "wallet_address")
                    coin_decimal = getattr(getattr(WalletAPI.coin_list, coin_name), "decimal")
                    withdraw_keypair = decrypt_string(getattr(getattr(WalletAPI.coin_list, coin_name), "walletkey"))
                    asset_ticker = getattr(getattr(WalletAPI.coin_list, coin_name), "header")
                    asset_issuer = getattr(getattr(WalletAPI.coin_list, coin_name), "contract")
                    send_tx = await WalletAPI.send_external_xlm(url, withdraw_keypair, tg_user, amount, address, coin_decimal, SERVER_BOT, coin_name, NetFee, asset_ticker, asset_issuer, 32)
                    if send_tx:
                        fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                            num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                        await log_to_channel(
                            "withdraw",
                            f"[{SERVER_BOT}] User {tg_user} successfully withdrew "\
                            f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                            f"{token_display}{equivalent_usd}."
                        )
                        msg = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                        message_text = text(bold('INFO:'),
                                            markdown.pre(msg))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    else:
                        msg = f'Failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                        message_text = text(bold('ERROR:'),
                                            markdown.pre(msg))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                        await log_to_channel(
                            "withdraw",
                            f"[FAILED] [{SERVER_BOT}] User {tg_user}  failed to withdraw "\
                            f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                            f"{token_display}{equivalent_usd}."
                        )
                    TX_IN_PROGRESS.remove(tg_user)
                else:
                    # reject and tell to wait
                    message_text = text(bold('ERROR:'),
                                        markdown.pre("You have another tx in process. Please wait it to finish."))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return
            elif type_coin == "ADA":
                if not address.startswith("addr1"):
                    msg = f'Invalid address. It should start with addr1.'
                    message_text = text(bold('ERROR:'),
                                        markdown.pre(msg))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    return
                if tg_user not in TX_IN_PROGRESS:
                    if coin_name == "ADA":
                        TX_IN_PROGRESS.append(tg_user)
                        coin_decimal = getattr(getattr(WalletAPI.coin_list, coin_name), "decimal")
                        fee_limit = getattr(getattr(WalletAPI.coin_list, coin_name), "fee_limit")
                        # Use fee limit as NetFee
                        send_tx = await WalletAPI.send_external_ada(
                            tg_user, amount, coin_decimal, SERVER_BOT, coin_name, fee_limit, address, 60
                        )
                        if "status" in send_tx and send_tx['status'] == "pending":
                            tx_hash = send_tx['id']
                            fee = send_tx['fee']['quantity'] / 10 ** coin_decimal + fee_limit
                            fee_txt = "\nWithdrew fee/node: {} {}.".format(
                                num_format_coin(fee, coin_name, coin_decimal, False), coin_name)
                            await log_to_channel(
                                "withdraw",
                                f"[{SERVER_BOT}] User {tg_user} successfully withdrew "\
                                f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                                f"{token_display}{equivalent_usd}."
                            )
                            msg = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to {address}.\nTransaction hash: {tx_hash}{fee_txt}'
                            message_text = text(bold('COMPLETED:'),
                                                markdown.pre(msg))
                            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                        elif "code" in send_tx and "message" in send_tx:
                            code = send_tx['code']
                            message = send_tx['message']
                            await log_to_channel(
                                "withdraw",
                                f"[{SERVER_BOT}] [FAILED] User {tg_user} failed to withdraw "\
                                f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                                f"{token_display}{equivalent_usd}.```code: {code}\nmessage: {message}```"
                            )
                            msg = f'Internal error, please try again later!'
                            message_text = text(bold('ERROR:'),
                                                markdown.pre(msg))
                            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                        else:
                            await log_to_channel(
                                "withdraw",
                                f"[{SERVER_BOT}] [FAILED] User {tg_user} failed to withdraw "\
                                f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                                f"{token_display}{equivalent_usd}."
                            )
                            msg = f'Internal error, please try again later!'
                            message_text = text(bold('ERROR:'),
                                                markdown.pre(msg))
                            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                        TX_IN_PROGRESS.remove(tg_user)
                        return
                    else:
                        ## 
                        # Check user's ADA balance.
                        GAS_COIN = None
                        fee_limit = None
                        try:
                            if getattr(getattr(WalletAPI.coin_list, coin_name), "withdraw_use_gas_ticker") == 1:
                                # add main token balance to check if enough to withdraw
                                GAS_COIN = getattr(getattr(WalletAPI.coin_list, coin_name), "gas_ticker")
                                fee_limit = getattr(getattr(WalletAPI.coin_list, coin_name), "fee_limit")
                                if GAS_COIN:
                                    userdata_balance = await WalletAPI.user_balance(
                                        tg_user, GAS_COIN, wallet_address, type_coin, height, getattr(
                                            getattr(WalletAPI.coin_list, GAS_COIN), "deposit_confirm_depth"),
                                            SERVER_BOT
                                    )
                                    actual_balance = userdata_balance['adjust']
                                    if actual_balance < fee_limit:  # use fee_limit to limit ADA
                                        msg = f'You do not have sufficient {GAS_COIN} to withdraw {coin_name}. You need to have at least a reserved {fee_limit} {GAS_COIN}.'
                                        message_text = text(bold('ERROR:'),
                                                            markdown.pre(msg))
                                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                                        await log_to_channel(
                                            "withdraw",
                                            f"[{SERVER_BOT}] User {tg_user} wants to withdraw asset "\
                                            f"{coin_name} but having only {actual_balance} {GAS_COIN}."
                                        )
                                        return
                                else:
                                    msg = f'Invalid main token, please report!'
                                    message_text = text(bold('ERROR:'),
                                                        markdown.pre(msg))
                                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                                    await log_to_channel(
                                        "withdraw",
                                        f"[{SERVER_BOT}] [BUG] {tg_user} invalid main token for {coin_name}."
                                    )
                                    return
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                            msg = f'Cannot check balance, please try again later!'
                            message_text = text(bold('ERROR:'),
                                                markdown.pre(msg))
                            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                            await log_to_channel(
                                "withdraw",
                                f"[{SERVER_BOT}] User {tg_user} failed to check balance {GAS_COIN} "\
                                f"for asset transfer..."
                            )
                            return

                        TX_IN_PROGRESS.append(tg_user)
                        coin_decimal = getattr(getattr(WalletAPI.coin_list, coin_name), "decimal")
                        asset_name = getattr(getattr(WalletAPI.coin_list, coin_name), "header")
                        policy_id = getattr(getattr(WalletAPI.coin_list, coin_name), "contract")
                        send_tx = await WalletAPI.send_external_ada_asset(
                            tg_user, amount, coin_decimal, SERVER_BOT,
                            coin_name, NetFee, address, asset_name,
                            policy_id, 60
                        )
                        if "status" in send_tx and send_tx['status'] == "pending":
                            tx_hash = send_tx['id']
                            gas_coin_msg = ""
                            if GAS_COIN is not None:
                                gas_coin_msg = " and fee {} {} you shall receive additional `{} {}`.".format(
                                    num_format_coin(send_tx['network_fee'] + fee_limit / 20, GAS_COIN, 6, False),
                                    GAS_COIN, num_format_coin(send_tx['ada_received'], GAS_COIN, 6, False), GAS_COIN)
                            fee_txt = "\nWithdrew fee/node: {} {}{}.".format(
                                num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name, gas_coin_msg)
                            await log_to_channel(
                                "withdraw",
                                f"[{SERVER_BOT}] User {tg_user} successfully withdrew "\
                                f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                                f"{token_display}{equivalent_usd}."
                            )
                            msg = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to {address}.\nTransaction hash: {tx_hash}{fee_txt}'
                            message_text = text(bold('COMPLETED:'),
                                                markdown.pre(msg))
                            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                        elif "code" in send_tx and "message" in send_tx:
                            code = send_tx['code']
                            message = send_tx['message']
                            await logchanbot(
                                f'[{SERVER_BOT}] [FAILED] User {tg_user} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.```code: {code}\nmessage: {message}```')
                            msg = f'Internal error, please try again later!'
                            message_text = text(bold('ERROR:'),
                                                markdown.pre(msg))
                            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                        else:
                            await logchanbot(
                                f'[{SERVER_BOT}] [FAILED] User {tg_user} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                            msg = f'Internal error, please try again later!'
                            message_text = text(bold('ERROR:'),
                                                markdown.pre(msg))
                            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                        TX_IN_PROGRESS.remove(tg_user)
                        return
                else:
                    # reject and tell to wait
                    message_text = text(bold('ERROR:'),
                                        markdown.pre("You have another tx in process. Please wait it to finish."))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                    return
            elif type_coin == "SOL" or type_coin == "SPL":
                if tg_user not in TX_IN_PROGRESS:
                    TX_IN_PROGRESS.append(tg_user)
                    tx_fee = getattr(getattr(WalletAPI.coin_list, coin_name), "tx_fee")
                    send_tx = await WalletAPI.send_external_sol(
                        WalletAPI.erc_node_list['SOL'], tg_user, amount, address,
                        coin_name, coin_decimal, tx_fee, NetFee, SERVER_BOT
                    )
                    if send_tx:
                        fee_txt = "\nWithdrew fee/node: {} {}.".format(
                            num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                        msg = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to {address}.\nTransaction hash: {send_tx}{fee_txt}'
                        message_text = text(bold('COMPLETED:'),
                                            markdown.pre(msg))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                        await log_to_channel(
                            "withdraw",
                            f"[{SERVER_BOT}] User {tg_user} successfully withdrew "\
                            f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                            f"{token_display}{equivalent_usd}."
                        )
                    else:
                        await log_to_channel(
                            "withdraw",
                            f"[{SERVER_BOT}] [FAILED] User {tg_user} failed to withdraw "\
                            f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                            f"{token_display}{equivalent_usd}."
                        )
                    TX_IN_PROGRESS.remove(tg_user)
                else:
                    # reject and tell to wait
                    message_text = text(bold('ERROR:'),
                                        markdown.pre("You have another tx in process. Please wait it to finish.")
                    )
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return
            elif type_coin == "BTC":
                if tg_user not in TX_IN_PROGRESS:
                    TX_IN_PROGRESS.append(tg_user)
                    send_tx = await WalletAPI.send_external_doge(tg_user, amount, address, coin_name, 0, NetFee,
                                                                SERVER_BOT)  # tx_fee=0
                    if send_tx:
                        fee_txt = "\nWithdrew fee/node: {} {}.".format(
                            num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                        msg = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                        message_text = text(bold('COMPLETED:'),
                                            markdown.pre(msg))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                        await log_to_channel(
                            "withdraw",
                            f"[SERVER_BOT] User {tg_user} successfully withdrew "\
                            f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                            f"{token_display}{equivalent_usd}."
                        )
                    else:
                        await log_to_channel(
                            "withdraw",
                            f"[{SERVER_BOT}] [FAILED] User {tg_user} failed to withdraw "\
                            f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                            f"{token_display}{equivalent_usd}."
                        )
                    TX_IN_PROGRESS.remove(tg_user)
                else:
                    # reject and tell to wait
                    msg = f'You have another tx in process. Please wait it to finish.'
                    message_text = text(bold('ERROR:'),
                                        markdown.pre(msg))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return
            elif type_coin == "XMR" or type_coin == "TRTL-API" or type_coin == "TRTL-SERVICE" or type_coin == "BCN":
                if tg_user not in TX_IN_PROGRESS:
                    TX_IN_PROGRESS.append(tg_user)
                    main_address = getattr(getattr(WalletAPI.coin_list, coin_name), "MainAddress")
                    mixin = getattr(getattr(WalletAPI.coin_list, coin_name), "mixin")
                    wallet_address = getattr(getattr(WalletAPI.coin_list, coin_name), "wallet_address")
                    header = getattr(getattr(WalletAPI.coin_list, coin_name), "header")
                    is_fee_per_byte = getattr(getattr(WalletAPI.coin_list, coin_name), "is_fee_per_byte")
                    send_tx = await WalletAPI.send_external_xmr(
                        type_coin, main_address, tg_user, amount, address,
                        coin_name, coin_decimal, tx_fee, NetFee, is_fee_per_byte,
                        mixin, SERVER_BOT, wallet_address, header,
                        None
                    )  # paymentId: None (end)
                    if send_tx:
                        fee_txt = "\nWithdrew fee/node: {} {}.".format(
                            num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                        msg = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to {address}.\nTransaction hash: `{send_tx}`{fee_txt}'
                        message_text = text(bold('COMPLETED:'),
                                            markdown.pre(msg))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                        await log_to_channel(
                            "withdraw",
                            f"[{SERVER_BOT}] User {tg_user} successfully executed withdraw "\
                            f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                            f"{token_display}{equivalent_usd}."
                        )
                    else:
                        await log_to_channel(
                            "withdraw",
                            f"[{SERVER_BOT}] User {tg_user} failed to execute to withdraw "\
                            f"{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                            f"{token_display}{equivalent_usd}."
                        )
                    TX_IN_PROGRESS.remove(tg_user)
                else:
                    # reject and tell to wait
                    message_text = text(bold('ERROR:'),
                                        markdown.pre("You have another tx in process. Please wait it to finish."))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
                return

@dp.message_handler(commands='price')
async def start_cmd_handler(message: types.Message):
    content = ' '.join(message.text.split())
    args = content.split(" ")
    if len(args) != 3:
        message_text = text(bold('ERROR:'),
                            markdown.pre("Please use /price amount coin"))
        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
        return
    else:
        original_amount = args[1]
        amount = args[1].replace(",", "")
        coin_name = args[2].upper()
        try:
            amount = float(amount)
        except ValueError:
            message_text = text(bold('ERROR:'),
                                markdown.pre("Invalid given amount!"))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2)
            return

        WalletAPI = WalletTG()
        await WalletAPI.get_coin_setting()
        per_unit = None
        if coin_name in WalletAPI.token_hints:
            id = WalletAPI.token_hints[coin_name]['ticker_name']
            per_unit = WalletAPI.coin_paprika_id_list[id]['price_usd']
            name = WalletAPI.coin_paprika_id_list[id]['name']
            id_name = id
        else:
            per_unit = WalletAPI.coin_paprika_symbol_list[coin_name]['price_usd']
            name = WalletAPI.coin_paprika_symbol_list[coin_name]['name']
            id_name = WalletAPI.coin_paprika_symbol_list[coin_name]['id']

        try:
            if per_unit:
                total_price = amount * per_unit
                total_price_str = ""
                if total_price > 1000:
                    total_price_str = "{:,.2f}".format(total_price)
                elif total_price > 100:
                    total_price_str = "{:.2f}".format(total_price)
                elif total_price > 1:
                    total_price_str = "{:.3f}".format(total_price)
                elif total_price > 0.01:
                    total_price_str = "{:.4f}".format(total_price)
                else:
                    total_price_str = "{:.8f}".format(total_price)

                link = "https://coinpaprika.com/coin/" + id_name
                keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
                keyboard_markup.add(
                    # url buttons have no callback data
                    types.InlineKeyboardButton('coinpaprika', url=link),
                )
                message_text = text(bold(f'{original_amount} {name}:'),
                                    markdown.pre("{} {}\n".format(total_price_str, "USD")))
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard_markup)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

@dp.message_handler()
async def echo(message: types.Message):
    global QUEUE_MSG, MIN_MSG_TO_SAVE
    # old style:
    # await bot.send_message(message.chat.id, message.text)
    # await message.answer(message.text)
    if message.chat.type != "private":
        try:
            QUEUE_MSG.append((
                message['message_id'], message['text'], time.mktime(message['date'].timetuple()),
                message['from']['username'] if message['from']['username'] else None,
                message['from']['id'], str(message['chat']['id']), message['chat']['title'],
                message['chat']['username'], message['chat']['type']
            ))
            if len(QUEUE_MSG) >= MIN_MSG_TO_SAVE:
                try:
                    WalletAPI = WalletTG()
                    inserted = await WalletAPI.insert_messages(QUEUE_MSG)
                    QUEUE_MSG = []
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

# Notify user
async def notify_new_tx_user():
    time_lap = 5  # seconds
    while True:
        await asyncio.sleep(time_lap)
        try:
            WalletAPI = WalletTG()
            await WalletAPI.get_coin_setting()
            pending_tx = await WalletAPI.sql_get_new_tx_table('NO', 'NO', SERVER_BOT)
            if len(pending_tx) > 0:
                # let's notify_new_tx_user
                for eachTx in pending_tx:
                    try:
                        coin_name = eachTx['coin_name']
                        coin_family = getattr(getattr(WalletAPI.coin_list, coin_name), "type")
                        coin_decimal = getattr(getattr(WalletAPI.coin_list, coin_name), "decimal")
                        if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR", "BTC", "CHIA", "NANO"]:
                            user_tx = await store.sql_get_userwallet_by_paymentid(
                                eachTx['payment_id'], eachTx['coin_name'], coin_family
                            )
                            if user_tx and user_tx['chat_id']:
                                is_notify_failed = False
                                to_user = user_tx['chat_id']
                                message_text = None
                                try:
                                    if coin_family == "NANO":
                                        message_text = "You got a new deposit: " + "Coin: {}\nAmount: {}".format(
                                            eachTx['coin_name'],
                                            num_format_coin(eachTx['amount'], coin_name, coin_decimal, False))
                                    elif coin_family != "BTC":
                                        message_text = "You got a new deposit confirmed: " + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}".format(
                                            eachTx['coin_name'], eachTx['txid'],
                                            num_format_coin(eachTx['amount'], coin_name, coin_decimal, False),
                                            eachTx['height'])
                                    else:
                                        message_text = "You got a new deposit confirmed: " + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}".format(
                                            eachTx['coin_name'], eachTx['txid'],
                                            num_format_coin(eachTx['amount'], coin_name, coin_decimal, False),
                                            eachTx['blockhash'])
                                    if message_text:
                                        try:
                                            send_msg = await bot.send_message(
                                                chat_id=to_user, text=message_text,
                                                parse_mode=ParseMode.MARKDOWN_V2
                                            )
                                            if send_msg:
                                                is_notify_failed = False
                                            else:
                                                await logchanbot("[{}] Can not send message to {}".format(SERVER_BOT, user_tx['chat_id']))
                                                is_notify_failed = True
                                        except exceptions.BotBlocked:
                                            await logchanbot(f"[{SERVER_BOT}] {coin_name} Target [ID:{to_user}]: blocked by user")
                                            await store.sql_update_notify_tx_table(eachTx['payment_id'], user_tx['user_id'], user_tx['user_id'], 'YES', 'YES', eachTx['txid'])
                                        except exceptions.ChatNotFound:
                                            await logchanbot(f"[{SERVER_BOT}] Target [ID:{to_user}]: invalid user ID")
                                        except exceptions.RetryAfter as e:
                                            await logchanbot(
                                                f"[{SERVER_BOT}] Target [ID:{to_user}]: Flood limit is exceeded. Sleep {e.timeout} seconds")
                                            await asyncio.sleep(e.timeout)
                                            return await bot.send_message(chat_id=to_user,
                                                                          text=message_text)  # Recursive call
                                        except exceptions.UserDeactivated:
                                            await logchanbot(
                                                f"[{SERVER_BOT}] Target [ID:{to_user}]: user is deactivated")
                                        except exceptions.TelegramAPIError:
                                            await logchanbot(f"[{SERVER_BOT}] Target [ID:{to_user}]: failed")
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
                                            is_notify_failed = True
                                        finally:
                                            await store.sql_update_notify_tx_table(
                                                eachTx['payment_id'], user_tx['user_id'], user_tx['user_id'], 'YES', 
                                                'NO' if is_notify_failed == False else 'YES', eachTx['txid']
                                            )
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)

async def notify_new_confirmed_ada():
    time_lap = 10  # seconds
    while True:
        await asyncio.sleep(time_lap)
        WalletAPI = WalletTG()
        await WalletAPI.get_coin_setting()
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `ada_get_transfers` 
                    WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s
                    """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id'] and eachTx['user_server'] == SERVER_BOT:
                                coin_name = eachTx['coin_name']
                                coin_decimal = getattr(getattr(WalletAPI.coin_list, coin_name), "decimal")
                                coin_family = getattr(getattr(WalletAPI.coin_list, coin_name), "type")
                                net_name = getattr(getattr(WalletAPI.coin_list, coin_name), "net_name")
                                type_coin = getattr(getattr(WalletAPI.coin_list, coin_name), "type")
                                get_deposit = await WalletAPI.sql_get_userwallet(
                                    eachTx['user_id'], coin_name, net_name, type_coin, SERVER_BOT, None
                                )
                                if get_deposit and get_deposit['chat_id']:
                                    to_user = get_deposit['chat_id']
                                    message_text = text(bold(f"You got a new deposit {coin_name}"),
                                                        " (it could take a few minutes to credit):\n",
                                                        markdown.pre(
                                                            "\nTx: {}\nAmount: {}".format(eachTx['hash_id'],
                                                            num_format_coin(eachTx['amount'], coin_name, coin_decimal, False)
                                                            )
                                                        )
                                    )
                                    try:
                                        send_msg = await bot.send_message(
                                            chat_id=to_user, text=message_text,
                                            parse_mode=ParseMode.MARKDOWN_V2
                                        )
                                        if send_msg:
                                            sql = """ UPDATE `ada_get_transfers` SET `notified_confirmation`=%s, `time_notified`=%s 
                                            WHERE `hash_id`=%s AND `coin_name`=%s LIMIT 1
                                            """
                                            await cur.execute(sql, (
                                                "YES", int(time.time()), eachTx['hash_id'], coin_name
                                            ))
                                            await conn.commit()
                                            is_notify_failed = False
                                        else:
                                            await logchanbot("[{}] Can not send message to {}".format(
                                                SERVER_BOT, get_deposit['chat_id'])
                                            )
                                            is_notify_failed = True
                                    except exceptions.BotBlocked:
                                        await logchanbot(f"[{SERVER_BOT}] {coin_name} Target [ID:{to_user}]: blocked by user")
                                        sql = """ UPDATE `ada_get_transfers` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `hash_id`=%s AND `coin_name`=%s LIMIT 1 """
                                        await cur.execute(sql, ("NO", "YES", eachTx['hash_id'], coin_name))
                                        await conn.commit()
                                    except exceptions.ChatNotFound:
                                        await logchanbot(f"[{SERVER_BOT}] Target [ID:{to_user}]: invalid user ID")
                                    except exceptions.RetryAfter as e:
                                        await logchanbot(
                                            f"[{SERVER_BOT}] Target [ID:{to_user}]: Flood limit is exceeded. Sleep {e.timeout} seconds")
                                        await asyncio.sleep(e.timeout)
                                        return await bot.send_message(
                                            chat_id=to_user, text=message_text
                                        )  # Recursive call
                                    except exceptions.UserDeactivated:
                                        await logchanbot(f"[{SERVER_BOT}] Target [ID:{to_user}]: user is deactivated")
                                    except exceptions.TelegramAPIError:
                                        await logchanbot(f"[{SERVER_BOT}] Target [ID:{to_user}]: failed")
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `ada_get_transfers` SET `notified_confirmation`=%s, `failed_notification`=%s 
                                        WHERE `hash_id`=%s AND `coin_name`=%s LIMIT 1
                                        """
                                        await cur.execute(sql, ("NO", "YES", eachTx['hash_id'], coin_name))
                                        await conn.commit()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)

async def notify_new_confirmed_hnt():
    time_lap = 10  # seconds
    while True:
        await asyncio.sleep(time_lap)
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `hnt_get_transfers` 
                    WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s
                    """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id'] and eachTx['user_server'] == SERVER_BOT:
                                coin_name = eachTx['coin_name']
                                coin_decimal = getattr(getattr(WalletAPI.coin_list, coin_name), "decimal")
                                coin_family = getattr(getattr(WalletAPI.coin_list, coin_name), "type")
                                net_name = getattr(getattr(WalletAPI.coin_list, coin_name), "net_name")
                                type_coin = getattr(getattr(WalletAPI.coin_list, coin_name), "type")
                                get_deposit = await WalletAPI.sql_get_userwallet(eachTx['user_id'], coin_name, net_name,
                                                                                 type_coin, SERVER_BOT, None)
                                if get_deposit and get_deposit['chat_id']:
                                    to_user = get_deposit['chat_id']
                                    message_text = text(bold(f"You got a new deposit {coin_name}"), 
                                        " (it could take a few minutes to credit):\n",
                                        markdown.pre(
                                            "\nTx: {}\nAmount: {}".format(
                                                eachTx['txid'], num_format_coin(eachTx['amount'], coin_name, coin_decimal, False)
                                            )
                                        )
                                    )
                                    try:
                                        send_msg = await bot.send_message(
                                            chat_id=to_user, text=message_text,
                                            parse_mode=ParseMode.MARKDOWN_V2
                                        )
                                        if send_msg:
                                            sql = """ UPDATE `hnt_get_transfers` SET `notified_confirmation`=%s, `time_notified`=%s 
                                            WHERE `txid`=%s AND `coin_name`=%s LIMIT 1
                                            """
                                            await cur.execute(sql, ("YES", int(time.time()), eachTx['txid'], coin_name))
                                            await conn.commit()
                                            is_notify_failed = False
                                        else:
                                            await logchanbot("[{}] Can not send message to {}".format(
                                                SERVER_BOT, get_deposit['chat_id'])
                                            )
                                            is_notify_failed = True
                                    except exceptions.BotBlocked:
                                        await logchanbot(f"[{SERVER_BOT}] {coin_name} Target [ID:{to_user}]: blocked by user")
                                        sql = """ UPDATE `hnt_get_transfers` SET `notified_confirmation`=%s, `failed_notification`=%s 
                                        WHERE `txid`=%s AND `coin_name`=%s LIMIT 1
                                        """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txid'], coin_name))
                                        await conn.commit()
                                    except exceptions.ChatNotFound:
                                        await logchanbot(f"[{SERVER_BOT}] Target [ID:{to_user}]: invalid user ID")
                                    except exceptions.RetryAfter as e:
                                        await logchanbot(
                                            f"[{SERVER_BOT}] Target [ID:{to_user}]: Flood limit is exceeded. Sleep {e.timeout} seconds")
                                        await asyncio.sleep(e.timeout)
                                        return await bot.send_message(chat_id=to_user,
                                                                      text=message_text)  # Recursive call
                                    except exceptions.UserDeactivated:
                                        await logchanbot(f"[{SERVER_BOT}] Target [ID:{to_user}]: user is deactivated")
                                    except exceptions.TelegramAPIError:
                                        await logchanbot(f"[{SERVER_BOT}] Target [ID:{to_user}]: failed")
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `hnt_get_transfers` SET `notified_confirmation`=%s, `failed_notification`=%s 
                                        WHERE `txid`=%s AND `coin_name`=%s LIMIT 1
                                        """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txid'], coin_name))
                                        await conn.commit()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)

async def notify_new_confirmed_xlm():
    time_lap = 10  # seconds
    while True:
        await asyncio.sleep(time_lap)
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `xlm_get_transfers` 
                    WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s
                    """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id'] and eachTx['user_server'] == SERVER_BOT:
                                coin_name = eachTx['coin_name']
                                coin_decimal = getattr(getattr(WalletAPI.coin_list, coin_name), "decimal")
                                coin_family = getattr(getattr(WalletAPI.coin_list, coin_name), "type")
                                net_name = getattr(getattr(WalletAPI.coin_list, coin_name), "net_name")
                                type_coin = getattr(getattr(WalletAPI.coin_list, coin_name), "type")
                                get_deposit = await WalletAPI.sql_get_userwallet(eachTx['user_id'], coin_name, net_name,
                                                                                 type_coin, SERVER_BOT, None)
                                if get_deposit and get_deposit['chat_id']:
                                    to_user = get_deposit['chat_id']
                                    message_text = text(bold(f"You got a new deposit {coin_name}"),
                                                        " (it could take a few minutes to credit):\n",
                                                        markdown.pre(
                                                            "\nTx: {}\nAmount: {}".format(
                                                                eachTx['txid'], num_format_coin(eachTx['amount'], coin_name, coin_decimal, False)
                                                            )
                                                        )
                                    )
                                    try:
                                        send_msg = await bot.send_message(
                                            chat_id=to_user, text=message_text,
                                            parse_mode=ParseMode.MARKDOWN_V2
                                        )
                                        if send_msg:
                                            sql = """ UPDATE `xlm_get_transfers` SET `notified_confirmation`=%s, `time_notified`=%s 
                                            WHERE `txid`=%s AND `coin_name`=%s LIMIT 1
                                            """
                                            await cur.execute(sql, ("YES", int(time.time()), eachTx['txid'], coin_name))
                                            await conn.commit()
                                            is_notify_failed = False
                                        else:
                                            await logchanbot("[{}] Can not send message to {}".format(SERVER_BOT, get_deposit['chat_id']))
                                            is_notify_failed = True
                                    except exceptions.BotBlocked:
                                        await logchanbot(f"[{SERVER_BOT}] {coin_name} Target [ID:{to_user}]: blocked by user")
                                        sql = """ UPDATE `xlm_get_transfers` SET `notified_confirmation`=%s, `failed_notification`=%s 
                                        WHERE `txid`=%s AND `coin_name`=%s LIMIT 1
                                        """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txid'], coin_name))
                                        await conn.commit()
                                    except exceptions.ChatNotFound:
                                        await logchanbot(f"[{SERVER_BOT}] Target [ID:{to_user}]: invalid user ID")
                                    except exceptions.RetryAfter as e:
                                        await logchanbot(
                                            f"[{SERVER_BOT}] Target [ID:{to_user}]: Flood limit is exceeded. Sleep {e.timeout} seconds")
                                        await asyncio.sleep(e.timeout)
                                        return await bot.send_message(chat_id=to_user,
                                                                      text=message_text)  # Recursive call
                                    except exceptions.UserDeactivated:
                                        await logchanbot(f"[{SERVER_BOT}] Target [ID:{to_user}]: user is deactivated")
                                    except exceptions.TelegramAPIError:
                                        await logchanbot(f"[{SERVER_BOT}] Target [ID:{to_user}]: failed")
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `xlm_get_transfers` SET `notified_confirmation`=%s, `failed_notification`=%s 
                                        WHERE `txid`=%s AND `coin_name`=%s LIMIT 1
                                        """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txid'], coin_name))
                                        await conn.commit()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.create_task(notify_new_tx_user())
    # ADA
    loop.create_task(notify_new_confirmed_ada())
    # HNT
    loop.create_task(notify_new_confirmed_hnt())
    # XLM
    loop.create_task(notify_new_confirmed_xlm())

    executor.start_polling(dp, skip_updates=True)
