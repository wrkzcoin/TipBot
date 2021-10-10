from discord_webhook import DiscordWebhook
import discord

from typing import List, Dict
from datetime import datetime
import time
import simplejson as json
import asyncio
import aiohttp
import aiomysql
from aiomysql.cursors import DictCursor

import daemonrpc_client, rpc_client, wallet, walletapi, addressvalidation
from config import config
import sys, traceback
import os.path

# For plot
import numpy as np
import matplotlib as mpl

import matplotlib.pyplot as plt
import matplotlib.dates as dates
import pandas as pd

# Encrypt
from cryptography.fernet import Fernet

# MySQL
import pymysql

# redis
import redis

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
Account.enable_unaudited_hdwallet_features()

redis_pool = None
redis_conn = None
redis_expired = 120

FEE_PER_BYTE_COIN = config.Fee_Per_Byte_Coin.split(",")

pool = None
pool_cmc = None

#conn = None
sys.path.append("..")

ENABLE_COIN = config.Enable_Coin.split(",")
ENABLE_XMR = config.Enable_Coin_XMR.split(",")
ENABLE_XCH = config.Enable_Coin_XCH.split(",")
ENABLE_COIN_DOGE = config.Enable_Coin_Doge.split(",")
ENABLE_COIN_NANO = config.Enable_Coin_Nano.split(",")
ENABLE_COIN_ERC = config.Enable_Coin_ERC.split(",")
ENABLE_COIN_TRC = config.Enable_Coin_TRC.split(",")
POS_COIN = config.PoS_Coin.split(",")

# Coin using wallet-api
WALLET_API_COIN = config.Enable_Coin_WalletApi.split(",")


def init():
    global redis_pool
    print("PID %d: initializing redis pool..." % os.getpid())
    redis_pool = redis.ConnectionPool(host='localhost', port=6379, decode_responses=True, db=8)


def openRedis():
    global redis_pool, redis_conn
    if redis_conn is None:
        try:
            redis_conn = redis.Redis(connection_pool=redis_pool)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


async def logchanbot(content: str):
    filterword = config.discord.logfilterword.split(",")
    for each in filterword:
        content = content.replace(each, config.discord.filteredwith)
    if len(content) > 1500: content = content[:1500]
    try:
        webhook = DiscordWebhook(url=config.discord.botdbghook, content=f'```{discord.utils.escape_markdown(content)}```')
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


# openConnection
async def openConnection():
    global pool
    try:
        if pool is None:
            pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=6, maxsize=12, 
                                                   user=config.mysql.user, password=config.mysql.password,
                                                   db=config.mysql.db, autocommit=True, cursorclass=DictCursor)
    except:
        print("ERROR: Unexpected error: Could not connect to MySql instance.")
        await logchanbot(traceback.format_exc())


# openConnection_cmc
async def openConnection_cmc():
    global pool_cmc
    try:
        if pool_cmc is None:
            pool_cmc = await aiomysql.create_pool(host=config.mysql_cmc.host, port=3306, minsize=2, maxsize=4, 
                                                       user=config.mysql_cmc.user, password=config.mysql_cmc.password,
                                                       db=config.mysql_cmc.db, cursorclass=DictCursor)
    except:
        print("ERROR: Unexpected error: Could not connect to MySql instance.")
        await logchanbot(traceback.format_exc())


async def get_coingecko_coin(coin: str):
    global pool_cmc
    try:
        await openConnection_cmc()
        async with pool_cmc.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM coingecko_v2 WHERE `symbol`=%s ORDER BY `last_updated` DESC LIMIT 1 """
                await cur.execute(sql, (coin.lower()))
                result = await cur.fetchone()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def get_all_user_balance_address(coin: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT `coin_name`, `balance_wallet_address`, `balance_wallet_address_ch`,`privateSpendKey` FROM `cn_user` WHERE `coin_name` = %s"""
                await cur.execute(sql, (coin))
                result = await cur.fetchall()
                listAddr=[]
                for row in result:
                    listAddr.append({'address':row['balance_wallet_address'], 'scanHeight': row['balance_wallet_address_ch'], 'privateSpendKey': decrypt_string(row['privateSpendKey'])})
                return listAddr
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_nano_update_balances(coin: str):
    global pool, redis_conn
    updated = 0
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","BAN")
    get_balance = await wallet.nano_get_wallet_balance_elements(COIN_NAME)
    all_user_info = await sql_nano_get_user_wallets(COIN_NAME)
    all_deposit_address = {}
    all_deposit_address_keys = []
    if all_user_info and len(all_user_info) > 0:
        all_deposit_address_keys = [each['balance_wallet_address'] for each in all_user_info]
        for each in all_user_info:
            all_deposit_address[each['balance_wallet_address']] = each
    if get_balance and len(get_balance) > 0:
        for address, balance in get_balance.items():
            try:
                # if bigger than minimum deposit, and no pending and the address is in user database addresses
                if int(balance['balance']) >= getattr(getattr(config,"daemon"+COIN_NAME),"min_deposit", 100000000000000000000000000000) \
                and int(balance['pending']) == 0 and address in all_deposit_address_keys:
                    # let's move balance to main_address
                    try:
                        main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
                        move_to_deposit = await wallet.nano_sendtoaddress(address, main_address, int(balance['balance']), COIN_NAME)
                        # add to DB
                        if move_to_deposit:
                            try:
                                await openConnection()
                                async with pool.acquire() as conn:
                                    async with conn.cursor() as cur:
                                        sql = """ INSERT INTO nano_move_deposit (`coin_name`, `user_id`, `balance_wallet_address`, `to_main_address`, `amount`, `decimal`, `block`, `time_insert`) 
                                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                                        await cur.execute(sql, (COIN_NAME, all_deposit_address[address]['user_id'], address, main_address, int(balance['balance']),  wallet.get_decimal(COIN_NAME), move_to_deposit['block'], int(time.time()), ))
                                        await conn.commit()
                                        updated += 1
                                        # add to notification list also
                                        # txid = new block ID
                                        # payment_id = deposit address
                                        sql = """ INSERT IGNORE INTO discord_notify_new_tx (`coin_name`, `txid`, `payment_id`, `amount`, `decimal`) 
                                                  VALUES (%s, %s, %s, %s, %s) """
                                        await cur.execute(sql, (COIN_NAME, move_to_deposit['block'], address, int(balance['balance']), wallet.get_decimal(COIN_NAME)))
                                        await conn.commit()
                            except Exception as e:
                                await logchanbot(traceback.format_exc())
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
            except Exception as e:
                await logchanbot(traceback.format_exc())
    return updated


async def sql_user_balance_get_xfer_in(userID: str, coin: str, user_server: str = 'DISCORD'):
    global pool, redis_pool, redis_conn, redis_expired
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    key = config.redis_setting.prefix_xfer_in + userID + ":" + COIN_NAME
    try:
        if redis_conn is None: redis_conn = redis.Redis(connection_pool=redis_pool)
        if redis_conn and redis_conn.exists(key):
            xfer_in = redis_conn.get(key).decode()
            if coin_family == "DOGE":
                return float(xfer_in)
            else:
                return int(float(xfer_in))
    except Exception as e:
        await logchanbot(traceback.format_exc())
    # redis_conn.set(key, json.dumps(decoded_data), ex=config.miningpoolstat.expired)
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    userwallet = await sql_get_userwallet(userID, COIN_NAME, user_server)
    # assume insert time 2mn
    confirmed_inserted = 4*60
    confirmed_inserted_doge_fam = 45*60
    IncomingTx = 0
    if userwallet is None:
        return IncomingTx    

    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if coin_family in ["TRTL", "BCN"]:
                    sql = """ SELECT SUM(amount) AS IncomingTx FROM cnoff_get_transfers WHERE `payment_id`=%s AND `coin_name` = %s 
                              AND `amount`>0 AND `time_insert`< %s """
                    await cur.execute(sql, (userwallet['paymentid'], COIN_NAME, int(time.time())-confirmed_inserted))
                    result = await cur.fetchone()
                    if result and result['IncomingTx']: IncomingTx = result['IncomingTx']
                elif coin_family == "XMR":
                    sql = """ SELECT SUM(amount) AS IncomingTx FROM xmroff_get_transfers WHERE `payment_id`=%s AND `coin_name` = %s 
                              AND `amount`>0 AND `time_insert`<%s """
                    await cur.execute(sql, (userwallet['paymentid'], COIN_NAME, int(time.time())-confirmed_inserted))
                    result = await cur.fetchone()
                    if result and result['IncomingTx']: IncomingTx = result['IncomingTx']
                elif coin_family == "XCH":
                    sql = """ SELECT SUM(amount) AS IncomingTx FROM xch_get_transfers WHERE `address`=%s AND `coin_name` = %s 
                              AND `amount`>0 AND `time_insert`<%s """
                    await cur.execute(sql, (userwallet['balance_wallet_address'], COIN_NAME, int(time.time())-confirmed_inserted))
                    result = await cur.fetchone()
                    if result and result['IncomingTx']: IncomingTx = result['IncomingTx']
                elif coin_family == "DOGE":
                    sql = """ SELECT SUM(amount) AS IncomingTx FROM doge_get_transfers WHERE `address`=%s AND `coin_name` = %s AND `category` = %s 
                              AND (`confirmations`>=%s OR `time_insert`< %s) AND `amount`>0 """
                    await cur.execute(sql, (userwallet['balance_wallet_address'], COIN_NAME, 'receive', wallet.get_confirm_depth(COIN_NAME), int(time.time())-confirmed_inserted_doge_fam))
                    result = await cur.fetchone()
                    if result and result['IncomingTx']: IncomingTx = result['IncomingTx']
                elif coin_family == "NANO":
                    sql = """ SELECT SUM(amount) AS IncomingTx FROM nano_move_deposit WHERE `user_id`=%s AND `coin_name` = %s 
                              AND `amount`>0 AND `time_insert`< %s """
                    await cur.execute(sql, (userID, COIN_NAME, int(time.time())-confirmed_inserted))
                    result = await cur.fetchone()
                    if result and result['IncomingTx']: IncomingTx = result['IncomingTx']
    except Exception as e:
        await logchanbot(traceback.format_exc())

    # store in redis
    try:
        if redis_conn is None: redis_conn = redis.Redis(connection_pool=redis_pool)
        if redis_conn: redis_conn.set(key, str(IncomingTx), ex=redis_expired)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return IncomingTx


async def sql_user_get_tipstat(userID: str, coin: str, update: bool=False, user_server: str = 'DISCORD'):
    global pool, redis_pool, redis_conn, redis_expired
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    COIN_NAME = coin.upper()
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    elif COIN_NAME in ENABLE_COIN_TRC:
        coin_family = "TRC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    key = f"TIPBOT:TIPSTAT_{COIN_NAME}:" + f"{user_server}_{userID}"
    if update == False:
        try:
            if redis_conn is None: redis_conn = redis.Redis(connection_pool=redis_pool)
            if redis_conn and redis_conn.exists(key):
                tipstat = redis_conn.get(key).decode()
                return json.loads(tipstat)
        except Exception as e:
            await logchanbot(traceback.format_exc())

    # if not in redis
    user_stat =  {'tx_out': 0, 'tx_in': 0}
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if coin_family in ["TRTL", "BCN"]:
                    sql = """ SELECT (SELECT COUNT(*) FROM cnoff_mv_tx WHERE `from_userid` = %s AND `coin_name`=%s ) as ex_tip,
                                     (SELECT COUNT(*) FROM cnoff_mv_tx WHERE `to_userid` = %s AND `coin_name`=%s ) as in_tip """
                    await cur.execute(sql, (userID, COIN_NAME, userID, COIN_NAME,))
                    result = await cur.fetchone()
                    if result:
                        user_stat =  {'tx_out': result['ex_tip'], 'tx_in': result['in_tip']}
                elif coin_family == "XMR":
                    sql = """ SELECT (SELECT COUNT(*) FROM xmroff_mv_tx WHERE `from_userid` = %s AND `coin_name`=%s ) as ex_tip,
                                     (SELECT COUNT(*) FROM xmroff_mv_tx WHERE `to_userid` = %s AND `coin_name`=%s ) as in_tip """
                    await cur.execute(sql, (userID, COIN_NAME, userID, COIN_NAME,))
                    result = await cur.fetchone()
                    if result:
                        user_stat =  {'tx_out': result['ex_tip'], 'tx_in': result['in_tip']}
                elif coin_family == "DOGE":
                    sql = """ SELECT (SELECT COUNT(*) FROM doge_mv_tx WHERE `from_userid` = %s AND `coin_name`=%s ) as ex_tip,
                                     (SELECT COUNT(*) FROM doge_mv_tx WHERE `to_userid` = %s AND `coin_name`=%s ) as in_tip """
                    await cur.execute(sql, (userID, COIN_NAME, userID, COIN_NAME,))
                    result = await cur.fetchone()
                    if result:
                        user_stat =  {'tx_out': result['ex_tip'], 'tx_in': result['in_tip']}
                elif coin_family == "NANO":
                    sql = """ SELECT (SELECT COUNT(*) FROM nano_mv_tx WHERE `from_userid` = %s AND `coin_name`=%s ) as ex_tip,
                                     (SELECT COUNT(*) FROM nano_mv_tx WHERE `to_userid` = %s AND `coin_name`=%s ) as in_tip """
                    await cur.execute(sql, (userID, COIN_NAME, userID, COIN_NAME,))
                    result = await cur.fetchone()
                    if result:
                        user_stat =  {'tx_out': result['ex_tip'], 'tx_in': result['in_tip']}
                elif coin_family == "ERC-20":
                    sql = """ SELECT (SELECT COUNT(*) FROM erc_mv_tx WHERE `from_userid` = %s AND `token_name`=%s ) as ex_tip,
                                     (SELECT COUNT(*) FROM erc_mv_tx WHERE `to_userid` = %s AND `token_name`=%s ) as in_tip """
                    await cur.execute(sql, (userID, COIN_NAME, userID, COIN_NAME,))
                    result = await cur.fetchone()
                    if result:
                        user_stat =  {'tx_out': result['ex_tip'], 'tx_in': result['in_tip']}
                elif coin_family == "TRC-20":
                    sql = """ SELECT (SELECT COUNT(*) FROM trx_mv_tx WHERE `from_userid` = %s AND `token_name`=%s ) as ex_tip,
                                     (SELECT COUNT(*) FROM trx_mv_tx WHERE `to_userid` = %s AND `token_name`=%s ) as in_tip """
                    await cur.execute(sql, (userID, COIN_NAME, userID, COIN_NAME,))
                    result = await cur.fetchone()
                    if result:
                        user_stat =  {'tx_out': result['ex_tip'], 'tx_in': result['in_tip']}
    except Exception as e:
        print(traceback.format_exc())
        await logchanbot(traceback.format_exc())
    # store in redis
    try:
        openRedis()
        if redis_conn:
            # set it longer. 20mn to store 0 balance
            redis_conn.set(key, json.dumps(user_stat), ex=config.redis_setting.tipstat)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return user_stat


async def sql_user_balance_adjust(userID: str, coin: str, update: bool=False, user_server: str = 'DISCORD'):
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return

    COIN_NAME = coin.upper()
    key = f"TIPBOT:TIPBAL_{COIN_NAME}:" + f"{user_server}_{userID}"
    if update == False:
        try:
            if redis_conn is None: redis_conn = redis.Redis(connection_pool=redis_pool)
            if redis_conn and redis_conn.exists(key):
                balance = redis_conn.get(key).decode()
                if COIN_NAME in ENABLE_COIN_ERC+ENABLE_COIN_TRC+ENABLE_COIN_DOGE:
                    return float(balance)
                elif COIN_NAME in ENABLE_COIN+ENABLE_COIN_NANO+ENABLE_XMR:
                    return int(balance)
        except Exception as e:
            await logchanbot(traceback.format_exc())

    userdata_balance = await sql_user_balance(userID, COIN_NAME, user_server)
    xfer_in = 0
    if COIN_NAME not in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
        xfer_in = await sql_user_balance_get_xfer_in(userID, COIN_NAME, user_server)
    if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_COIN_TRC:
        actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
    elif COIN_NAME in ENABLE_COIN_NANO:
        actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
        actual_balance = round(actual_balance / wallet.get_decimal(COIN_NAME), 6) * wallet.get_decimal(COIN_NAME)
    else:
        actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])

    # store in redis
    try:
        openRedis()
        if redis_conn:
            redis_conn.set(key, str(actual_balance), ex=config.redis_setting.balance_in_redis)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return actual_balance


async def sql_user_balance(userID: str, coin: str, user_server: str = 'DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    COIN_NAME = coin.upper()
    if COIN_NAME in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
        ## update balance called_Update
        try:
            update_call = await sql_update_erc_trc_user_update_call(userID, COIN_NAME, user_server)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    elif COIN_NAME in ENABLE_COIN_TRC:
        coin_family = "TRC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if coin_family in ["TRTL", "BCN"]:
                    sql = """ SELECT SUM(amount) AS Expense FROM cnoff_mv_tx WHERE `from_userid`=%s AND `coin_name` = %s AND `user_server` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        Expense = result['Expense']
                    else:
                        Expense = 0

                    sql = """ SELECT SUM(amount) AS Income FROM cnoff_mv_tx WHERE `to_userid`=%s AND `coin_name` = %s AND `user_server` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        Income = result['Income']
                    else:
                        Income = 0

                    sql = """ SELECT SUM(amount+fee) AS TxExpense FROM cnoff_external_tx WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        TxExpense = result['TxExpense']
                    else:
                        TxExpense = 0

                    sql = """ SELECT SUM(amount) AS SwapIn FROM discord_swap_balance WHERE `owner_id`=%s AND `coin_name` = %s and `to` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, 'TIPBOT'))
                    result = await cur.fetchone()
                    if result:
                        SwapIn = result['SwapIn']
                    else:
                        SwapIn = 0

                    sql = """ SELECT SUM(amount) AS SwapOut FROM discord_swap_balance WHERE `owner_id`=%s AND `coin_name` = %s and `from` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, 'TIPBOT'))
                    result = await cur.fetchone()
                    if result:
                        SwapOut = result['SwapOut']
                    else:
                        SwapOut = 0
                elif coin_family == "XMR":
                    sql = """ SELECT SUM(amount) AS Expense FROM xmroff_mv_tx WHERE `from_userid`=%s AND `coin_name` = %s AND `user_server` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        Expense = result['Expense']
                    else:
                        Expense = 0

                    sql = """ SELECT SUM(amount) AS Income FROM xmroff_mv_tx WHERE `to_userid`=%s AND `coin_name` = %s AND `user_server` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        Income = result['Income']
                    else:
                        Income = 0

                    sql = """ SELECT SUM(amount+fee) AS TxExpense FROM xmroff_external_tx WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        TxExpense = result['TxExpense']
                    else:
                        TxExpense = 0

                    sql = """ SELECT SUM(amount) AS SwapIn FROM discord_swap_balance WHERE `owner_id`=%s AND `coin_name` = %s and `to` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, 'TIPBOT'))
                    result = await cur.fetchone()
                    if result:
                        SwapIn = result['SwapIn']
                    else:
                        SwapIn = 0

                    sql = """ SELECT SUM(amount) AS SwapOut FROM discord_swap_balance WHERE `owner_id`=%s AND `coin_name` = %s and `from` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, 'TIPBOT'))
                    result = await cur.fetchone()
                    if result:
                        SwapOut = result['SwapOut']
                    else:
                        SwapOut = 0
                elif coin_family == "XCH":
                    sql = """ SELECT SUM(amount) AS Expense FROM xch_mv_tx WHERE `from_userid`=%s AND `coin_name` = %s AND `user_server` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        Expense = result['Expense']
                    else:
                        Expense = 0

                    sql = """ SELECT SUM(amount) AS Income FROM xch_mv_tx WHERE `to_userid`=%s AND `coin_name` = %s AND `user_server` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        Income = result['Income']
                    else:
                        Income = 0

                    sql = """ SELECT SUM(amount+fee) AS TxExpense FROM xch_external_tx WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        TxExpense = result['TxExpense']
                    else:
                        TxExpense = 0

                    sql = """ SELECT SUM(amount) AS SwapIn FROM discord_swap_balance WHERE `owner_id`=%s AND `coin_name` = %s and `to` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, 'TIPBOT'))
                    result = await cur.fetchone()
                    if result:
                        SwapIn = result['SwapIn']
                    else:
                        SwapIn = 0

                    sql = """ SELECT SUM(amount) AS SwapOut FROM discord_swap_balance WHERE `owner_id`=%s AND `coin_name` = %s and `from` = %s """
                    await cur.execute(sql, (userID, COIN_NAME, 'TIPBOT'))
                    result = await cur.fetchone()
                    if result:
                        SwapOut = result['SwapOut']
                    else:
                        SwapOut = 0
                # DOGE
                elif coin_family == "DOGE":
                    sql = """ SELECT SUM(amount) AS Expense FROM doge_mv_tx WHERE `from_userid`=%s AND `coin_name`=%s AND `user_server`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        Expense = result['Expense']
                    else:
                        Expense = 0

                    sql = """ SELECT SUM(amount) AS Income FROM doge_mv_tx WHERE `to_userid`=%s AND `coin_name`=%s AND `user_server`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        Income = result['Income']
                    else:
                        Income = 0

                    sql = """ SELECT SUM(amount+fee) AS TxExpense FROM doge_external_tx WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        TxExpense = result['TxExpense']
                    else:
                        TxExpense = 0

                    sql = """ SELECT SUM(amount) AS SwapIn FROM discord_swap_balance WHERE `owner_id`=%s AND `coin_name` = %s AND `to` = %s AND `user_server`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, 'TIPBOT', user_server))
                    result = await cur.fetchone()
                    if result:
                        SwapIn = result['SwapIn']
                    else:
                        SwapIn = 0

                    sql = """ SELECT SUM(amount) AS SwapOut FROM discord_swap_balance WHERE `owner_id`=%s AND `coin_name` = %s AND `from` = %s AND `user_server`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, 'TIPBOT', user_server))
                    result = await cur.fetchone()
                    if result:
                        SwapOut = result['SwapOut']
                    else:
                        SwapOut = 0
                # NANO
                elif coin_family == "NANO":
                    sql = """ SELECT SUM(amount) AS Expense FROM nano_mv_tx WHERE `from_userid`=%s AND `coin_name`=%s AND `user_server`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        Expense = result['Expense']
                    else:
                        Expense = 0

                    sql = """ SELECT SUM(amount) AS Income FROM nano_mv_tx WHERE `to_userid`=%s AND `coin_name`=%s AND `user_server`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        Income = result['Income']
                    else:
                        Income = 0

                    sql = """ SELECT SUM(amount) AS TxExpense FROM nano_external_tx WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        TxExpense = result['TxExpense']
                    else:
                        TxExpense = 0
                elif coin_family == "ERC-20":
                    token_info = await get_token_info(COIN_NAME)
                    confirmed_depth = token_info['deposit_confirm_depth']
                    # When sending tx out, (negative)
                    sql = """ SELECT SUM(real_amount+real_external_fee) AS TxExpense FROM erc_external_tx 
                              WHERE `user_id`=%s AND `token_name` = %s AND `user_server`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        TxExpense = result['TxExpense']
                    else:
                        TxExpense = 0

                    sql = """ SELECT SUM(real_amount) AS Expense FROM erc_mv_tx WHERE `from_userid`=%s AND `token_name` = %s AND `user_server`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        Expense = result['Expense']
                    else:
                        Expense = 0

                    sql = """ SELECT SUM(real_amount) AS Income FROM erc_mv_tx WHERE `to_userid`=%s AND `token_name` = %s AND `user_server`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        Income = result['Income']
                    else:
                        Income = 0
                    # in case deposit fee -real_deposit_fee
                    sql = """ SELECT SUM(real_amount - real_deposit_fee) AS Deposit FROM erc_move_deposit WHERE `user_id`=%s 
                              AND `token_name` = %s AND `confirmed_depth`>= %s """
                    await cur.execute(sql, (userID, COIN_NAME, confirmed_depth))
                    result = await cur.fetchone()
                    if result:
                        Deposit = result['Deposit']
                    else:
                        Deposit = 0
                elif coin_family == "TRC-20":
                    token_info = await get_token_info(COIN_NAME)
                    confirmed_depth = token_info['deposit_confirm_depth']
                    # When sending tx out, (negative)
                    sql = """ SELECT SUM(real_amount+real_external_fee) AS TxExpense FROM trx_external_tx 
                              WHERE `user_id`=%s AND `token_name` = %s AND `user_server`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        TxExpense = result['TxExpense']
                    else:
                        TxExpense = 0

                    sql = """ SELECT SUM(real_amount) AS Expense FROM trx_mv_tx WHERE `from_userid`=%s AND `token_name` = %s AND `user_server`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        Expense = result['Expense']
                    else:
                        Expense = 0

                    sql = """ SELECT SUM(real_amount) AS Income FROM trx_mv_tx WHERE `to_userid`=%s AND `token_name` = %s AND `user_server`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        Income = result['Income']
                    else:
                        Income = 0
                    # in case deposit fee -real_deposit_fee
                    sql = """ SELECT SUM(real_amount - real_deposit_fee) AS Deposit FROM trx_move_deposit WHERE `user_id`=%s 
                              AND `token_name` = %s AND `confirmed_depth`>= %s AND `status`=%s """
                    await cur.execute(sql, (userID, COIN_NAME, confirmed_depth, 'CONFIRMED'))
                    result = await cur.fetchone()
                    if result:
                        Deposit = result['Deposit']
                    else:
                        Deposit = 0
                # Credit by admin is positive (Positive)
                sql = """ SELECT SUM(amount) AS Credited FROM credit_balance WHERE `coin_name`=%s AND `to_userid`=%s 
                      AND `user_server`=%s """
                await cur.execute(sql, (COIN_NAME, userID, user_server))
                result = await cur.fetchone()
                if result:
                    Credited = result['Credited']
                else:
                    Credited = 0

                # Voucher create (Negative)
                sql = """ SELECT SUM(amount+reserved_fee) AS Expended_Voucher FROM cn_voucher 
                          WHERE `coin_name`=%s AND `user_id`=%s AND `user_server`=%s """
                await cur.execute(sql, (COIN_NAME, userID, user_server))
                result = await cur.fetchone()
                if result:
                    Expended_Voucher = result['Expended_Voucher']
                else:
                    Expended_Voucher = 0

                # Game Credit
                sql = """ SELECT SUM(won_amount) AS GameCredit FROM discord_game WHERE `coin_name`=%s AND `played_user`=%s 
                      AND `user_server`=%s """
                await cur.execute(sql, (COIN_NAME, userID, user_server))
                result = await cur.fetchone()
                if result:
                    GameCredit = result['GameCredit']
                else:
                    GameCredit = 0

                # Expense (negative)
                sql = """ SELECT SUM(amount_sell) AS OpenOrder FROM open_order WHERE `coin_sell`=%s AND `userid_sell`=%s 
                          AND `status`=%s
                      """
                await cur.execute(sql, (COIN_NAME, userID, 'OPEN'))
                result = await cur.fetchone()
                if result:
                    OpenOrder = result['OpenOrder']
                else:
                    OpenOrder = 0

                # Complete Order could be partial match but data is at the complete_order, they are CompleteOrderAdd (Negative)
                sql = """ SELECT SUM(amount_sell) AS CompleteOrderMinus FROM open_order WHERE `coin_sell`=%s AND `userid_sell`=%s  
                          AND `status`=%s
                      """
                await cur.execute(sql, (COIN_NAME, userID, 'COMPLETE'))
                result = await cur.fetchone()
                CompleteOrderMinus = 0
                if result and ('CompleteOrderMinus' in result) and (result['CompleteOrderMinus'] is not None):
                    CompleteOrderMinus = result['CompleteOrderMinus']

                # Complete Order could be partial match but data is at the complete_order, they are CompleteOrderAdd (Negative)
                sql = """ SELECT SUM(amount_get_after_fee) AS CompleteOrderMinus2 FROM open_order WHERE `coin_get`=%s AND `userid_get`=%s  
                          AND `status`=%s
                      """
                await cur.execute(sql, (COIN_NAME, userID, 'COMPLETE'))
                result = await cur.fetchone()
                CompleteOrderMinus2 = 0
                if result and ('CompleteOrderMinus2' in result) and (result['CompleteOrderMinus2'] is not None):
                    CompleteOrderMinus2 = result['CompleteOrderMinus2']

                # Complete Order could be partial match but data is at the complete_order, they are CompleteOrderAdd (Positive)
                sql = """ SELECT SUM(amount_sell_after_fee) AS CompleteOrderAdd FROM open_order WHERE `coin_sell`=%s AND `userid_get`=%s  
                          AND `status`=%s
                      """
                await cur.execute(sql, (COIN_NAME, userID, 'COMPLETE'))
                result = await cur.fetchone()
                CompleteOrderAdd = 0
                if result and ('CompleteOrderAdd' in result) and (result['CompleteOrderAdd'] is not None):
                    CompleteOrderAdd = result['CompleteOrderAdd']

                # Complete Order could be partial match but data is at the complete_order, they are CompleteOrderAdd (Positive)
                sql = """ SELECT SUM(amount_get_after_fee) AS CompleteOrderAdd2 FROM open_order WHERE `coin_get`=%s AND `userid_sell`=%s  
                          AND `status`=%s
                      """
                await cur.execute(sql, (COIN_NAME, userID, 'COMPLETE'))
                result = await cur.fetchone()
                CompleteOrderAdd2 = 0
                if result and ('CompleteOrderAdd2' in result) and (result['CompleteOrderAdd2'] is not None):
                    CompleteOrderAdd2 = result['CompleteOrderAdd2']

                # user_move_balance move_out
                sql = """ SELECT SUM(amount) AS move_out FROM user_move_balance WHERE `coin_name`=%s AND `from_userid`=%s  
                          AND `from_server`=%s
                      """
                await cur.execute(sql, (COIN_NAME, userID, user_server))
                result = await cur.fetchone()
                move_out = 0
                if result and ('move_out' in result) and result['move_out']:
                    move_out = result['move_out']

                # user_move_balance move_in
                sql = """ SELECT SUM(amount) AS move_in FROM user_move_balance WHERE `coin_name`=%s AND `to_userid`=%s  
                          AND `to_server`=%s
                      """
                await cur.execute(sql, (COIN_NAME, userID, user_server))
                result = await cur.fetchone()
                move_in = 0
                if result and ('move_in' in result) and result['move_in']:
                    move_in = result['move_in']

                # guild_raffle_entries fee entry
                sql = """ SELECT SUM(amount) AS raffle_fee FROM guild_raffle_entries WHERE `coin_name`=%s AND `user_id`=%s  
                          AND `user_server`=%s AND `status`=%s
                      """
                await cur.execute(sql, (COIN_NAME, userID, user_server, 'REGISTERED'))
                result = await cur.fetchone()
                raffle_fee = 0
                if result and ('raffle_fee' in result) and result['raffle_fee']:
                    raffle_fee = result['raffle_fee']

                # guild_raffle_entries reward
                sql = """ SELECT SUM(won_amount) AS raffle_reward FROM guild_raffle_entries WHERE `coin_name`=%s AND `user_id`=%s  
                          AND `user_server`=%s AND `status`=%s
                      """
                await cur.execute(sql, (COIN_NAME, userID, user_server, 'WINNER'))
                result = await cur.fetchone()
                raffle_reward = 0
                if result and ('raffle_reward' in result) and result['raffle_reward']:
                    raffle_reward = result['raffle_reward']

                # economy reward earn
                sql = """ SELECT SUM(reward_amount) AS eco_userearn FROM discord_economy_activities WHERE `reward_coin_name`=%s AND `user_id`=%s  
                      """
                await cur.execute(sql, (COIN_NAME, userID,))
                result = await cur.fetchone()
                eco_userearn = 0
                if result and ('eco_userearn' in result) and result['eco_userearn']:
                    eco_userearn = result['eco_userearn']

                # economy food spend
                sql = """ SELECT SUM(cost_expense_amount) AS eating_spend FROM discord_economy_eating WHERE `cost_coin_name`=%s AND `user_id`=%s  
                      """
                await cur.execute(sql, (COIN_NAME, userID,))
                result = await cur.fetchone()
                eating_spend = 0
                if result and ('eating_spend' in result) and result['eating_spend']:
                    eating_spend = result['eating_spend']

                # guild economy reward earn
                sql = """ SELECT (-SUM(reward_amount)-SUM(ABS(fee_amount))) AS eco_guildearn FROM discord_economy_activities WHERE `reward_coin_name`=%s AND `guild_id`=%s  
                      """
                await cur.execute(sql, (COIN_NAME, userID,))
                result = await cur.fetchone()
                eco_guildearn = 0
                if result and ('eco_guildearn' in result) and result['eco_guildearn']:
                    eco_guildearn = result['eco_guildearn']

                # guild economy food spend
                sql = """ SELECT (SUM(cost_expense_amount)-SUM(ABS(fee_amount))) AS eating_guildearn FROM discord_economy_eating WHERE `cost_coin_name`=%s AND `guild_id`=%s  
                      """
                await cur.execute(sql, (COIN_NAME, userID,))
                result = await cur.fetchone()
                eating_guildearn = 0
                if result and ('eating_guildearn' in result) and result['eating_guildearn']:
                    eating_guildearn = result['eating_guildearn']

                economy_balance = eco_userearn - eating_spend + eco_guildearn + eating_guildearn
                # discord_swap_token
                if COIN_NAME in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
                    sql = """ SELECT SUM(from_real_amount) AS swap_token_out FROM discord_swap_token WHERE `from_coin_name`=%s AND `user_id`=%s  
                              AND `user_server`=%s
                          """
                else:
                    sql = """ SELECT SUM(from_real_amount*POWER(10, from_decimal)) AS swap_token_out FROM discord_swap_token WHERE `from_coin_name`=%s AND `user_id`=%s  
                              AND `user_server`=%s
                          """
                await cur.execute(sql, (COIN_NAME, userID, user_server))
                result = await cur.fetchone()
                swap_token_out = 0
                if result and ('swap_token_out' in result) and result['swap_token_out']:
                    swap_token_out = result['swap_token_out']
                if COIN_NAME in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
                    sql = """ SELECT SUM(to_real_amount) AS swap_token_in FROM discord_swap_token WHERE `to_coin_name`=%s AND `user_id`=%s  
                              AND `user_server`=%s
                          """
                else:
                    sql = """ SELECT SUM(to_real_amount*POWER(10, to_decimal)) AS swap_token_in FROM discord_swap_token WHERE `to_coin_name`=%s AND `user_id`=%s  
                              AND `user_server`=%s
                          """
                await cur.execute(sql, (COIN_NAME, userID, user_server))
                result = await cur.fetchone()
                swap_token_in = 0
                if result and ('swap_token_in' in result) and result['swap_token_in']:
                    swap_token_in = result['swap_token_in']

                balance = {}
                if coin_family == "NANO":
                    balance['Expense'] = Expense or 0
                    balance['Income'] = Income or 0
                    balance['TxExpense'] = TxExpense or 0
                    balance['Credited'] = Credited if Credited else 0
                    balance['GameCredit'] = GameCredit if GameCredit else 0
                    balance['Expended_Voucher'] = Expended_Voucher if Expended_Voucher else 0

                    balance['OpenOrder'] = OpenOrder if OpenOrder else 0
                    balance['CompleteOrderMinus'] = CompleteOrderMinus if CompleteOrderMinus else 0
                    balance['CompleteOrderMinus2'] = CompleteOrderMinus2 if CompleteOrderMinus2 else 0
                    balance['CompleteOrderAdd'] = CompleteOrderAdd if CompleteOrderAdd else 0
                    balance['CompleteOrderAdd2'] = CompleteOrderAdd2 if CompleteOrderAdd2 else 0

                    balance['move_in'] = move_in if move_in else 0
                    balance['move_out'] = move_out if move_out else 0

                    balance['raffle_fee'] = raffle_fee if raffle_fee else 0
                    balance['raffle_reward'] = raffle_reward if raffle_reward else 0

                    balance['swap_token_in'] = swap_token_in if swap_token_in else 0
                    balance['swap_token_out'] = swap_token_out if swap_token_out else 0

                    balance['Adjust'] = int(balance['Credited']) + int(balance['GameCredit']) \
                    + int(balance['Income']) - int(balance['Expense']) - int(balance['TxExpense']) - int(balance['Expended_Voucher']) \
                    - balance['OpenOrder'] - balance['CompleteOrderMinus'] - balance['CompleteOrderMinus2'] \
                    + balance['CompleteOrderAdd'] + balance['CompleteOrderAdd2'] \
                    + balance['move_in'] - balance['move_out'] \
                    + balance['raffle_reward'] - balance['raffle_fee'] \
                    + balance['swap_token_in'] - balance['swap_token_out']
                    balance['economy_balance'] = economy_balance
                elif coin_family == "DOGE":
                    balance['Expense'] = Expense or 0
                    balance['Expense'] = round(balance['Expense'], 4)
                    balance['Income'] = Income or 0
                    balance['TxExpense'] = TxExpense or 0
                    balance['SwapIn'] = SwapIn or 0
                    balance['SwapOut'] = SwapOut or 0
                    balance['Credited'] = Credited if Credited else 0
                    balance['GameCredit'] = GameCredit if GameCredit else 0
                    balance['Expended_Voucher'] = Expended_Voucher if Expended_Voucher else 0

                    balance['OpenOrder'] = OpenOrder if OpenOrder else 0
                    balance['CompleteOrderMinus'] = CompleteOrderMinus if CompleteOrderMinus else 0
                    balance['CompleteOrderMinus2'] = CompleteOrderMinus2 if CompleteOrderMinus2 else 0
                    balance['CompleteOrderAdd'] = CompleteOrderAdd if CompleteOrderAdd else 0
                    balance['CompleteOrderAdd2'] = CompleteOrderAdd2 if CompleteOrderAdd2 else 0

                    balance['move_in'] = move_in if move_in else 0
                    balance['move_out'] = move_out if move_out else 0

                    balance['raffle_fee'] = raffle_fee if raffle_fee else 0
                    balance['raffle_reward'] = raffle_reward if raffle_reward else 0

                    balance['swap_token_in'] = swap_token_in if swap_token_in else 0
                    balance['swap_token_out'] = swap_token_out if swap_token_out else 0

                    balance['Adjust'] = float(balance['Credited']) + float(balance['GameCredit']) + float(balance['Income']) + float(balance['SwapIn']) - float(balance['Expense']) \
                    - float(balance['TxExpense']) - float(balance['SwapOut']) - float(balance['Expended_Voucher']) \
                    - float(balance['OpenOrder']) - float(balance['CompleteOrderMinus']) - float(balance['CompleteOrderMinus2']) \
                    + float(balance['CompleteOrderAdd']) + float(balance['CompleteOrderAdd2']) \
                    + float(balance['move_in']) - float(balance['move_out']) \
                    + float(balance['raffle_reward']) - float(balance['raffle_fee']) \
                    + float(balance['swap_token_in']) - float(balance['swap_token_out'])
                    balance['economy_balance'] = float(economy_balance)
                elif coin_family == "XMR" or coin_family == "XCH":
                    balance['Expense'] = float(Expense) if Expense else 0
                    balance['Expense'] = float(round(balance['Expense'], 4))
                    balance['Income'] = float(Income) if Income else 0
                    balance['TxExpense'] = float(TxExpense) if TxExpense else 0
                    balance['Credited'] = float(Credited) if Credited else 0
                    balance['GameCredit'] = float(GameCredit) if GameCredit else 0
                    balance['SwapIn'] = float(SwapIn) if SwapIn else 0
                    balance['SwapOut'] = float(SwapOut) if SwapOut else 0
                    balance['Expended_Voucher'] = float(Expended_Voucher) if Expended_Voucher else 0

                    balance['OpenOrder'] = OpenOrder if OpenOrder else 0
                    balance['CompleteOrderMinus'] = CompleteOrderMinus if CompleteOrderMinus else 0
                    balance['CompleteOrderMinus2'] = CompleteOrderMinus2 if CompleteOrderMinus2 else 0
                    balance['CompleteOrderAdd'] = CompleteOrderAdd if CompleteOrderAdd else 0
                    balance['CompleteOrderAdd2'] = CompleteOrderAdd2 if CompleteOrderAdd2 else 0

                    balance['move_in'] = move_in if move_in else 0
                    balance['move_out'] = move_out if move_out else 0

                    balance['raffle_fee'] = raffle_fee if raffle_fee else 0
                    balance['raffle_reward'] = raffle_reward if raffle_reward else 0

                    balance['swap_token_in'] = swap_token_in if swap_token_in else 0
                    balance['swap_token_out'] = swap_token_out if swap_token_out else 0

                    balance['Adjust'] = balance['Credited'] + balance['GameCredit'] + balance['Income'] + balance['SwapIn'] - balance['Expense'] - balance['TxExpense'] \
                    - balance['SwapOut'] - balance['Expended_Voucher'] \
                    - int(balance['OpenOrder']) - int(balance['CompleteOrderMinus']) - int(balance['CompleteOrderMinus2']) \
                    + int(balance['CompleteOrderAdd']) + int(balance['CompleteOrderAdd2']) \
                    + int(balance['move_in']) - int(balance['move_out']) \
                    + int(balance['raffle_reward']) - int(balance['raffle_fee']) \
                    + int(balance['swap_token_in']) - int(balance['swap_token_out'])
                    balance['economy_balance'] = int(economy_balance)
                elif coin_family == "ERC-20" or coin_family == "TRC-20":
                    balance['Deposit'] = float("%.3f" % Deposit) if Deposit else 0
                    balance['Expense'] = float("%.3f" % Expense) if Expense else 0
                    balance['Income'] = float("%.3f" % Income) if Income else 0
                    balance['TxExpense'] = float("%.3f" % TxExpense) if TxExpense else 0
                    balance['Credited'] = float("%.3f" % Credited) if Credited else 0
                    balance['GameCredit'] = float("%.3f" % GameCredit) if GameCredit else 0
                    balance['Expended_Voucher'] = float("%.3f" % Expended_Voucher) if Expended_Voucher else 0

                    balance['OpenOrder'] = float("%.3f" % OpenOrder) if OpenOrder else 0
                    balance['CompleteOrderMinus'] = float("%.3f" % CompleteOrderMinus) if CompleteOrderMinus else 0
                    balance['CompleteOrderMinus2'] = float("%.3f" % CompleteOrderMinus2) if CompleteOrderMinus2 else 0
                    balance['CompleteOrderAdd'] = float("%.3f" % CompleteOrderAdd) if CompleteOrderAdd else 0
                    balance['CompleteOrderAdd2'] = float("%.3f" % CompleteOrderAdd2) if CompleteOrderAdd2 else 0

                    balance['move_in'] = float("%.3f" % move_in) if move_in else 0
                    balance['move_out'] = float("%.3f" % move_out) if move_out else 0

                    balance['raffle_fee'] = float("%.3f" % raffle_fee) if raffle_fee else 0
                    balance['raffle_reward'] = float("%.3f" % raffle_reward) if raffle_reward else 0

                    balance['swap_token_in'] = float("%.3f" % swap_token_in) if swap_token_in else 0
                    balance['swap_token_out'] = float("%.3f" % swap_token_out) if swap_token_out else 0

                    balance['Adjust'] = float("%.3f" % (balance['Deposit'] + balance['Credited'] + balance['GameCredit'] + balance['Income'] - balance['Expense'] \
                    - balance['TxExpense'] - balance['Expended_Voucher'] \
                    - balance['OpenOrder'] - balance['CompleteOrderMinus'] - balance['CompleteOrderMinus2'] \
                    + balance['CompleteOrderAdd'] + balance['CompleteOrderAdd2'])) \
                    + balance['move_in'] - balance['move_out'] \
                    + balance['raffle_reward'] - balance['raffle_fee'] \
                    + balance['swap_token_in'] - balance['swap_token_out']
                    balance['economy_balance'] = float("%.3f" % economy_balance)
                elif coin_family in ["TRTL", "BCN"]:
                    balance['Expense'] = float(Expense) if Expense else 0
                    balance['Expense'] = float(round(balance['Expense'], 4))
                    balance['Income'] = float(Income) if Income else 0
                    balance['TxExpense'] = float(TxExpense) if TxExpense else 0
                    balance['SwapIn'] = float(SwapIn) if SwapIn else 0
                    balance['SwapOut'] = float(SwapOut) if SwapOut else 0
                    balance['Credited'] = float(Credited) if Credited else 0
                    balance['GameCredit'] = float(GameCredit) if GameCredit else 0
                    balance['Expended_Voucher'] = float(Expended_Voucher) if Expended_Voucher else 0

                    balance['OpenOrder'] = OpenOrder if OpenOrder else 0
                    balance['CompleteOrderMinus'] = CompleteOrderMinus if CompleteOrderMinus else 0
                    balance['CompleteOrderMinus2'] = CompleteOrderMinus2 if CompleteOrderMinus2 else 0
                    balance['CompleteOrderAdd'] = CompleteOrderAdd if CompleteOrderAdd else 0
                    balance['CompleteOrderAdd2'] = CompleteOrderAdd2 if CompleteOrderAdd2 else 0

                    balance['move_in'] = move_in if move_in else 0
                    balance['move_out'] = move_out if move_out else 0

                    balance['raffle_fee'] = raffle_fee if raffle_fee else 0
                    balance['raffle_reward'] = raffle_reward if raffle_reward else 0

                    balance['swap_token_in'] = swap_token_in if swap_token_in else 0
                    balance['swap_token_out'] = swap_token_out if swap_token_out else 0

                    balance['Adjust'] = balance['Credited'] + balance['GameCredit'] + balance['Income'] + balance['SwapIn'] - balance['Expense'] \
                    - balance['TxExpense'] - balance['SwapOut'] - balance['Expended_Voucher'] \
                    - int(balance['OpenOrder']) - int(balance['CompleteOrderMinus']) - int(balance['CompleteOrderMinus2']) \
                    + int(balance['CompleteOrderAdd']) + int(balance['CompleteOrderAdd2']) \
                    + int(balance['move_in']) - int(balance['move_out']) \
                    + int(balance['raffle_reward']) - int(balance['raffle_fee']) \
                    + int(balance['swap_token_in']) - int(balance['swap_token_out'])
                    balance['economy_balance'] = int(economy_balance)
                balance['Adjust'] += balance['economy_balance']
                return balance
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_nano_get_user_wallets(coin: str):
    global pool
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","BAN")
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM nano_user WHERE `coin_name` = %s """
                await cur.execute(sql, (COIN_NAME,))
                result = await cur.fetchall()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


# NANO Based
async def sql_mv_nano_single(user_from: str, to_user: str, amount: float, coin: str, tiptype: str, user_server: str = 'DISCORD'):
    global pool
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","NANO")
    if coin_family != "NANO":
        return False
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO nano_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`, `user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (COIN_NAME, user_from, to_user, amount, wallet.get_decimal(COIN_NAME), tiptype.upper(), int(time.time()), user_server))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_mv_nano_multiple(user_from: str, user_tos, amount_each: float, coin: str, tiptype: str):
    # user_tos is array "account1", "account2", ....
    global pool
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","NANO")
    if coin_family != "NANO":
        return False
    if tiptype.upper() not in ["TIPS", "TIPALL", "FREETIP", "FREETIPS", "GUILDTIP"]:
        return False
    values_str = []
    currentTs = int(time.time())
    for item in user_tos:
        values_str.append(f"('{COIN_NAME}', '{user_from}', '{item}', {amount_each}, {wallet.get_decimal(COIN_NAME)}, '{tiptype.upper()}', {currentTs})\n")
    values_sql = "VALUES " + ",".join(values_str)
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO nano_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`) 
                          """+values_sql+""" """
                await cur.execute(sql,)
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_external_nano_single(user_from: str, amount: int, to_address: str, coin: str, tiptype: str):
    global pool
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","NANO")
    if coin_family != "NANO":
        return False
    if tiptype.upper() not in ["SEND", "WITHDRAW"]:
        return False
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if coin_family == "NANO":
                    main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
                    tx_hash = await wallet.nano_sendtoaddress(main_address, to_address, amount, COIN_NAME)
                    if tx_hash:
                        updateTime = int(time.time())
                        async with conn.cursor() as cur: 
                            sql = """ INSERT INTO nano_external_tx (`coin_name`, `user_id`, `amount`, `decimal`, `to_address`, 
                                      `type`, `date`, `tx_hash`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, user_from, amount, wallet.get_decimal(COIN_NAME), to_address, tiptype.upper(), int(time.time()), tx_hash['block'],))
                            await conn.commit()
                            return tx_hash
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_block_height(coin: str):
    global pool, redis_conn
    updateTime = int(time.time())
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    gettopblock = None
    timeout = 60
    try:
        if COIN_NAME not in ENABLE_COIN_DOGE:
            gettopblock = await daemonrpc_client.gettopblock(COIN_NAME, time_out=timeout)
        else:
            gettopblock = await rpc_client.call_doge('getblockchaininfo', COIN_NAME)
    except asyncio.TimeoutError:
        pass
    except Exception as e:
        await logchanbot(traceback.format_exc())

    height = None
    if gettopblock:
        if COIN_NAME == "TRTL" or coin_family in ["XCH"]:
            height = int(gettopblock['height'])
        elif coin_family in ["TRTL", "BCN", "XMR"]:
            height = int(gettopblock['block_header']['height'])
        elif coin_family == "DOGE":
            height = int(gettopblock['blocks'])
        # store in redis
        try:
            openRedis()
            if redis_conn:
                redis_conn.set(f'{config.redis_setting.prefix_daemon_height}{COIN_NAME}', str(height))
        except Exception as e:
            await logchanbot(traceback.format_exc())


async def sql_update_balances(coin: str = None):
    global pool, redis_conn
    updateTime = int(time.time())
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    gettopblock = None
    timeout = 60
    try:
        if COIN_NAME not in ENABLE_COIN_DOGE:
            gettopblock = await daemonrpc_client.gettopblock(COIN_NAME, time_out=timeout)
        else:
            gettopblock = await rpc_client.call_doge('getblockchaininfo', COIN_NAME)
    except asyncio.TimeoutError:
        pass
    except Exception as e:
        await logchanbot(traceback.format_exc())

    height = None
    if gettopblock:
        if COIN_NAME == "TRTL" or coin_family == "XCH":
            height = int(gettopblock['height'])
        elif coin_family in ["TRTL", "BCN", "XMR"]:
            height = int(gettopblock['block_header']['height'])
        elif coin_family == "DOGE":
            height = int(gettopblock['blocks'])
        # store in redis
        try:
            openRedis()
            if redis_conn:
                redis_conn.set(f'{config.redis_setting.prefix_daemon_height}{COIN_NAME}', str(height))
        except Exception as e:
            await logchanbot(traceback.format_exc())
    else:
        try:
            openRedis()
            if redis_conn and redis_conn.exists(f'{config.redis_setting.prefix_daemon_height}{COIN_NAME}'):
                height = int(redis_conn.get(f'{config.redis_setting.prefix_daemon_height}{COIN_NAME}'))
        except Exception as e:
            await logchanbot(traceback.format_exc())

    if coin_family in ["TRTL", "BCN"]:
        #print('SQL: Updating get_transfers '+COIN_NAME)
        if COIN_NAME in WALLET_API_COIN:
            try:
                get_transfers = await walletapi.walletapi_get_transfers(COIN_NAME, height - 2000, height)
                list_balance_user = {}
                if get_transfers and len(get_transfers) >= 1:
                    await openConnection()
                    async with pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            sql = """ SELECT * FROM cnoff_get_transfers WHERE `coin_name` = %s """
                            await cur.execute(sql, (COIN_NAME,))
                            result = await cur.fetchall()
                            d = [i['txid'] for i in result]
                            # print('=================='+COIN_NAME+'===========')
                            # print(d)
                            # print('=================='+COIN_NAME+'===========')
                            for tx in get_transfers:
                                # Could be one block has two or more tx with different payment ID
                                # add to balance only confirmation depth meet
                                if len(tx['transfers']) > 0 and height >= int(tx['blockHeight']) + wallet.get_confirm_depth(COIN_NAME) \
                                and tx['transfers'][0]['amount'] >= wallet.get_min_deposit_amount(COIN_NAME) and 'paymentID' in tx:
                                    if ('paymentID' in tx) and (tx['paymentID'] in list_balance_user):
                                        if tx['transfers'][0]['amount'] > 0:
                                            list_balance_user[tx['paymentID']] += tx['transfers'][0]['amount']
                                    elif ('paymentID' in tx) and (tx['paymentID'] not in list_balance_user):
                                        if tx['transfers'][0]['amount'] > 0:
                                            list_balance_user[tx['paymentID']] = tx['transfers'][0]['amount']
                                    try:
                                        if tx['hash'] not in d:
                                            addresses = tx['transfers']
                                            address = ''
                                            for each_add in addresses:
                                                if len(each_add['address']) > 0: address = each_add['address']
                                                break
                                                    
                                            sql = """ INSERT IGNORE INTO cnoff_get_transfers (`coin_name`, `txid`, 
                                            `payment_id`, `height`, `timestamp`, `amount`, `fee`, `decimal`, `address`, time_insert) 
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                            await cur.execute(sql, (COIN_NAME, tx['hash'], tx['paymentID'], tx['blockHeight'], tx['timestamp'],
                                                                    tx['transfers'][0]['amount'], tx['fee'], wallet.get_decimal(COIN_NAME), address, int(time.time())))
                                            await conn.commit()
                                            # add to notification list also
                                            sql = """ INSERT IGNORE INTO discord_notify_new_tx (`coin_name`, `txid`, 
                                            `payment_id`, `height`, `amount`, `fee`, `decimal`) 
                                            VALUES (%s, %s, %s, %s, %s, %s, %s) """
                                            await cur.execute(sql, (COIN_NAME, tx['hash'], tx['paymentID'], tx['blockHeight'],
                                                                    tx['transfers'][0]['amount'], tx['fee'], wallet.get_decimal(COIN_NAME)))
                                            await conn.commit()
                                    except pymysql.err.Warning as e:
                                        await logchanbot(traceback.format_exc())
                                    except Exception as e:
                                        await logchanbot(traceback.format_exc())
                                elif len(tx['transfers']) > 0 and height < int(tx['blockHeight']) + wallet.get_confirm_depth(COIN_NAME) and \
                                tx['transfers'][0]['amount'] >= wallet.get_min_deposit_amount(COIN_NAME) and 'paymentID' in tx:
                                    # add notify to redis and alert deposit. Can be clean later?
                                    if config.notify_new_tx.enable_new_no_confirm == 1:
                                        key_tx_new = config.redis_setting.prefix_new_tx + 'NOCONFIRM'
                                        key_tx_json = config.redis_setting.prefix_new_tx + tx['hash']
                                        try:
                                            openRedis()
                                            if redis_conn and redis_conn.llen(key_tx_new) > 0:
                                                list_new_tx = redis_conn.lrange(key_tx_new, 0, -1)
                                                if list_new_tx and len(list_new_tx) > 0 and tx['hash'].encode() not in list_new_tx:
                                                    redis_conn.lpush(key_tx_new, tx['hash'])
                                                    redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['hash'], 'payment_id': tx['paymentID'], 'height': tx['blockHeight'],
                                                                                            'amount': tx['transfers'][0]['amount'], 'fee': tx['fee'], 'decimal': wallet.get_decimal(COIN_NAME)}), ex=86400)
                                            elif redis_conn and redis_conn.llen(key_tx_new) == 0:
                                                redis_conn.lpush(key_tx_new, tx['hash'])
                                                redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['hash'], 'payment_id': tx['paymentID'], 'height': tx['blockHeight'],
                                                                                        'amount': tx['transfers'][0]['amount'], 'fee': tx['fee'], 'decimal': wallet.get_decimal(COIN_NAME)}), ex=86400)
                                        except Exception as e:
                                            await logchanbot(traceback.format_exc())
                if list_balance_user and len(list_balance_user) > 0:
                    await openConnection()
                    async with pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            sql = """ SELECT coin_name, payment_id, SUM(amount) AS txIn FROM cnoff_get_transfers 
                                      WHERE coin_name = %s AND amount > 0 
                                      GROUP BY payment_id """
                            await cur.execute(sql, (COIN_NAME,))
                            result = await cur.fetchall()
                            timestamp = int(time.time())
                            list_update = []
                            if result and len(result) > 0:
                                for eachTxIn in result:
                                    list_update.append((eachTxIn['txIn'], timestamp, eachTxIn['payment_id']))
                                await cur.executemany(""" UPDATE cnoff_user_paymentid SET `actual_balance` = %s, `lastUpdate` = %s 
                                                          WHERE paymentid = %s """, list_update)
                                await conn.commit()
            except Exception as e:
                await logchanbot(traceback.format_exc())
        else:
            try:
                get_transfers = await wallet.getTransactions(COIN_NAME, int(height)-2000, 2000)
                list_balance_user = {}
                if get_transfers and len(get_transfers) >= 1:
                    await openConnection()
                    async with pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            sql = """ SELECT * FROM cnoff_get_transfers WHERE `coin_name` = %s """
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
                                    if height >= int(tx['blockIndex']) + wallet.get_confirm_depth(COIN_NAME) and tx['amount'] >= wallet.get_min_deposit_amount(COIN_NAME) \
                                    and 'paymentId' in tx:
                                        if ('paymentId' in tx) and (tx['paymentId'] in list_balance_user):
                                            if tx['amount'] > 0:
                                                list_balance_user[tx['paymentId']] += tx['amount']
                                        elif ('paymentId' in tx) and (tx['paymentId'] not in list_balance_user):
                                            if tx['amount'] > 0:
                                                list_balance_user[tx['paymentId']] = tx['amount']
                                        try:
                                            if tx['transactionHash'] not in d:
                                                addresses = tx['transfers']
                                                address = ''
                                                for each_add in addresses:
                                                    if len(each_add['address']) > 0: address = each_add['address']
                                                    break
                                                    
                                                sql = """ INSERT IGNORE INTO cnoff_get_transfers (`coin_name`, `txid`, 
                                                `payment_id`, `height`, `timestamp`, `amount`, `fee`, `decimal`, `address`, time_insert) 
                                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                await cur.execute(sql, (COIN_NAME, tx['transactionHash'], tx['paymentId'], tx['blockIndex'], tx['timestamp'],
                                                                        tx['amount'], tx['fee'], wallet.get_decimal(COIN_NAME), address, int(time.time())))
                                                await conn.commit()
                                                # add to notification list also
                                                sql = """ INSERT IGNORE INTO discord_notify_new_tx (`coin_name`, `txid`, 
                                                `payment_id`, `height`, `amount`, `fee`, `decimal`) 
                                                VALUES (%s, %s, %s, %s, %s, %s, %s) """
                                                await cur.execute(sql, (COIN_NAME, tx['transactionHash'], tx['paymentId'], tx['blockIndex'],
                                                                        tx['amount'], tx['fee'], wallet.get_decimal(COIN_NAME)))
                                                await conn.commit()
                                        except pymysql.err.Warning as e:
                                            await logchanbot(traceback.format_exc())
                                        except Exception as e:
                                            await logchanbot(traceback.format_exc())
                                    elif height < int(tx['blockIndex']) + wallet.get_confirm_depth(COIN_NAME) and tx['amount'] >= wallet.get_min_deposit_amount(COIN_NAME) \
                                    and 'paymentId' in tx:
                                        # add notify to redis and alert deposit. Can be clean later?
                                        if config.notify_new_tx.enable_new_no_confirm == 1:
                                            key_tx_new = config.redis_setting.prefix_new_tx + 'NOCONFIRM'
                                            key_tx_json = config.redis_setting.prefix_new_tx + tx['transactionHash']
                                            try:
                                                openRedis()
                                                if redis_conn and redis_conn.llen(key_tx_new) > 0:
                                                    list_new_tx = redis_conn.lrange(key_tx_new, 0, -1)
                                                    if list_new_tx and len(list_new_tx) > 0 and tx['transactionHash'].encode() not in list_new_tx:
                                                        redis_conn.lpush(key_tx_new, tx['transactionHash'])
                                                        redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['transactionHash'], 'payment_id': tx['paymentId'], 'height': tx['blockIndex'],
                                                                                                'amount': tx['amount'], 'fee': tx['fee'], 'decimal': wallet.get_decimal(COIN_NAME)}), ex=86400)
                                                elif redis_conn and redis_conn.llen(key_tx_new) == 0:
                                                    redis_conn.lpush(key_tx_new, tx['transactionHash'])
                                                    redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['transactionHash'], 'payment_id': tx['paymentId'], 'height': tx['blockIndex'],
                                                                                            'amount': tx['amount'], 'fee': tx['fee'], 'decimal': wallet.get_decimal(COIN_NAME)}), ex=86400)
                                            except Exception as e:
                                                await logchanbot(traceback.format_exc())
                if list_balance_user and len(list_balance_user) > 0:
                    await openConnection()
                    async with pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            sql = """ SELECT coin_name, payment_id, SUM(amount) AS txIn FROM cnoff_get_transfers 
                                      WHERE coin_name = %s AND amount > 0 
                                      GROUP BY payment_id """
                            await cur.execute(sql, (COIN_NAME,))
                            result = await cur.fetchall()
                            timestamp = int(time.time())
                            list_update = []
                            if result and len(result) > 0:
                                for eachTxIn in result:
                                    list_update.append((eachTxIn['txIn'], timestamp, eachTxIn['payment_id']))
                                await cur.executemany(""" UPDATE cnoff_user_paymentid SET `actual_balance` = %s, `lastUpdate` = %s 
                                                          WHERE paymentid = %s """, list_update)
                                await conn.commit()
            except Exception as e:
                await logchanbot(traceback.format_exc())
    elif coin_family == "XMR":
        #print('SQL: Updating get_transfers '+COIN_NAME)
        get_transfers = await wallet.get_transfers_xmr(COIN_NAME, height - 2000, height)
        if get_transfers and len(get_transfers) >= 1 and 'in' in get_transfers:
            try:
                await openConnection()
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM xmroff_get_transfers WHERE `coin_name` = %s """
                        await cur.execute(sql, (COIN_NAME,))
                        result = await cur.fetchall()
                        d = [i['txid'] for i in result]
                        # print('=================='+COIN_NAME+'===========')
                        # print(d)
                        # print('=================='+COIN_NAME+'===========')
                        list_balance_user = {}
                        for tx in get_transfers['in']:
                            # add to balance only confirmation depth meet
                            if height >= int(tx['height']) + wallet.get_confirm_depth(COIN_NAME) and tx['amount'] >= wallet.get_min_deposit_amount(COIN_NAME) \
                            and 'payment_id' in tx:
                                if ('payment_id' in tx) and (tx['payment_id'] in list_balance_user):
                                    list_balance_user[tx['payment_id']] += tx['amount']
                                elif ('payment_id' in tx) and (tx['payment_id'] not in list_balance_user):
                                    list_balance_user[tx['payment_id']] = tx['amount']
                                try:
                                    if tx['txid'] not in d:
                                        tx_address = tx['address'] if COIN_NAME != "LTHN" else getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
                                        sql = """ INSERT IGNORE INTO xmroff_get_transfers (`coin_name`, `in_out`, `txid`, 
                                        `payment_id`, `height`, `timestamp`, `amount`, `fee`, `decimal`, `address`, time_insert) 
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                        await cur.execute(sql, (COIN_NAME, tx['type'].upper(), tx['txid'], tx['payment_id'], tx['height'], tx['timestamp'],
                                                                tx['amount'], tx['fee'], wallet.get_decimal(COIN_NAME), tx_address, int(time.time())))
                                        await conn.commit()
                                        # add to notification list also
                                        sql = """ INSERT IGNORE INTO discord_notify_new_tx (`coin_name`, `txid`, 
                                        `payment_id`, `height`, `amount`, `fee`, `decimal`) 
                                        VALUES (%s, %s, %s, %s, %s, %s, %s) """
                                        await cur.execute(sql, (COIN_NAME, tx['txid'], tx['payment_id'], tx['height'],
                                                                tx['amount'], tx['fee'], wallet.get_decimal(COIN_NAME)))
                                        await conn.commit()
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            elif height < int(tx['height']) + wallet.get_confirm_depth(COIN_NAME) and tx['amount'] >= wallet.get_min_deposit_amount(COIN_NAME) \
                            and 'payment_id' in tx:
                                # add notify to redis and alert deposit. Can be clean later?
                                if config.notify_new_tx.enable_new_no_confirm == 1:
                                    key_tx_new = config.redis_setting.prefix_new_tx + 'NOCONFIRM'
                                    key_tx_json = config.redis_setting.prefix_new_tx + tx['txid']
                                    try:
                                        openRedis()
                                        if redis_conn and redis_conn.llen(key_tx_new) > 0:
                                            list_new_tx = redis_conn.lrange(key_tx_new, 0, -1)
                                            if list_new_tx and len(list_new_tx) > 0 and tx['txid'].encode() not in list_new_tx:
                                                redis_conn.lpush(key_tx_new, tx['txid'])
                                                redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['txid'], 'payment_id': tx['payment_id'], 'height': tx['height'],
                                                                                    'amount': tx['amount'], 'fee': tx['fee'], 'decimal': wallet.get_decimal(COIN_NAME)}), ex=86400)
                                        elif redis_conn and redis_conn.llen(key_tx_new) == 0:
                                            redis_conn.lpush(key_tx_new, tx['txid'])
                                            redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['txid'], 'payment_id': tx['payment_id'], 'height': tx['height'],
                                                                                    'amount': tx['amount'], 'fee': tx['fee'], 'decimal': wallet.get_decimal(COIN_NAME)}), ex=86400)
                                    except Exception as e:
                                        await logchanbot(traceback.format_exc())
                        if len(list_balance_user) > 0:
                            list_update = []
                            timestamp = int(time.time())
                            for key, value in list_balance_user.items():
                                list_update.append((value, timestamp, key))
                            await cur.executemany(""" UPDATE xmroff_user_paymentid SET `actual_balance` = %s, `lastUpdate` = %s 
                                                      WHERE paymentid = %s """, list_update)
                            await conn.commit()
            except Exception as e:
                await logchanbot(traceback.format_exc())
    elif coin_family == "DOGE":
        #print('SQL: Updating get_transfers '+COIN_NAME)
        get_transfers = await wallet.doge_listtransactions(COIN_NAME)
        if get_transfers and len(get_transfers) >= 1:
            try:
                await openConnection()
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM doge_get_transfers WHERE `coin_name` = %s AND `category` IN (%s, %s) """
                        await cur.execute(sql, (COIN_NAME, 'receive', 'send'))
                        result = await cur.fetchall()
                        d = [i['txid'] for i in result]
                        # print('=================='+COIN_NAME+'===========')
                        # print(d)
                        # print('=================='+COIN_NAME+'===========')
                        list_balance_user = {}
                        for tx in get_transfers:
                            # add to balance only confirmation depth meet
                            if COIN_NAME in POS_COIN and 'generated' in tx and tx['generated']:
                                # Skip PoS tx
                                continue
                            if wallet.get_confirm_depth(COIN_NAME) <= int(tx['confirmations']) and tx['amount'] >= wallet.get_min_deposit_amount(COIN_NAME):
                                if ('address' in tx) and (tx['address'] in list_balance_user) and (tx['amount'] > 0):
                                    list_balance_user[tx['address']] += tx['amount']
                                elif ('address' in tx) and (tx['address'] not in list_balance_user) and (tx['amount'] > 0):
                                    list_balance_user[tx['address']] = tx['amount']
                                try:
                                    if tx['txid'] not in d:
                                        if tx['category'] == "receive":
                                            sql = """ INSERT IGNORE INTO doge_get_transfers (`coin_name`, `txid`, `blockhash`, 
                                            `address`, `blocktime`, `amount`, `confirmations`, `category`, `time_insert`) 
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                            await cur.execute(sql, (COIN_NAME, tx['txid'], tx['blockhash'], tx['address'],
                                                                    tx['blocktime'], tx['amount'], tx['confirmations'], tx['category'], int(time.time())))
                                            await conn.commit()
                                        # add to notification list also, doge payment_id = address
                                        if (tx['amount'] > 0) and tx['category'] == 'receive':
                                            sql = """ INSERT IGNORE INTO discord_notify_new_tx (`coin_name`, `txid`, 
                                            `payment_id`, `blockhash`, `amount`, `decimal`) 
                                            VALUES (%s, %s, %s, %s, %s, %s) """
                                            await cur.execute(sql, (COIN_NAME, tx['txid'], tx['address'], tx['blockhash'],
                                                                    tx['amount'], wallet.get_decimal(COIN_NAME)))
                                            await conn.commit()
                                except pymysql.err.Warning as e:
                                    await logchanbot(traceback.format_exc())
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            if wallet.get_confirm_depth(COIN_NAME) > int(tx['confirmations']) > 0 and tx['amount'] >= wallet.get_min_deposit_amount(COIN_NAME):
                                # add notify to redis and alert deposit. Can be clean later?
                                if config.notify_new_tx.enable_new_no_confirm == 1:
                                    key_tx_new = config.redis_setting.prefix_new_tx + 'NOCONFIRM'
                                    key_tx_json = config.redis_setting.prefix_new_tx + tx['txid']
                                    try:
                                        openRedis()
                                        if redis_conn and redis_conn.llen(key_tx_new) > 0:
                                            list_new_tx = redis_conn.lrange(key_tx_new, 0, -1)
                                            if list_new_tx and len(list_new_tx) > 0 and tx['txid'].encode() not in list_new_tx:
                                                redis_conn.lpush(key_tx_new, tx['txid'])
                                                redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['txid'], 'payment_id': tx['address'], 'blockhash': tx['blockhash'],
                                                                                        'amount': tx['amount'], 'decimal': wallet.get_decimal(COIN_NAME)}), ex=86400)
                                        elif redis_conn and redis_conn.llen(key_tx_new) == 0:
                                            redis_conn.lpush(key_tx_new, tx['txid'])
                                            redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['txid'], 'payment_id': tx['address'], 'blockhash': tx['blockhash'],
                                                                                    'amount': tx['amount'], 'decimal': wallet.get_decimal(COIN_NAME)}), ex=86400)
                                    except Exception as e:
                                        await logchanbot(traceback.format_exc())
                                        await logchanbot(json.dumps(tx))
                        if len(list_balance_user) > 0:
                            list_update = []
                            timestamp = int(time.time())
                            for key, value in list_balance_user.items():
                                list_update.append((value, timestamp, key))
                            await cur.executemany(""" UPDATE doge_user SET `actual_balance` = %s, `lastUpdate` = %s 
                                                      WHERE balance_wallet_address = %s """, list_update)
                            await conn.commit()
            except Exception as e:
                await logchanbot(traceback.format_exc())
    elif coin_family == "XCH":
        #print('SQL: Updating get_transfers '+COIN_NAME)
        get_transfers = await wallet.xch_listtransactions(COIN_NAME)
        if get_transfers and len(get_transfers) >= 1:
            try:
                await openConnection()
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM xch_get_transfers WHERE `coin_name` = %s  """
                        await cur.execute(sql, (COIN_NAME))
                        result = await cur.fetchall()
                        d = [i['txid'] for i in result]
                        # print('=================='+COIN_NAME+'===========')
                        # print(d)
                        # print('=================='+COIN_NAME+'===========')
                        list_balance_user = {}
                        for tx in get_transfers:
                            # add to balance only confirmation depth meet
                            if height >= wallet.get_confirm_depth(COIN_NAME) + int(tx['confirmed_at_height']) and tx['amount'] >= wallet.get_min_deposit_amount(COIN_NAME):
                                if ('to_address' in tx) and (tx['to_address'] in list_balance_user) and (tx['amount'] > 0):
                                    list_balance_user[tx['to_address']] += tx['amount']
                                elif ('to_address' in tx) and (tx['to_address'] not in list_balance_user) and (tx['amount'] > 0):
                                    list_balance_user[tx['to_address']] = tx['amount']
                                try:
                                    if tx['name'] not in d:
                                        # receive
                                        if len(tx['sent_to']) == 0:
                                            sql = """ INSERT IGNORE INTO xch_get_transfers (`coin_name`, `txid`, `height`, `timestamp`, 
                                                      `address`, `amount`, `fee`, `decimal`, `time_insert`) 
                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                            await cur.execute(sql, (COIN_NAME, tx['name'], tx['confirmed_at_height'], tx['created_at_time'],
                                                                    tx['to_address'], tx['amount'], tx['fee_amount'], wallet.get_decimal(COIN_NAME), int(time.time())))
                                            await conn.commit()
                                        # add to notification list also, doge payment_id = address
                                        if (tx['amount'] > 0) and len(tx['sent_to']) == 0:
                                            sql = """ INSERT IGNORE INTO discord_notify_new_tx (`coin_name`, `txid`, 
                                                      `payment_id`, `blockhash`, `height`, `amount`, `fee`, `decimal`) 
                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                                            await cur.execute(sql, (COIN_NAME, tx['name'], tx['to_address'], tx['name'], int(tx['confirmed_at_height']), 
                                                                    tx['amount'], tx['fee_amount'], wallet.get_decimal(COIN_NAME)))
                                            await conn.commit()
                                except pymysql.err.Warning as e:
                                    await logchanbot(traceback.format_exc())
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            if height <wallet.get_confirm_depth(COIN_NAME) + int(tx['confirmed_at_height']) and tx['amount'] >= wallet.get_min_deposit_amount(COIN_NAME):
                                # add notify to redis and alert deposit. Can be clean later?
                                if config.notify_new_tx.enable_new_no_confirm == 1:
                                    key_tx_new = config.redis_setting.prefix_new_tx + 'NOCONFIRM'
                                    key_tx_json = config.redis_setting.prefix_new_tx + tx['name']
                                    try:
                                        openRedis()
                                        if redis_conn and redis_conn.llen(key_tx_new) > 0:
                                            list_new_tx = redis_conn.lrange(key_tx_new, 0, -1)
                                            if list_new_tx and len(list_new_tx) > 0 and tx['name'].encode() not in list_new_tx:
                                                redis_conn.lpush(key_tx_new, tx['name'])
                                                redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['name'], 'payment_id': tx['to_address'], 'height': tx['confirmed_at_height'],
                                                                                        'amount': tx['amount'], 'decimal': wallet.get_decimal(COIN_NAME)}), ex=86400)
                                        elif redis_conn and redis_conn.llen(key_tx_new) == 0:
                                            redis_conn.lpush(key_tx_new, tx['name'])
                                            redis_conn.set(key_tx_json, json.dumps({'coin_name': COIN_NAME, 'txid': tx['name'], 'payment_id': tx['to_address'], 'height': tx['confirmed_at_height'],
                                                                                    'amount': tx['amount'], 'decimal': wallet.get_decimal(COIN_NAME)}), ex=86400)
                                    except Exception as e:
                                        await logchanbot(traceback.format_exc())
                                        await logchanbot(json.dumps(tx))
                        if len(list_balance_user) > 0:
                            list_update = []
                            timestamp = int(time.time())
                            for key, value in list_balance_user.items():
                                list_update.append((value, timestamp, key))
                            await cur.executemany(""" UPDATE xch_user SET `actual_balance` = %s, `lastUpdate` = %s 
                                                      WHERE balance_wallet_address = %s """, list_update)
                            await conn.commit()
            except Exception as e:
                await logchanbot(traceback.format_exc())



async def sql_credit(user_from: str, to_user: str, amount: float, coin: str, reason: str):
    global pool
    COIN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO credit_balance (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `credit_date`, `reason`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (COIN_NAME, user_from, to_user, amount, wallet.get_decimal(COIN_NAME), int(time.time()), reason,))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_register_user(userID, coin: str, user_server: str = 'DISCORD', chat_id: int = 0, w=None):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    if user_server == "TELEGRAM" and chat_id == 0:
        return
    COIN_NAME = coin.upper()
    coin_family = "TRTL"
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    elif COIN_NAME in ENABLE_COIN_TRC:
        coin_family = "TRC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if coin_family in ["TRTL", "BCN"]:
                    sql = """ SELECT user_id, int_address, user_wallet_address, user_server FROM cnoff_user_paymentid 
                              WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (userID, COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "XMR":
                    sql = """ SELECT * FROM xmroff_user_paymentid 
                              WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "XCH":
                    sql = """ SELECT * FROM xch_user 
                              WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "DOGE":
                    sql = """ SELECT * FROM doge_user WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "NANO":
                    sql = """ SELECT * FROM nano_user WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "ERC-20":
                    sql = """ SELECT * FROM erc_user WHERE `user_id`=%s AND `token_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "TRC-20":
                    sql = """ SELECT * FROM trx_user WHERE `user_id`=%s AND `token_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                    result = await cur.fetchone()
                if result is None:
                    balance_address = None
                    main_address = None
                    if coin_family in ["TRTL", "BCN"]:
                        main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
                        balance_address = {}
                        balance_address['payment_id'] = addressvalidation.paymentid()
                        balance_address['integrated_address'] = addressvalidation.make_integrated_cn(main_address, COIN_NAME, balance_address['payment_id'])['integrated_address']
                    elif coin_family == "XMR":
                        main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
                        balance_address = await wallet.make_integrated_address_xmr(main_address, COIN_NAME)
                    elif coin_family == "DOGE":
                        balance_address = await wallet.doge_register(str(userID), COIN_NAME, user_server)
                    elif coin_family == "XCH":
                        balance_address = await wallet.xch_register(COIN_NAME, user_server)
                    elif coin_family == "NANO":
                        # No need ID
                        balance_address = await wallet.nano_register(COIN_NAME, user_server)
                    elif coin_family == "ERC-20":
                        balance_address = w['address']
                    elif coin_family == "TRC-20":
                        balance_address = w['base58check_address']
                    if balance_address is None:
                        print('Internal error during call register wallet-api')
                        return
                    else:
                        if coin_family in ["TRTL", "BCN"]:
                            sql = """ INSERT INTO cnoff_user_paymentid (`coin_name`, `user_id`, `main_address`, `paymentid`, 
                                  `int_address`, `paymentid_ts`, `user_server`, `chat_id`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, str(userID), main_address, balance_address['payment_id'], 
                                                    balance_address['integrated_address'], int(time.time()), user_server, chat_id))
                            await conn.commit()
                        elif coin_family == "XMR":
                            sql = """ INSERT INTO xmroff_user_paymentid (`coin_name`, `user_id`, `main_address`, `paymentid`, 
                                      `int_address`, `paymentid_ts`, `user_server`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, str(userID), main_address, balance_address['payment_id'], 
                                                    balance_address['integrated_address'], int(time.time()), user_server))
                            await conn.commit()
                        elif coin_family == "XCH":
                            sql = """ INSERT INTO xch_user (`coin_name`, `user_id`, `balance_wallet_address`, `address_ts`, `user_server`, `chat_id`) 
                                      VALUES (%s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, str(userID), balance_address['address'], int(time.time()), user_server, chat_id))
                            await conn.commit()
                        elif coin_family == "DOGE":
                            sql = """ INSERT INTO doge_user (`coin_name`, `user_id`, `balance_wallet_address`, `address_ts`, 
                                      `privateKey`, `user_server`, `chat_id`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, str(userID), balance_address['address'], int(time.time()), 
                                                    encrypt_string(balance_address['privateKey']), user_server, chat_id))
                            await conn.commit()
                        elif coin_family == "NANO":
                            sql = """ INSERT INTO nano_user (`coin_name`, `user_id`, `balance_wallet_address`, `address_ts`, 
                                      `user_server`, `chat_id`) 
                                      VALUES (%s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, str(userID), balance_address['address'], int(time.time()), 
                                                    user_server, chat_id))
                            await conn.commit()
                        elif coin_family == "ERC-20":
                            token_info = await get_token_info(COIN_NAME)
                            sql = """ INSERT INTO erc_user (`token_name`, `contract`, `user_id`, `balance_wallet_address`, `address_ts`, 
                                      `token_decimal`, `seed`, `private_key`, `user_server`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, token_info['contract'].lower(), str(userID), w['address'].lower(), int(time.time()), 
                                              token_info['token_decimal'], encrypt_string(w['seed']), encrypt_string(w['private_key']), user_server))
                            await conn.commit()
                        elif coin_family == "TRC-20":
                            token_info = await get_token_info(COIN_NAME)
                            sql = """ INSERT INTO trx_user (`token_name`, `contract`, `user_id`, `balance_wallet_address`, `hex_address`, `address_ts`, 
                                      `token_decimal`, `private_key`, `public_key`, `user_server`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, token_info['contract'], str(userID), w['base58check_address'], w['hex_address'], int(time.time()), 
                                              token_info['token_decimal'], encrypt_string(w['private_key']), encrypt_string(w['public_key']), user_server))
                            await conn.commit()
                    return balance_address
                else:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def sql_update_user_chat_id(userID, coin: str, chat_id: int, user_server: str = 'TELEGRAM'):
    if user_server not in ['TELEGRAM']:
        return
    COIN_NAME = coin.upper()
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    elif COIN_NAME in ENABLE_COIN_TRC:
        coin_family = "TRC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if coin_family in ["TRTL", "BCN"]:
                    sql = """ UPDATE cnoff_user_paymentid SET chat_id=%s WHERE user_id=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """               
                    await cur.execute(sql, (chat_id, str(userID), COIN_NAME, user_server))
                    await conn.commit()
                elif coin_family == "XMR":
                    sql = """ UPDATE xmroff_user_paymentid SET chat_id=%s WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """               
                    await cur.execute(sql, (chat_id, str(userID), COIN_NAME, user_server))
                    await conn.commit()
                elif coin_family == "DOGE":
                    sql = """ UPDATE doge_user SET chat_id=%s WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """               
                    await cur.execute(sql, (chat_id, str(userID), COIN_NAME, user_server))
                    await conn.commit()
                elif coin_family == "NANO":
                    sql = """ UPDATE nano_user SET chat_id=%s WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """               
                    await cur.execute(sql, (chat_id, str(userID), COIN_NAME, user_server))
                    await conn.commit()
                elif coin_family == "ERC-20":
                    sql = """ UPDATE erc_user SET chat_id=%s WHERE `user_id`=%s AND `token_name` = %s AND `user_server`=%s LIMIT 1 """               
                    await cur.execute(sql, (chat_id, str(userID), COIN_NAME, user_server))
                    await conn.commit()
                elif coin_family == "TRC-20":
                    sql = """ UPDATE trx_user SET chat_id=%s WHERE `user_id`=%s AND `token_name` = %s AND `user_server`=%s LIMIT 1 """               
                    await cur.execute(sql, (chat_id, str(userID), COIN_NAME, user_server))
                    await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False



async def sql_update_user(userID, user_wallet_address, coin: str, user_server: str = 'DISCORD'):
    global redis_conn, pool
    COIN_NAME = coin.upper()
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return

    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    elif COIN_NAME in ENABLE_COIN_TRC:
        coin_family = "TRC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if coin_family in ["TRTL", "BCN"]:
                    sql = """ UPDATE cnoff_user_paymentid SET user_wallet_address=%s WHERE user_id=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """               
                    await cur.execute(sql, (user_wallet_address, str(userID), COIN_NAME, user_server))
                    await conn.commit()
                elif coin_family == "XMR":
                    sql = """ UPDATE xmroff_user_paymentid SET user_wallet_address=%s WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """               
                    await cur.execute(sql, (user_wallet_address, str(userID), COIN_NAME, user_server))
                    await conn.commit()
                elif coin_family == "XCH":
                    sql = """ UPDATE xch_user SET user_wallet_address=%s WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """               
                    await cur.execute(sql, (user_wallet_address, str(userID), COIN_NAME, user_server))
                    await conn.commit()
                elif coin_family == "DOGE":
                    sql = """ UPDATE doge_user SET user_wallet_address=%s WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """               
                    await cur.execute(sql, (user_wallet_address, str(userID), COIN_NAME, user_server))
                    await conn.commit()
                elif coin_family == "NANO":
                    sql = """ UPDATE nano_user SET user_wallet_address=%s WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """               
                    await cur.execute(sql, (user_wallet_address, str(userID), COIN_NAME, user_server))
                    await conn.commit()
                elif coin_family == "ERC-20":
                    sql = """ UPDATE erc_user SET user_wallet_address=%s WHERE `user_id`=%s AND `token_name` = %s AND `user_server`=%s LIMIT 1 """               
                    await cur.execute(sql, (user_wallet_address, str(userID), COIN_NAME, user_server))
                    await conn.commit()
                elif coin_family == "TRC-20":
                    sql = """ UPDATE trx_user SET user_wallet_address=%s WHERE `user_id`=%s AND `token_name` = %s AND `user_server`=%s LIMIT 1 """               
                    await cur.execute(sql, (user_wallet_address, str(userID), COIN_NAME, user_server))
                    await conn.commit()
                return user_wallet_address  # return userwallet
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def redis_delete_userwallet(userID: str, coin: str, user_server: str = 'DISCORD'):
    global redis_conn, redis_pool
    COIN_NAME = coin.upper()
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    key = config.redis_setting.prefix_get_userwallet + user_server + "_" + userID + ":" + COIN_NAME
    try:
        if redis_conn is None: redis_conn = redis.Redis(connection_pool=redis_pool)
        if redis_conn and redis_conn.exists(key): redis_conn.delete(key)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return True


async def coin_check_balance_address_in_users(address: str, coin: str):
    global pool
    COIN_NAME = coin.upper()
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
        return await erc_check_balance_address_in_users(address, COIN_NAME)
    elif COIN_NAME in ENABLE_COIN_TRC:
        coin_family = "TRC-20"
        return await trx_check_balance_address_in_users(address, COIN_NAME)
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family in ["TRTL", "BCN"]:
        tb_name = "cnoff_user_paymentid"
        field_name = "int_address"
    elif coin_family == "XMR":
        tb_name = "xmroff_user_paymentid"
        field_name = "int_address"
    elif coin_family == "XCH":
        tb_name = "xch_user"
        field_name = "balance_wallet_address"
    elif coin_family == "DOGE":
        tb_name = "doge_user"
        field_name = "balance_wallet_address"
    elif coin_family == "NANO":
        tb_name = "nano_user"
        field_name = "balance_wallet_address"
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ SELECT `"""+field_name+"""` FROM """+tb_name+""" 
                          WHERE `coin_name`=%s AND LOWER(`"""+field_name+"""`)=LOWER(%s) LIMIT 1 """
                await cur.execute(sql, (COIN_NAME, address))
                result = await cur.fetchone()
                if result: return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def sql_get_userwallet(userID: str, coin: str, user_server: str = 'DISCORD'):
    global pool, redis_conn, redis_pool, redis_expired
    COIN_NAME = coin.upper()
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    elif COIN_NAME in ENABLE_COIN_TRC:
        coin_family = "TRC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    key = config.redis_setting.prefix_get_userwallet + user_server + "_" + userID + ":" + COIN_NAME
    try:
        if redis_conn is None: redis_conn = redis.Redis(connection_pool=redis_pool)
        if redis_conn and redis_conn.exists(key):
            pass
            #return json.loads(redis_conn.get(key))
    except Exception as e:
        await logchanbot(traceback.format_exc())

    wallet_res = None
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if coin_family in ["TRTL", "BCN"]:
                    sql = """ SELECT * FROM cnoff_user_paymentid WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "XMR":
                    sql = """ SELECT * FROM xmroff_user_paymentid WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "XCH":
                    sql = """ SELECT * FROM xch_user WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "DOGE":
                    sql = """ SELECT user_id, balance_wallet_address, user_wallet_address, address_ts, lastUpdate, chat_id 
                              FROM doge_user WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "NANO":
                    sql = """ SELECT * FROM nano_user WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "ERC-20":
                    sql = """ SELECT * FROM erc_user WHERE `user_id`=%s AND `token_name`=%s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "TRC-20":
                    sql = """ SELECT * FROM trx_user WHERE `user_id`=%s AND `token_name`=%s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                    result = await cur.fetchone()
                if result:
                    userwallet = result
                    if coin_family == "XMR":
                        userwallet['balance_wallet_address'] = userwallet['int_address']
                    elif coin_family in ["TRTL", "BCN"]:
                        userwallet['balance_wallet_address'] = userwallet['int_address']
                        userwallet['lastUpdate'] = int(result['lastUpdate'])
                    elif coin_family == "DOGE":
                        async with conn.cursor() as cur:
                            sql = """ SELECT * FROM doge_user WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                            await cur.execute(sql, (str(userID), COIN_NAME, user_server))
                            result = await cur.fetchone()
                            if result: userwallet['lastUpdate'] = result['lastUpdate']
                    elif coin_family == "NANO" or coin_family == "ERC-20" or coin_family == "TRC-20":
                        wallet_res = userwallet
                    if result['lastUpdate'] == 0 and (coin_family in ["TRTL", "BCN"] or coin_family == "XMR"):
                        userwallet['lastUpdate'] = result['paymentid_ts']
                    else:
                        userwallet['lastUpdate'] = 0
                    wallet_res = userwallet
                    # store in redis
                    try:
                        openRedis()
                        if redis_conn:
                            redis_conn.set(key, json.dumps(wallet_res), ex=config.redis_setting.get_userwallet_time)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return wallet_res


async def sql_get_countLastTip(userID, lastDuration: int):
    global pool
    lapDuration = int(time.time()) - lastDuration
    count = 0
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT SUM(
                          (SELECT COUNT(*) FROM cn_tip WHERE `from_user` = %s AND `date`>%s )
                          +
                          (SELECT COUNT(*) FROM cn_tipall WHERE `from_user` = %s AND `date`>%s )
                          +
                          (SELECT COUNT(*) FROM cn_send WHERE `from_user` = %s AND `date`>%s )
                          +
                          (SELECT COUNT(*) FROM cn_withdraw WHERE `user_id` = %s AND `date`>%s )
                          +
                          (SELECT COUNT(*) FROM cn_donate WHERE `from_user` = %s AND `date`>%s )
                          ) as OLD_CN"""
                await cur.execute(sql, (str(userID), lapDuration, str(userID), lapDuration, str(userID), lapDuration,
                                        str(userID), lapDuration, str(userID), lapDuration,))
                result = await cur.fetchone()
                count += int(result['OLD_CN']) if result and result['OLD_CN'] else 0

                # Can be tipall or tip many, let's count all
                sql = """ SELECT COUNT(*) as CNOFF FROM cnoff_mv_tx WHERE `from_userid` = %s AND `date`>%s """
                await cur.execute(sql, (str(userID), lapDuration,))
                result = await cur.fetchone()
                count += int(result['CNOFF']) if result and result['CNOFF'] else 0

                # doge table
                sql = """ SELECT COUNT(*) as DOGE FROM doge_mv_tx WHERE `from_userid` = %s AND `date`>%s """
                await cur.execute(sql, (str(userID), lapDuration,))
                result = await cur.fetchone()
                count += int(result['DOGE']) if result and result['DOGE'] else 0

                # erc table
                sql = """ SELECT COUNT(*) as ERC FROM erc_mv_tx WHERE `from_userid` = %s AND `date`>%s """
                await cur.execute(sql, (str(userID), lapDuration,))
                result = await cur.fetchone()
                count += int(result['ERC']) if result and result['ERC'] else 0

                # xmr table
                sql = """ SELECT COUNT(*) as XMR FROM xmroff_mv_tx WHERE `from_userid` = %s AND `date`>%s """
                await cur.execute(sql, (str(userID), lapDuration,))
                result = await cur.fetchone()
                count += int(result['XMR']) if result and result['XMR'] else 0

                # nano table
                sql = """ SELECT COUNT(*) as NANO FROM nano_mv_tx WHERE `from_userid` = %s AND `date`>%s """
                await cur.execute(sql, (str(userID), lapDuration,))
                result = await cur.fetchone()
                count += int(result['NANO']) if result and result['NANO'] else 0
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return count


async def sql_mv_cn_single(user_from: str, user_to: str, amount: int, tiptype: str, coin: str, user_server: str = 'DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    user_from_wallet = None
    user_to_wallet = None
    if coin_family in ["TRTL", "BCN", "XMR"]:
        user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME, user_server)
        user_to_wallet = await sql_get_userwallet(user_to, COIN_NAME, user_server)
    if user_from_wallet['balance_wallet_address']:
        if coin_family in ["TRTL", "BCN"]:
            # Move balance
            try:
                await openConnection()
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO cnoff_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (COIN_NAME, user_from, user_to, amount, wallet.get_decimal(COIN_NAME), tiptype.upper(), int(time.time()), user_server,))
                        await conn.commit()
                        return {'transactionHash': 'NONE', 'fee': 0}
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
    return False


async def sql_mv_cn_multiple(user_from: str, amount_div: int, user_ids, tiptype: str, coin: str, user_server: str = 'DISCORD'):
    global pool
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    if tiptype.upper() not in ["TIPS", "TIPALL", "FREETIP", "FREETIPS", "GUILDTIP"]:
        return None

    user_from_wallet = None
    if coin_family in ["TRTL", "BCN", "XMR"]:
        user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME, user_server)
    if user_from_wallet['balance_wallet_address']:
        if coin_family in ["TRTL", "BCN"]:
            # Move offchain
            values_str = []
            currentTs = int(time.time())
            for item in user_ids:
                values_str.append(f"('{COIN_NAME}', '{user_from}', '{item}', {amount_div}, {wallet.get_decimal(COIN_NAME)}, '{tiptype.upper()}', {currentTs})\n")
            values_sql = "VALUES " + ",".join(values_str)
            try:
                await openConnection()
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO cnoff_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`) 
                                  """+values_sql+""" """
                        await cur.execute(sql,)
                        await conn.commit()
                        return {'transactionHash': 'NONE', 'fee': 0}
            except Exception as e:
                await logchanbot(traceback.format_exc())
                print(f"SQL:\n{sql}\n")
    return False


async def sql_external_cn_single(user_from: str, address_to: str, amount: int, coin: str, user_server: str = 'DISCORD', tiptype: str = 'WITHDRAW'):
    global pool
    COIN_NAME = coin.upper()
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    user_from_wallet = None

    tx_hash = None
    if coin_family in ["TRTL", "BCN"]:
        # send from wallet and store in cnoff_external_tx
        main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
        if COIN_NAME in WALLET_API_COIN:
            tx_hash = await walletapi.walletapi_send_transaction(main_address, address_to, 
                                                                 amount, COIN_NAME)

        else:
            tx_hash = await wallet.send_transaction(main_address, address_to, 
                                                    amount, COIN_NAME)
    elif coin_family == "XMR":
        tx_hash = await wallet.send_transaction('TIPBOT', address_to, 
                                                amount, COIN_NAME, 0)
    if tx_hash:
        updateTime = int(time.time())
        try:
            await openConnection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    fee = wallet.get_tx_node_fee(COIN_NAME)
                    if coin_family in ["TRTL", "BCN"]:
                        sql = """ INSERT INTO cnoff_external_tx (`coin_name`, `user_id`, `to_address`, `amount`, `decimal`, `date`, 
                                  `tx_hash`, `fee`, `user_server`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (COIN_NAME, user_from, address_to, amount, wallet.get_decimal(COIN_NAME), updateTime, 
                                                tx_hash['transactionHash'], fee, user_server))
                        await conn.commit()
                    if coin_family == "XMR":
                        async with conn.cursor() as cur: 
                            sql = """ INSERT INTO xmroff_external_tx (`coin_name`, `user_id`, `amount`, `fee`, `decimal`, `to_address`, 
                                      `type`, `date`, `tx_hash`, `tx_key`, `user_server`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, user_from, amount, fee, wallet.get_decimal(COIN_NAME), 
                                                    address_to, tiptype.upper(), int(time.time()), tx_hash['tx_hash'], tx_hash['tx_key'], user_server))
                            await conn.commit()
                            tx_hash['transactionHash'] = tx_hash['tx_hash']
                            return tx_hash
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return tx_hash
    return False


async def sql_external_cn_single_id(user_from: str, address_to: str, amount: int, paymentid, coin: str, user_server: str = 'DISCORD'):
    global pool
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    tx_hash = None
    if coin_family in ["TRTL", "BCN"]:
        # send from wallet and store in cnoff_external_tx
        main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
        if COIN_NAME in WALLET_API_COIN:
            tx_hash = await walletapi.walletapi_send_transaction_id(main_address, address_to,
                                                                    amount, paymentid, COIN_NAME)
        else:
            tx_hash = await wallet.send_transaction_id(main_address, address_to,
                                                       amount, paymentid, COIN_NAME)
    if tx_hash:
        updateTime = int(time.time())
        try:
            await openConnection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    timestamp = int(time.time())
                    if coin_family in ["TRTL", "BCN"]:
                        fee = wallet.get_tx_node_fee(COIN_NAME)
                        sql = """ INSERT INTO cnoff_external_tx (`coin_name`, `user_id`, `to_address`, `amount`, `decimal`, `date`, 
                                  `tx_hash`, `paymentid`, `fee`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (COIN_NAME, user_from, address_to, amount, wallet.get_decimal(COIN_NAME), 
                                                timestamp, tx_hash['transactionHash'], paymentid, fee, user_server))
                        await conn.commit()
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return tx_hash
    return False


async def sql_donate(user_from: str, address_to: str, amount: int, coin: str, user_server: str = 'DISCORD') -> str:
    global pool
    user_server = user_server.upper()
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME, user_server)
    if all(v is not None for v in [user_from_wallet['balance_wallet_address'], address_to]):
        if coin_family in ["TRTL", "BCN"]:
            # Move balance
            try:
                await openConnection()
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO cnoff_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (COIN_NAME, user_from, wallet.get_donate_address(COIN_NAME), amount, 
                                                wallet.get_decimal(COIN_NAME), 'DONATE', int(time.time()), user_server))
                        await conn.commit()
                        return {'transactionHash': 'NONE', 'fee': 0}
            except Exception as e:
                await logchanbot(traceback.format_exc())
    else:
        return None


async def sql_get_donate_list():
    global pool
    donate_list = {}
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # TRTL fam
                for coin in ENABLE_COIN:
                    sql = """ SELECT SUM(amount) AS donate FROM cn_donate WHERE `coin_name`= %s """
                    await cur.execute(sql, (coin.upper()))
                    result = await cur.fetchone()
                    if result['donate'] is None:
                        donate_list.update({coin: 0})
                    else:
                        donate_list.update({coin: float(result['donate'])})
                # TRTL fam but in cnoff_mv_tx table
                for coin in ENABLE_COIN:
                    sql = """ SELECT SUM(amount) AS donate FROM cnoff_mv_tx WHERE `coin_name`= %s AND `type`=%s """
                    await cur.execute(sql, (coin.upper(), 'DONATE'))
                    result = await cur.fetchone()
                    if result and result['donate'] and result['donate'] > 0:
                        donate_list[coin] += float(result['donate'])
                # DOGE fam
                for coin in ENABLE_COIN_DOGE:
                    sql = """ SELECT SUM(amount) AS donate FROM doge_mv_tx WHERE `type`='DONATE' AND `to_userid`= %s AND `coin_name`= %s """
                    await cur.execute(sql, ((wallet.get_donate_address(coin), coin.upper())))
                    result = await cur.fetchone()
                    if result['donate'] is None:
                        donate_list.update({coin: 0})
                    else:
                       donate_list.update({coin: float(result['donate'])})
                for coin in ENABLE_XMR:
                    sql = """ SELECT SUM(amount) AS donate FROM xmroff_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
                    await cur.execute(sql, (wallet.get_donate_address(coin.upper())))
                    result = await cur.fetchone()
                    if result['donate'] is None:
                        donate_list.update({coin: 0})
                    else:
                        donate_list.update({coin: float(result['donate'])})
                for coin in ENABLE_COIN_ERC:
                    sql = """ SELECT SUM(real_amount) AS donate FROM erc_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
                    await cur.execute(sql, (coin.upper()))
                    result = await cur.fetchone()
                    if result['donate'] is None:
                        donate_list.update({coin: 0})
                    else:
                        donate_list.update({coin: float(result['donate'])})
                for coin in ENABLE_COIN_TRC:
                    sql = """ SELECT SUM(real_amount) AS donate FROM trx_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
                    await cur.execute(sql, (coin.upper()))
                    result = await cur.fetchone()
                    if result['donate'] is None:
                        donate_list.update({coin: 0})
                    else:
                        donate_list.update({coin: float(result['donate'])})
            return donate_list
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_send_to_voucher(user_id: str, user_name: str, message_creating: str, amount: float, reserved_fee: float, comment: str, secret_string: str, voucher_image_name: str, coin: str, user_server: str='DISCORD'):
    global pool
    COIN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO cn_voucher (`coin_name`, `user_id`, `user_name`, `message_creating`, `amount`, 
                          `decimal`, `reserved_fee`, `date_create`, `comment`, `secret_string`, `voucher_image_name`, `user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (COIN_NAME, user_id, user_name, message_creating, amount, wallet.get_decimal(COIN_NAME), reserved_fee, 
                                        int(time.time()), comment, secret_string, voucher_image_name, user_server))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_voucher_get_user(user_id: str, user_server: str='DISCORD', last: int=10, already_claimed: str='YESNO'):
    global pool
    user_server = user_server.upper()
    already_claimed = already_claimed.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if already_claimed == 'YESNO':
                    sql = """ SELECT * FROM cn_voucher WHERE `user_id`=%s AND `user_server`=%s 
                              ORDER BY `date_create` DESC LIMIT """ + str(last)+ """ """
                    await cur.execute(sql, (user_id, user_server,))
                    result = await cur.fetchall()
                    return result
                elif already_claimed == 'YES' or already_claimed == 'NO':
                    sql = """ SELECT * FROM cn_voucher WHERE `user_id`=%s AND `user_server`=%s AND `already_claimed`=%s
                              ORDER BY `date_create` DESC LIMIT """ + str(last)+ """ """
                    await cur.execute(sql, (user_id, user_server, already_claimed))
                    result = await cur.fetchall()
                    return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_voucher_get_setting(coin: str):
    global pool
    COIN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM cn_voucher_settings WHERE `coin_name`=%s LIMIT 1 """
                await cur.execute(sql, (COIN_NAME,))
                result = await cur.fetchone()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_faucet_add(claimed_user: str, claimed_server: str, coin_name: str, claimed_amount: float, decimal: int, user_server: str = 'DISCORD'):
    global pool, redis_conn
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_faucet (`claimed_user`, `coin_name`, `claimed_amount`, 
                          `decimal`, `claimed_at`, `claimed_server`, `user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (claimed_user, coin_name, claimed_amount, decimal, 
                                        int(time.time()), claimed_server, user_server))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_faucet_penalty_checkuser(userID: str, penalty_add: False, user_server: str = 'DISCORD'):
    global pool, redis_conn, redis_pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    # Check if in redis already:
    key = config.redis_setting.prefix_faucet_take_penalty + user_server + "_" + userID
    result = None
    if penalty_add == False:
        try:
            if redis_conn is None: redis_conn = redis.Redis(connection_pool=redis_pool)
            if redis_conn and redis_conn.exists(key):
                penalty_at = redis_conn.get(key).decode()
                result = {'penalty_at': penalty_at}
        except Exception as e:
            await logchanbot(traceback.format_exc())
    else:
        # add
        try:
            if redis_conn is None: redis_conn = redis.Redis(connection_pool=redis_pool)
            if redis_conn: redis_conn.set(key, str(int(time.time())), int(int(config.faucet.interval)*3600/2)) # 12h
        except Exception as e:
            await logchanbot(traceback.format_exc())
    return result


async def sql_faucet_checkuser(userID: str, user_server: str = 'DISCORD'):
    global pool, redis_conn, redis_pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return

    result = None
    list_roach = None
    if user_server == 'DISCORD':
        list_roach = await sql_roach_get_by_id(userID, user_server)
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if list_roach:
                    roach_sql = "(" + ",".join(list_roach) + ")"
                    sql = """ SELECT * FROM discord_faucet WHERE claimed_user IN """+roach_sql+""" AND `user_server`=%s 
                              ORDER BY claimed_at DESC LIMIT 1"""
                    await cur.execute(sql, (user_server,))
                else:
                    sql = """ SELECT * FROM discord_faucet WHERE `claimed_user` = %s AND `user_server`=%s 
                              ORDER BY claimed_at DESC LIMIT 1"""
                    await cur.execute(sql, (userID, (user_server,)))
                result = await cur.fetchone()
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return result


async def sql_faucet_count_user(userID: str, user_server: str = 'DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT COUNT(*) FROM discord_faucet WHERE claimed_user = %s AND `user_server`=%s """
                await cur.execute(sql, (userID, user_server))
                result = await cur.fetchone()
                return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_faucet_count_all():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT COUNT(*) FROM discord_faucet """
                await cur.execute(sql,)
                result = await cur.fetchone()
                return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_faucet_sum_count_claimed(coin: str):
    COIN_NAME = coin.upper()
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT SUM(claimed_amount) as claimed, COUNT(claimed_amount) as count FROM discord_faucet
                          WHERE `coin_name`=%s """
                await cur.execute(sql, (COIN_NAME))
                result = await cur.fetchone()
                # {'claimed_amount': xxx, 'count': xxx}
                # print(result)
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_game_count_user(userID: str, lastDuration: int, user_server: str = 'DISCORD', free: bool=False):
    global pool
    lapDuration = int(time.time()) - lastDuration
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if free == False:
                    sql = """ SELECT COUNT(*) FROM discord_game WHERE `played_user` = %s AND `user_server`=%s 
                              AND `played_at`>%s """
                else:
                    sql = """ SELECT COUNT(*) FROM discord_game_free WHERE `played_user` = %s AND `user_server`=%s 
                              AND `played_at`>%s """
                await cur.execute(sql, (userID, user_server, lapDuration))
                result = await cur.fetchone()
                return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_game_add(game_result: str, played_user: str, coin_name: str, win_lose: str, won_amount: float, decimal: int, \
played_server: str, game_type: str, duration: int=0, user_server: str = 'DISCORD'):
    global pool
    game_result = game_result.replace("\t", "")
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_game (`played_user`, `coin_name`, `win_lose`, 
                          `won_amount`, `decimal`, `played_server`, `played_at`, `game_type`, `user_server`, `game_result`, `duration`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (played_user, coin_name, win_lose, won_amount, decimal, played_server, 
                                        int(time.time()), game_type, user_server, game_result, duration))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_game_free_add(game_result: str, played_user: str, win_lose: str, played_server: str, game_type: str, duration: int=0, user_server: str = 'DISCORD'):
    global pool
    game_result = game_result.replace("\t", "")
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_game_free (`played_user`, `win_lose`, `played_server`, `played_at`, `game_type`, `user_server`, `game_result`, `duration`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (played_user, win_lose, played_server, int(time.time()), game_type, user_server, game_result, duration))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_game_stat():
    global pool
    stat = {}
    GAME_COIN = config.game.coin_game.split(",")
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_game """
                await cur.execute(sql,)
                result_game = await cur.fetchall()
                if result_game and len(result_game) > 0:
                    stat['paid_play'] = len(result_game)
                    # https://stackoverflow.com/questions/21518271/how-to-sum-values-of-the-same-key-in-a-dictionary
                    stat['paid_hangman_play'] = sum(d.get('HANGMAN', 0) for d in result_game)
                    stat['paid_bagel_play'] = sum(d.get('BAGEL', 0) for d in result_game)
                    stat['paid_slot_play'] = sum(d.get('SLOT', 0) for d in result_game)
                    for each in GAME_COIN:
                        stat[each] = sum(d.get('won_amount', 0) for d in result_game if d['coin_name'] == each)
                sql = """ SELECT * FROM discord_game_free """
                await cur.execute(sql,)
                result_game_free = await cur.fetchall()
                if result_game_free and len(result_game_free) > 0:
                    stat['free_play'] = len(result_game_free)
                    stat['free_hangman_play'] = sum(d.get('HANGMAN', 0) for d in result_game_free)
                    stat['free_bagel_play'] = sum(d.get('BAGEL', 0) for d in result_game_free)
                    stat['free_slot_play'] = sum(d.get('SLOT', 0) for d in result_game_free)
            return stat
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_count_tx_all():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT COUNT(*) FROM cnoff_external_tx """
                await cur.execute(sql,)
                result = await cur.fetchone()
                cnoff_external_tx = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

                sql = """ SELECT COUNT(*) FROM cnoff_mv_tx """
                await cur.execute(sql,)
                result = await cur.fetchone()
                cnoff_mv_tx = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

                sql = """ SELECT COUNT(*) FROM cn_tip """
                await cur.execute(sql,)
                result = await cur.fetchone()
                cn_tip = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

                sql = """ SELECT COUNT(*) FROM cn_send """
                await cur.execute(sql,)
                result = await cur.fetchone()
                cn_send = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

                sql = """ SELECT COUNT(*) FROM cn_withdraw """
                await cur.execute(sql,)
                result = await cur.fetchone()
                cn_withdraw = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

                sql = """ SELECT COUNT(*) FROM doge_external_tx """
                await cur.execute(sql,)
                result = await cur.fetchone()
                doge_external_tx = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

                sql = """ SELECT COUNT(*) FROM doge_mv_tx """
                await cur.execute(sql,)
                result = await cur.fetchone()
                doge_mv_tx = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

                sql = """ SELECT COUNT(*) FROM xmroff_external_tx """
                await cur.execute(sql,)
                result = await cur.fetchone()
                xmroff_external_tx = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

                sql = """ SELECT COUNT(*) FROM xmroff_mv_tx """
                await cur.execute(sql,)
                result = await cur.fetchone()
                xmroff_mv_tx = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
                
                on_chain = cnoff_external_tx + cn_tip + cn_send + cn_withdraw + doge_external_tx + xmroff_external_tx
                off_chain = cnoff_mv_tx + doge_mv_tx + xmroff_mv_tx
                return {'on_chain': on_chain, 'off_chain': off_chain, 'total': on_chain+off_chain}
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_tag_by_server(server_id: str, tag_id: str = None):
    global pool, redis_pool, redis_conn, redis_expired
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if tag_id is None: 
                    sql = """ SELECT * FROM discord_tag WHERE tag_serverid = %s """
                    await cur.execute(sql, (server_id,))
                    result = await cur.fetchall()
                    tag_list = result
                    return tag_list
                else:
                    # Check if exist in redis
                    try:
                        openRedis()
                        if redis_conn and redis_conn.exists(f'TIPBOT:TAG_{str(server_id)}_{tag_id}'):
                            sql = """ UPDATE discord_tag SET num_trigger=num_trigger+1 WHERE tag_serverid = %s AND tag_id=%s """
                            await cur.execute(sql, (server_id, tag_id,))
                            await conn.commit()
                            return json.loads(redis_conn.get(f'TIPBOT:TAG_{str(server_id)}_{tag_id}'))
                        else:
                            sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, 
                                      `added_byuid`, `num_trigger` FROM discord_tag WHERE tag_serverid = %s AND tag_id=%s """
                            await cur.execute(sql, (server_id, tag_id,))
                            result = await cur.fetchone()
                            if result:
                                redis_conn.set(f'TIPBOT:TAG_{str(server_id)}_{tag_id}', json.dumps(result), ex=redis_expired)
                                return json.loads(redis_conn.get(f'TIPBOT:TAG_{str(server_id)}_{tag_id}'))
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_tag_by_server_add(server_id: str, tag_id: str, tag_desc: str, added_byname: str, added_byuid: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT COUNT(*) FROM discord_tag WHERE tag_serverid=%s """
                await cur.execute(sql, (server_id,))
                counting = await cur.fetchone()
                if counting:
                    if counting['COUNT(*)'] > 50:
                        return None
                sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, `added_byuid`, 
                          `num_trigger` 
                          FROM discord_tag WHERE tag_serverid = %s AND tag_id=%s """
                await cur.execute(sql, (server_id, tag_id.upper(),))
                result = await cur.fetchone()
                if result is None:
                    sql = """ INSERT INTO discord_tag (`tag_id`, `tag_desc`, `date_added`, `tag_serverid`, 
                              `added_byname`, `added_byuid`) 
                              VALUES (%s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (tag_id.upper(), tag_desc, int(time.time()), server_id, added_byname, added_byuid,))
                    await conn.commit()
                    return tag_id.upper()
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_tag_by_server_del(server_id: str, tag_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, 
                          `added_byuid`, `num_trigger` 
                          FROM discord_tag WHERE tag_serverid = %s AND tag_id=%s """
                await cur.execute(sql, (server_id, tag_id.upper(),))
                result = await cur.fetchone()
                if result:
                    sql = """ DELETE FROM discord_tag WHERE `tag_id`=%s AND `tag_serverid`=%s """
                    await cur.execute(sql, (tag_id.upper(), server_id,))
                    await conn.commit()
                    # Check if exist in redis
                    try:
                        openRedis()
                        if redis_conn and redis_conn.exists(f'TIPBOT:TAG_{str(server_id)}_{tag_id}'):
                            redis_conn.delete(f'TIPBOT:TAG_{str(server_id)}_{tag_id}')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                    return tag_id.upper()
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_itag_by_server(server_id: str, tag_id: str = None):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if tag_id is None: 
                    sql = """ SELECT * FROM discord_itag WHERE itag_serverid = %s """
                    await cur.execute(sql, (server_id,))
                    result = await cur.fetchall()
                    tag_list = result
                    return tag_list
                else:
                    sql = """ SELECT * FROM discord_itag WHERE itag_serverid = %s AND itag_id=%s """
                    await cur.execute(sql, (server_id, tag_id,))
                    result = await cur.fetchone()
                    if result:
                        tag = result
                        sql = """ UPDATE discord_itag SET num_trigger=num_trigger+1 WHERE itag_serverid = %s AND itag_id=%s """
                        await cur.execute(sql, (server_id, tag_id,))
                        await conn.commit()
                        return tag
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_itag_by_server_add(server_id: str, tag_id: str, added_byname: str, added_byuid: str, orig_name: str, stored_name: str, fsize: int):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT COUNT(*) FROM discord_itag WHERE itag_serverid=%s """
                await cur.execute(sql, (server_id,))
                counting = await cur.fetchone()
                if counting:
                    if counting['COUNT(*)'] > config.itag.max_per_server:
                        return None
                sql = """ SELECT * FROM discord_itag WHERE itag_serverid = %s AND itag_id=%s """
                await cur.execute(sql, (server_id, tag_id.upper(),))
                result = await cur.fetchone()
                if result is None:
                    sql = """ INSERT INTO discord_itag (`itag_id`, `date_added`, `itag_serverid`, 
                              `added_byname`, `added_byuid`, `original_name`, `stored_name`, `size`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (tag_id.upper(), int(time.time()), server_id, added_byname, added_byuid, orig_name, stored_name, fsize))
                    await conn.commit()
                    return tag_id.upper()
                else:
                    return None
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_itag_by_server_del(server_id: str, tag_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_itag WHERE itag_serverid = %s AND itag_id=%s """
                await cur.execute(sql, (server_id, tag_id.upper(),))
                result = await cur.fetchone()
                if result:
                    if os.path.exists(config.itag.path + result['stored_name']):
                        os.remove(config.itag.path + result['stored_name'])
                    sql = """ DELETE FROM discord_itag WHERE `itag_id`=%s AND `itag_serverid`=%s """
                    await cur.execute(sql, (tag_id.upper(), server_id,))
                    await conn.commit()
                    return tag_id.upper()
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_get_allguild():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_server """
                await cur.execute(sql,)
                result = await cur.fetchall()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_info_by_server(server_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_server WHERE serverid = %s LIMIT 1 """
                await cur.execute(sql, (server_id,))
                result = await cur.fetchone()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_addinfo_by_server(server_id: str, servername: str, prefix: str, default_coin: str, rejoin: bool = True):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if rejoin:
                    sql = """ INSERT INTO `discord_server` (`serverid`, `servername`, `prefix`, `default_coin`)
                              VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE 
                              `servername` = %s, `prefix` = %s, `default_coin` = %s, `status` = %s """
                    await cur.execute(sql, (server_id, servername[:28], prefix, default_coin, servername[:28], prefix, default_coin, "REJOINED", ))
                    await conn.commit()
                else:
                    sql = """ INSERT INTO `discord_server` (`serverid`, `servername`, `prefix`, `default_coin`)
                              VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE 
                              `servername` = %s, `prefix` = %s, `default_coin` = %s"""
                    await cur.execute(sql, (server_id, servername[:28], prefix, default_coin, servername[:28], prefix, default_coin,))
                    await conn.commit()
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_add_messages(list_messages):
    if len(list_messages) == 0:
        return 0
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT IGNORE INTO `discord_messages` (`serverid`, `server_name`, `channel_id`, `channel_name`, `user_id`, 
                          `message_author`, `message_id`, `message_content`, `message_time`)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.executemany(sql, list_messages)
                await conn.commit()
                return cur.rowcount
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_get_messages(server_id: str, channel_id: str, time_int: int, num_user: int=None):
    global pool
    lapDuration = int(time.time()) - time_int
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                list_talker = []
                if num_user is None:
                    sql = """ SELECT DISTINCT `user_id` FROM discord_messages 
                              WHERE `serverid` = %s AND `channel_id` = %s AND `message_time`>%s """
                    await cur.execute(sql, (server_id, channel_id, lapDuration,))
                    result = await cur.fetchall()
                    if result:
                        for item in result:
                            if int(item['user_id']) not in list_talker:
                                list_talker.append(int(item['user_id']))
                else:
                    sql = """ SELECT `user_id` FROM discord_messages WHERE `serverid` = %s AND `channel_id` = %s 
                              GROUP BY `user_id` ORDER BY max(`message_time`) DESC LIMIT %s """
                    await cur.execute(sql, (server_id, channel_id, num_user,))
                    result = await cur.fetchall()
                    if result:
                        for item in result:
                            if int(item['user_id']) not in list_talker:
                                list_talker.append(int(item['user_id']))
                return list_talker
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_changeinfo_by_server(server_id: str, what: str, value: str):
    global pool
    if what.lower() in ["servername", "prefix", "default_coin", "tiponly", "numb_user", "numb_bot", "numb_channel", \
    "react_tip", "react_tip_100", "lastUpdate", "botchan", "enable_faucet", "enable_game", "enable_market", "enable_trade", "tip_message", \
    "tip_message_by", "tip_notifying_acceptance", "game_2048_channel", "game_bagel_channel", "game_blackjack_channel", "game_dice_channel", \
    "game_maze_channel", "game_slot_channel", "game_snail_channel", "game_sokoban_channel", "game_hangman_channel", "enable_nsfw"]:
        try:
            #print(f"ok try to change {what} to {value}")
            await openConnection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE discord_server SET `""" + what.lower() + """` = %s WHERE `serverid` = %s """
                    await cur.execute(sql, (value, server_id,))
                    await conn.commit()
        except Exception as e:
            await logchanbot(traceback.format_exc())


async def sql_updatestat_by_server(server_id: str, numb_user: int, numb_bot: int, numb_channel: int, numb_online: int, servername: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE discord_server SET `numb_user` = %s, 
                          `numb_bot`= %s, `numb_channel` = %s, `numb_online` = %s, 
                         `lastUpdate` = %s, `servername` = %s WHERE `serverid` = %s """
                await cur.execute(sql, (numb_user, numb_bot, numb_channel, numb_online, int(time.time()), server_id, conn.escape(servername)))
                await conn.commit()
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_discord_userinfo_get(user_id: str, user_server: str='DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # select first
                sql = """ SELECT * FROM discord_userinfo 
                          WHERE `user_id` = %s AND `user_server`=%s """
                await cur.execute(sql, (user_id, user_server))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_userinfo_locked(user_id: str, locked: str, locked_reason: str, locked_by: str):
    global pool
    if locked.upper() not in ["YES", "NO"]:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # select first
                sql = """ SELECT `user_id` FROM discord_userinfo 
                          WHERE `user_id` = %s """
                await cur.execute(sql, (user_id,))
                result = await cur.fetchone()
                if result is None:
                    sql = """ INSERT INTO `discord_userinfo` (`user_id`, `locked`, `locked_reason`, `locked_by`, `locked_date`)
                          VALUES (%s, %s, %s, %s, %s) """
                    await cur.execute(sql, (user_id, locked.upper(), locked_reason, locked_by, int(time.time())))
                    await conn.commit()
                else:
                    sql = """ UPDATE `discord_userinfo` SET `locked`= %s, `locked_reason` = %s, `locked_by` = %s, `locked_date` = %s
                          WHERE `user_id` = %s """
                    await cur.execute(sql, (locked.upper(), locked_reason, locked_by, int(time.time()), user_id))
                    await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_roach_add(main_id: str, roach_id: str, roach_name: str, main_name: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # select first
                sql = """ SELECT `roach_id`, `main_id`, `date` FROM discord_faucetroach 
                          WHERE `roach_id` = %s AND `main_id` = %s """
                await cur.execute(sql, (roach_id, main_id,))
                result = await cur.fetchone()
                if result is None:
                    sql = """ INSERT INTO `discord_faucetroach` (`roach_id`, `main_id`, `roach_name`, `main_name`, `date`)
                          VALUES (%s, %s, %s, %s, %s) """
                    await cur.execute(sql, (roach_id, main_id, roach_name, main_name, int(time.time())))
                    await conn.commit()
                    return True
                else:
                    return None
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_roach_get_by_id(roach_id: str, user_server: str = 'DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # select first
                sql = """ SELECT `roach_id`, `main_id`, `date` FROM discord_faucetroach 
                          WHERE (`roach_id` = %s OR `main_id` = %s) AND `user_server`=%s """
                await cur.execute(sql, (roach_id, roach_id, user_server))
                result = await cur.fetchall()
                if result is None:
                    return None
                else:
                    roaches = []
                    for each in result:
                        roaches.append(each['roach_id'])
                        roaches.append(each['main_id'])
                    return set(roaches)
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_userinfo_2fa_insert(user_id: str, twofa_secret: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # select first
                sql = """ SELECT `user_id` FROM discord_userinfo 
                          WHERE `user_id` = %s """
                await cur.execute(sql, (user_id,))
                result = await cur.fetchone()
                if result is None:
                    sql = """ INSERT INTO `discord_userinfo` (`user_id`, `twofa_secret`, `twofa_activate_ts`)
                          VALUES (%s, %s, %s) """
                    await cur.execute(sql, (user_id, encrypt_string(twofa_secret), int(time.time())))
                    await conn.commit()
                    return True
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_userinfo_2fa_update(user_id: str, twofa_secret: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # select first
                sql = """ SELECT `user_id` FROM discord_userinfo 
                          WHERE `user_id` = %s """
                await cur.execute(sql, (user_id,))
                result = await cur.fetchone()
                if result:
                    sql = """ UPDATE `discord_userinfo` SET `twofa_secret` = %s, `twofa_activate_ts` = %s 
                          WHERE `user_id`=%s """
                    await cur.execute(sql, (encrypt_string(twofa_secret), int(time.time()), user_id))
                    await conn.commit()
                    return True
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_userinfo_2fa_verify(user_id: str, verify: str):
    if verify.upper() not in ["YES", "NO"]:
        return
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # select first
                sql = """ SELECT `user_id` FROM discord_userinfo 
                          WHERE `user_id` = %s """
                await cur.execute(sql, (user_id,))
                result = await cur.fetchone()
                if result:
                    sql = """ UPDATE `discord_userinfo` SET `twofa_verified` = %s, `twofa_verified_ts` = %s 
                          WHERE `user_id`=%s """
                    if verify.upper() == "NO":
                        # if unverify, need to clear secret code as well, and disactivate other related 2FA.
                        sql = """ UPDATE `discord_userinfo` SET `twofa_verified` = %s, `twofa_verified_ts` = %s, `twofa_secret` = %s, `twofa_activate_ts` = %s, 
                              `twofa_onoff` = %s, `twofa_active` = %s
                              WHERE `user_id`=%s """
                        await cur.execute(sql, (verify.upper(), int(time.time()), '', int(time.time()), 'OFF', 'NO', user_id))
                        await conn.commit()
                    else:
                        await cur.execute(sql, (verify.upper(), int(time.time()), user_id))
                        await conn.commit()
                    return True
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_change_userinfo_single(user_id: str, what: str, value: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # select first
                sql = """ SELECT `user_id` FROM discord_userinfo 
                          WHERE `user_id` = %s """
                await cur.execute(sql, (user_id,))
                result = await cur.fetchone()
                if result:
                    sql = """ UPDATE discord_userinfo SET `""" + what.lower() + """` = %s WHERE `user_id` = %s """
                    await cur.execute(sql, (value, user_id))
                    await conn.commit()
                else:
                    sql = """ INSERT INTO `discord_userinfo` (`user_id`, `""" + what.lower() + """`)
                          VALUES (%s, %s) """
                    await cur.execute(sql, (user_id, value))
                    await conn.commit()
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_addignorechan_by_server(server_id: str, ignorechan: str, by_userid: str, by_name: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT IGNORE INTO `discord_ignorechan` (`serverid`, `ignorechan`, `set_by_userid`, `by_author`, `set_when`)
                          VALUES (%s, %s, %s, %s, %s) """
                await cur.execute(sql, (server_id, ignorechan, by_userid, by_name, int(time.time())))
                await conn.commit()
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_delignorechan_by_server(server_id: str, ignorechan: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ DELETE FROM `discord_ignorechan` WHERE `serverid` = %s AND `ignorechan` = %s """
                await cur.execute(sql, (server_id, ignorechan,))
                await conn.commit()
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_listignorechan():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_ignorechan` """
                await cur.execute(sql)
                result = await cur.fetchall()
                ignore_chan = {}
                if result:
                    for row in result:
                        if str(row['serverid']) in ignore_chan:
                            ignore_chan[str(row['serverid'])].append(str(row['ignorechan']))
                        else:
                            ignore_chan[str(row['serverid'])] = []
                            ignore_chan[str(row['serverid'])].append(str(row['ignorechan']))
                    return ignore_chan
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_add_mutechan_by_server(server_id: str, mutechan: str, by_userid: str, by_name: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT IGNORE INTO `discord_mutechan` (`serverid`, `mutechan`, `set_by_userid`, `by_author`, `set_when`)
                          VALUES (%s, %s, %s, %s, %s) """
                await cur.execute(sql, (server_id, mutechan, by_userid, by_name, int(time.time())))
                await conn.commit()
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_del_mutechan_by_server(server_id: str, mutechan: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ DELETE FROM `discord_mutechan` WHERE `serverid` = %s AND `mutechan` = %s """
                await cur.execute(sql, (server_id, mutechan,))
                await conn.commit()
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_list_mutechan():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_mutechan` """
                await cur.execute(sql)
                result = await cur.fetchall()
                mute_chan = {}
                if result:
                    for row in result:
                        if str(row['serverid']) in mute_chan:
                            mute_chan[str(row['serverid'])].append(str(row['mutechan']))
                        else:
                            mute_chan[str(row['serverid'])] = []
                            mute_chan[str(row['serverid'])].append(str(row['mutechan']))
                    return mute_chan
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_add_logs_tx(list_tx):
    global pool
    if len(list_tx) == 0:
        return 0
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT IGNORE INTO `action_tx_logs` (`uuid`, `action`, `user_id`, `user_name`, 
                          `event_date`, `msg_content`, `user_server`, `end_point`)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.executemany(sql, list_tx)
                await conn.commit()
                return cur.rowcount
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_add_failed_tx(coin: str, user_id: str, user_author: str, amount: int, tx_type: str):
    global pool
    if tx_type.upper() not in ['TIP','TIPS','TIPALL','DONATE','WITHDRAW','SEND', 'REACTTIP', 'FREETIP', 'GUILDTIP']:
        return None
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT IGNORE INTO `discord_txfail` (`coin_name`, `user_id`, `tx_author`, `amount`, `tx_type`, `fail_time`)
                          VALUES (%s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (coin.upper(), user_id, user_author, amount, tx_type.upper(), int(time.time())))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_get_tipnotify():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT `user_id`, `date` FROM bot_tipnotify_user """
                await cur.execute(sql,)
                result = await cur.fetchall()
                ignorelist = []
                for row in result:
                    ignorelist.append(row['user_id'])
                return ignorelist
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_toggle_tipnotify(user_id: str, onoff: str):
    # Bot will add user_id if it failed to DM
    global pool
    onoff = onoff.upper()
    if onoff == "OFF":
        try:
            await openConnection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `bot_tipnotify_user` WHERE `user_id` = %s LIMIT 1 """
                    await cur.execute(sql, (user_id))
                    result = await cur.fetchone()
                    if result is None:
                        sql = """ INSERT INTO `bot_tipnotify_user` (`user_id`, `date`)
                                  VALUES (%s, %s) """    
                        await cur.execute(sql, (user_id, int(time.time())))
                        await conn.commit()
        except pymysql.err.Warning as e:
            await logchanbot(traceback.format_exc())
        except Exception as e:
            await logchanbot(traceback.format_exc())
    elif onoff == "ON":
        try:
            await openConnection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ DELETE FROM `bot_tipnotify_user` WHERE `user_id` = %s """
                    await cur.execute(sql, str(user_id))
                    await conn.commit()
        except Exception as e:
            await logchanbot(traceback.format_exc())


async def sql_updateinfo_by_server(server_id: str, what: str, value: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT serverid, servername, prefix, default_coin, numb_user, numb_bot, tiponly 
                          FROM discord_server WHERE serverid = %s """
                await cur.execute(sql, (server_id,))
                result = await cur.fetchone()
                if result is None:
                    return None
                else:
                    if what in ["servername", "prefix", "default_coin", "tiponly", "status"]:
                        sql = """ UPDATE discord_server SET `"""+what+"""`=%s WHERE serverid=%s """
                        await cur.execute(sql, (value, server_id,))
                        await conn.commit()
                    else:
                        return None
    except Exception as e:
        await logchanbot(str(traceback.format_exc()) + "\n\n" + f"({sql}, ({what}, {value}, {server_id},)")


# DOGE
async def sql_mv_doge_single(user_from: str, to_user: str, amount: float, coin: str, tiptype: str, user_server: str = 'DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN_DOGE:
        return False
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO doge_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `type`, `date`, `user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (COIN_NAME, user_from, to_user, amount, tiptype.upper(), int(time.time()), user_server))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_mv_doge_multiple(user_from: str, user_tos, amount_each: float, coin: str, tiptype: str):
    # user_tos is array "account1", "account2", ....
    global pool
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN_DOGE:
        return False
    if tiptype.upper() not in ["TIPS", "TIPALL", "FREETIP", "FREETIPS", "GUILDTIP"]:
        return False
    values_str = []
    currentTs = int(time.time())
    for item in user_tos:
        values_str.append(f"('{COIN_NAME}', '{user_from}', '{item}', {amount_each}, '{tiptype.upper()}', {currentTs})\n")
    values_sql = "VALUES " + ",".join(values_str)
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO doge_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `type`, `date`) 
                          """+values_sql+""" """
                await cur.execute(sql,)
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_external_doge_single(user_from: str, amount: float, fee: float, to_address: str, coin: str, tiptype: str, user_server: str = 'DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN_DOGE:
        return False
    if tiptype.upper() not in ["SEND", "WITHDRAW"]:
        return False
    try:
        await openConnection()
        txHash = await wallet.doge_sendtoaddress(to_address, amount, user_from, COIN_NAME)
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO doge_external_tx (`coin_name`, `user_id`, `amount`, `fee`, `to_address`, 
                          `type`, `date`, `tx_hash`, `user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (COIN_NAME, user_from, amount, fee, to_address, tiptype.upper(), int(time.time()), txHash, user_server))
                await conn.commit()
                return txHash
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


# XMR Based
async def sql_mv_xmr_single(user_from: str, to_user: str, amount: float, coin: str, tiptype: str, user_server: str = 'DISCORD'):
    global pool
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family != "XMR":
        return False
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO xmroff_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`, `user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (COIN_NAME, user_from, to_user, amount, wallet.get_decimal(COIN_NAME), tiptype.upper(), int(time.time()), user_server))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_mv_xmr_multiple(user_from: str, user_tos, amount_each: float, coin: str, tiptype: str):
    # user_tos is array "account1", "account2", ....
    global pool
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family != "XMR":
        return False
    if tiptype.upper() not in ["TIPS", "TIPALL", "FREETIP", "FREETIPS", "GUILDTIP"]:
        return False
    values_str = []
    currentTs = int(time.time())
    for item in user_tos:
        values_str.append(f"('{COIN_NAME}', '{user_from}', '{item}', {amount_each}, {wallet.get_decimal(COIN_NAME)}, '{tiptype.upper()}', {currentTs})\n")
    values_sql = "VALUES " + ",".join(values_str)
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO xmroff_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`) 
                          """+values_sql+""" """
                await cur.execute(sql,)
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_external_xmr_single(user_from: str, amount: float, to_address: str, coin: str, tiptype: str, fee: float):
    global pool
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family != "XMR":
        return False
    if tiptype.upper() not in ["SEND", "WITHDRAW"]:
        return False
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if coin_family == "XMR":
                    tx_hash = await wallet.send_transaction('TIPBOT', to_address, 
                                                            amount, COIN_NAME, 0)
                    if tx_hash:
                        updateTime = int(time.time())
                        async with conn.cursor() as cur: 
                            sql = """ INSERT INTO xmroff_external_tx (`coin_name`, `user_id`, `amount`, `fee`, `decimal`, `to_address`, 
                                      `type`, `date`, `tx_hash`, `tx_key`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (COIN_NAME, user_from, amount, fee, wallet.get_decimal(COIN_NAME), to_address, tiptype.upper(), int(time.time()), tx_hash['tx_hash'], tx_hash['tx_key'],))
                            await conn.commit()
                            return tx_hash
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_get_userwallet_by_paymentid(paymentid: str, coin: str, user_server: str = 'DISCORD'):
    global pool, redis_conn, redis_pool
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    COIN_NAME = coin.upper()
    user_server = user_server.upper()

    key = config.redis_setting.prefix_paymentid_addr + user_server + "_" + paymentid + ":" + COIN_NAME
    try:
        if redis_conn is None: redis_conn = redis.Redis(connection_pool=redis_pool)
        if redis_conn and redis_conn.exists(key):
            value = json.loads(redis_conn.get(key))
            if value: return json.loads(redis_conn.get(key))
    except Exception as e:
        await logchanbot(traceback.format_exc())

    result = False
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    elif COIN_NAME in ENABLE_COIN_TRC:
        coin_family = "TRC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                result = None
                if coin_family == "TRTL" or coin_family == "BCN":
                    sql = """ SELECT * FROM cnoff_user_paymentid WHERE `paymentid`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (paymentid, COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "XMR":
                    sql = """ SELECT * FROM xmroff_user_paymentid WHERE `paymentid`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (paymentid, COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "XCH":
                    sql = """ SELECT * FROM xch_user WHERE `balance_wallet_address`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (paymentid, COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "DOGE":
                    # if doge family, address is paymentid
                    sql = """ SELECT * FROM doge_user WHERE `balance_wallet_address`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (paymentid, COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "NANO":
                    # if doge family, address is paymentid
                    sql = """ SELECT * FROM nano_user WHERE `balance_wallet_address`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (paymentid, COIN_NAME, user_server))
                    result = await cur.fetchone()
    except Exception as e:
        await logchanbot(traceback.format_exc())
    # store in redis
    try:
        openRedis()
        if redis_conn:
            redis_conn.set(key, json.dumps(result), ex=config.redis_setting.default_time)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return result


# XCH Based
async def sql_mv_xch_single(user_from: str, to_user: str, amount: float, coin: str, tiptype: str, user_server: str = 'DISCORD'):
    global pool
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family != "XCH":
        return False
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO xch_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`, `user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (COIN_NAME, user_from, to_user, amount, wallet.get_decimal(COIN_NAME), tiptype.upper(), int(time.time()), user_server))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_mv_xch_multiple(user_from: str, user_tos, amount_each: float, coin: str, tiptype: str):
    # user_tos is array "account1", "account2", ....
    global pool
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family != "XCH":
        return False
    if tiptype.upper() not in ["TIPS", "TIPALL", "FREETIP", "FREETIPS", "GUILDTIP"]:
        return False
    values_str = []
    currentTs = int(time.time())
    for item in user_tos:
        values_str.append(f"('{COIN_NAME}', '{user_from}', '{item}', {amount_each}, {wallet.get_decimal(COIN_NAME)}, '{tiptype.upper()}', {currentTs})\n")
    values_sql = "VALUES " + ",".join(values_str)
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO xch_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`) 
                          """+values_sql+""" """
                await cur.execute(sql,)
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_external_xch_single(user_from: str, amount: float, to_address: str, coin: str, tiptype: str, user_server: str='DISCORD'):
    global pool
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family != "XCH":
        return False
    if tiptype.upper() not in ["SEND", "WITHDRAW"]:
        return False
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                tx_hash = await wallet.send_transaction('TIPBOT', to_address, 
                                                        amount, COIN_NAME, 0)
                if tx_hash:
                    updateTime = int(time.time())
                    async with conn.cursor() as cur: 
                        sql = """ INSERT INTO xch_external_tx (`coin_name`, `user_id`, `amount`, `fee`, `decimal`, `to_address`, 
                                  `type`, `date`, `tx_hash`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (COIN_NAME, user_from, amount, tx_hash['tx_hash']['fee_amount'], wallet.get_decimal(COIN_NAME), to_address, tiptype.upper(), int(time.time()), tx_hash['tx_hash']['name'], user_server,))
                        await conn.commit()
                        return tx_hash
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_get_new_tx_table(notified: str = 'NO', failed_notify: str = 'NO'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_notify_new_tx WHERE `notified`=%s AND `failed_notify`=%s """
                await cur.execute(sql, (notified, failed_notify,))
                result = await cur.fetchall()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_update_notify_tx_table(payment_id: str, owner_id: str, owner_name: str, notified: str = 'YES', failed_notify: str = 'NO'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE discord_notify_new_tx SET `owner_id`=%s, `owner_name`=%s, `notified`=%s, `failed_notify`=%s, 
                          `notified_time`=%s WHERE `payment_id`=%s """
                await cur.execute(sql, (owner_id, owner_name, notified, failed_notify, float("%.3f" % time.time()), payment_id,))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_update_move_balance_table(id_tx: int, send_receive: str):
    global pool
    send_receive = send_receive.upper()
    if send_receive == "SENDER":
        set_who = "notified_sender"
        set_time = "notified_sender_time"
    elif send_receive == "RECEIVER":
        set_who = "notified_receiver"
        set_time = "notified_receiver_time"
    else:
        return False
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE user_move_balance SET `"""+set_who+"""`=%s, `"""+set_time+"""`=%s WHERE `id`=%s """
                await cur.execute(sql, ('YES', int(time.time()), id_tx,))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_get_move_balance_table(notified_receiver: str = 'NO', notified_sender: str = 'NO'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM user_move_balance WHERE `notified_receiver`=%s AND `notified_sender`=%s """
                await cur.execute(sql, (notified_receiver, notified_sender,))
                result = await cur.fetchall()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_feedback_add(user_id: str, user_name:str, feedback_id: str, text_in: str, feedback_text: str, howto_contact_back: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `discord_feedback` (`user_id`, `user_name`, `feedback_id`, `text_in`, `feedback_text`, `feedback_date`, `howto_contact_back`)
                          VALUES (%s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (user_id, user_name, feedback_id, text_in, feedback_text, int(time.time()), howto_contact_back))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_get_feedback_count_last(userID, lastDuration: int):
    global pool
    lapDuration = int(time.time()) - lastDuration
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_feedback WHERE `user_id` = %s AND `feedback_date`>%s 
                          ORDER BY `feedback_date` DESC LIMIT 100 """
                await cur.execute(sql, (userID, lapDuration,))
                result = await cur.fetchall()
                if result is None:
                    return 0
                return len(result) if result else 0
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def sql_feedback_by_ref(ref: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_feedback WHERE `feedback_id`=%s """
                await cur.execute(sql, (ref,))
                result = await cur.fetchone()
                return result if result else None
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_feedback_list_by_user(userid: str, last: int):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_feedback WHERE `user_id`=%s 
                          ORDER BY `feedback_date` DESC LIMIT """+str(last)
                await cur.execute(sql, (userid,))
                result = await cur.fetchall()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


# Remote only
async def sql_depositlink_user(userid: str, user_server: str = 'DISCORD'):
    global pool
    user_server = user_server.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_depositlink WHERE `user_id`=%s 
                          AND `user_server`=%s """
                await cur.execute(sql, (userid, user_server))
                result = await cur.fetchone()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_depositlink_user_create(user_id: str, user_name:str, link_key: str, user_server: str):
    global pool
    user_server = user_server.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `discord_depositlink` (`user_id`, `user_name`, `date_create`, `link_key`, `user_server`)
                          VALUES (%s, %s, %s, %s, %s) """
                await cur.execute(sql, (user_id, user_name, int(time.time()), link_key, user_server))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_depositlink_user_update(user_id: str, what: str, value: str, user_server: str):
    global pool
    user_server = user_server.upper()
    if what.lower() not in ["link_key", "enable"]:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `discord_depositlink` SET `"""+what+"""`=%s, `updated_date`=%s WHERE `user_id`=%s AND `user_server`=%s LIMIT 1 """
                await cur.execute(sql, (value, int(time.time()), user_id, user_server))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_deposit_getall_address_user(userid: str, user_server: str = 'DISCORD'):
    global pool
    user_server = user_server.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT `coin_name`, `user_id`, `int_address`, `user_server` FROM cnoff_user_paymentid WHERE `user_id`=%s 
                          AND `user_server`=%s """
                await cur.execute(sql, (userid, user_server))
                cnoff_user_paymentid = await cur.fetchall()
                sql = """ SELECT `coin_name`, `user_id`, `int_address`, `user_server` FROM xmroff_user_paymentid WHERE `user_id`=%s 
                          AND `user_server`=%s """
                await cur.execute(sql, (userid, user_server))
                xmroff_user_paymentid = await cur.fetchall()
                sql = """ SELECT `coin_name`, `user_id`, `balance_wallet_address`, `user_server` FROM doge_user WHERE `user_id`=%s 
                          AND `user_server`=%s """
                await cur.execute(sql, (userid, user_server))
                doge_user = await cur.fetchall()
                user_coin_list = {}
                if cnoff_user_paymentid and len(cnoff_user_paymentid) > 0:
                    for each in cnoff_user_paymentid:
                        user_coin_list[each['coin_name']] = each['int_address']
                if xmroff_user_paymentid and len(xmroff_user_paymentid) > 0:
                    for each in xmroff_user_paymentid:
                        user_coin_list[each['coin_name']] = each['int_address']
                if doge_user and len(doge_user) > 0:
                    for each in doge_user:
                        user_coin_list[each['coin_name']] = each['balance_wallet_address']
                return user_coin_list
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_deposit_getall_address_user_remote(userid: str, user_server: str = 'DISCORD'):
    global pool
    user_server = user_server.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_depositlink_address WHERE `user_id`=%s 
                          AND `user_server`=%s """
                await cur.execute(sql, (userid, user_server))
                result = await cur.fetchall()
                user_coin_list = {}
                if result and len(result) > 0:
                    for each in result:
                        user_coin_list[each['coin_name']] = each['deposit_address']
                    return user_coin_list
                else:
                    return None
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_depositlink_user_insert_address(user_id: str, coin_name: str, deposit_address: str, user_server: str):
    global pool
    user_server = user_server.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `discord_depositlink_address` (`user_id`, `coin_name`, `deposit_address`, `user_server`)
                          VALUES (%s, %s, %s, %s) """
                await cur.execute(sql, (user_id, coin_name, deposit_address, user_server))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_depositlink_user_delete_address(user_id: str, coin_name: str, user_server: str):
    global pool
    user_server = user_server.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ DELETE FROM `discord_depositlink_address` WHERE `user_id`=%s AND `user_server`=%s and `coin_name`=%s """
                await cur.execute(sql, (user_id, user_server, coin_name))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_miningpoolstat_fetch(coin_name: str, user_id: str, user_name: str, requested_date: int, \
respond_date: int, response: str, guild_id: str, guild_name: str, channel_id: str, is_cache: str='NO', user_server: str='DISCORD', using_browser: str='NO'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `miningpoolstat_fetch` (`coin_name`, `user_id`, `user_name`, `requested_date`, `respond_date`, 
                          `response`, `guild_id`, `guild_name`, `channel_id`, `user_server`, `is_cache`, `using_browser`)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (coin_name, user_id, user_name, requested_date, respond_date, response, guild_id, 
                                        guild_name, channel_id, user_server, is_cache, using_browser))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_add_tbfun(user_id: str, user_name: str, channel_id: str, guild_id: str, \
guild_name: str, funcmd: str, msg_content: str, user_server: str='DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `discord_tbfun` (`user_id`, `user_name`, `channel_id`, `guild_id`, `guild_name`, 
                          `funcmd`, `msg_content`, `time`, `user_server`)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (user_id, user_name, channel_id, guild_id, guild_name, funcmd, msg_content, 
                                        int(time.time()), user_server))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_add_tts(user_id: str, user_name: str, msg_content: str, lang: str, tts_mp3: str, user_server: str='DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `discord_tts` (`user_id`, `user_name`, `msg_content`, `lang`, `time`, `tts_mp3`, `user_server`)
                          VALUES (%s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (user_id, user_name, msg_content, lang, int(time.time()), tts_mp3, user_server))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_add_trans_tts(user_id: str, user_name: str, original: str, translated: str, from_lang: str, to_lang: str, media_file: str, user_server: str='DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `discord_trans_tts` (`user_id`, `user_name`, `original`, `translated`, `from_lang`, `to_lang`, `time`, `media_file`, `user_server`)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (user_id, user_name, original, translated, from_lang, to_lang, int(time.time()), media_file, user_server))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_game_get_level_tpl(level: int, game_name: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_game_level_tpl WHERE `level`=%s 
                          AND `game_name`=%s LIMIT 1 """
                await cur.execute(sql, (level, game_name.upper()))
                result = await cur.fetchone()
                if result and len(result) > 0:
                    return result
                else:
                    return None
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_game_get_level_user(userid: str, game_name: str):
    global pool
    level = -1
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_game WHERE `played_user`=%s 
                          AND `game_type`=%s AND `win_lose`=%s ORDER BY `played_at` DESC LIMIT 1 """
                await cur.execute(sql, (userid, game_name.upper(), 'WIN'))
                result = await cur.fetchone()
                if result and len(result) > 0:
                    try:
                        level = int(result['game_result'])
                    except Exception as e:
                        await logchanbot(traceback.format_exc())

                sql = """ SELECT * FROM discord_game_free WHERE `played_user`=%s 
                          AND `game_type`=%s AND `win_lose`=%s ORDER BY `played_at` DESC LIMIT 1 """
                await cur.execute(sql, (userid, game_name.upper(), 'WIN'))
                result = await cur.fetchone()
                if result and len(result) > 0:
                    try:
                        if level and int(result['game_result']) > level:
                            level = int(result['game_result'])
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                return level
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return level


# original ValueInUSD
async def market_value_in_usd(amount, ticker) -> str:
    global pool_cmc
    try:
        await openConnection_cmc()
        async with pool_cmc.acquire() as conn:
            async with conn.cursor() as cur:
                # Read a single record from cmc_v2
                sql = """ SELECT * FROM `cmc_v2` WHERE `symbol`=%s ORDER BY `last_updated` DESC LIMIT 1 """
                await cur.execute(sql, (ticker.upper()))
                result = await cur.fetchone()

                sql = """ SELECT * FROM `coingecko_v2` WHERE `symbol`=%s ORDER BY `last_updated` DESC LIMIT 1 """
                await cur.execute(sql, (ticker.lower()))
                result2 = await cur.fetchone()

            if all(v is None for v in [result, result2]):
                # return 'We can not find ticker {} in Coinmarketcap or CoinGecko'.format(ticker.upper())
                return None
            else:
                market_price = {}
                if result:
                    name = result['name']
                    ticker = result['symbol'].upper()
                    price = result['priceUSD']
                    totalValue = amount * price
                    # update = datetime.datetime.strptime(result['last_updated'].split(".")[0], '%Y-%m-%dT%H:%M:%S')
                    market_price['name_cmc'] = name
                    market_price['cmc_price'] = price
                    market_price['cmc_totalvalue'] = totalValue
                    market_price['cmc_update'] = result['last_updated']
                if result2:				
                    name2 = result2['name']
                    ticker2 = result2['symbol'].upper()
                    price2 = result2['marketprice_USD']
                    totalValue2 = amount * price2
                    market_price['name_cg'] = name2
                    market_price['cg_price'] = price2
                    market_price['cg_totalvalue'] = totalValue2
                    market_price['cg_update'] = result2['last_updated']
                return market_price
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


# original ValueCmcUSD
async def market_value_cmc_usd(ticker) -> float:
    global pool_cmc
    try:
        await openConnection_cmc()
        async with pool_cmc.acquire() as conn:
            async with conn.cursor() as cur:
                # Read a single record from cmc_v2
                sql = """ SELECT * FROM `cmc_v2` WHERE `symbol`=%s ORDER BY `last_updated` DESC LIMIT 1 """
                await cur.execute(sql, (ticker.upper()))
                result = await cur.fetchone()
                if result and 'priceUSD' in result and result['priceUSD']: return float(result['priceUSD'])
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


# original ValueGeckoUSD
async def market_value_cg_usd(ticker) -> float:
    global pool_cmc
    try:
        await openConnection_cmc()
        async with pool_cmc.acquire() as conn:
            async with conn.cursor() as cur:
                # Read a single record from cmc_v2
                sql = """ SELECT * FROM `coingecko_v2` WHERE `symbol`=%s ORDER BY `last_updated` DESC LIMIT 1 """
                await cur.execute(sql, (ticker.lower()))
                result = await cur.fetchone()
                if result and 'marketprice_USD' in result and result['marketprice_USD']: return float(result['marketprice_USD'])
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


# plot cg to image, return path
async def cg_plot_price(ticker, last_n_days: int, out_file: str):
    mpl.use('Agg')
    global pool_cmc
    SMALL_SIZE = 6
    MEDIUM_SIZE = 8
    BIGGER_SIZE = 10
    try:
        await openConnection_cmc()
        async with pool_cmc.acquire() as conn:
            async with conn.cursor() as cur:
                # Read a single record from cmc_v2
                sql = """ SELECT STR_TO_DATE(LEFT(s.last_updated, 10), '%Y-%m-%d') AS last_updated, 
                                 AVG(s.marketprice_USD) AS marketprice_USD,
                                 AVG(s.totalVolume_USD) AS totalVolume_USD
                          FROM `coingecko_v2` AS s WHERE symbol='"""+ticker.lower()+"""' 
                          AND STR_TO_DATE(LEFT(s.last_updated, 10), '%Y-%m-%d') >= DATE_SUB(NOW(), INTERVAL """+str(last_n_days)+""" DAY)
                          GROUP BY STR_TO_DATE(LEFT(s.last_updated, 10), '%Y-%m-%d') """
                await cur.execute(sql,)
                result = await cur.fetchall()
                if result:
                    to_plot1 = pd.DataFrame(result, columns=['marketprice_USD', 'last_updated']).set_index('last_updated')
                    to_plot2 = pd.DataFrame(result, columns=['totalVolume_USD', 'last_updated']).set_index('last_updated')

                    plt.style.use('grayscale')
                    plt.rc('axes', labelcolor='Green')
                    plt.rc('font', size=SMALL_SIZE)
                    plt.rc('axes', labelsize=SMALL_SIZE)    # fontsize of the x and y labels
                    plt.rc('xtick', labelsize=SMALL_SIZE)    # fontsize of the tick labels
                    plt.rc('ytick', labelsize=SMALL_SIZE)    # fontsize of the tick labels

                    plt.subplot(2, 1, 1)
                    plt.gcf().subplots_adjust(left=0.15)
                    plt.ticklabel_format(useOffset=False, style='plain', axis='y')
                    plt.autoscale()
                    plt.grid(True, linestyle='-.')
                    plt.tick_params(labelcolor='r')
                    plt.xticks([])
                    plt.plot(to_plot1, color='Green')
                    plt.title(f'Market Price {ticker.upper()} - Last {str(last_n_days)} days', color='Green')
                    plt.ylabel('Price (USD)', color='Green')

                    plt.subplot(2, 1, 2)
                    plt.gcf().subplots_adjust(left=0.15)
                    plt.ticklabel_format(useOffset=False, style='plain', axis='y')
                    plt.autoscale()
                    plt.grid(True, linestyle='-.')
                    plt.tick_params(labelcolor='r')
                    plt.xticks(rotation=20, color='Green')
                    plt.plot(to_plot2, color='Green')
                    plt.ylabel('Volume (USD)', color='Green')

                    # Save to outfile
                    plt.savefig(out_file, transparent=True)
                    plt.close()
                    return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None



async def sql_help_doc_add(section: str, what: str, detail: str, added_byname: str, added_byuid: str, example: str=None):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_help_docs WHERE `section` = %s AND `what`=%s LIMIT 1 """
                await cur.execute(sql, (section.upper(), what.upper(),))
                result = await cur.fetchone()
                if result is None:
                    sql = """ INSERT INTO discord_help_docs (`section`, `what`, `detail`, `example`, 
                              `time_added`, `added_by`, `added_name`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (section.upper(), what.upper(), detail, example, int(time.time()), added_byuid, added_byname,))
                    await conn.commit()
                    return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_help_doc_del(section: str, what: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_help_docs WHERE `section` = %s AND `what`=%s LIMIT 1 """
                await cur.execute(sql, (section.upper(), what.upper(),))
                result = await cur.fetchone()
                if result:
                    sql = """ DELETE FROM discord_help_docs
                              WHERE `section`=%s AND `what`=%s """
                    await cur.execute(sql, (section.upper(), what.upper(),))
                    await conn.commit()
                    return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_help_doc_get(section: str, what: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if section.upper() == 'ANY':
                    sql = """ SELECT * FROM discord_help_docs WHERE `what`=%s LIMIT 1 """
                    await cur.execute(sql, (what.upper(),))
                    result = await cur.fetchone()
                    if result: return result
                else:
                    sql = """ SELECT * FROM discord_help_docs WHERE `section` = %s AND `what`=%s LIMIT 1 """
                    await cur.execute(sql, (section.upper(), what.upper(),))
                    result = await cur.fetchone()
                    if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_help_doc_list(section: str='HELP', getall:bool=False):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if getall == False:
                    sql = """ SELECT * FROM discord_help_docs WHERE `section` = %s """
                    await cur.execute(sql, (section.upper(),))
                    result = await cur.fetchall()
                    if result: return result
                else:
                    sql = """ SELECT * FROM discord_help_docs """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def sql_help_doc_search(term: str, max_result: int=10):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT *, MATCH(detail, example) AGAINST(%s IN BOOLEAN MODE) AS `score` 
                          FROM discord_help_docs WHERE MATCH(detail, example) AGAINST(%s IN BOOLEAN MODE) 
                          ORDER BY `score` DESC LIMIT """+str(max_result)+"""; """
                await cur.execute(sql, (term, term))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


## Section of Trade
async def sql_count_open_order_by_sellerid(userID: str, user_server: str, status: str = None):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return

    if status is None: status = 'OPEN'
    if status: status = status.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT COUNT(*) FROM `open_order` WHERE `userid_sell` = %s 
                          AND `status`=%s AND `sell_user_server`=%s """
                await cur.execute(sql, (userID, status, user_server))
                result = await cur.fetchone()
                return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)


# use if same rate, then update them up.
async def sql_get_order_by_sellerid_pair_rate(sell_user_server: str, userid_sell: str, coin_sell: str, coin_get: str, sell_div_get: float, 
                                              real_amount_sell, real_amount_buy, fee_sell, fee_buy, status: str = 'OPEN'):
    global pool
    sell_user_server = sell_user_server.upper()
    if sell_user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return

    if real_amount_sell == 0 or real_amount_buy == 0 or fee_sell == 0 \
    or fee_buy == 0 or sell_div_get == 0:
        print("Catch zero amount in {sql_get_order_by_sellerid_pair_rate}!!!")
        return False
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `open_order` WHERE `userid_sell`=%s AND `coin_sell` = %s 
                          AND coin_get=%s AND sell_div_get=%s AND `status`=%s AND `sell_user_server`=%s ORDER BY order_created_date DESC LIMIT 1"""
                await cur.execute(sql, (userid_sell, coin_sell, coin_get, sell_div_get, status, sell_user_server))
                result = await cur.fetchone()
                if result:
                    # then update by adding more amount to it
                    sql = """ UPDATE open_order SET amount_sell=amount_sell+%s, amount_sell_after_fee=amount_sell_after_fee+%s,
                              amount_get=amount_get+%s, amount_get_after_fee=amount_get_after_fee+%s
                              WHERE order_id=%s AND `sell_user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (real_amount_sell, real_amount_sell-fee_sell, real_amount_buy, real_amount_buy-fee_buy, result['order_id'], sell_user_server))
                    await conn.commit()
                    return {"error": False, "msg": f"We added order to your existing one #{result['order_id']}"}
                else:
                    return {"error": True, "msg": None}
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return {"error": True, "msg": "Error with database {sql_get_order_by_sellerid_pair_rate}"}


# use to store data
async def sql_store_openorder(msg_id: str, msg_content: str, coin_sell: str, real_amount_sell: float, 
                              amount_sell_after_fee: float, userid_sell: str, coin_get: str, 
                              real_amount_get: float, amount_get_after_fee: float, sell_div_get: float, 
                              sell_user_server: str = 'DISCORD'):
    global pool
    sell_user_server = sell_user_server.upper()
    if sell_user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return

    coin_sell = coin_sell.upper()
    coin_get = coin_get.upper()
    if real_amount_sell == 0 or amount_sell_after_fee == 0 or real_amount_get == 0 \
    or amount_get_after_fee == 0 or sell_div_get == 0:
        print("Catch zero amount in {sql_store_openorder}!!!")
        return False
    try:
        # coin_sell
        coin_sell_decimal = 1
        coin_get_decimal = 1
        if coin_sell not in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
            coin_sell_decimal = wallet.get_decimal(coin_sell)
        # coin_get
        if coin_get not in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
            coin_get_decimal = wallet.get_decimal(coin_get)
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO open_order (`msg_id`, `msg_content`, `coin_sell`, `coin_sell_decimal`, 
                          `amount_sell`, `amount_sell_after_fee`, `userid_sell`, `coin_get`, `coin_get_decimal`, 
                          `amount_get`, `amount_get_after_fee`, `sell_div_get`, `order_created_date`, `pair_name`, 
                          `status`, `sell_user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (str(msg_id), msg_content, coin_sell, coin_sell_decimal,
                                  real_amount_sell, amount_sell_after_fee, userid_sell, coin_get, coin_get_decimal,
                                  real_amount_get, amount_get_after_fee, sell_div_get, float("%.3f" % time.time()), coin_sell + "-" + coin_get, 
                                  'OPEN', sell_user_server))
                await conn.commit()
                return cur.lastrowid
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_get_open_order_by_alluser_by_coins(coin1: str, coin2: str, status: str, option_order: str="ASC"):
    global pool
    option_order = option_order.upper()
    if option_order not in ["DESC", "ASC"]:
        return False
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if coin2.upper() == "ALL":
                    sql = """ SELECT * FROM open_order WHERE `status`=%s AND `coin_sell`=%s 
                              ORDER BY sell_div_get """+option_order+""" LIMIT 50 """
                    await cur.execute(sql, (status, coin1.upper()))
                    result = await cur.fetchall()
                    return result
                else:
                    sql = """ SELECT * FROM open_order WHERE `status`=%s AND `coin_sell`=%s AND `coin_get`=%s 
                              ORDER BY sell_div_get """+option_order+""" LIMIT 50 """
                    await cur.execute(sql, (status, coin1.upper(), coin2.upper()))
                    result = await cur.fetchall()
                    return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_get_order_numb(order_num: str, status: str = None):
    global pool
    if status is None: status = 'OPEN'
    if status: status = status.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                result = None
                if status == "ANY":
                    sql = """ SELECT * FROM `open_order` WHERE `order_id` = %s LIMIT 1 """
                    await cur.execute(sql, (order_num))
                    result = await cur.fetchone()
                else:
                    sql = """ SELECT * FROM `open_order` WHERE `order_id` = %s 
                              AND `status`=%s LIMIT 1 """
                    await cur.execute(sql, (order_num, status))
                    result = await cur.fetchone()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)


async def sql_match_order_by_sellerid(userid_get: str, ref_numb: str, buy_user_server: str):
    global pool
    buy_user_server = buy_user_server.upper()
    if buy_user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    ref_numb = int(ref_numb)
                    sql = """ UPDATE `open_order` SET `status`=%s, `order_completed_date`=%s, 
                              `userid_get` = %s, `buy_user_server`=%s 
                              WHERE `order_id`=%s AND `status`=%s """
                    await cur.execute(sql, ('COMPLETE', float("%.3f" % time.time()), userid_get, buy_user_server, ref_numb, 'OPEN'))
                    await conn.commit()
                    return True
                except ValueError:
                    return False
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_get_open_order_by_alluser(coin: str, status: str, need_to_buy: bool):
    global pool
    COIN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if need_to_buy: 
                    sql = """ SELECT * FROM `open_order` WHERE `status`=%s AND `coin_get`=%s ORDER BY sell_div_get ASC LIMIT 50 """
                    await cur.execute(sql, (status, COIN_NAME))
                elif COIN_NAME == 'ALL':
                    sql = """ SELECT * FROM `open_order` WHERE `status`=%s ORDER BY order_created_date DESC LIMIT 50 """
                    await cur.execute(sql, (status))
                else:
                    sql = """ SELECT * FROM `open_order` WHERE `status`=%s AND `coin_sell`=%s ORDER BY sell_div_get ASC LIMIT 50 """
                    await cur.execute(sql, (status, COIN_NAME))
                result = await cur.fetchall()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_get_open_order_by_sellerid_all(userid_sell: str, status: str = 'OPEN'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `open_order` WHERE `userid_sell`=%s 
                          AND `status`=%s ORDER BY order_created_date DESC LIMIT 20 """
                await cur.execute(sql, (userid_sell, status))
                result = await cur.fetchall()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_cancel_open_order_by_sellerid(userid_sell: str, coin: str = 'ALL'):
    global pool
    COIN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if len(coin) < 6:
                    if COIN_NAME == 'ALL':
                        sql = """ UPDATE open_order SET `status`=%s, `cancel_date`=%s WHERE `userid_sell`=%s 
                                  AND `status`=%s """
                        await cur.execute(sql, ('CANCEL', float("%.3f" % time.time()), userid_sell, 'OPEN'))
                        await conn.commit()
                        return True
                    else:
                        sql = """ UPDATE open_order SET `status`=%s, `cancel_date`=%s WHERE `userid_sell`=%s 
                                  AND `status`=%s AND `coin_sell`=%s """
                        await cur.execute(sql, ('CANCEL', float("%.3f" % time.time()), userid_sell, 'OPEN', COIN_NAME))
                        await conn.commit()
                        return True
                else:
                    try:
                        ref_numb = int(coin)
                        sql = """ UPDATE open_order SET `status`=%s, `cancel_date`=%s WHERE `userid_sell`=%s 
                                  AND `status`=%s AND `order_id`=%s """
                        await cur.execute(sql, ('CANCEL', float("%.3f" % time.time()), userid_sell, 'OPEN', ref_numb))
                        await conn.commit()
                        return True
                    except ValueError:
                        return False
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_get_open_order_by_sellerid(userid_sell: str, coin: str, status: str = 'OPEN'):
    global pool
    COIN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `open_order` WHERE `userid_sell`=%s AND `coin_sell` = %s 
                          AND `status`=%s ORDER BY order_created_date DESC LIMIT 20 """
                await cur.execute(sql, (userid_sell, COIN_NAME, status))
                result = await cur.fetchall()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False
## END OF Section of Trade


## TradeView
async def sql_get_tradeview_available(market: str, pair1: str, pair2: str, enable:str='ENABLE'):
    global pool
    enable = enable.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `market_chart_pair` WHERE UPPER(`market_name`)=UPPER(%s) AND UPPER(`pair1`) = UPPER(%s) 
                          AND UPPER(`pair2`)=UPPER(%s) AND `enable_disable`=%s LIMIT 1 """
                await cur.execute(sql, (market, pair1, pair2, enable))
                result = await cur.fetchone()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_get_tradeview_market_setting(market: str, enable:str='ENABLE'):
    global pool
    enable = enable.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `market_chart_setting` WHERE UPPER(`market_name`)=UPPER(%s)
                          AND `enable_disable`=%s LIMIT 1 """
                await cur.execute(sql, (market, enable))
                result = await cur.fetchone()
                return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_get_tradeview_insert_fetch(market_name: str, pair_name: str, pair_url: str, by_userid: str, image_name: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO market_chart_fetch (`market_name`, `pair_name`, `pair_url`, `by_userid`, `requested_date`, `image_name`) 
                          VALUES (%s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (market_name, pair_name, pair_url, by_userid, int(time.time()), image_name))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False

## TradeView


## Start of Dai
async def get_token_info(coin: str):
    global pool
    TOKEN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                if TOKEN_NAME in ENABLE_COIN_ERC:
                    sql = """ SELECT * FROM erc_contract WHERE `token_name`=%s LIMIT 1 """
                    await cur.execute(sql, (TOKEN_NAME))
                    result = await cur.fetchone()
                    if result: return result
                elif TOKEN_NAME in ENABLE_COIN_TRC:
                    sql = """ SELECT * FROM trx_contract WHERE `token_name`=%s LIMIT 1 """
                    await cur.execute(sql, (TOKEN_NAME))
                    result = await cur.fetchone()
                    if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def erc_validate_address(address: str, coin: str):
    TOKEN_NAME = coin.upper()
    token_info = await get_token_info(TOKEN_NAME)
    try:
        # HTTPProvider:
        w3 = Web3(Web3.HTTPProvider(token_info[token_info['http_using']]))

        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        return w3.toChecksumAddress(address)
    except ValueError:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def http_wallet_getbalance(address: str, coin: str, re_check: bool=True) -> Dict:
    global redis_conn
    TOKEN_NAME = coin.upper()
    key = f'TIPBOT:BAL_TOKEN_{TOKEN_NAME}:{address}'
    balance = 0
    timeout = 64
    token_info = await get_token_info(TOKEN_NAME)
    # If it is not main address, check in redis.
    if re_check == False and TOKEN_NAME not in ENABLE_COIN_TRC:
        if address.upper() != token_info['withdraw_address'].upper():
            try:
                openRedis()
                if redis_conn and redis_conn.exists(key):
                    return int(redis_conn.get(key))
            except Exception as e:
                await logchanbot(traceback.format_exc())
    # Re-check if it is tron, get from redis first
    if TOKEN_NAME in ENABLE_COIN_TRC:
        try:
            openRedis()
            if redis_conn and redis_conn.exists(key):
                return int(redis_conn.get(key))
        except Exception as e:
            await logchanbot(traceback.format_exc())
    contract = token_info['contract']
    url = token_info[token_info['http_using']]
    if TOKEN_NAME == "XDAI" and token_info['http_using'] != "http_address_local":
        url = token_info['api_url'] + "?module=account&action=eth_get_balance&address="+address
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={'Content-Type': 'application/json'}, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        await session.close()
                        decoded_data = json.loads(res_data)
                        if decoded_data and 'result' in decoded_data:
                            if decoded_data['result'] == "0x":
                                balance = 0
                            else:
                                balance = int(decoded_data['result'], 16)
        except asyncio.TimeoutError:
            print('TIMEOUT: get balance {} for {}s'.format(TOKEN_NAME, timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
    elif TOKEN_NAME == "XDAI" and token_info['http_using'] == "http_address_local":
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
                            if decoded_data['result'] == "0x":
                                balance = 0
                            else:
                                balance = int(decoded_data['result'], 16)
        except asyncio.TimeoutError:
            print('TIMEOUT: get balance {} for {}s'.format(TOKEN_NAME, timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
    elif TOKEN_NAME == "ETH" or TOKEN_NAME == "BNB" or TOKEN_NAME == "MATIC":
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
                            if decoded_data['result'] == "0x":
                                balance = 0
                            else:
                                balance = int(decoded_data['result'], 16)
        except asyncio.TimeoutError:
            print('TIMEOUT: get balance {} for {}s'.format(TOKEN_NAME, timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
    else:
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
                            if decoded_data['result'] == "0x":
                                balance = 0
                            else:
                                balance = int(decoded_data['result'], 16)
        except asyncio.TimeoutError:
            print('TIMEOUT: get balance {} for {}s'.format(TOKEN_NAME, timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    # store in redis if balance equal to 0, else no need.
    if balance == 0:
        try:
            openRedis()
            if redis_conn:
                # set it longer. 3mn to store 0 balance
                redis_conn.set(key, str(balance), ex=3*60)
        except Exception as e:
            await logchanbot(traceback.format_exc())
    return balance


async def sql_mv_erc_single(user_from: str, to_user: str, amount: float, coin: str, tiptype: str, contract: str, user_server: str = 'DISCORD'):
    global pool
    TOKEN_NAME = coin.upper()
    token_info = await get_token_info(TOKEN_NAME)
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ INSERT INTO erc_mv_tx (`token_name`, `contract`, `from_userid`, `to_userid`, `real_amount`, `token_decimal`, `type`, `date`, `user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (TOKEN_NAME, contract, user_from, to_user, amount, token_info['token_decimal'], tiptype.upper(), int(time.time()), user_server))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False


async def sql_mv_erc_multiple(user_from: str, user_tos, amount_each: float, coin: str, tiptype: str, contract: str):
    # user_tos is array "account1", "account2", ....
    global pool
    TOKEN_NAME = coin.upper()
    token_info = await get_token_info(TOKEN_NAME)
    token_decimal = token_info['token_decimal']
    TOKEN_NAME = coin.upper()
    if tiptype.upper() not in ["TIPS", "TIPALL", "FREETIP", "FREETIPS"]:
        return False
    values_str = []
    currentTs = int(time.time())
    for item in user_tos:
        values_str.append(f"('{TOKEN_NAME}', '{contract}', '{user_from}', '{item}', {amount_each}, {token_decimal}, '{tiptype.upper()}', {currentTs})\n")
    values_sql = "VALUES " + ",".join(values_str)
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ INSERT INTO erc_mv_tx (`token_name`, `contract`, `from_userid`, `to_userid`, `real_amount`, `token_decimal`, `type`, `date`) 
                          """+values_sql+""" """
                await cur.execute(sql,)
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False


async def sql_external_erc_single(user_id: str, to_address: str, amount: float, coin: str, tiptype: str, user_server: str='DISCORD'):
    global pool
    TOKEN_NAME = coin.upper()
    if tiptype.upper() not in ["SEND", "WITHDRAW"]:
        return False
    token_info = await get_token_info(TOKEN_NAME)
    user_server = user_server.upper()
    url = token_info[token_info['http_using']]
    try:
        # HTTPProvider:
        w3 = Web3(Web3.HTTPProvider(url))
        signed_txn = None
        sent_tx = None

        if TOKEN_NAME == "XDAI" or TOKEN_NAME == "ETH" or TOKEN_NAME == "BNB" or TOKEN_NAME == "MATIC":
            if token_info['net_name'] == "MATIC":
                nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(token_info['withdraw_address']), 'pending')
            else:
                nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(token_info['withdraw_address']))

            # get gas price
            gasPrice = w3.eth.gasPrice

            estimateGas = w3.eth.estimateGas({'to': w3.toChecksumAddress(to_address), 'from': w3.toChecksumAddress(token_info['withdraw_address']), 'value':  int(amount * 10**token_info['token_decimal'])})

            atomic_amount = int(amount * 10**18)
            transaction = {
                    'from': w3.toChecksumAddress(token_info['withdraw_address']),
                    'to': w3.toChecksumAddress(to_address),
                    'value': atomic_amount,
                    'nonce': nonce,
                    'gasPrice': gasPrice,
                    'gas': estimateGas,
                    'chainId': token_info['chain_id']
                }
            try:
                signed_txn = w3.eth.account.sign_transaction(transaction, private_key=decrypt_string(token_info['withdraw_key']))
                # send Transaction for gas:
                sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        else:
            # inject the poa compatibility middleware to the innermost layer
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            unicorns = w3.eth.contract(address=w3.toChecksumAddress(token_info['contract']), abi=EIP20_ABI)
            if token_info['net_name'] == "MATIC":
                nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(token_info['withdraw_address']), 'pending')
            else:
                nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(token_info['withdraw_address']))
                            
            unicorn_txn = unicorns.functions.transfer(
                w3.toChecksumAddress(to_address),
                int(amount * 10**token_info['token_decimal']) # amount to send
             ).buildTransaction({
                'from': w3.toChecksumAddress(token_info['withdraw_address']),
                'gasPrice': w3.eth.gasPrice,
                'nonce': nonce
             })

            signed_txn = w3.eth.account.signTransaction(unicorn_txn, private_key=decrypt_string(token_info['withdraw_key']))
            sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
        if signed_txn and sent_tx:
            # Add to SQL
            try:
                await openConnection()
                async with pool.acquire() as conn:
                    await conn.ping(reconnect=True)
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO erc_external_tx (`token_name`, `contract`, `user_id`, `real_amount`, 
                                  `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, 
                                  `type`, `user_server`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (TOKEN_NAME, token_info['contract'], user_id, amount, token_info['real_withdraw_fee'], token_info['token_decimal'], 
                                                to_address, int(time.time()), sent_tx.hex(), tiptype.upper(), user_server))
                        await conn.commit()
                        return sent_tx.hex()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())


async def erc_check_minimum_deposit(coin: str, time_lap: int=0):
    global pool
    TOKEN_NAME = coin.upper()
    if TOKEN_NAME not in ENABLE_COIN_ERC:
        return

    token_info = await get_token_info(TOKEN_NAME)
    msg_deposit = ""
    url = token_info[token_info['http_using']]
    list_user_addresses = await sql_get_all_erc_user(TOKEN_NAME, time_lap)

    balance_main_gas = 0
    balance_below_min = 0
    balance_above_min = 0
    num_address_moving_gas = 0
    if TOKEN_NAME == "XDAI" or TOKEN_NAME == "ETH" or TOKEN_NAME == "BNB" or TOKEN_NAME == "MATIC":
        # we do not need gas, we move straight
        if list_user_addresses and len(list_user_addresses) > 0:
            # OK check them one by one
            for each_address in list_user_addresses:
                deposited_balance = await http_wallet_getbalance(each_address['balance_wallet_address'], TOKEN_NAME, False)
                if deposited_balance is None:
                    continue
                real_deposited_balance = float("%.6f" % (int(deposited_balance) / 10**token_info['token_decimal']))
                if real_deposited_balance < token_info['min_move_deposit']:
                    balance_below_min += 1
                    # skip balance move below this
                    # print("Skipped {}, {}. Having {}, minimum {}".format(TOKEN_NAME, each_address['balance_wallet_address'], real_deposited_balance, token_info['min_move_deposit']))
                    pass
                # token_info['withdraw_address'] => each_address['balance_wallet_address']
                else:
                    balance_above_min += 1
                    try:
                        w3 = Web3(Web3.HTTPProvider(url))

                        # inject the poa compatibility middleware to the innermost layer
                        # w3.middleware_onion.inject(geth_poa_middleware, layer=0)

                        if token_info['net_name'] == "MATIC":
                            nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(each_address['balance_wallet_address']), 'pending')
                        else:
                            nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(each_address['balance_wallet_address']))

                        # get gas price
                        gasPrice = int(w3.eth.gasPrice * 1.0)

                        estimateGas = w3.eth.estimateGas({'to': w3.toChecksumAddress(token_info['withdraw_address']), 'from': w3.toChecksumAddress(each_address['balance_wallet_address']), 'value':  deposited_balance})
                        print("TX {} deposited_balance: {}, gasPrice*estimateGas: {}*{}={}, ".format(TOKEN_NAME, deposited_balance, gasPrice, estimateGas, gasPrice*estimateGas))
                        transaction = {
                                'from': w3.toChecksumAddress(each_address['balance_wallet_address']),
                                'to': w3.toChecksumAddress(token_info['withdraw_address']),
                                'value': deposited_balance - gasPrice*estimateGas,
                                'nonce': nonce,
                                'gasPrice': gasPrice,
                                'gas': estimateGas,
                                'chainId': token_info['chain_id']
                            }
                    
                        signed_txn = w3.eth.account.sign_transaction(transaction, private_key=decrypt_string(each_address['private_key']))

                        # send Transaction for gas:
                        sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
                        if signed_txn and sent_tx:
                            # Add to SQL
                            try:
                                inserted = await erc_move_deposit_for_spendable(TOKEN_NAME, token_info['contract'], each_address['user_id'], each_address['balance_wallet_address'], 
                                                                                token_info['withdraw_address'], real_deposited_balance, token_info['real_deposit_fee'],  token_info['token_decimal'],
                                                                                sent_tx.hex())
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                                #await logchanbot(traceback.format_exc())
                    except Exception as e:
                        print("ERROR TOKEN: {} - from {} to {}".format(TOKEN_NAME, each_address['balance_wallet_address'], token_info['withdraw_address']))
                        traceback.print_exc(file=sys.stdout)
                        #await logchanbot(traceback.format_exc())
            msg_deposit += "TOKEN {}: Total deposit address: {}: Below min.: {} Above min. {}".format(TOKEN_NAME, len(list_user_addresses), balance_below_min, balance_above_min)
        else:
            msg_deposit += "TOKEN {}: No deposit address.".format(TOKEN_NAME)
    else:
        # get withdraw gas balance
        gas_main_balance = None
        try:
            gas_main_balance = await http_wallet_getbalance(token_info['withdraw_address'], token_info['net_name'].upper(), True)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # main balance has gas?
        main_balance_gas_sufficient = True
        if gas_main_balance: balance_main_gas = gas_main_balance / 10**18
        msg_deposit += "Main Gas: {}{}\n".format(balance_main_gas, token_info['net_name'].upper())
        if gas_main_balance and gas_main_balance / 10**token_info['token_decimal'] >= token_info['min_gas_tx']:
            #print(f"Main gas balance for {TOKEN_NAME} sufficient. Having {gas_main_balance / 10**18}")
            pass
        else:
            main_balance_gas_sufficient = False
            #print(f"Main gas balance for {TOKEN_NAME} not sufficient!!! Need {token_info['min_gas_tx']}, having only {gas_main_balance}")
            await logchanbot(f"Main gas balance for {TOKEN_NAME} not sufficient!!! Need {token_info['min_gas_tx']}, having only {gas_main_balance/10**token_info['token_decimal']}.")
            pass
        if list_user_addresses and len(list_user_addresses) > 0:
            # OK check them one by one
            for each_address in list_user_addresses:
                deposited_balance = await http_wallet_getbalance(each_address['balance_wallet_address'], TOKEN_NAME, False)
                if deposited_balance is None:
                    continue
                real_deposited_balance = int(deposited_balance) / 10**token_info['token_decimal']
                if real_deposited_balance < token_info['min_move_deposit']:
                    balance_below_min += 1
                    pass
                else:
                    balance_above_min += 1
                    # Check if there is gas remaining to spend there
                    gas_of_address = await http_wallet_getbalance(each_address['balance_wallet_address'], token_info['net_name'].upper(), True)
                    if gas_of_address / 10**18 >= token_info['min_gas_tx']:
                        print('Address {} still has gas {}{}'.format(each_address['balance_wallet_address'], gas_of_address / 10**18, "ETH/DAI"))
                        # TODO: Let's move balance from there to withdraw address and save Tx
                        # HTTPProvider:
                        w3 = Web3(Web3.HTTPProvider(url))

                        # inject the poa compatibility middleware to the innermost layer
                        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

                        unicorns = w3.eth.contract(address=w3.toChecksumAddress(token_info['contract']), abi=EIP20_ABI)
                        if token_info['net_name'] == "MATIC":
                            nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(each_address['balance_wallet_address']), 'pending')
                        else:
                            nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(each_address['balance_wallet_address']))
                        
                        unicorn_txn = unicorns.functions.transfer(
                             w3.toChecksumAddress(token_info['withdraw_address']),
                             deposited_balance # amount to send
                         ).buildTransaction({
                             'from': w3.toChecksumAddress(each_address['balance_wallet_address']),
                             'gasPrice': int(w3.eth.gasPrice*1.0),
                             'nonce': nonce
                         })

                        try:
                            signed_txn = w3.eth.account.signTransaction(unicorn_txn, private_key=decrypt_string(each_address['private_key']))
                            sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
                            if signed_txn and sent_tx:
                                # Add to SQL
                                try:
                                    inserted = await erc_move_deposit_for_spendable(TOKEN_NAME, token_info['contract'], each_address['user_id'], each_address['balance_wallet_address'], 
                                                                                    token_info['withdraw_address'], real_deposited_balance, token_info['real_deposit_fee'],  token_info['token_decimal'],
                                                                                    sent_tx.hex())
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                    await logchanbot(traceback.format_exc())
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot(traceback.format_exc())
                    elif gas_of_address / 10**18 < token_info['min_gas_tx'] and main_balance_gas_sufficient:
                        # HTTPProvider:
                        w3 = Web3(Web3.HTTPProvider(url))

                        # inject the poa compatibility middleware to the innermost layer
                        # w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                        # TODO: Let's move gas from main to have sufficient to move
                        if token_info['net_name'] == "MATIC":
                            nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(token_info['withdraw_address']), 'pending')
                        else:
                            nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(token_info['withdraw_address']))

                        # get gas price
                        gasPrice = int(w3.eth.gasPrice*1.0)

                        estimateGas = w3.eth.estimateGas({'to': w3.toChecksumAddress(each_address['balance_wallet_address']), 'from': w3.toChecksumAddress(token_info['withdraw_address']), 'value':  int(token_info['move_gas_amount'] * 10**token_info['token_decimal'])})

                        amount_gas_move = int(token_info['move_gas_amount'] * 10**18)
                        transaction = {
                                'from': w3.toChecksumAddress(token_info['withdraw_address']),
                                'to': w3.toChecksumAddress(each_address['balance_wallet_address']),
                                'value': amount_gas_move,
                                'nonce': nonce,
                                'gasPrice': gasPrice,
                                'gas': estimateGas,
                                'chainId': token_info['chain_id']
                            }
                        try:
                            signed = w3.eth.account.sign_transaction(transaction, private_key=decrypt_string(token_info['withdraw_key']))
                            # send Transaction for gas:
                            send_gas_tx = w3.eth.sendRawTransaction(signed.rawTransaction)
                            num_address_moving_gas += 1
                            await asyncio.sleep(45) # sleep 30s before another tx
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot(traceback.format_exc())
                    elif gas_of_address / 10**18 < token_info['move_gas_amount'] and main_balance_gas_sufficient == False:
                        await logchanbot('Main address has no sufficient balance to supply gas {}. Main address for gas deposit {}'.format(each_address['balance_wallet_address'], token_info['withdraw_address']))
                        msg_deposit += 'TOKEN {}: Main address has no sufficient balance to supply gas {}. Main address for gas deposit {}\n.'.format(each_address['balance_wallet_address'], token_info['withdraw_address'])
                    else:
                        print('Internal error for gas checking {}'.format(each_address['balance_wallet_address']))
            msg_deposit += "TOKEN {}: Total deposit address: {}: Below min.: {} Above min. {}".format(TOKEN_NAME, len(list_user_addresses), balance_below_min, balance_above_min)
        else:
            msg_deposit += "TOKEN {}: No deposit address.\n".format(TOKEN_NAME)
        if num_address_moving_gas > 0:
            msg_deposit += "TOKEN {}: Moving gas to {} adddresses().".format(TOKEN_NAME, num_address_moving_gas)
    return msg_deposit


async def erc_move_deposit_for_spendable(token_name: str, contract: str, user_id: str, balance_wallet_address: str, to_main_address: str, \
real_amount: float, real_deposit_fee: float, token_decimal: int, txn: str, user_server: str='DISCORD'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ INSERT INTO erc_move_deposit (`token_name`, `contract`, `user_id`, `balance_wallet_address`, 
                          `to_main_address`, `real_amount`, `real_deposit_fee`, `token_decimal`, `txn`, `time_insert`, 
                          `user_server`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (token_name, contract, user_id, balance_wallet_address, to_main_address, real_amount, 
                                        real_deposit_fee, token_decimal, txn, int(time.time()), user_server.upper()))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False


async def erc_check_pending_move_deposit(coin: str, option: str='PENDING'):
    global pool
    TOKEN_NAME = coin.upper()

    topBlock = await erc_get_block_number(TOKEN_NAME)
    if topBlock is None:
        await logchanbot('Can not get top block for {}.'.format(TOKEN_NAME))
        return

    token_info = await get_token_info(TOKEN_NAME)
    list_pending = await sql_get_pending_move_deposit(TOKEN_NAME, option.upper())

    if list_pending and len(list_pending) > 0:
        # Have pending, let's check
        for each_tx in list_pending:
            # Check tx from RPC
            try:
                check_tx = await erc_get_tx_info(each_tx['txn'], TOKEN_NAME)
                if check_tx:
                    tx_block_number = int(check_tx['blockNumber'], 16)
                    #if option.upper() == "ALL":
                    #    print("Checking tx: {}... for {}".format(each_tx['txn'][0:10], TOKEN_NAME))
                    #    print("topBlock: {}, Conf Depth: {}, Tx Block Numb: {}".format(topBlock, token_info['deposit_confirm_depth'] , tx_block_number))
                    if topBlock - token_info['deposit_confirm_depth'] > tx_block_number:
                        confirming_tx = await erc_update_confirming_move_tx(each_tx['txn'], tx_block_number, topBlock - tx_block_number, TOKEN_NAME)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())


async def erc_update_confirming_move_tx(tx: str, blockNumber: int, confirmed_depth: int, coin: str):
    global pool
    TOKEN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ UPDATE erc_move_deposit SET `status`=%s, `blockNumber`=%s, `confirmed_depth`=%s WHERE `txn`=%s AND `token_name`=%s """
                await cur.execute(sql, ('CONFIRMED', blockNumber, confirmed_depth, tx, TOKEN_NAME))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def erc_get_tx_info(tx: str, coin: str):
    TOKEN_NAME = coin.upper()
    timeout = 64
    token_info = await get_token_info(TOKEN_NAME)
    data = '{"jsonrpc":"2.0", "method": "eth_getTransactionByHash", "params":["'+tx+'"], "id":1}'
    url = token_info[token_info['http_using']]

    try:
        if token_info['method'] == "HTTP":
            url = token_info['api_url'] + "?module=transaction&action=gettxinfo&txhash="+tx
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={'Content-Type': 'application/json'}, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        await session.close()
                        decoded_data = json.loads(res_data)
                        if decoded_data and 'result' in decoded_data:
                            return decoded_data['result']
        elif token_info['method'] == "RPC":
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
        print('TIMEOUT: get block number {}s for TOKEN {}'.format(timeout, TOKEN_NAME))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def erc_get_block_number(coin: str, timeout:int = 64):
    TOKEN_NAME = coin.upper()
    if TOKEN_NAME not in ENABLE_COIN_ERC:
        return
    token_info = await get_token_info(TOKEN_NAME)
    height = 0
    if token_info['method'] == "HTTP":
        url = token_info['api_url'] + "?module=block&action=eth_block_number"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={'Content-Type': 'application/json'}, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        await session.close()
                        decoded_data = json.loads(res_data)
                        if decoded_data and 'result' in decoded_data:
                            height = int(decoded_data['result'], 16)
        except asyncio.TimeoutError:
            print('TIMEOUT: get balance {} for {}s'.format(TOKEN_NAME, timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
    elif token_info['method'] == "RPC":
        data = '{"jsonrpc":"2.0", "method":"eth_blockNumber", "params":[], "id":1}'
        url = token_info[token_info['http_using']]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers={'Content-Type': 'application/json'}, json=json.loads(data), timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        await session.close()
                        decoded_data = json.loads(res_data)
                        if decoded_data and 'result' in decoded_data:
                            # store in redis
                            try:
                                openRedis()
                                if redis_conn:
                                    redis_conn.set(f'{config.redis_setting.prefix_daemon_height}{TOKEN_NAME}', str(int(decoded_data['result'], 16)))
                            except Exception as e:
                                await logchanbot(traceback.format_exc())
                            height = int(decoded_data['result'], 16)
        except asyncio.TimeoutError:
            print('TIMEOUT: get block number {}s for TOKEN {}'.format(timeout, TOKEN_NAME))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
    # store in redis
    try:
        openRedis()
        if redis_conn:
            redis_conn.set(f'{config.redis_setting.prefix_daemon_height}{TOKEN_NAME}', str(height))
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return height


async def sql_get_pending_move_deposit(coin: str, option: str='PENDING'):
    global pool
    TOKEN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                if option.upper() == "PENDING":
                    sql = """ SELECT * FROM erc_move_deposit 
                              WHERE `status`=%s AND `token_name`=%s 
                              AND `notified_confirmation`=%s """
                    await cur.execute(sql, (option.upper(), TOKEN_NAME, 'NO'))
                    result = await cur.fetchall()
                    if result: return result
                elif option.upper() == "ALL":
                    sql = """ SELECT * FROM erc_move_deposit 
                              WHERE `token_name`=%s AND `status`<>%s """
                    await cur.execute(sql, (TOKEN_NAME, 'CONFIRMED'))
                    result = await cur.fetchall()
                    if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def erc_get_pending_notification_users(coin: str):
    global pool
    TOKEN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM erc_move_deposit 
                          WHERE `status`=%s AND `token_name`=%s 
                          AND `notified_confirmation`=%s """
                await cur.execute(sql, ('CONFIRMED', TOKEN_NAME, 'NO'))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def erc_updating_pending_move_deposit(notified_confirmation: bool, failed_notification: bool, txn: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ UPDATE erc_move_deposit 
                          SET `notified_confirmation`=%s, `failed_notification`=%s, `time_notified`=%s
                          WHERE `txn`=%s """
                await cur.execute(sql, ('YES' if notified_confirmation else 'NO', 'YES' if failed_notification else 'NO', int(time.time()), txn))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def sql_get_all_erc_user(coin: str, called_Update: int=0):
    # Check update only who has recently called for balance
    # If called_Update = 3600, meaning who called balance for last 1 hr
    global pool
    TOKEN_NAME = coin.upper()
    if TOKEN_NAME not in ENABLE_COIN_ERC:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                if called_Update == 0:
                    sql = """ SELECT `user_id`, `token_name`, `contract`, `balance_wallet_address`, `seed`, `private_key` FROM erc_user 
                              WHERE `user_id`<>%s AND `token_name`=%s """
                    await cur.execute(sql, ('WITHDRAW', TOKEN_NAME))
                    result = await cur.fetchall()
                    if result: return result
                elif called_Update > 0:
                    lap = int(time.time()) - called_Update
                    sql = """ SELECT `user_id`, `token_name`, `contract`, `balance_wallet_address`, `seed`, `private_key` FROM erc_user 
                              WHERE `user_id`<>%s AND `token_name`=%s AND `called_Update`>%s """
                    await cur.execute(sql, ('WITHDRAW', TOKEN_NAME, lap))
                    result = await cur.fetchall()
                    if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def sql_update_erc_trc_user_update_call(userID: str, coin: str, user_server: str = 'DISCORD'):
    global pool
    TOKEN_NAME = coin.upper()
    if TOKEN_NAME not in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                if TOKEN_NAME in ENABLE_COIN_ERC:
                    sql = """ UPDATE erc_user SET `called_Update`=%s WHERE `user_id`=%s AND `token_name`=%s AND `user_server`=%s """
                elif TOKEN_NAME in ENABLE_COIN_TRC:
                    sql = """ UPDATE trx_user SET `called_Update`=%s WHERE `user_id`=%s AND `token_name`=%s AND `user_server`=%s """
                await cur.execute(sql, (int(time.time()), userID, TOKEN_NAME, user_server))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def erc_check_balance_address_in_users(address: str, coin: str):
    global pool
    TOKEN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ SELECT `balance_wallet_address` FROM erc_user 
                          WHERE `token_name`=%s AND LOWER(`balance_wallet_address`)=LOWER(%s) LIMIT 1 """
                await cur.execute(sql, (TOKEN_NAME, address))
                result = await cur.fetchone()
                if result: return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None

## End of xDai


## Start of Tron
async def create_address_trx():
    try:
        _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                   timeout=Timeout(timeout=10, connect=5, read=5))
        TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
        create_wallet = TronClient.generate_address()
        await TronClient.close()
        return create_wallet
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def trx_get_pending_notification_users(coin: str):
    global pool
    TOKEN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM trx_move_deposit 
                          WHERE `status`=%s AND `token_name`=%s 
                          AND `notified_confirmation`=%s """
                await cur.execute(sql, ('CONFIRMED', TOKEN_NAME, 'NO'))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def trx_updating_pending_move_deposit(notified_confirmation: bool, failed_notification: bool, txn: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ UPDATE trx_move_deposit 
                          SET `notified_confirmation`=%s, `failed_notification`=%s, `time_notified`=%s
                          WHERE `txn`=%s """
                await cur.execute(sql, ('YES' if notified_confirmation else 'NO', 'YES' if failed_notification else 'NO', int(time.time()), txn))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def trx_wallet_getbalance(address: str, coin: str):
    TOKEN_NAME = coin.upper()
    token_info = await get_token_info(TOKEN_NAME)
    balance = 0.0
    try:
        _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                   timeout=Timeout(timeout=10, connect=5, read=5))
        TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
        if TOKEN_NAME == "TRX":
            try:
                balance = await TronClient.get_account_balance(address)
            except AddressNotFound:
                balance = 0.0
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        else:
            if token_info['trc_type'] == "TRC20":
                try:
                    cntr = await TronClient.get_contract(token_info['contract'])
                    SYM = await cntr.functions.symbol()
                    if TOKEN_NAME == SYM:
                        precision = await cntr.functions.decimals()
                        balance = await cntr.functions.balanceOf(address) / 10**precision
                    else:
                        await logchanbot("Mis-match SYM vs TOKEN NAME: {} vs {}".format(SYM, TOKEN_NAME))
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            elif token_info['trc_type'] == "TRC10":
                try:
                    precision = token_info['token_decimal']
                    balance = await TronClient.get_account_asset_balance(addr=address, token_id=int(token_info['contract'])) / 10**precision
                except AddressNotFound:
                    balance = 0.0
                except Exception as e:
                    pass
        await TronClient.close()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    except AddressNotFound:
        balance = 0.0
    return balance


async def trx_validate_address(address: str):
    timeout = 32
    token_info = await get_token_info('TRX')
    url = token_info[token_info['http_using']] + "/wallet/validateaddress"
    data = '{"address": "'+address+'"}'
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
        print('TIMEOUT: trx_validate_address {} for {}s'.format(address, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False


async def trx_check_balance_address_in_users(address: str, coin: str):
    global pool
    TOKEN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ SELECT `balance_wallet_address` FROM trx_user 
                          WHERE `token_name`=%s AND LOWER(`balance_wallet_address`)=LOWER(%s) LIMIT 1 """
                await cur.execute(sql, (TOKEN_NAME, address))
                result = await cur.fetchone()
                if result: return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def trx_get_block_number(coin: str, timeout:int = 64):
    TOKEN_NAME = coin.upper()
    if TOKEN_NAME not in ENABLE_COIN_TRC:
        return
    token_info = await get_token_info(TOKEN_NAME)
    height = 0
    url = token_info[token_info['http_using']] + "/wallet/getnowblock"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'Content-Type': 'application/json'}, timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data and 'block_header' in decoded_data:
                        height = decoded_data['block_header']['raw_data']['number']
                        # store in redis
                        try:
                            openRedis()
                            if redis_conn:
                                redis_conn.set(f'{config.redis_setting.prefix_daemon_height}{TOKEN_NAME}', str(height))
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
    except asyncio.TimeoutError:
        print('TIMEOUT: get block number {}s for TOKEN {}'.format(timeout, TOKEN_NAME))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    # store in redis
    try:
        openRedis()
        if redis_conn:
            redis_conn.set(f'{config.redis_setting.prefix_daemon_height}{TOKEN_NAME}', str(height))
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return height


async def sql_get_all_trx_user(coin: str, called_Update: int=0):
    # Check update only who has recently called for balance
    # If called_Update = 3600, meaning who called balance for last 1 hr
    global pool
    TOKEN_NAME = coin.upper()
    if TOKEN_NAME not in ENABLE_COIN_TRC:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                if called_Update == 0:
                    sql = """ SELECT `user_id`, `token_name`, `contract`, `balance_wallet_address`, `hex_address`, `private_key` FROM trx_user 
                              WHERE `user_id`<>%s AND `token_name`=%s """
                    await cur.execute(sql, ('WITHDRAW', TOKEN_NAME))
                    result = await cur.fetchall()
                    if result: return result
                elif called_Update > 0:
                    lap = int(time.time()) - called_Update
                    sql = """ SELECT `user_id`, `token_name`, `contract`, `balance_wallet_address`, `hex_address`, `private_key` FROM trx_user 
                              WHERE `user_id`<>%s AND `token_name`=%s AND `called_Update`>%s """
                    await cur.execute(sql, ('WITHDRAW', TOKEN_NAME, lap))
                    result = await cur.fetchall()
                    if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def sql_external_trx_single(user_id: str, to_address: str, amount: float, coin: str, tiptype: str, user_server: str='DISCORD'):
    global pool
    TOKEN_NAME = coin.upper()
    if tiptype.upper() not in ["SEND", "WITHDRAW"]:
        return False
    token_info = await get_token_info(TOKEN_NAME)
    user_server = user_server.upper()
    url = token_info[token_info['http_using']]
    try:
        _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                   timeout=Timeout(timeout=10, connect=5, read=5))
        TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
        if TOKEN_NAME == "TRX":
            txb = (
                TronClient.trx.transfer(token_info['withdraw_address'], to_address, int(amount*10**token_info['token_decimal']))
                #.memo("test memo")
                .fee_limit(int(token_info['fee_limit']*10**token_info['token_decimal']))
            )
            txn = await txb.build()
            priv_key = PrivateKey(bytes.fromhex(decrypt_string(token_info['withdraw_key'])))
            txn_ret = await txn.sign(priv_key).broadcast()
            try:
                in_block = await txn_ret.wait()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await TronClient.close()
            if txn_ret and in_block:
                # Add to SQL
                try:
                    await openConnection()
                    async with pool.acquire() as conn:
                        await conn.ping(reconnect=True)
                        async with conn.cursor() as cur:
                            sql = """ INSERT INTO trx_external_tx (`token_name`, `contract`, `user_id`, `real_amount`, 
                                      `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, 
                                      `type`, `user_server`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (TOKEN_NAME, token_info['contract'], user_id, amount, token_info['real_withdraw_fee'], token_info['token_decimal'], 
                                                    to_address, int(time.time()), txn_ret['txid'], tiptype.upper(), user_server))
                            await conn.commit()
                            return txn_ret['txid']
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
        else:
            if token_info['trc_type'] == "TRC20":
                try:
                    cntr = await TronClient.get_contract(token_info['contract'])
                    precision = await cntr.functions.decimals()
                    ## TODO: alert if balance below threshold
                    ## balance = await cntr.functions.balanceOf(token_info['withdraw_address']) / 10**precision
                    txb = await cntr.functions.transfer(to_address, int(amount*10**6))
                    txb = txb.with_owner(token_info['withdraw_address']).fee_limit(int(token_info['fee_limit']*10**token_info['token_decimal']))
                    txn = await txb.build()
                    priv_key = PrivateKey(bytes.fromhex(decrypt_string(token_info['withdraw_key'])))
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
                            await openConnection()
                            async with pool.acquire() as conn:
                                await conn.ping(reconnect=True)
                                async with conn.cursor() as cur:
                                    sql = """ INSERT INTO trx_external_tx (`token_name`, `contract`, `user_id`, `real_amount`, 
                                              `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, 
                                              `type`, `user_server`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                    await cur.execute(sql, (TOKEN_NAME, token_info['contract'], user_id, amount, token_info['real_withdraw_fee'], token_info['token_decimal'], 
                                                            to_address, int(time.time()), txn_ret['txid'], tiptype.upper(), user_server))
                                    await conn.commit()
                                    return txn_ret['txid']
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot(traceback.format_exc())
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            elif token_info['trc_type'] == "TRC10":
                try:
                    precision = 10**token_info['token_decimal']
                    txb = (
                        TronClient.trx.asset_transfer(
                            token_info['withdraw_address'], to_address, int(precision*amount), token_id=int(token_info['contract'])
                        )
                        .fee_limit(int(token_info['fee_limit']*10**token_info['token_decimal']))
                    )
                    txn = await txb.build()
                    priv_key = PrivateKey(bytes.fromhex(decrypt_string(token_info['withdraw_key'])))
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
                            await openConnection()
                            async with pool.acquire() as conn:
                                await conn.ping(reconnect=True)
                                async with conn.cursor() as cur:
                                    sql = """ INSERT INTO trx_external_tx (`token_name`, `contract`, `user_id`, `real_amount`, 
                                              `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, 
                                              `type`, `user_server`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                    await cur.execute(sql, (TOKEN_NAME, str(token_info['contract']), user_id, amount, token_info['real_withdraw_fee'], token_info['token_decimal'], 
                                                            to_address, int(time.time()), txn_ret['txid'], tiptype.upper(), user_server))
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


async def trx_check_minimum_deposit(coin: str, time_lap: int=0):
    global pool
    TOKEN_NAME = coin.upper()
    if TOKEN_NAME not in ENABLE_COIN_TRC:
        return

    token_info = await get_token_info(TOKEN_NAME)
    url = token_info[token_info['http_using']]
    list_user_addresses = await sql_get_all_trx_user(TOKEN_NAME, time_lap)
    msg_deposit = ""
    balance_below_min = 0
    balance_above_min = 0
    if list_user_addresses and len(list_user_addresses) > 0:
        # OK check them one by one
        for each_address in list_user_addresses:
            deposited_balance = float(await trx_wallet_getbalance(each_address['balance_wallet_address'], TOKEN_NAME))
            if deposited_balance is None or deposited_balance == 0:
                continue
            
            if deposited_balance < token_info['min_move_deposit']:
                balance_below_min += 1
                pass
            else:
                balance_above_min += 1
                await asyncio.sleep(2)
                if TOKEN_NAME == "TRX":
                    real_deposited_balance = deposited_balance-token_info['min_gas_tx']
                    try:
                        _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                                   timeout=Timeout(timeout=10, connect=5, read=5))
                        TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
                        txb = (
                            TronClient.trx.transfer(each_address['balance_wallet_address'], token_info['withdraw_address'], int(real_deposited_balance*10**token_info['token_decimal']))
                            #.memo("test memo")
                            #.fee_limit(100_000_000)
                            .fee_limit(int(token_info['min_gas_tx']*10**token_info['token_decimal']))
                        )
                        
                        txn = await txb.build()
                        priv_key = PrivateKey(bytes.fromhex(decrypt_string(each_address['private_key'])))
                        txn_ret = await txn.sign(priv_key).broadcast()
                        try:
                            in_block = await txn_ret.wait()
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        await TronClient.close()
                        if txn_ret and in_block:
                            try:
                                inserted = await trx_move_deposit_for_spendable(TOKEN_NAME, token_info['contract'], each_address['user_id'], each_address['balance_wallet_address'], 
                                                                                token_info['withdraw_address'], real_deposited_balance, token_info['real_deposit_fee'],  token_info['token_decimal'],
                                                                                txn_ret['txid'], in_block['blockNumber'])
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                        await asyncio.sleep(3)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                else:
                    # Let's move to main address
                    if token_info['trc_type'] == "TRC20":
                        try:
                            _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                                       timeout=Timeout(timeout=10, connect=5, read=5))
                            TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
                            cntr = await TronClient.get_contract(token_info['contract'])
                            precision = await cntr.functions.decimals()
                            balance = await cntr.functions.balanceOf(each_address['balance_wallet_address']) / 10**precision
                            # Check balance and Transfer gas to it
                            try:
                                gas_balance = await trx_wallet_getbalance(each_address['balance_wallet_address'], "TRX")
                                if gas_balance < token_info['min_gas_tx']:
                                    txb_gas = (
                                        TronClient.trx.transfer(token_info['withdraw_address'], each_address['balance_wallet_address'], int(token_info['move_gas_amount']*10**token_info['token_decimal']))
                                        .fee_limit(int(token_info['min_gas_tx']*10**token_info['token_decimal']))
                                    )
                                    txn_gas = await txb_gas.build()
                                    priv_key_gas = PrivateKey(bytes.fromhex(decrypt_string(token_info['withdraw_key'])))
                                    txn_ret_gas = await txn_gas.sign(priv_key_gas).broadcast()
                                    await asyncio.sleep(3)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            txb = await cntr.functions.transfer(token_info['withdraw_address'], int(balance*10**6))
                            txb = txb.with_owner(each_address['balance_wallet_address']).fee_limit(int(token_info['min_gas_tx']*10**token_info['token_decimal']))
                            txn = await txb.build()
                            priv_key = PrivateKey(bytes.fromhex(decrypt_string(each_address['private_key'])))
                            txn_ret = await txn.sign(priv_key).broadcast()
                            in_block = None
                            try:
                                in_block = await txn_ret.wait()
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            await TronClient.close()
                            if txn_ret and in_block:
                                try:
                                    inserted = await trx_move_deposit_for_spendable(TOKEN_NAME, token_info['contract'], each_address['user_id'], each_address['balance_wallet_address'], 
                                                                                    token_info['withdraw_address'], balance, token_info['real_deposit_fee'],  token_info['token_decimal'],
                                                                                    txn_ret['txid'], in_block['blockNumber'])
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                            await asyncio.sleep(3)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    elif token_info['trc_type'] == "TRC10":
                        try:
                            _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                                       timeout=Timeout(timeout=10, connect=5, read=5))
                            TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))                            
                            balance = await trx_wallet_getbalance(each_address['balance_wallet_address'], TOKEN_NAME)
                            # Check balance and Transfer gas to it
                            try:
                                gas_balance = await trx_wallet_getbalance(each_address['balance_wallet_address'], "TRX")
                                if gas_balance < token_info['min_gas_tx']:
                                    txb_gas = (
                                        TronClient.trx.transfer(token_info['withdraw_address'], each_address['balance_wallet_address'], int(token_info['move_gas_amount']*10**token_info['token_decimal']))
                                        .fee_limit(int(token_info['min_gas_tx']*10**token_info['token_decimal']))
                                    )
                                    txn_gas = await txb_gas.build()
                                    priv_key_gas = PrivateKey(bytes.fromhex(decrypt_string(token_info['withdraw_key'])))
                                    txn_ret_gas = await txn_gas.sign(priv_key_gas).broadcast()
                                    await asyncio.sleep(3)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            ### here
                            precision = 10**token_info['token_decimal']
                            amount = int(precision*balance)
                            txb = (
                                TronClient.trx.asset_transfer(
                                    each_address['balance_wallet_address'], token_info['withdraw_address'], amount, token_id=int(token_info['contract'])
                                )
                                .fee_limit(int(token_info['min_gas_tx']*10**token_info['token_decimal']))
                            )
                            txn = await txb.build()
                            priv_key = PrivateKey(bytes.fromhex(decrypt_string(each_address['private_key'])))
                            txn_ret = await txn.sign(priv_key).broadcast()
                            in_block = None
                            try:
                                in_block = await txn_ret.wait()
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            await TronClient.close()
                            if txn_ret and in_block:
                                try:
                                    inserted = await trx_move_deposit_for_spendable(TOKEN_NAME, str(token_info['contract']), each_address['user_id'], each_address['balance_wallet_address'], 
                                                                                    token_info['withdraw_address'], balance, token_info['real_deposit_fee'],  token_info['token_decimal'],
                                                                                    txn_ret['txid'], in_block['blockNumber'])
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                            await asyncio.sleep(3)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
        msg_deposit += "TOKEN {}: Total deposit address: {}: Below min.: {} Above min. {}".format(TOKEN_NAME, len(list_user_addresses), balance_below_min, balance_above_min)
    else:
        msg_deposit += "TOKEN {}: No deposit address.\n".format(TOKEN_NAME)
    return msg_deposit


async def trx_move_deposit_for_spendable(token_name: str, contract: str, user_id: str, balance_wallet_address: str, to_main_address: str, \
real_amount: float, real_deposit_fee: float, token_decimal: int, txn: str, blockNumber: int, user_server: str='DISCORD'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ INSERT INTO trx_move_deposit (`token_name`, `contract`, `user_id`, `balance_wallet_address`, 
                          `to_main_address`, `real_amount`, `real_deposit_fee`, `token_decimal`, `txn`, `blockNumber`, `time_insert`, 
                          `user_server`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (token_name, contract, user_id, balance_wallet_address, to_main_address, real_amount, 
                                        real_deposit_fee, token_decimal, txn, blockNumber, int(time.time()), user_server.upper()))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False



async def sql_mv_trx_single(user_from: str, to_user: str, amount: float, coin: str, tiptype: str, contract: str, user_server: str = 'DISCORD'):
    global pool
    TOKEN_NAME = coin.upper()
    token_info = await get_token_info(TOKEN_NAME)
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ INSERT INTO trx_mv_tx (`token_name`, `contract`, `from_userid`, `to_userid`, `real_amount`, `token_decimal`, `type`, `date`, `user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (TOKEN_NAME, contract, user_from, to_user, amount, token_info['token_decimal'], tiptype.upper(), int(time.time()), user_server))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False


async def sql_mv_trx_multiple(user_from: str, user_tos, amount_each: float, coin: str, tiptype: str, contract: str):
    # user_tos is array "account1", "account2", ....
    global pool
    TOKEN_NAME = coin.upper()
    token_info = await get_token_info(TOKEN_NAME)
    token_decimal = token_info['token_decimal']
    TOKEN_NAME = coin.upper()
    if tiptype.upper() not in ["TIPS", "TIPALL", "FREETIP", "FREETIPS"]:
        return False
    values_str = []
    currentTs = int(time.time())
    for item in user_tos:
        values_str.append(f"('{TOKEN_NAME}', '{contract}', '{user_from}', '{item}', {amount_each}, {token_decimal}, '{tiptype.upper()}', {currentTs})\n")
    values_sql = "VALUES " + ",".join(values_str)
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ INSERT INTO trx_mv_tx (`token_name`, `contract`, `from_userid`, `to_userid`, `real_amount`, `token_decimal`, `type`, `date`) 
                          """+values_sql+""" """
                await cur.execute(sql,)
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False


async def trx_get_pending_move_deposit(coin: str, option: str='PENDING'):
    global pool
    TOKEN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                if option.upper() == "PENDING":
                    sql = """ SELECT * FROM trx_move_deposit 
                              WHERE `status`=%s AND `token_name`=%s 
                              AND `notified_confirmation`=%s """
                    await cur.execute(sql, (option.upper(), TOKEN_NAME, 'NO'))
                    result = await cur.fetchall()
                    if result: return result
                elif option.upper() == "ALL":
                    sql = """ SELECT * FROM trx_move_deposit 
                              WHERE `token_name`=%s AND `status`<>%s AND `status`<>%s """
                    await cur.execute(sql, (TOKEN_NAME, 'FAILED', 'CONFIRMED'))
                    result = await cur.fetchall()
                    if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def trx_check_pending_move_deposit(coin: str, option: str='PENDING'):
    global pool
    TOKEN_NAME = coin.upper()

    topBlock = await trx_get_block_number(TOKEN_NAME)
    if topBlock is None:
        await logchanbot('Can not get top block for {}.'.format(TOKEN_NAME))
        return

    token_info = await get_token_info(TOKEN_NAME)
    list_pending = await trx_get_pending_move_deposit(TOKEN_NAME, option.upper())

    if list_pending and len(list_pending) > 0:
        # Have pending, let's check
        for each_tx in list_pending:
            try:
                tx_block_number = each_tx['blockNumber']
                #if option.upper() == "ALL":
                #    print("Checking tx: {}... for {}".format(each_tx['txn'][0:10], TOKEN_NAME))
                #    print("topBlock: {}, Conf Depth: {}, Tx Block Numb: {}".format(topBlock, token_info['deposit_confirm_depth'] , tx_block_number))
                if topBlock - token_info['deposit_confirm_depth'] > tx_block_number:
                    check_tx = await trx_get_tx_info(each_tx['txn'], TOKEN_NAME)
                    if check_tx:
                        confirming_tx = await trx_update_confirming_move_tx(each_tx['txn'], topBlock - tx_block_number, TOKEN_NAME, 'CONFIRMED')
                    else:
                        confirming_tx = await trx_update_confirming_move_tx(each_tx['txn'], topBlock - tx_block_number, TOKEN_NAME, 'FAILED')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())


async def trx_update_confirming_move_tx(tx: str, confirmed_depth: int, coin: str, status: str='CONFIRMED'):
    global pool
    TOKEN_NAME = coin.upper()
    status = status.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ UPDATE trx_move_deposit SET `status`=%s, `confirmed_depth`=%s WHERE `txn`=%s AND `token_name`=%s """
                await cur.execute(sql, (status, confirmed_depth, tx, TOKEN_NAME))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def trx_get_tx_info(tx: str, coin: str):
    TOKEN_NAME = coin.upper()
    timeout = 64
    try:
        _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                   timeout=Timeout(timeout=10, connect=5, read=5))
        TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
        getTx = await TronClient.get_transaction(tx)
        await TronClient.close()
        if getTx['ret'][0]['contractRet'] != "SUCCESS":
            # That failed.
            await logchanbot("TRX {} not succeeded with tx: {}".format(TOKEN_NAME, tx))
            return False
        else:
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False
    

## End of Tron


async def sql_tipto_crossing(coin: str, from_userid: str, from_username: str, from_server: str, \
to_userid: str, to_username: str, to_server: str, amount: float, decimal_pts: int):
    global pool	
    COIN_NAME = coin.upper()		
    try:	
        await openConnection()	
        async with pool.acquire() as conn:	
            async with conn.cursor() as cur:	
                sql = """ INSERT INTO user_move_balance (`coin_name`, `from_userid`, `from_name`, `from_server`, 
                          `to_userid`, `to_name`, `to_server`, `amount`, `decimal`, `execute_time`) 	
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """	
                await cur.execute(sql, (COIN_NAME, from_userid, from_username, from_server, to_userid, to_username,
                                        to_server, amount, decimal_pts, int(time.time())))
                await conn.commit()	
                return True	
    except Exception as e:	
        await logchanbot(traceback.format_exc())	
    return False


async def sql_get_all_userid_by_coin(coin: str):
    global pool
    COIN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                if COIN_NAME in ENABLE_XMR:
                    sql = """ SELECT `user_id`, `paymentid`, `user_server` FROM `xmroff_user_paymentid` 
                              WHERE `coin_name`=%s """
                    await cur.execute(sql, (COIN_NAME))
                    result = await cur.fetchall()
                    if result: return result
                elif COIN_NAME in ENABLE_COIN:
                    sql = """ SELECT `user_id`, `paymentid`, `user_server` FROM `cnoff_user_paymentid` 
                              WHERE `coin_name`=%s """
                    await cur.execute(sql, (COIN_NAME))
                    result = await cur.fetchall()
                    if result: return result
                elif COIN_NAME in ENABLE_XCH:
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `user_server` FROM `xch_user` 
                              WHERE `coin_name`=%s """
                    await cur.execute(sql, (COIN_NAME))
                    result = await cur.fetchall()
                    if result: return result
                elif COIN_NAME in ENABLE_COIN_DOGE:
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `user_server` FROM `doge_user` 
                              WHERE `coin_name`=%s """
                    await cur.execute(sql, (COIN_NAME))
                    result = await cur.fetchall()
                    if result: return result
                elif COIN_NAME in ENABLE_COIN_NANO:
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `user_server` FROM `nano_user` 
                              WHERE `coin_name`=%s """
                    await cur.execute(sql, (COIN_NAME))
                    result = await cur.fetchall()
                    if result: return result
                elif COIN_NAME in ENABLE_COIN_TRC:
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `user_server` FROM `trx_user` 
                              WHERE `token_name`=%s """
                    await cur.execute(sql, (COIN_NAME))
                    result = await cur.fetchall()
                    if result: return result
                elif COIN_NAME in ENABLE_COIN_ERC:
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `user_server` FROM `erc_user` 
                              WHERE `token_name`=%s """
                    await cur.execute(sql, (COIN_NAME))
                    result = await cur.fetchall()
                    if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def sql_swap_balance_token(from_coin_name: str, from_real_amount: float, from_decimal: int, to_coin_name: str, \
to_real_amount: float, to_decimal: int, user_id: str, user_name: str, user_server: str='DISCORD'):	
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:	
        await openConnection()	
        async with pool.acquire() as conn:	
            async with conn.cursor() as cur:	
                sql = """ INSERT INTO discord_swap_token (`from_coin_name`, `from_real_amount`, `from_decimal`, 
                          `to_coin_name`, `to_real_amount`, `to_decimal`, `user_id`, `user_name`, `swap_time`, `user_server`)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """	
                await cur.execute(sql, (from_coin_name.upper(), from_real_amount, from_decimal, to_coin_name.upper(), to_real_amount, 
                                        to_decimal, user_id, user_name, int(time.time()), user_server))
                await conn.commit()	
                return True	
    except Exception as e:	
        await logchanbot(traceback.format_exc())	
    return False


async def sql_swap_count_user(userID, lastDuration: int):
    global pool
    lapDuration = int(time.time()) - lastDuration
    count = 0
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Can be tipall or tip many, let's count all
                sql = """ SELECT COUNT(*) as SWAPCOUNT FROM discord_swap_token WHERE `user_id` = %s AND `swap_time`>%s """
                await cur.execute(sql, (str(userID), lapDuration,))
                result = await cur.fetchone()
                count += int(result['SWAPCOUNT']) if result and result['SWAPCOUNT'] else 0
    except Exception as e:
        print(traceback.format_exc())
        await logchanbot(traceback.format_exc())
    return count

## Raffle
async def raffle_get_all(user_server: str='DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()	
        async with pool.acquire() as conn:	
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM guild_raffle 
                          WHERE `user_server`=%s AND `status` IN ('OPENED', 'ONGOING') """
                await cur.execute(sql, (user_server))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:	
        await logchanbot(traceback.format_exc())	
    return None


async def raffle_get_from_guild(guild: str, last_play: bool=False, user_server: str='DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()	
        async with pool.acquire() as conn:	
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM guild_raffle 
                          WHERE `guild_id`=%s AND `user_server`=%s ORDER BY `id` DESC LIMIT 1 """
                if last_play: sql += "OFFSET 1"
                await cur.execute(sql, (guild, user_server))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:	
        await logchanbot(traceback.format_exc())	
    return None


async def raffle_get_from_by_id(idx: str, user_server: str='DISCORD', user_check: str=None):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:	
        await openConnection()	
        async with pool.acquire() as conn:	
            async with conn.cursor() as cur:	
                sql = """ SELECT * FROM guild_raffle 
                          WHERE `id`=%s AND `user_server`=%s LIMIT 1 """
                await cur.execute(sql, (idx, user_server))
                result = await cur.fetchone()
                if result:
                    sql = """ SELECT * FROM guild_raffle_entries 
                              WHERE `raffle_id`=%s AND `user_server`=%s ORDER BY `entry_id` DESC """
                    await cur.execute(sql, (idx, user_server))
                    result_list = await cur.fetchall()
                    if result_list and len(result_list) > 0:
                        result['entries'] = result_list
                        if user_check:
                            sql = """ SELECT * FROM guild_raffle_entries 
                                      WHERE `raffle_id`=%s AND `user_server`=%s AND `user_id`=%s LIMIT 1 """
                            await cur.execute(sql, (idx, user_server, user_check))
                            result_check = await cur.fetchone()
                            if result_check:
                                result['user_joined'] = True
                            else:
                                result['user_joined'] = False
                    else:
                        result['entries'] = None
                        result['user_joined'] = False
                return result
    except Exception as e:	
        await logchanbot(traceback.format_exc())	
    return None


async def raffle_get_entry_by_entry_id(entry_id: str, user_server: str='DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:	
        await openConnection()	
        async with pool.acquire() as conn:	
            async with conn.cursor() as cur:	
                sql = """ SELECT * FROM guild_raffle_entries 
                          WHERE `entry_id`=%s AND `user_server`=%s LIMIT 1 """
                await cur.execute(sql, (entry_id, user_server))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:	
        await logchanbot(traceback.format_exc())	
    return None


async def raffle_insert_new(guild_id: str, guild_name: str, amount: float, decimal: int, coin: str, created_userid: str, \
created_username: str, created_ts: int, ending_ts: str, user_server: str='DISCORD'):
    global pool	
    COIN_NAME = coin.upper()
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return    
    try:	
        await openConnection()	
        async with pool.acquire() as conn:	
            async with conn.cursor() as cur:	
                sql = """ INSERT INTO guild_raffle (`guild_id`, `guild_name`, `amount`, `decimal`, 
                          `coin_name`, `created_userid`, `created_username`, `created_ts`, `ending_ts`, `user_server`) 	
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """	
                await cur.execute(sql, (guild_id, guild_name, amount, decimal, COIN_NAME, created_userid,
                                        created_username, created_ts, ending_ts, user_server,))
                await conn.commit()	
                return True	
    except Exception as e:	
        await logchanbot(traceback.format_exc())	
    return False


async def raffle_insert_new_entry(raffle_id: int, guild_id: str, amount: float, decimal: int, coin: str, user_id: str, \
user_name: str, user_server: str='DISCORD'):
    global pool	
    COIN_NAME = coin.upper()
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return    
    try:	
        await openConnection()	
        async with pool.acquire() as conn:	
            async with conn.cursor() as cur:	
                sql = """ INSERT INTO guild_raffle_entries (`raffle_id`, `guild_id`, `amount`, `decimal`, 
                          `coin_name`, `user_id`, `user_name`, `entry_ts`, `user_server`) 	
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """	
                await cur.execute(sql, (raffle_id, guild_id, amount, decimal, COIN_NAME, user_id,
                                        user_name, int(time.time()), user_server,))
                await conn.commit()	
                return True	
    except Exception as e:	
        await logchanbot(traceback.format_exc())	
    return False

async def raffle_update_id(raffle_id: int, status: str, list_winner=None, list_amounts=None):
    # list_winner = 3
    # list_amounts = 4
    try:
        await openConnection()	
        async with pool.acquire() as conn:	
            async with conn.cursor() as cur:
                if list_winner is None and list_amounts is None:
                    sql = """ UPDATE guild_raffle SET `status`=%s WHERE `id`=%s """	
                    await cur.execute(sql, (status.upper(), raffle_id))
                    await conn.commit()
                    return True
                else:
                    if status.upper() == "COMPLETED" and list_winner and list_amounts:
                        sql = """ UPDATE guild_raffle SET `status`=%s, `winner_userid_1st`=%s,
                                  `winner_1st_amount`=%s, `winner_userid_2nd`=%s,
                                  `winner_2nd_amount`=%s, `winner_userid_3rd`=%s,
                                  `winner_3rd_amount`=%s, `raffle_fund_pot`=%s WHERE `id`=%s """
                        await cur.execute(sql, (status.upper(), list_winner[0], list_amounts[0], 
                                                list_winner[1], list_amounts[1], list_winner[2],
                                                list_amounts[2], list_amounts[3], raffle_id))
                        await conn.commit()	
                        # Update # guild_raffle_entries
                        sql = """ UPDATE guild_raffle_entries SET `status`=%s, `won_amount`=%s WHERE `raffle_id`=%s 
                                  AND `user_id`=%s """
                        await cur.executemany(sql, [('WINNER', list_amounts[0], raffle_id, list_winner[0]),
                                                    ('WINNER', list_amounts[1], raffle_id, list_winner[1]),
                                                    ('WINNER', list_amounts[2], raffle_id, list_winner[2])])
                        await conn.commit()	
                        return True	
    except Exception as e:	
        await logchanbot(traceback.format_exc())	
    return False

async def raffle_cancel_id(raffle_id: int):
    try:	
        await openConnection()	
        async with pool.acquire() as conn:	
            async with conn.cursor() as cur:
                sql = """ UPDATE guild_raffle SET `status`=%s WHERE `id`=%s AND `status` IN ('ONGOING', 'OPENED') LIMIT 1 """	
                await cur.execute(sql, ('CANCELLED', raffle_id))
                await conn.commit()	
                sql = """ UPDATE guild_raffle_entries SET `status`=%s WHERE `raffle_id`=%s """	
                await cur.execute(sql, ('CANCELLED', raffle_id))
                await conn.commit()	
                return True	
    except Exception as e:	
        await logchanbot(traceback.format_exc())	
    return False
## End of Raffle

## Reddit
async def reddit_check_exist(msg_name: str):
    global pool
    try:
        await openConnection()	
        async with pool.acquire() as conn:	
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM reddit_messages 
                          WHERE `msg_name`=%s LIMIT 1 """
                await cur.execute(sql, (msg_name))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:	
        await logchanbot(traceback.format_exc())	
    return None

async def reddit_insert_msg(msg_id: str, msg_name: str, author_name: str, dest_name: str, msg_body: str, msg_body_html: str, msg_created: int):
    global pool
    try:
        await openConnection()	
        async with pool.acquire() as conn:	
            async with conn.cursor() as cur:
                sql = """ INSERT INTO reddit_messages (`msg_id`, `msg_name`, `author_name`, `dest_name`, `msg_body`, 
                          `msg_body_html`, `msg_created`, `msg_inserted`) 	
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """	
                await cur.execute(sql, (msg_id, msg_name, author_name, dest_name, msg_body, msg_body_html,
                                        msg_created, int(time.time()),))
                await conn.commit()	
                return True	
    except Exception as e:	
        await logchanbot(traceback.format_exc())	
    return None
## End of Reddit


## economy
async def economy_get_user(user_id: str, user_name: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_userinfo WHERE `user_id` = %s LIMIT 1 """
                await cur.execute(sql, (user_id,))
                result = await cur.fetchone()
                if result is None:
                    sql = """ INSERT INTO discord_economy_userinfo (`user_id`, `user_name`, `joined`) 
                              VALUES (%s, %s, %s) """
                    await cur.execute(sql, (user_id, user_name, int(time.time()),))
                    await conn.commit()

                    sql = """ SELECT * FROM discord_economy_userinfo WHERE `user_id` = %s LIMIT 1 """
                    await cur.execute(sql, (user_id,))
                    result = await cur.fetchone()
                    return result
                else:
                    return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None

async def economy_get_last_activities(user_id: str, all_activities: bool=False):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if all_activities:
                    sql = """ SELECT * FROM discord_economy_activities WHERE `user_id` = %s ORDER BY `id` DESC """
                    await cur.execute(sql, (user_id,))
                    result = await cur.fetchall()
                    if result: return result
                else:
                    sql = """ SELECT * FROM discord_economy_activities WHERE `user_id` = %s ORDER BY `id` DESC LIMIT 1 """
                    await cur.execute(sql, (user_id,))
                    result = await cur.fetchone()
                    if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_get_user_activities_duration(user_id: str, duration: int=3600):
    global pool
    lapDuration = int(time.time()) - duration
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_activities WHERE `user_id` = %s AND `status`=%s AND `started`>%s ORDER BY `started` DESC """
                await cur.execute(sql, (user_id, 'COMPLETED', lapDuration,))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return []


async def economy_get_guild_worklist(guild_id: str, get_all: bool=True):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if get_all:
                    sql = """ SELECT * FROM discord_economy_work_reward WHERE `status`=%s ORDER BY `work_id` ASC """
                    await cur.execute(sql, (1))
                    result = await cur.fetchall()
                    if result: return result
                else:
                    sql = """ SELECT * FROM discord_economy_work_reward WHERE `guild_id` = %s AND `status`=%s ORDER BY `work_id` ASC """
                    await cur.execute(sql, (guild_id, 1))
                    result = await cur.fetchall()
                    if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_get_workd_id(work_id: int):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_work_reward WHERE `work_id`=%s LIMIT 1 """
                await cur.execute(sql, (work_id))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_insert_activity(user_id: str, guild_id: str, work_id: int, duration_in_second: int, reward_coin_name: str, reward_amount: float, fee_amount: float, reward_decimal: float, exp: float, health: float, energy: float):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_economy_activities (`user_id`, `guild_id`, `work_id`, `started`, `duration_in_second`, `reward_coin_name`, 
                          `reward_amount`, `fee_amount`, `reward_decimal`, `exp`, `health`, `energy`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (user_id, guild_id, work_id, int(time.time()), duration_in_second, reward_coin_name, reward_amount, fee_amount, reward_decimal, exp, health, energy))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_update_activity(act_id: int, user_id: str, exp: int, health: float, energy: float):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE discord_economy_activities SET `completed`=%s, `status`=%s 
                          WHERE `id`=%s AND `user_id`=%s """
                await cur.execute(sql, (int(time.time()), 'COMPLETED', act_id, user_id,))
                # 2nd query
                sql = """ UPDATE discord_economy_userinfo SET `exp`=`exp`+%s, `health_current`=`health_current`+%s,
                          `energy_current`=`energy_current`+%s WHERE `user_id`=%s """
                await cur.execute(sql, (exp, health, energy, user_id,))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_get_guild_foodlist(guild_id: str, get_all: bool=True):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if get_all:
                    sql = """ SELECT * FROM discord_economy_food ORDER BY `food_id` ASC """
                    await cur.execute(sql)
                    result = await cur.fetchall()
                    if result: return result
                else:
                    sql = """ SELECT * FROM discord_economy_food WHERE `guild_id` = %s ORDER BY `food_id` ASC """
                    await cur.execute(sql, (guild_id,))
                    result = await cur.fetchall()
                    if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_insert_eating(user_id: str, guild_id: str, cost_coin_name: str, cost_expense_amount: float, fee_amount: float, cost_decimal: float, gained_energy: float):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_economy_eating (`user_id`, `guild_id`, `date`, `cost_coin_name`, `cost_expense_amount`, 
                          `fee_amount`, `cost_decimal`, `gained_energy`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (user_id, guild_id, int(time.time()), cost_coin_name, cost_expense_amount, fee_amount, cost_decimal, gained_energy,))
                # 2nd query
                sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`+%s WHERE `user_id`=%s """
                await cur.execute(sql, (gained_energy, user_id,))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None

async def economy_get_food_id(food_id: int):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_food WHERE `food_id`=%s LIMIT 1 """
                await cur.execute(sql, (food_id))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_get_guild_eating_list_record(guild_id: str, duration: int=3600):
    global pool
    lapDuration = int(time.time()) - duration
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_eating WHERE `guild_id` = %s AND `date`>%s ORDER BY `date` DESC """
                await cur.execute(sql, (guild_id, lapDuration,))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None

async def economy_get_user_eating_list_record(user_id: str, duration: int=3600):
    global pool
    lapDuration = int(time.time()) - duration
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_eating WHERE `user_id` = %s AND `date`>%s ORDER BY `date` DESC """
                await cur.execute(sql, (user_id, lapDuration,))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None

async def economy_get_list_secret_items():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_secret_items WHERE `usable`=%s """
                await cur.execute(sql, ('YES'))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return []

async def economy_insert_secret_findings(item_id: int, user_id: str, guild_id: str, item_health: float, item_energy: float, item_gem: int, can_use: bool=True):
    global pool
    usable = "NO"
    if can_use:
        usable = "YES"
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_economy_secret_findings (`item_id`, `user_id`, `guild_id`, `date`, 
                          `item_health`, `item_energy`, `item_gem`, `can_use`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (item_id, user_id, guild_id, int(time.time()), item_health, item_energy, item_gem, usable,))
                # 2nd query
                if item_id != 8:
                    sql = """ UPDATE discord_economy_userinfo SET `backpack_items`=`backpack_items`+1 WHERE `user_id`=%s """
                    await cur.execute(sql, (user_id,))
                sql = """ UPDATE discord_economy_secret_items SET `found_times`=`found_times`+1 WHERE `id`=%s """
                await cur.execute(sql, (item_id,))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_get_user_searched_item_list_record(user_id: str, duration: int=3600):
    global pool
    lapDuration = int(time.time()) - duration
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_secret_findings WHERE `user_id` = %s AND `date`>%s ORDER BY `date` DESC """
                await cur.execute(sql, (user_id, lapDuration,))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return []

async def economy_get_user_inventory(user_id: str, count_what: str='ALL'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if count_what == "ALL":
                    sql = """ SELECT A.item_id, B.item_name, B.item_emoji, A.user_id, A.item_health, A.item_energy, A.item_gem, COUNT(*) AS numbers 
                              FROM discord_economy_secret_findings A JOIN discord_economy_secret_items B ON B.id = A.item_id 
                              AND A.user_id=%s AND A.used=%s AND A.can_use=%s GROUP BY A.item_id """
                    await cur.execute(sql, (user_id, 'NO', 'YES'))
                    result = await cur.fetchall()
                    if result: return result
                else:
                    sql = """ SELECT A.item_id, B.item_name, B.item_emoji, A.user_id, A.item_health, A.item_energy, A.item_gem, COUNT(*) AS numbers 
                              FROM discord_economy_secret_findings A JOIN discord_economy_secret_items B ON B.id = A.item_id 
                              AND A.user_id=%s AND A.used=%s AND A.can_use=%s AND B.item_name=%s GROUP BY A.item_id """
                    await cur.execute(sql, (user_id, 'NO', 'YES', count_what))
                    result = await cur.fetchone()
                    if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return []


async def economy_get_item_id(item_id: int):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_secret_items WHERE `id`=%s LIMIT 1 """
                await cur.execute(sql, (item_id))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None

async def economy_item_update_used(user_id: str, item_id: str, gained_energy: float=0.0, gained_health: float=0.0):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE discord_economy_secret_findings SET `used_date`=%s, `used`=%s WHERE `used`=%s AND `item_id`=%s AND `user_id`=%s LIMIT 1 """
                await cur.execute(sql, (int(time.time()), 'YES', 'NO', item_id, user_id,))
                # 2nd query
                if gained_energy > 0:
                    sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`+%s, `backpack_items`=`backpack_items`-1 WHERE `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (gained_energy, user_id,))
                # could be 3rd query
                if gained_health > 0:
                    sql = """ UPDATE discord_economy_userinfo SET `health_current`=`health_current`+%s, `backpack_items`=`backpack_items`-1 WHERE `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (gained_health, user_id,))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_shop_get_item(item_name: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_shopbot WHERE `item_name`=%s OR `item_emoji`=%s LIMIT 1 """
                await cur.execute(sql, (item_name, item_name))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None

async def economy_shop_get_item_list():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_shopbot ORDER BY `credit_cost` DESC """
                await cur.execute(sql,)
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return []


async def discord_economy_userinfo_what(guild_id: str, user_id: str, item_id: int, what: str, item_nos: int, credit: int):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE discord_economy_shopbot SET `numb_bought`=`numb_bought`+1 WHERE `id`=%s """
                await cur.execute(sql, (item_id,))
                # 2nd query
                if what.upper() == "BAIT" or what == "🎣":
                    sql = """ UPDATE discord_economy_userinfo SET `fishing_bait`=`fishing_bait`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                    await cur.execute(sql, (item_nos, credit, user_id,))
                elif what.upper() == "SEED" or what == "🌱":
                    sql = """ UPDATE discord_economy_userinfo SET `tree_seed`=`tree_seed`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                    await cur.execute(sql, (item_nos, credit, user_id,))
                elif what.upper() == "FARM" or what == "👨‍🌾":
                    sql = """ UPDATE discord_economy_userinfo SET `numb_farm`=`numb_farm`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                    await cur.execute(sql, (item_nos, credit, user_id,))
                elif what.upper() == "CHICKENFARM" or what.upper() == "CHICKEN_FARM" or what.upper() == "CHICKEN FARM":
                    sql = """ UPDATE discord_economy_userinfo SET `numb_chicken_farm`=`numb_chicken_farm`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                    await cur.execute(sql, (item_nos, credit, user_id,))
                elif what.upper() == "TRACTOR" or what == "🚜":
                    sql = """ UPDATE discord_economy_userinfo SET `numb_tractor`=`numb_tractor`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                    await cur.execute(sql, (item_nos, credit, user_id,))
                elif what.upper() == "BOAT" or what == "🚣":
                    sql = """ UPDATE discord_economy_userinfo SET `numb_boat`=`numb_boat`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                    await cur.execute(sql, (item_nos, credit, user_id,))
                elif what.upper() == "DAIRY CATTLE" or what == "DAIRYCATTLE":
                    sql = """ UPDATE discord_economy_userinfo SET `numb_dairy_cattle`=`numb_dairy_cattle`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                    await cur.execute(sql, (item_nos, credit, user_id,))
                elif what.upper() == "MARKET" or what == "🛒":
                    sql = """ UPDATE discord_economy_userinfo SET `numb_market`=`numb_market`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                    await cur.execute(sql, (item_nos, credit, user_id,))
                elif what.upper() == "COW" or what == "🐄":
                    sql = """ UPDATE discord_economy_userinfo SET `numb_cow`=`numb_cow`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                    await cur.execute(sql, (item_nos, credit, user_id,))
                    # insert to dairy ownership
                    sql = """ INSERT INTO discord_economy_dairy_cattle_ownership (`user_id`, `guild_id`, `bought_date`, `credit_cost`, `possible_collect_date`) 
                              VALUES (%s, %s, %s, %s, %s) """
                    await cur.execute(sql, (user_id, guild_id, int(time.time()), credit, int(time.time())+config.economy.dairy_collecting_time))
                elif what.upper() == "CHICKEN" or what == "🐔":
                    sql = """ UPDATE discord_economy_userinfo SET `numb_chicken`=`numb_chicken`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                    await cur.execute(sql, (item_nos, credit, user_id,))
                    # insert to dairy ownership
                    sql = """ INSERT INTO discord_economy_chickenfarm_ownership (`user_id`, `guild_id`, `bought_date`, `credit_cost`, `possible_collect_date`) 
                              VALUES (%s, %s, %s, %s, %s) """
                    await cur.execute(sql, (user_id, guild_id, int(time.time()), credit, int(time.time())+config.economy.egg_collecting_time))
                elif what.upper() == "CREDIT" or what == "💵":
                    sql = """ UPDATE discord_economy_userinfo SET `credit`=`credit`+%s,`gem_credit`=`gem_credit`-1 WHERE `user_id`=%s """
                    await cur.execute(sql, (credit, user_id))
                # update to activities
                sql = """ INSERT INTO discord_economy_shopbot_activities (`shopitem_id`, `user_id`, `guild_id`, `credit_cost`, `date`) 
                          VALUES (%s, %s, %s, %s, %s) """
                await cur.execute(sql, (item_id, user_id, guild_id, credit, int(time.time()),))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_get_list_fish_items():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_fish_items """
                await cur.execute(sql,)
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return []

# Planned not use
# TODO: remove
async def economy_insert_fishing(fish_id: int, user_id: str, guild_id: str, fish_strength: float, fish_weight: float, exp_gained: float, energy_loss: float, caught: str, sellable: str="YES"):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_economy_fishing (`fish_id`, `user_id`, `guild_id`, `fish_strength`, `fish_weight`, 
                           `exp_gained`, `energy_loss`, `caught`, `date`, `sellable`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (fish_id, user_id, guild_id, fish_strength, fish_weight, exp_gained, energy_loss, caught, int(time.time()), sellable,))
                ## add experience and engery loss
                sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`-%s, `fishing_exp`=`fishing_exp`+%s,`fishing_bait`=`fishing_bait`-1 WHERE `user_id`=%s LIMIT 1 """
                await cur.execute(sql, (energy_loss, exp_gained, user_id,))
                # add fish found
                sql = """ UPDATE discord_economy_fish_items SET `found_times`=`found_times`+1 WHERE `id`=%s LIMIT 1 """
                await cur.execute(sql, (fish_id,))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_insert_fishing_multiple(list_fishes, total_energy_loss: float, total_exp: float, user_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_economy_fishing (`fish_id`, `user_id`, `guild_id`, `fish_strength`, `fish_weight`, 
                           `exp_gained`, `energy_loss`, `caught`, `date`, `sellable`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                fishing_arr = []
                for each_fish in list_fishes:
                    fishing_arr.append((each_fish['id'], each_fish['user_id'], each_fish['guild_id'], each_fish['fish_strength'], each_fish['fish_weight'], each_fish['exp_gained'], each_fish['energy_loss'], each_fish['caught'], int(time.time()), 'YES'))
                await cur.executemany(sql, fishing_arr)

                ## add experience and engery loss
                sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`-%s, `fishing_exp`=`fishing_exp`+%s,`fishing_bait`=`fishing_bait`-%s WHERE `user_id`=%s LIMIT 1 """
                await cur.execute(sql, (total_energy_loss, total_exp, len(list_fishes), user_id,))
                # add fish found
                sql = """ UPDATE discord_economy_fish_items SET `found_times`=`found_times`+1 WHERE `id`=%s LIMIT 1 """
                fishing_id_arr = []
                for each_fish in list_fishes:
                    fishing_id_arr.append((each_fish['id']))
                await cur.executemany(sql, fishing_id_arr)
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None

async def economy_get_list_fish_caught(user_id: str, sold: str='NO', caught: str='YES'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT A.fish_id, B.fish_name, B.fish_emoji, B.minimum_sell_kg, B.credit_per_kg, A.user_id, A.sold, 
                          COUNT(*) AS numbers, SUM(fish_weight) AS Weights 
                          FROM discord_economy_fishing A JOIN discord_economy_fish_items B ON B.id = A.fish_id 
                          AND A.user_id=%s AND A.sold=%s AND A.caught=%s GROUP BY A.fish_id """
                await cur.execute(sql, (user_id, 'NO', 'YES'))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return []


async def economy_sell_fishes(fish_id: int, user_id: str, guild_id: str, total_weight: float, total_credit: float):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_economy_fish_sold (`fish_id`, `user_id`, `guild_id`, `total_weight`, `total_credit`, `date`) 
                          VALUES (%s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (fish_id, user_id, guild_id, total_weight, total_credit, int(time.time()),))
                ## add user credit
                sql = """ UPDATE discord_economy_userinfo SET `credit`=`credit`+%s WHERE `user_id`=%s LIMIT 1 """
                await cur.execute(sql, (total_credit, user_id,))
                # update selected fishes to sold
                sql = """ UPDATE discord_economy_fishing SET `sold`=%s, `sold_date`=%s WHERE `fish_id`=%s AND `user_id`=%s AND `sold`=%s AND `sellable`=%s """
                await cur.execute(sql, ('YES', int(time.time()), fish_id, user_id, 'NO', 'YES'))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_insert_planting(user_id: str, guild_id: str, exp_gained: float, energy_loss: float):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_economy_planting (`user_id`, `guild_id`, `exp_gained`, `energy_loss`, `date`) 
                          VALUES (%s, %s, %s, %s, %s) """
                await cur.execute(sql, (user_id, guild_id, exp_gained, energy_loss, int(time.time()),))
                ## add experience and engery loss
                sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`-%s,`tree_seed`=`tree_seed`-1,`plant_exp`=`plant_exp`+%s, `tree_planted`=`tree_planted`+1 
                          WHERE `user_id`=%s LIMIT 1 """
                await cur.execute(sql, (energy_loss, exp_gained, user_id,))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None

async def economy_insert_woodcutting(user_id: str, guild_id: str, timber_volume: float, leaf_kg: float, energy_loss: float):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_economy_woodcutting (`user_id`, `guild_id`, `timber_volume`, `leaf_kg`, `energy_loss`, `date`) 
                          VALUES (%s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (user_id, guild_id, timber_volume, leaf_kg, energy_loss, int(time.time()),))
                ## add experience and engery loss
                sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`-%s,`tree_cut`=`tree_cut`+1 WHERE `user_id`=%s LIMIT 1 """
                await cur.execute(sql, (energy_loss, user_id,))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_get_timber_user(user_id: str, sold_timber: str='NO', sold_leaf='NO'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT COUNT(*) AS tree_numbers, SUM(timber_volume) AS timbers 
                          FROM discord_economy_woodcutting WHERE `user_id`=%s AND `timber_sold`=%s """
                await cur.execute(sql, (user_id, 'NO'))
                result = await cur.fetchone()
                sql = """ SELECT COUNT(*) AS tree_numbers, SUM(leaf_kg) AS leaves 
                          FROM discord_economy_woodcutting WHERE `user_id`=%s AND `leaf_sold`=%s """
                await cur.execute(sql, (user_id, 'NO'))
                result2 = await cur.fetchone()
                if result and result2: return {'timber_nos': result['tree_numbers'], 'timber_vol': result['timbers'], 'leaf_nos': result2['tree_numbers'], 'leaf_kg': result2['leaves']}
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return []


async def economy_farm_get_list_plants():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_farm_plantlist """
                await cur.execute(sql,)
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return []


async def economy_farm_user_planting_check_max(user_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT COUNT(*) FROM discord_economy_farm_planting 
                          WHERE `user_id`=%s and `harvested`=%s """
                await cur.execute(sql, (user_id, "NO"))
                result = await cur.fetchone()
                if 'COUNT(*)' in result:
                    return int(result['COUNT(*)'])
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return 0


async def economy_farm_user_planting_group_harvested(user_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT A.id, A.plant_id, B.plant_name, B.growing_emoji, B.plant_emoji, B.duration_harvest, A.user_id, A.date, 
                          A.harvest_date, A.can_harvest_date, A.harvested, A.number_of_item, A.credit_per_item, A.sold, 
                          COUNT(*) as numbers, SUM(B.number_of_item) AS total_products 
                          FROM discord_economy_farm_planting A JOIN discord_economy_farm_plantlist B ON B.id = A.plant_id 
                          AND A.harvested=%s AND A.sold=%s AND A.user_id=%s
                          GROUP BY A.plant_id """
                await cur.execute(sql, ('YES', 'NO', user_id))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return []


async def economy_farm_user_planting_nogroup(user_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT A.id, A.plant_id, B.plant_name, B.growing_emoji, B.plant_emoji, B.duration_harvest, A.user_id, A.date, 
                          A.harvest_date, A.can_harvest_date, A.harvested, A.number_of_item, A.credit_per_item 
                          FROM discord_economy_farm_planting A JOIN discord_economy_farm_plantlist B ON B.id = A.plant_id 
                          AND A.user_id=%s WHERE A.harvested=%s ORDER BY id ASC """
                await cur.execute(sql, (user_id, 'NO'))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return []

async def economy_farm_insert_crop(plant_id: int, user_id: str, guild_id: str, can_harvest_date: int, number_of_item: int, credit_per_item: float, exp_gained: float, energy_loss: float, numb_planting: int=1):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if numb_planting > 1:
                    sql = """ INSERT INTO discord_economy_farm_planting (`plant_id`, `user_id`, `guild_id`, `date`, `can_harvest_date`, 
                              `number_of_item`, `credit_per_item`, `energy_loss`, `exp_gained`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    energy_loss = round(energy_loss/numb_planting, 2)
                    temp_list = [(plant_id, user_id, guild_id, int(time.time()), can_harvest_date, number_of_item, credit_per_item, energy_loss, exp_gained)]*numb_planting
                    await cur.executemany(sql, temp_list)
                    inserted = cur.rowcount
                    ## add experience and engery loss
                    sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`-%s,`tree_seed`=`tree_seed`-%s,`plant_exp`=`plant_exp`+%s, `farm_grow`=`farm_grow`+%s 
                              WHERE `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (energy_loss, numb_planting, exp_gained*numb_planting, numb_planting, user_id,))
                    # add planted numbers found
                    sql = """ UPDATE discord_economy_farm_plantlist SET `planted_times`=`planted_times`+%s WHERE `id`=%s LIMIT 1 """
                    await cur.execute(sql, (numb_planting, plant_id,))
                    await conn.commit()
                    return True
                elif numb_planting == 1:
                    sql = """ INSERT INTO discord_economy_farm_planting (`plant_id`, `user_id`, `guild_id`, `date`, `can_harvest_date`, 
                              `number_of_item`, `credit_per_item`, `energy_loss`, `exp_gained`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (plant_id, user_id, guild_id, int(time.time()), can_harvest_date, number_of_item, credit_per_item, energy_loss, exp_gained,))
                    ## add experience and engery loss
                    sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`-%s,`tree_seed`=`tree_seed`-1,`plant_exp`=`plant_exp`+%s, `farm_grow`=`farm_grow`+1 
                              WHERE `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (energy_loss, exp_gained, user_id,))
                    # add planted numbers found
                    sql = """ UPDATE discord_economy_farm_plantlist SET `planted_times`=`planted_times`+1 WHERE `id`=%s LIMIT 1 """
                    await cur.execute(sql, (plant_id,))
                    await conn.commit()
                    return True                
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_farm_harvesting(user_id: str, plantlist):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE discord_economy_farm_planting SET `harvest_date`=%s, `harvested`=%s WHERE `user_id`=%s AND `id`=%s AND `harvested`=%s """
                list_update = []
                for each_item in plantlist:
                    list_update.append((int(time.time()), 'YES', user_id, each_item, 'NO'))
                await cur.executemany(sql, list_update)
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_farm_sell_item(plant_id: int, user_id: str, guild_id: str, total_credit: float, farm_item_sold: int):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                ## add user credit
                sql = """ UPDATE discord_economy_userinfo SET `credit`=`credit`+%s, `farm_item_sold`=`farm_item_sold`+%s WHERE `user_id`=%s LIMIT 1 """
                await cur.execute(sql, (total_credit, farm_item_sold, user_id,))
                # update selected item to sold
                sql = """ UPDATE discord_economy_farm_planting SET `sold`=%s, `sold_date`=%s WHERE `plant_id`=%s AND `user_id`=%s AND `sold`=%s AND `harvested`=%s """
                await cur.execute(sql, ('YES', int(time.time()), plant_id, user_id, 'NO', 'YES'))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_dairy_cow_ownership(user_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_dairy_cattle_ownership WHERE `user_id`=%s """
                await cur.execute(sql, (user_id))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return []

async def economy_dairy_collecting(user_id: str, cowlist, qty_collect: float, credit_raw_milk_liter: float):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_economy_dairy_collected (`user_id`, `collected_date`, `collected_qty`, `credit_per_item`) 
                          VALUES (%s, %s, %s, %s) """
                await cur.execute(sql, (user_id, int(time.time()), qty_collect, credit_raw_milk_liter))

                ## add raw_milk_qty
                sql = """ UPDATE discord_economy_userinfo SET `raw_milk_qty`=`raw_milk_qty`+%s 
                          WHERE `user_id`=%s LIMIT 1 """
                await cur.execute(sql, (qty_collect, user_id,))

                sql = """ UPDATE discord_economy_dairy_cattle_ownership SET `last_collect_date`=%s, `possible_collect_date`=%s, `total_produced_qty`=`total_produced_qty`+%s 
                          WHERE `user_id`=%s AND `id`=%s """
                list_update = []
                for each_item in cowlist:
                    list_update.append((int(time.time()), int(time.time())+config.economy.dairy_collecting_time, config.economy.raw_milk_per_cow, user_id, each_item))
                await cur.executemany(sql, list_update)
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_dairy_collected(user_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_dairy_collected WHERE `user_id`=%s AND `sold`=%s """
                await cur.execute(sql, (user_id, 'NO'))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return []


async def economy_dairy_sell_milk(user_id: str, ids, credit: float, qty_sell: float):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                ## update raw_milk_qty
                sql = """ UPDATE discord_economy_userinfo SET `raw_milk_qty`=`raw_milk_qty`-%s, `raw_milk_qty_sold`=`raw_milk_qty_sold`+%s, `credit`=`credit`+%s 
                          WHERE `user_id`=%s LIMIT 1 """
                await cur.execute(sql, (qty_sell, qty_sell, credit, user_id,))
                sql = """ UPDATE discord_economy_dairy_collected SET `sold`=%s, `sold_date`=%s 
                          WHERE `user_id`=%s AND `id`=%s AND `sold`=%s """
                list_update = []
                for each_item in ids:
                    list_update.append(('YES', int(time.time()), user_id, each_item, 'NO'))
                await cur.executemany(sql, list_update)
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_chicken_farm_ownership(user_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_chickenfarm_ownership WHERE `user_id`=%s """
                await cur.execute(sql, (user_id))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return []


async def economy_egg_collecting(user_id: str, chickenlist, qty_collect: float, credit_egg: float):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_economy_egg_collected (`user_id`, `collected_date`, `collected_qty`, `credit_per_item`) 
                          VALUES (%s, %s, %s, %s) """
                await cur.execute(sql, (user_id, int(time.time()), qty_collect, credit_egg))

                ## add egg
                sql = """ UPDATE discord_economy_userinfo SET `egg_qty`=`egg_qty`+%s 
                          WHERE `user_id`=%s LIMIT 1 """
                await cur.execute(sql, (qty_collect, user_id,))

                sql = """ UPDATE discord_economy_chickenfarm_ownership SET `last_collect_date`=%s, `possible_collect_date`=%s, `total_produced_qty`=`total_produced_qty`+%s 
                          WHERE `user_id`=%s AND `id`=%s """
                list_update = []
                for each_item in chickenlist:
                    list_update.append((int(time.time()), int(time.time())+config.economy.egg_collecting_time, config.economy.egg_per_chicken, user_id, each_item))
                await cur.executemany(sql, list_update)
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None


async def economy_egg_collected(user_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_economy_egg_collected WHERE `user_id`=%s AND `sold`=%s """
                await cur.execute(sql, (user_id, 'NO'))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return []


async def economy_chickenfarm_sell_egg(user_id: str, ids, credit: float, qty_sell: float):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                ## update egg
                sql = """ UPDATE discord_economy_userinfo SET `egg_qty`=`egg_qty`-%s, `egg_qty_sold`=`egg_qty_sold`+%s, `credit`=`credit`+%s 
                          WHERE `user_id`=%s LIMIT 1 """
                await cur.execute(sql, (qty_sell, qty_sell, credit, user_id,))
                sql = """ UPDATE discord_economy_egg_collected SET `sold`=%s, `sold_date`=%s 
                          WHERE `user_id`=%s AND `id`=%s AND `sold`=%s """
                list_update = []
                for each_item in ids:
                    list_update.append(('YES', int(time.time()), user_id, each_item, 'NO'))
                await cur.executemany(sql, list_update)
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return None
## end of economy

# Steal from https://nitratine.net/blog/post/encryption-and-decryption-in-python/
def encrypt_string(to_encrypt: str):
    key = (config.encrypt.key).encode()

    # Encrypt
    message = to_encrypt.encode()
    f = Fernet(key)
    encrypted = f.encrypt(message)
    return encrypted.decode()


def decrypt_string(decrypted: str):
    key = (config.encrypt.key).encode()

    # Decrypt
    f = Fernet(key)
    decrypted = f.decrypt(decrypted.encode())
    return decrypted.decode()
