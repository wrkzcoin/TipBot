from typing import List, Dict
from datetime import datetime
import time
import json
import asyncio

import daemonrpc_client, rpc_client, wallet, walletapi, addressvalidation
from config import config
import sys, traceback
import os.path

# Encrypt
from cryptography.fernet import Fernet

# MySQL
import pymysql, pymysqlpool
import pymysql.cursors

# redis
import redis
redis_pool = None
redis_conn = None
redis_expired = 120

FEE_PER_BYTE_COIN = config.Fee_Per_Byte_Coin.split(",")

pymysqlpool.logger.setLevel('DEBUG')
myconfig = {
    'host': config.mysql.host,
    'user':config.mysql.user,
    'password':config.mysql.password,
    'database':config.mysql.db,
    'charset':'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit':True
    }

connPool = pymysqlpool.ConnectionPool(size=5, name='connPool', **myconfig)
conn = connPool.get_connection(timeout=5, retry_num=2)

myconfig_voucher = {
    'host': config.mysql_voucher.host,
    'user':config.mysql_voucher.user,
    'password':config.mysql_voucher.password,
    'database':config.mysql_voucher.db,
    'charset':'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit':True
    }

connPool_Voucher = pymysqlpool.ConnectionPool(size=2, name='connPool_Voucher', **myconfig_voucher)
conn_voucher = connPool_Voucher.get_connection(timeout=5, retry_num=2)

#conn = None
sys.path.append("..")

ENABLE_COIN = config.Enable_Coin.split(",")
ENABLE_XMR = config.Enable_Coin_XMR.split(",")
ENABLE_COIN_DOGE = config.Enable_Coin_Doge.split(",")
XS_COIN = ["DEGO"]
ENABLE_COIN_OFFCHAIN = config.Enable_Coin_Offchain.split(",")
ENABLE_SWAP = config.Enabe_Swap_Coin.split(",")


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


# openConnection
def openConnection():
    global conn, connPool
    try:
        if conn is None:
            conn = connPool.get_connection(timeout=5, retry_num=2)
        conn.ping(reconnect=True)  # reconnecting mysql
    except:
        print("ERROR: Unexpected error: Could not connect to MySql instance.")
        sys.exit()


# openConnection Voucher
def openConnection_Voucher():
    global conn_voucher, connPool_Voucher
    try:
        if conn_voucher is None:
            conn_voucher = connPool_Voucher.get_connection(timeout=5, retry_num=2)
        conn_voucher.ping(reconnect=True)  # reconnecting mysql
    except:
        print("ERROR: Unexpected error: Could not connect to MySql instance.")
        sys.exit()


async def get_all_user_balance_address(coin: str):
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT `coin_name`, `balance_wallet_address`, `balance_wallet_address_ch`,`privateSpendKey` FROM `cn_user` WHERE `coin_name` = %s"""
            cur.execute(sql, (coin))
            result = cur.fetchall()
            listAddr=[]
            for row in result:
                listAddr.append({'address':row['balance_wallet_address'], 'scanHeight': row['balance_wallet_address_ch'], 'privateSpendKey': decrypt_string(row['privateSpendKey'])})
            return listAddr
    except Exception as e:
        print(e)
    finally:
        conn.close()


async def sql_update_balances(coin: str = None):
    global conn
    updateTime = int(time.time())
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    gettopblock = None
    timeout = 12
    try:
        if COIN_NAME not in ENABLE_COIN_DOGE:
            gettopblock = await daemonrpc_client.gettopblock(COIN_NAME, time_out=timeout)
        else:
            gettopblock = await rpc_client.call_doge('getblockchaininfo', COIN_NAME)
    except asyncio.TimeoutError:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

    height = None
    if gettopblock:
        if coin_family == "TRTL" or coin_family == "XMR":
            height = int(gettopblock['block_header']['height'])
        elif coin_family == "DOGE":
            height = int(gettopblock['blocks'])
        # store in redis
        try:
            openRedis()
            if redis_conn:
                redis_conn.set(f'TIPBOT:DAEMON_HEIGHT_{COIN_NAME}', str(height))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    else:
        try:
            openRedis()
            if redis_conn and redis_conn.exists(f'TIPBOT:DAEMON_HEIGHT_{COIN_NAME}'):
                height = int(redis_conn.get(f'TIPBOT:DAEMON_HEIGHT_{COIN_NAME}'))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
        print('SQL: Updating all wallet balances '+COIN_NAME)
        start = time.time()
        if COIN_NAME in WALLET_API_COIN:
            balances = await walletapi.walletapi_get_all_balances_all(COIN_NAME)
        else:
            balances = await wallet.get_all_balances_all(COIN_NAME)
        end = time.time()
        print('Time spending collecting all wallet: '+str(end - start))
        try:
            openConnection()
            with conn.cursor() as cur:
                values_str = []
                for details in balances:
                    address = details['address']
                    actual_balance = details['unlocked']
                    locked_balance = details['locked']
                    decimal = wallet.get_decimal(COIN_NAME)
                    values_str.append(f"('{COIN_NAME}', '{address}', {actual_balance}, {locked_balance}, {decimal}, {updateTime})\n")
                values_sql = "VALUES " + ",".join(values_str)
                sql = """ INSERT INTO cn_walletapi (`coin_name`, `balance_wallet_address`, `actual_balance`, 
                          `locked_balance`, `decimal`, `lastUpdate`) """+values_sql+""" 
                          ON DUPLICATE KEY UPDATE 
                          `actual_balance` = VALUES(`actual_balance`),
                          `locked_balance` = VALUES(`locked_balance`),
                          `decimal` = VALUES(`decimal`),
                          `lastUpdate` = VALUES(`lastUpdate`)
                          """
                cur.execute(sql,)
                conn.commit()
                end_sql = time.time()
                print('Time updated to SQL: '+str(end_sql - end))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    elif coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
        #print('SQL: Updating get_transfers '+COIN_NAME)
        get_transfers = await wallet.getTransactions(COIN_NAME, int(height)-100000, 100000)
        try:
            if len(get_transfers) >= 1:
                openConnection()
                with conn.cursor() as cur:
                    sql = """ SELECT * FROM cnoff_get_transfers WHERE `coin_name` = %s """
                    cur.execute(sql, (COIN_NAME,))
                    result = cur.fetchall()
                    d = [i['txid'] for i in result]
                    # print('=================='+COIN_NAME+'===========')
                    # print(d)
                    # print('=================='+COIN_NAME+'===========')
                    list_balance_user = {}
                    for txes in get_transfers:
                        tx_in_block = txes['transactions']
                        for tx in tx_in_block:
                            # Could be one block has two or more tx with different payment ID
                            # add to balance only confirmation depth meet
                            if height > int(tx['blockIndex']) + wallet.get_confirm_depth(COIN_NAME):
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
                                        cur.execute(sql, (COIN_NAME, tx['transactionHash'], tx['paymentId'], tx['blockIndex'], tx['timestamp'],
                                                          tx['amount'], tx['fee'], wallet.get_decimal(COIN_NAME), address, int(time.time())))
                                        conn.commit()
                                        # add to notification list also
                                        sql = """ INSERT IGNORE INTO discord_notify_new_tx (`coin_name`, `txid`, 
                                        `payment_id`, `height`, `amount`, `fee`, `decimal`) 
                                        VALUES (%s, %s, %s, %s, %s, %s, %s) """
                                        cur.execute(sql, (COIN_NAME, tx['transactionHash'], tx['paymentId'], tx['blockIndex'],
                                                          tx['amount'], tx['fee'], wallet.get_decimal(COIN_NAME)))
                                        conn.commit()
                                except pymysql.err.Warning as e:
                                    print(e)
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                            else:
                                # print('{} has some tx but not yet meet confirmation depth.'.format(COIN_NAME))
                                pass
            if list_balance_user and len(list_balance_user) > 0:
                openConnection()
                with conn.cursor() as cur:
                    sql = """ SELECT coin_name, payment_id, SUM(amount) AS txIn FROM cnoff_get_transfers 
                              WHERE coin_name = %s AND amount > 0 
                              GROUP BY payment_id """
                    cur.execute(sql, (COIN_NAME,))
                    result = cur.fetchall()
                    timestamp = int(time.time())
                    list_update = []
                    if result and len(result) > 0:
                        for eachTxIn in result:
                            list_update.append((eachTxIn['txIn'], timestamp, eachTxIn['payment_id']))
                        cur.executemany(""" UPDATE cnoff_user_paymentid SET `actual_balance` = %s, `lastUpdate` = %s 
                                            WHERE paymentid = %s """, list_update)
                        conn.commit()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    elif coin_family == "XMR":
        #print('SQL: Updating get_transfers '+COIN_NAME)
        get_transfers = await wallet.get_transfers_xmr(COIN_NAME)
        if len(get_transfers) >= 1:
            try:
                openConnection()
                with conn.cursor() as cur:
                    sql = """ SELECT * FROM xmroff_get_transfers WHERE `coin_name` = %s """
                    cur.execute(sql, (COIN_NAME,))
                    result = cur.fetchall()
                    d = [i['txid'] for i in result]
                    # print('=================='+COIN_NAME+'===========')
                    # print(d)
                    # print('=================='+COIN_NAME+'===========')
                    list_balance_user = {}
                    for tx in get_transfers['in']:
                        # add to balance only confirmation depth meet
                        if height > int(tx['height']) + wallet.get_confirm_depth(COIN_NAME):
                            if ('payment_id' in tx) and (tx['payment_id'] in list_balance_user):
                                list_balance_user[tx['payment_id']] += tx['amount']
                            elif ('payment_id' in tx) and (tx['payment_id'] not in list_balance_user):
                                list_balance_user[tx['payment_id']] = tx['amount']
                            try:
                                if tx['txid'] not in d:
                                    sql = """ INSERT IGNORE INTO xmroff_get_transfers (`coin_name`, `in_out`, `txid`, 
                                    `payment_id`, `height`, `timestamp`, `amount`, `fee`, `decimal`, `address`, time_insert) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                    cur.execute(sql, (COIN_NAME, tx['type'].upper(), tx['txid'], tx['payment_id'], tx['height'], tx['timestamp'],
                                                      tx['amount'], tx['fee'], wallet.get_decimal(COIN_NAME), tx['address'], int(time.time())))
                                    conn.commit()
                                    # add to notification list also
                                    sql = """ INSERT IGNORE INTO discord_notify_new_tx (`coin_name`, `txid`, 
                                    `payment_id`, `height`, `amount`, `fee`, `decimal`) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s) """
                                    cur.execute(sql, (COIN_NAME, tx['txid'], tx['payment_id'], tx['height'],
                                                      tx['amount'], tx['fee'], wallet.get_decimal(COIN_NAME)))
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                    if len(list_balance_user) > 0:
                        list_update = []
                        timestamp = int(time.time())
                        for key, value in list_balance_user.items():
                            list_update.append((value, timestamp, key))
                        cur.executemany(""" UPDATE xmroff_user_paymentid SET `actual_balance` = %s, `lastUpdate` = %s 
                                        WHERE paymentid = %s """, list_update)
                        conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
    elif coin_family == "DOGE":
        #print('SQL: Updating get_transfers '+COIN_NAME)
        get_transfers = await wallet.doge_listtransactions(COIN_NAME)
        if get_transfers and len(get_transfers) >= 1:
            try:
                openConnection()
                with conn.cursor() as cur:
                    sql = """ SELECT * FROM doge_get_transfers WHERE `coin_name` = %s AND `category` IN (%s, %s) """
                    cur.execute(sql, (COIN_NAME, 'receive', 'send'))
                    result = cur.fetchall()
                    d = [i['txid'] for i in result]
                    # print('=================='+COIN_NAME+'===========')
                    # print(d)
                    # print('=================='+COIN_NAME+'===========')
                    list_balance_user = {}
                    for tx in get_transfers:
                        # add to balance only confirmation depth meet
                        if wallet.get_confirm_depth(COIN_NAME) < int(tx['confirmations']):
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
                                        cur.execute(sql, (COIN_NAME, tx['txid'], tx['blockhash'], tx['address'],
                                                          tx['blocktime'], tx['amount'], tx['confirmations'], tx['category'], int(time.time())))
                                        conn.commit()
                                    # add to notification list also, doge payment_id = address
                                    if (tx['amount'] > 0) and tx['category'] == 'receive':
                                        sql = """ INSERT IGNORE INTO discord_notify_new_tx (`coin_name`, `txid`, 
                                        `payment_id`, `blockhash`, `amount`, `decimal`) 
                                        VALUES (%s, %s, %s, %s, %s, %s) """
                                        cur.execute(sql, (COIN_NAME, tx['txid'], tx['address'], tx['blockhash'],
                                                          tx['amount'], wallet.get_decimal(COIN_NAME)))
                            except pymysql.err.Warning as e:
                                print(e)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                    if len(list_balance_user) > 0:
                        list_update = []
                        timestamp = int(time.time())
                        for key, value in list_balance_user.items():
                            list_update.append((value, timestamp, key))
                        cur.executemany(""" UPDATE doge_user SET `actual_balance` = %s, `lastUpdate` = %s 
                                        WHERE balance_wallet_address = %s """, list_update)
                        conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)


async def sql_credit(user_from: str, to_user: str, amount: float, coin: str, reason: str):
    global conn
    COIN_NAME = coin.upper()
    try:
        openConnection()
        print((COIN_NAME, user_from, to_user, amount, wallet.get_decimal(COIN_NAME), int(time.time()), reason,))
        with conn.cursor() as cur: 
            sql = """ INSERT INTO credit_balance (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `credit_date`, `reason`) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
            cur.execute(sql, (COIN_NAME, user_from, to_user, amount, wallet.get_decimal(COIN_NAME), int(time.time()), reason,))
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_update_some_balances(wallet_addresses: List[str], coin: str):
    global conn
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    updateTime = int(time.time())
    if coin_family == "TRTL":
        print('SQL: Updating some wallet balances '+COIN_NAME)
        if COIN_NAME in WALLET_API_COIN:
            balances = await walletapi.walletapi_get_some_balances(wallet_addresses, COIN_NAME)
        else:
            balances = await wallet.get_some_balances(wallet_addresses, COIN_NAME)
        try:
            openConnection()
            with conn.cursor() as cur:
                values_str = []
                for details in balances:
                    address = details['address']
                    actual_balance = details['unlocked']
                    locked_balance = details['locked']
                    decimal = wallet.get_decimal(COIN_NAME)
                    values_str.append(f"('{COIN_NAME}', '{address}', {actual_balance}, {locked_balance}, {decimal}, {updateTime})\n")
                values_sql = "VALUES " + ",".join(values_str)
                sql = """ INSERT INTO cn_walletapi (`coin_name`, `balance_wallet_address`, `actual_balance`, 
                          `locked_balance`, `decimal`, `lastUpdate`) """+values_sql+""" 
                          ON DUPLICATE KEY UPDATE 
                          `actual_balance` = VALUES(`actual_balance`),
                          `locked_balance` = VALUES(`locked_balance`),
                          `decimal` = VALUES(`decimal`),
                          `lastUpdate` = VALUES(`lastUpdate`)
                          """
                cur.execute(sql,)
                conn.commit()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    else:
        return


async def sql_get_alluser_balance(coin: str, filename: str):
    global conn
    COIN_NAME = coin.upper()
    if COIN_NAME in ENABLE_COIN:
        try:
            openConnection()
            with conn.cursor() as cur:
                sql = """ SELECT user_id, balance_wallet_address, user_wallet_address, user_server FROM cn_user 
                          WHERE `coin_name` = %s """
                cur.execute(sql, (COIN_NAME,))
                result = cur.fetchall()
                write_csv_dumpinfo = open(filename, "w")
                for item in result:
                    getBalance = await sql_get_userwallet(item['user_id'], COIN_NAME)
                    if getBalance:
                        user_balance_total = getBalance['actual_balance'] + getBalance['locked_balance']
                        write_csv_dumpinfo.write(str(item['user_id']) + ';' + wallet.num_format_coin(user_balance_total, COIN_NAME) + ';' + item['balance_wallet_address'] + '\n')
                write_csv_dumpinfo.close()
                return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            return None
    else:
        return None


async def sql_register_user(userID, coin: str, user_server: str = 'DISCORD', chat_id: int = 0):
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    if user_server == "TELEGRAM" and chat_id == 0:
        return
        
    global conn
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = None
            result = None
            if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
                sql = """ SELECT user_id, balance_wallet_address, user_wallet_address, user_server FROM cn_user 
                          WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                cur.execute(sql, (userID, COIN_NAME, user_server))
                result = cur.fetchone()
            elif coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
                sql = """ SELECT user_id, int_address, user_wallet_address, user_server FROM cnoff_user_paymentid 
                          WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                cur.execute(sql, (userID, COIN_NAME, user_server))
                result = cur.fetchone()
            elif coin_family == "XMR":
                sql = """ SELECT * FROM xmroff_user_paymentid 
                          WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                cur.execute(sql, (str(userID), COIN_NAME, user_server))
                result = cur.fetchone()
            elif coin_family == "DOGE":
                sql = """ SELECT * FROM doge_user WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                cur.execute(sql, (str(userID), COIN_NAME, user_server))
                result = cur.fetchone()
            if result is None:
                balance_address = None
                main_address = None
                if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
                    if COIN_NAME in WALLET_API_COIN:
                        balance_address = await walletapi.walletapi_registerOTHER(COIN_NAME)
                    else:
                        balance_address = await wallet.registerOTHER(COIN_NAME)
                elif coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
                    main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
                    balance_address = {}
                    balance_address['payment_id'] = addressvalidation.paymentid()
                    balance_address['integrated_address'] = addressvalidation.make_integrated_cn(main_address, COIN_NAME, balance_address['payment_id'])['integrated_address']
                elif coin_family == "XMR":
                    main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
                    balance_address = await wallet.make_integrated_address_xmr(main_address, COIN_NAME)
                elif coin_family == "DOGE":
                    balance_address = await wallet.doge_register(str(userID), COIN_NAME, user_server)
                if balance_address is None:
                    print('Internal error during call register wallet-api')
                    return
                else:
                    chainHeight = 0
                    walletStatus = None
                    if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
                        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
                    elif COIN_NAME in ENABLE_COIN_DOGE:
                        walletStatus = await daemonrpc_client.getDaemonRPCStatus(COIN_NAME)
                            
                    if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
                        chainHeight = int(walletStatus['blockCount'])
                        sql = """ INSERT INTO cn_user (`coin_name`, `user_id`, `balance_wallet_address`, 
                                  `balance_wallet_address_ts`, `balance_wallet_address_ch`, `privateSpendKey`,
                                  `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, str(userID), balance_address['address'], int(time.time()), chainHeight,
                                          encrypt_string(balance_address['privateSpendKey']), user_server, ))
                        conn.commit()
                    elif coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
                        sql = """ INSERT INTO cnoff_user_paymentid (`coin_name`, `user_id`, `main_address`, `paymentid`, 
                              `int_address`, `paymentid_ts`, `user_server`, `chat_id`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, str(userID), main_address, balance_address['payment_id'], 
                                          balance_address['integrated_address'], int(time.time()), user_server, chat_id))
                        conn.commit()
                    elif coin_family == "XMR":
                        sql = """ INSERT INTO xmroff_user_paymentid (`coin_name`, `user_id`, `main_address`, `paymentid`, 
                                  `int_address`, `paymentid_ts`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, str(userID), main_address, balance_address['payment_id'], 
                                          balance_address['integrated_address'], int(time.time()), user_server))
                        conn.commit()
                    elif coin_family == "DOGE":
                        sql = """ INSERT INTO doge_user (`coin_name`, `user_id`, `balance_wallet_address`, `address_ts`, 
                                  `privateKey`, `user_server`, `chat_id`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, str(userID), balance_address['address'], int(time.time()), 
                                         encrypt_string(balance_address['privateKey']), user_server, chat_id))
                        balance_address['address'] = balance_address['address']
                        conn.commit()
                    return balance_address
            else:
                return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def sql_update_user(userID, user_wallet_address, coin: str, user_server: str = 'DISCORD'):
    global redis_conn
    COIN_NAME = coin.upper()
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    # Check if exist in redis
    try:
        openRedis()
        if redis_conn and redis_conn.exists(f'TIPBOT:WALLET_{str(userID)}_{COIN_NAME}'):
            redis_conn.delete(f'TIPBOT:WALLET_{str(userID)}_{COIN_NAME}')
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
                sql = """ UPDATE cn_user SET user_wallet_address=%s WHERE user_id=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """               
                cur.execute(sql, (user_wallet_address, str(userID), COIN_NAME, user_server))
                conn.commit()
            elif coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
                sql = """ UPDATE cnoff_user_paymentid SET user_wallet_address=%s WHERE user_id=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """               
                cur.execute(sql, (user_wallet_address, str(userID), COIN_NAME, user_server))
                conn.commit()
            elif coin_family == "XMR":
                sql = """ UPDATE xmroff_user_paymentid SET user_wallet_address=%s WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """               
                cur.execute(sql, (user_wallet_address, str(userID), COIN_NAME, user_server))
                conn.commit()
            elif coin_family == "DOGE":
                sql = """ UPDATE doge_user SET user_wallet_address=%s WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """               
                cur.execute(sql, (user_wallet_address, str(userID), COIN_NAME, user_server))
                conn.commit()
            return user_wallet_address  # return userwallet
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def sql_get_userwallet(userID, coin: str, user_server: str = 'DISCORD'):
    global conn, redis_conn, redis_expired
    COIN_NAME = coin.upper()
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    # Check if exist in redis
    try:
        openRedis()
        if redis_conn and redis_conn.exists(f'TIPBOT:WALLET_{str(userID)}_{COIN_NAME}'):
            return json.loads(redis_conn.get(f'TIPBOT:WALLET_{str(userID)}_{COIN_NAME}').decode())
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    try:
        openConnection()
        sql = None
        with conn.cursor() as cur:
            result = None
            if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
                sql = """ SELECT user_id, balance_wallet_address, user_wallet_address, balance_wallet_address_ts, 
                          balance_wallet_address_ch, forwardtip 
                          FROM cn_user WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                cur.execute(sql, (str(userID), COIN_NAME, user_server))
                result = cur.fetchone()
            elif coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
                sql = """ SELECT * FROM cnoff_user_paymentid WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                cur.execute(sql, (str(userID), COIN_NAME, user_server))
                result = cur.fetchone()
            elif coin_family == "XMR":
                sql = """ SELECT * FROM xmroff_user_paymentid WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                cur.execute(sql, (str(userID), COIN_NAME, user_server))
                result = cur.fetchone()
            elif coin_family == "DOGE":
                sql = """ SELECT user_id, balance_wallet_address, user_wallet_address, address_ts, lastUpdate, chat_id 
                          FROM doge_user WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s LIMIT 1 """
                cur.execute(sql, (str(userID), COIN_NAME, user_server))
                result = cur.fetchone()
            if result:
                userwallet = result
                if coin_family == "XMR":
                    userwallet['balance_wallet_address'] = userwallet['int_address']
                elif coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
                    with conn.cursor() as cur:
                        sql = """ SELECT `balance_wallet_address`, `actual_balance`, `locked_balance`, `decimal`, `lastUpdate` FROM cn_walletapi 
                                  WHERE `balance_wallet_address` = %s AND `coin_name` = %s LIMIT 1 """
                        cur.execute(sql, (userwallet['balance_wallet_address'], COIN_NAME,))
                        result2 = cur.fetchone()
                        if result2:
                            userwallet['actual_balance'] = int(result2['actual_balance'])
                            userwallet['locked_balance'] = int(result2['locked_balance'])
                            userwallet['lastUpdate'] = int(result2['lastUpdate'])
                        else:
                            userwallet['actual_balance'] = 0
                            userwallet['locked_balance'] = 0
                            userwallet['lastUpdate'] = int(time.time())
                elif coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
                    userwallet['balance_wallet_address'] = userwallet['int_address']
                    userwallet['actual_balance'] = int(result['actual_balance'])
                    userwallet['locked_balance'] = int(result['locked_balance'])
                    userwallet['lastUpdate'] = int(result['lastUpdate'])
                elif coin_family == "DOGE":
                    with conn.cursor() as cur:
                        sql = """ SELECT * FROM doge_user WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                        cur.execute(sql, (str(userID), COIN_NAME, user_server))
                        result = cur.fetchone()
                        if result:
                            userwallet['actual_balance'] = result['actual_balance']
                            userwallet['locked_balance'] = 0 # There shall not be locked balance
                            userwallet['lastUpdate'] = result['lastUpdate']
                if result['lastUpdate'] == 0 and (coin_family == "TRTL" or coin_family == "XMR"):
                    userwallet['lastUpdate'] = result['paymentid_ts']
                return userwallet
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


def sql_get_countLastTip(userID, lastDuration: int):
    global conn
    lapDuration = int(time.time()) - lastDuration
    try:
        openConnection()
        sql = None
        with conn.cursor() as cur:
            sql = """ (SELECT `coin_name`, `from_user`,`amount`,`date` FROM cn_tip WHERE `from_user` = %s AND `date`>%s )
                      UNION
                      (SELECT `coin_name`, `from_user`,`amount_total`,`date` FROM cn_tipall WHERE `from_user` = %s AND `date`>%s )
                      UNION
                      (SELECT `coin_name`, `from_user`,`amount`,`date` FROM cn_send WHERE `from_user` = %s AND `date`>%s )
                      UNION
                      (SELECT `coin_name`, `user_id`,`amount`,`date` FROM cn_withdraw WHERE `user_id` = %s AND `date`>%s )
                      UNION
                      (SELECT `coin_name`, `from_user`,`amount`,`date` FROM cn_donate WHERE `from_user` = %s AND `date`>%s )
                      ORDER BY `date` DESC LIMIT 10 """
            cur.execute(sql, (str(userID), lapDuration, str(userID), lapDuration, str(userID), lapDuration,
                              str(userID), lapDuration, str(userID), lapDuration,))
            result = cur.fetchall()

            # Can be tipall or tip many, let's count all
            sql = """ SELECT `coin_name`, `from_userid`,`amount`,`date` FROM cnoff_mv_tx WHERE `from_userid` = %s AND `date`>%s 
                      ORDER BY `date` DESC LIMIT 100 """
            cur.execute(sql, (str(userID), lapDuration,))
            result2 = cur.fetchall()

            # doge table
            sql = """ SELECT `coin_name`, `from_userid`,`amount`,`date` FROM doge_mv_tx WHERE `from_userid` = %s AND `date`>%s 
                      ORDER BY `date` DESC LIMIT 100 """
            cur.execute(sql, (str(userID), lapDuration,))
            result3 = cur.fetchall()

            if (result is None) and (result2 is None) and (result3 is None):
                return 0
            else:
                return (len(result) if result else 0) + (len(result2) if result2 else 0) + (len(result3) if result3 else 0)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def sql_send_tip(user_from: str, user_to: str, amount: int, tiptype: str, coin: str, user_server: str = 'DISCORD'):
    global conn
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    user_from_wallet = None
    user_to_wallet = None
    address_to = None
    if coin_family == "TRTL" or coin_family == "XMR":
        user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME, user_server)
        user_to_wallet = await sql_get_userwallet(user_to, COIN_NAME, user_server)
        if user_to_wallet and user_to_wallet['forwardtip'] == "ON" and user_to_wallet['user_wallet_address']:
            address_to = user_to_wallet['user_wallet_address']
        else:
            address_to = user_to_wallet['balance_wallet_address']
    if all(v is not None for v in [user_from_wallet['balance_wallet_address'], address_to]):
        tx_hash = None
        if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
            if COIN_NAME in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transaction(user_from_wallet['balance_wallet_address'],
                                                                     address_to, amount, COIN_NAME)
            else:
                tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'],
                                                        address_to, amount, COIN_NAME)
        elif coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
            # Move balance
            try:
                openConnection()
                with conn.cursor() as cur: 
                    sql = """ INSERT INTO cnoff_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`, `user_server`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                    cur.execute(sql, (COIN_NAME, user_from, user_to, amount, wallet.get_decimal(COIN_NAME), tiptype.upper(), int(time.time()), user_server,))
                    conn.commit()
                return {'transactionHash': 'NONE', 'fee': 0}
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        if tx_hash and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    sql = None
                    if coin_family == "TRTL":
                        fee = 0
                        if COIN_NAME not in FEE_PER_BYTE_COIN:
                            fee = wallet.get_tx_fee(COIN_NAME)
                        else:
                            fee = tx_hash['fee']
                        sql = """ INSERT INTO cn_tip (`coin_name`, `from_user`, `to_user`, `amount`, `decimal`, `date`, `tx_hash`, `tip_tips_tipall`, `fee`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, user_from, user_to, amount, wallet.get_decimal(COIN_NAME), timestamp, tx_hash['transactionHash'], tiptype.upper(), fee, user_server))
                        conn.commit()
                        await sql_update_some_balances([user_from_wallet['balance_wallet_address'], user_to_wallet['balance_wallet_address']], COIN_NAME)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        return tx_hash
    else:
        return None


async def sql_send_tipall(user_from: str, user_tos, amount: int, amount_div: int, user_ids, tiptype: str, coin: str, user_server: str = 'DISCORD'):
    global conn
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    if tiptype.upper() not in ["TIPS", "TIPALL"]:
        return None

    user_from_wallet = None
    if coin_family == "TRTL" or coin_family == "XMR":
        user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME, user_server)
    if user_from_wallet['balance_wallet_address']:
        tx_hash = None
        if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
            if COIN_NAME in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transactionall(user_from_wallet['balance_wallet_address'], user_tos, COIN_NAME)
            else:
                tx_hash = await wallet.send_transactionall(user_from_wallet['balance_wallet_address'], user_tos, COIN_NAME)
        elif coin_family == "TRTL" and COIN_NAME in ENABLE_COIN_OFFCHAIN:
            # Move offchain
            values_str = []
            currentTs = int(time.time())
            for item in user_ids:
                values_str.append(f"('{COIN_NAME}', '{user_from}', '{item}', {amount_div}, {wallet.get_decimal(COIN_NAME)}, '{tiptype.upper()}', {currentTs})\n")
            values_sql = "VALUES " + ",".join(values_str)
            try:
                openConnection()
                with conn.cursor() as cur: 
                    sql = """ INSERT INTO cnoff_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`) 
                              """+values_sql+""" """
                    cur.execute(sql,)
                    conn.commit()
                return {'transactionHash': 'NONE', 'fee': 0}
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                print(f"SQL:\n{sql}\n")
        if tx_hash:
            tx_hash_hash = tx_hash['transactionHash']
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    if coin_family == "TRTL" or coin_family == "CCX":
                        fee = 0
                        if COIN_NAME not in FEE_PER_BYTE_COIN:
                            fee = wallet.get_tx_fee(COIN_NAME)
                        else:
                            fee = tx_hash['fee']
                        sql = """ INSERT INTO cn_tipall (`coin_name`, `from_user`, `amount_total`, `decimal`, `date`, `tx_hash`, `numb_receivers`, `fee`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, user_from, amount, wallet.get_decimal(COIN_NAME), timestamp, tx_hash['transactionHash'], len(user_tos), fee))
                        conn.commit()

                        values_str = []
                        for item in user_ids:
                            values_str.append(f"('{COIN_NAME}', '{user_from}', '{item}', {amount_div}, {int(wallet.get_decimal(COIN_NAME))}, {timestamp}, '{tx_hash_hash}', '{tiptype.upper()}')\n")
                        values_sql = "VALUES " + ",".join(values_str)
                        sql = """ INSERT INTO cn_tip (`coin_name`, `from_user`, `to_user`, `amount`, `decimal`, `date`, `tx_hash`, `tip_tips_tipall`) 
                                  """+values_sql+""" """
                        cur.execute(sql,)
                        conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                print(f"SQL:\n{sql}\n")
        return tx_hash
    else:
        return None


async def sql_send_tip_Ex(user_from: str, address_to: str, amount: int, coin: str, user_server: str = 'DISCORD'):
    global conn
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    user_from_wallet = None
    if coin_family == "TRTL" or coin_family == "XMR":
        user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME, user_server)
    if user_from_wallet['balance_wallet_address']:
        tx_hash = None
        if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
            if COIN_NAME in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transaction(user_from_wallet['balance_wallet_address'], address_to, 
                                                                     amount, COIN_NAME)

            else:
                tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'], address_to, 
                                                        amount, COIN_NAME)
        elif coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
            # send from wallet and store in cnoff_external_tx
            main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
            if COIN_NAME in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transaction(main_address, address_to, 
                                                                     amount, COIN_NAME)

            else:
                tx_hash = await wallet.send_transaction(main_address, address_to, 
                                                        amount, COIN_NAME)
        elif coin_family == "XMR":
            tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'], address_to, 
                                                    amount, COIN_NAME, user_from_wallet['account_index'])
        if tx_hash:
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    updateBalance = None
                    if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
                        fee = 0
                        if COIN_NAME not in FEE_PER_BYTE_COIN:
                            fee = wallet.get_tx_fee(COIN_NAME)
                        else:
                            fee = tx_hash['fee']
                        sql = """ INSERT INTO cn_send (`coin_name`, `from_user`, `to_address`, `amount`, `decimal`, `date`, 
                                  `tx_hash`, `fee`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, user_from, address_to, amount, wallet.get_decimal(COIN_NAME), timestamp, tx_hash['transactionHash'], fee))
                        conn.commit()
                        if COIN_NAME in WALLET_API_COIN:
                            updateBalance = await walletapi.walletapi_get_balance_address(user_from_wallet['balance_wallet_address'], 
                                                                                          COIN_NAME)
                        else:
                            updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], 
                                                                             COIN_NAME)
                    elif coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
                        fee = 0
                        if COIN_NAME not in FEE_PER_BYTE_COIN:
                            fee = wallet.get_tx_fee(COIN_NAME)
                        else:
                            fee = tx_hash['fee']
                        sql = """ INSERT INTO cnoff_external_tx (`coin_name`, `user_id`, `to_address`, `amount`, `decimal`, `date`, 
                                  `tx_hash`, `fee`, `user_server`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, user_from, address_to, amount, wallet.get_decimal(COIN_NAME), timestamp, 
                                    tx_hash['transactionHash'], fee, user_server))
                        conn.commit()
                    if updateBalance:
                        if coin_family == "TRTL":
                            sql = """ UPDATE cn_walletapi SET `actual_balance`=%s, 
                                      `locked_balance`=%s, `lastUpdate`=%s, `decimal`=%s 
                                      WHERE `balance_wallet_address`=%s AND `coin_name` = %s LIMIT 1 """
                            cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'],
                                        updateTime, wallet.get_decimal(COIN_NAME), user_from_wallet['balance_wallet_address'], COIN_NAME,))
                            conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        return tx_hash
    else:
        return None


async def sql_send_tip_Ex_id(user_from: str, address_to: str, amount: int, paymentid, coin: str, user_server: str = 'DISCORD'):
    global conn
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME, user_server)
    if 'balance_wallet_address' in user_from_wallet:
        tx_hash = None
        if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
            if COIN_NAME in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transaction_id(user_from_wallet['balance_wallet_address'], address_to,
                                                                        amount, paymentid, COIN_NAME)
            else:
                tx_hash = await wallet.send_transaction_id(user_from_wallet['balance_wallet_address'], address_to,
                                                           amount, paymentid, COIN_NAME)
        elif coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
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
                openConnection()
                updateBalance = None
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
                        fee = 0
                        if COIN_NAME not in FEE_PER_BYTE_COIN:
                            fee = wallet.get_tx_fee(COIN_NAME)
                        else:
                            fee = tx_hash['fee']
                        sql = """ INSERT INTO cn_send (`coin_name`, `from_user`, `to_address`, `amount`, `decimal`, `date`, 
                                  `tx_hash`, `paymentid`, `fee`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, user_from, address_to, amount, wallet.get_decimal(COIN_NAME), timestamp, tx_hash['transactionHash'], paymentid, fee))
                        conn.commit()
                        if COIN_NAME in WALLET_API_COIN:
                            updateBalance = await walletapi.walletapi_get_balance_address(user_from_wallet['balance_wallet_address'], COIN_NAME)
                        else:
                            updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], COIN_NAME)
                    elif coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
                        fee = 0
                        if COIN_NAME not in FEE_PER_BYTE_COIN:
                            fee = wallet.get_tx_fee(COIN_NAME)
                        else:
                            fee = tx_hash['fee']
                        sql = """ INSERT INTO cnoff_external_tx (`coin_name`, `user_id`, `to_address`, `amount`, `decimal`, `date`, 
                                  `tx_hash`, `paymentid`, `fee`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, user_from, address_to, amount, wallet.get_decimal(COIN_NAME), 
                                    timestamp, tx_hash['transactionHash'], paymentid, fee, user_server))
                        conn.commit()
                    if updateBalance:
                        if COIN_NAME in ENABLE_COIN:
                            sql = """ UPDATE cn_walletapi SET `actual_balance`=%s, 
                                      `locked_balance`=%s, `lastUpdate`=%s, `decimal`=%s WHERE `balance_wallet_address`=%s 
                                      AND `coin_name` = %s LIMIT 1 """
                            cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'], 
                                        updateTime, wallet.get_decimal(COIN_NAME), user_from_wallet['balance_wallet_address'], COIN_NAME,))
                            conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        return tx_hash
    else:
        return None


async def sql_withdraw(user_from: str, amount: int, coin: str, user_server: str = 'DISCORD'):
    global conn
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    tx_hash = None
    user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME, user_server)
    if all(v is not None for v in [user_from_wallet['balance_wallet_address'], user_from_wallet['user_wallet_address']]):
        if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
            if COIN_NAME in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transaction(user_from_wallet['balance_wallet_address'],
                                                                     user_from_wallet['user_wallet_address'], amount, COIN_NAME)

            else:
                tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'],
                                                        user_from_wallet['user_wallet_address'], amount, COIN_NAME)
        elif coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
            # send from wallet and store in cnoff_external_tx
            main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
            if COIN_NAME in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transaction(main_address,
                                                                     user_from_wallet['user_wallet_address'], amount, COIN_NAME)

            else:
                tx_hash = await wallet.send_transaction(main_address,
                                                        user_from_wallet['user_wallet_address'], amount, COIN_NAME)
        elif coin_family == "XMR":
            tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'],
                                                    user_from_wallet['user_wallet_address'], amount, COIN_NAME, user_from_wallet['account_index'])
        if tx_hash:
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    updateBalance = None
                    if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
                        sql = """ INSERT INTO cn_withdraw (`coin_name`, `user_id`, `to_address`, `amount`, 
                                  `decimal`, `date`, `tx_hash`, `fee`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                        fee = 0
                        if COIN_NAME not in FEE_PER_BYTE_COIN:
                            fee = wallet.get_tx_fee(COIN_NAME)
                        else:
                            fee = tx_hash['fee']
                        cur.execute(sql, (COIN_NAME, user_from, user_from_wallet['user_wallet_address'], amount, wallet.get_decimal(COIN_NAME), timestamp, tx_hash['transactionHash'], fee))
                        conn.commit()
                        if COIN_NAME in WALLET_API_COIN:
                            updateBalance = await walletapi.walletapi_get_balance_address(user_from_wallet['balance_wallet_address'], COIN_NAME)
                        else:
                            updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], COIN_NAME)
                    if coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
                        sql = """ INSERT INTO cnoff_external_tx (`coin_name`, `user_id`, `to_address`, `amount`, 
                                  `decimal`, `date`, `tx_hash`, `fee`, `user_server`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        fee = 0
                        if COIN_NAME not in FEE_PER_BYTE_COIN:
                            fee = wallet.get_tx_fee(COIN_NAME)
                        else:
                            fee = tx_hash['fee']
                        cur.execute(sql, (COIN_NAME, user_from, user_from_wallet['user_wallet_address'], amount, wallet.get_decimal(COIN_NAME), timestamp, tx_hash['transactionHash'], fee, user_server))
                        conn.commit()
                    if coin_family == "XMR":
                        sql = """ INSERT INTO xmroff_withdraw (`coin_name`, `user_id`, `to_address`, `amount`, 
                                  `fee`, `date`, `tx_hash`, `tx_key`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, user_from, user_from_wallet['user_wallet_address'], amount, tx_hash['fee'], timestamp, tx_hash['tx_hash'], tx_hash['tx_key'],))
                        conn.commit()
                    if updateBalance:
                        if coin_family == "TRTL" or coin_family == "CCX":
                            sql = """ UPDATE cn_walletapi SET `actual_balance`=%s, 
                                      `locked_balance`=%s, `lastUpdate`=%s, `decimal` = %s WHERE `balance_wallet_address`=%s 
                                      and `coin_name` = %s LIMIT 1 """
                            cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'], 
                                        updateTime, wallet.get_decimal(COIN_NAME), user_from_wallet['balance_wallet_address'], COIN_NAME, ))
                            conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        return tx_hash
    else:
        return None


async def sql_donate(user_from: str, address_to: str, amount: int, coin: str, user_server: str = 'DISCORD') -> str:
    global conn
    user_server = user_server.upper()
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME, user_server)
    if all(v is not None for v in [user_from_wallet['balance_wallet_address'], address_to]):
        tx_hash = None
        if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
            if COIN_NAME in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transaction(user_from_wallet['balance_wallet_address'], address_to, amount, COIN_NAME)
            else:
                tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'], address_to, amount, COIN_NAME)
        elif coin_family == "TRTL" and (COIN_NAME in ENABLE_COIN_OFFCHAIN):
            # Move balance
            try:
                openConnection()
                with conn.cursor() as cur: 
                    sql = """ INSERT INTO cnoff_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`, `user_server`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                    cur.execute(sql, (COIN_NAME, user_from, wallet.get_donate_address(COIN_NAME), amount, 
                                wallet.get_decimal(COIN_NAME), 'DONATE', int(time.time()), user_server))
                    conn.commit()
                return {'transactionHash': 'NONE', 'fee': 0}
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        if tx_hash:
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    updateBalance = None
                    if coin_family == "TRTL" and (COIN_NAME not in ENABLE_COIN_OFFCHAIN):
                        sql = """ INSERT INTO cn_donate (`coin_name`, `from_user`, `to_address`, `amount`, 
                                  `decimal`, `date`, `tx_hash`, `fee`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                        fee = 0
                        if COIN_NAME not in FEE_PER_BYTE_COIN:
                            fee = wallet.get_tx_fee(COIN_NAME)
                        else:
                            fee = tx_hash['fee']
                        cur.execute(sql, (COIN_NAME, user_from, address_to, amount, wallet.get_decimal(COIN_NAME), timestamp, tx_hash['transactionHash'], fee))
                        conn.commit()
                        if COIN_NAME in WALLET_API_COIN:
                            updateBalance = await walletapi.walletapi_get_balance_address(user_from_wallet['balance_wallet_address'], COIN_NAME)
                        else:
                            updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], COIN_NAME)
                    if updateBalance:
                        if coin_family == "TRTL" or coin_family == "CCX":
                            sql = """ UPDATE cn_walletapi SET `actual_balance`=%s, 
                                      `locked_balance`=%s, `lastUpdate`=%s, `decimal` = %s 
                                      WHERE `balance_wallet_address`=%s AND `coin_name` = %s LIMIT 1 """
                            cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'], 
                                        updateTime, wallet.get_decimal(COIN_NAME), user_from_wallet['balance_wallet_address'], COIN_NAME, ))
                            conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        return tx_hash
    else:
        return None


def sql_get_donate_list():
    global conn
    donate_list = {}
    try:
        openConnection()
        sql = None
        with conn.cursor() as cur:
            # TRTL fam
            for coin in ENABLE_COIN:
                sql = """ SELECT SUM(amount) AS donate FROM cn_donate WHERE `coin_name`= %s """
                cur.execute(sql, (coin.upper()))
                result = cur.fetchone()
                if result['donate'] is None:
                   donate_list.update({coin: 0})
                else:
                   donate_list.update({coin: float(result['donate'])})
            # DOGE fam
            for coin in ENABLE_COIN_DOGE:
                sql = """ SELECT SUM(amount) AS donate FROM doge_mv_tx WHERE `type`='DONATE' AND `to_userid`= %s AND `coin_name`= %s """
                cur.execute(sql, ((wallet.get_donate_address(coin), coin.upper())))
                result = cur.fetchone()
                if result['donate'] is None:
                   donate_list.update({coin: 0})
                else:
                   donate_list.update({coin: float(result['donate'])})
            # XTOR
            coin = "XTOR"
            sql = """ SELECT SUM(amount) AS donate FROM xmroff_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # LOKI
            coin = "LOKI"
            sql = """ SELECT SUM(amount) AS donate FROM xmroff_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # XMR
            coin = "XMR"
            sql = """ SELECT SUM(amount) AS donate FROM xmroff_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # ARQ
            coin = "ARQ"
            sql = """ SELECT SUM(amount) AS donate FROM xmroff_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # MSR
            coin = "MSR"
            sql = """ SELECT SUM(amount) AS donate FROM xmroff_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # XAM
            coin = "XAM"
            sql = """ SELECT SUM(amount) AS donate FROM xmroff_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # BLOG
            coin = "BLOG"
            sql = """ SELECT SUM(amount) AS donate FROM xmroff_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # UPX
            coin = "UPX"
            sql = """ SELECT SUM(amount) AS donate FROM xmroff_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # XWP
            coin = "XWP"
            sql = """ SELECT SUM(amount) AS donate FROM xmroff_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
        return donate_list
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def sql_send_to_voucher(user_id: str, user_name: str, message_creating: str, amount: int, reserved_fee: int, comment: str, secret_string: str, voucher_image_name: str, coin: str, user_server: str='DISCORD'):
    global conn, conn_voucher
    COIN_NAME = coin.upper()
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT INTO cn_voucher (`coin_name`, `user_id`, `user_name`, `message_creating`, `amount`, 
                      `decimal`, `reserved_fee`, `date_create`, `comment`, `secret_string`, `voucher_image_name`, `user_server`) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
            cur.execute(sql, (COIN_NAME, user_id, user_name, message_creating, amount, wallet.get_decimal(COIN_NAME), reserved_fee, 
                              int(time.time()), comment, secret_string, voucher_image_name, user_server))
            conn.commit()
        openConnection_Voucher()
        with conn_voucher.cursor() as cur:
            sql = """ INSERT INTO cn_voucher (`coin_name`, `user_id`, `user_name`, `message_creating`, `amount`, 
                      `decimal`, `reserved_fee`, `date_create`, `comment`, `secret_string`, `voucher_image_name`, `user_server`) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
            cur.execute(sql, (COIN_NAME, user_id, user_name, message_creating, amount, wallet.get_decimal(COIN_NAME), reserved_fee, 
                              int(time.time()), comment, secret_string, voucher_image_name, user_server))
            conn_voucher.commit()
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_voucher_get_user(user_id: str, user_server: str='DISCORD', last: int=10):
    global conn
    user_server = user_server.upper()
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT * FROM cn_voucher WHERE `user_id`=%s AND `user_server`=%s 
                      ORDER BY `date_create` DESC LIMIT """ + str(last)+ """ """
            cur.execute(sql, (user_id, user_server,))
            result = cur.fetchall()
            return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


def sql_faucet_add(claimed_user: str, claimed_server: str, coin_name: str, claimed_amount: float, decimal: int, tx_hash: str, user_server: str = 'DISCORD'):
    global conn
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    tx_hash = tx_hash if tx_hash else 'NULL'
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT INTO discord_faucet (`claimed_user`, `coin_name`, `claimed_amount`, 
                      `decimal`, `tx_hash`, `claimed_at`, `claimed_server`, `user_server`) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
            cur.execute(sql, (claimed_user, coin_name, claimed_amount, decimal, tx_hash['transactionHash'], 
                        int(time.time()), claimed_server, user_server))
            conn.commit()
            return True
    except Exception as e:
        print((claimed_user, coin_name, claimed_amount, decimal, tx_hash['transactionHash'], 
                        int(time.time()), claimed_server, user_server))
        traceback.print_exc(file=sys.stdout)


def sql_faucet_checkuser(userID: str, user_server: str = 'DISCORD'):
    global conn
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    list_roach = sql_roach_get_by_id(userID, user_server)
    try:
        openConnection()
        with conn.cursor() as cur:
            if list_roach:
                roach_sql = "(" + ",".join(list_roach) + ")"
                sql = """ SELECT * FROM discord_faucet WHERE claimed_user IN """+roach_sql+""" AND `user_server`=%s 
                          ORDER BY claimed_at DESC LIMIT 1"""
                cur.execute(sql, (user_server,))
            else:
                sql = """ SELECT * FROM discord_faucet WHERE `claimed_user` = %s AND `user_server`=%s 
                          ORDER BY claimed_at DESC LIMIT 1"""
                cur.execute(sql, (userID, (user_server,)))
            result = cur.fetchone()
            return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_faucet_count_user(userID: str, user_server: str = 'DISCORD'):
    global conn
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT COUNT(*) FROM discord_faucet WHERE claimed_user = %s AND `user_server`=%s """
            cur.execute(sql, (userID, user_server))
            result = cur.fetchone()
            return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_faucet_count_all():
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT COUNT(*) FROM discord_faucet """
            cur.execute(sql,)
            result = cur.fetchone()
            return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_count_tx_all():
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT COUNT(*) FROM cnoff_external_tx """
            cur.execute(sql,)
            result = cur.fetchone()
            cnoff_external_tx = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

            sql = """ SELECT COUNT(*) FROM cnoff_mv_tx """
            cur.execute(sql,)
            result = cur.fetchone()
            cnoff_mv_tx = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

            sql = """ SELECT COUNT(*) FROM cn_tip """
            cur.execute(sql,)
            result = cur.fetchone()
            cn_tip = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

            sql = """ SELECT COUNT(*) FROM cn_send """
            cur.execute(sql,)
            result = cur.fetchone()
            cn_send = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

            sql = """ SELECT COUNT(*) FROM cn_withdraw """
            cur.execute(sql,)
            result = cur.fetchone()
            cn_withdraw = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

            sql = """ SELECT COUNT(*) FROM doge_external_tx """
            cur.execute(sql,)
            result = cur.fetchone()
            doge_external_tx = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

            sql = """ SELECT COUNT(*) FROM doge_mv_tx """
            cur.execute(sql,)
            result = cur.fetchone()
            doge_mv_tx = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

            sql = """ SELECT COUNT(*) FROM xmroff_external_tx """
            cur.execute(sql,)
            result = cur.fetchone()
            xmroff_external_tx = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0

            sql = """ SELECT COUNT(*) FROM xmroff_mv_tx """
            cur.execute(sql,)
            result = cur.fetchone()
            xmroff_mv_tx = int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
            
            on_chain = cnoff_external_tx + cn_tip + cn_send + cn_withdraw + doge_external_tx + xmroff_external_tx
            off_chain = cnoff_mv_tx + doge_mv_tx + xmroff_mv_tx
            return {'on_chain': on_chain, 'off_chain': off_chain, 'total': on_chain+off_chain}
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

def sql_tag_by_server(server_id: str, tag_id: str = None):
    global conn, redis_pool, redis_conn, redis_expired
    try:
        openConnection()
        with conn.cursor() as cur:
            if tag_id is None: 
                sql = """ SELECT * FROM discord_tag WHERE tag_serverid = %s """
                cur.execute(sql, (server_id,))
                result = cur.fetchall()
                tag_list = result
                return tag_list
            else:
                # Check if exist in redis
                try:
                    openRedis()
                    if redis_conn and redis_conn.exists(f'TIPBOT:TAG_{str(server_id)}_{tag_id}'):
                        sql = """ UPDATE discord_tag SET num_trigger=num_trigger+1 WHERE tag_serverid = %s AND tag_id=%s """
                        cur.execute(sql, (server_id, tag_id,))
                        conn.commit()
                        return json.loads(redis_conn.get(f'TIPBOT:TAG_{str(server_id)}_{tag_id}'))
                    else:
                        sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, 
                                  `added_byuid`, `num_trigger` FROM discord_tag WHERE tag_serverid = %s AND tag_id=%s """
                        cur.execute(sql, (server_id, tag_id,))
                        result = cur.fetchone()
                        if result:
                            redis_conn.set(f'TIPBOT:TAG_{str(server_id)}_{tag_id}', json.dumps(result), ex=redis_expired)
                            return json.loads(redis_conn.get(f'TIPBOT:TAG_{str(server_id)}_{tag_id}'))
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)

    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_tag_by_server_add(server_id: str, tag_id: str, tag_desc: str, added_byname: str, added_byuid: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT COUNT(*) FROM discord_tag WHERE tag_serverid=%s """
            cur.execute(sql, (server_id,))
            counting = cur.fetchone()
            if counting:
                if counting['COUNT(*)'] > 50:
                    return None
            sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, `added_byuid`, 
                      `num_trigger` 
                      FROM discord_tag WHERE tag_serverid = %s AND tag_id=%s """
            cur.execute(sql, (server_id, tag_id.upper(),))
            result = cur.fetchone()
            if result is None:
                sql = """ INSERT INTO discord_tag (`tag_id`, `tag_desc`, `date_added`, `tag_serverid`, 
                          `added_byname`, `added_byuid`) 
                          VALUES (%s, %s, %s, %s, %s, %s) """
                cur.execute(sql, (tag_id.upper(), tag_desc, int(time.time()), server_id, added_byname, added_byuid,))
                conn.commit()
                return tag_id.upper()
            else:
                return None
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_tag_by_server_del(server_id: str, tag_id: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, 
                      `added_byuid`, `num_trigger` 
                      FROM discord_tag WHERE tag_serverid = %s AND tag_id=%s """
            cur.execute(sql, (server_id, tag_id.upper(),))
            result = cur.fetchone()
            if result is None:
                return None
            else:
                sql = """ DELETE FROM discord_tag WHERE `tag_id`=%s AND `tag_serverid`=%s """
                cur.execute(sql, (tag_id.upper(), server_id,))
                conn.commit()
                # Check if exist in redis
                try:
                    openRedis()
                    if redis_conn and redis_conn.exists(f'TIPBOT:TAG_{str(server_id)}_{tag_id}'):
                        redis_conn.delete(f'TIPBOT:TAG_{str(server_id)}_{tag_id}')
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                return tag_id.upper()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_itag_by_server(server_id: str, tag_id: str = None):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            if tag_id is None: 
                sql = """ SELECT * FROM discord_itag WHERE itag_serverid = %s """
                cur.execute(sql, (server_id,))
                result = cur.fetchall()
                tag_list = result
                return tag_list
            else:
                sql = """ SELECT * FROM discord_itag WHERE itag_serverid = %s AND itag_id=%s """
                cur.execute(sql, (server_id, tag_id,))
                result = cur.fetchone()
                if result:
                    tag = result
                    sql = """ UPDATE discord_itag SET num_trigger=num_trigger+1 WHERE itag_serverid = %s AND itag_id=%s """
                    cur.execute(sql, (server_id, tag_id,))
                    conn.commit()
                    return tag
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_itag_by_server_add(server_id: str, tag_id: str, added_byname: str, added_byuid: str, orig_name: str, stored_name: str, fsize: int):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT COUNT(*) FROM discord_itag WHERE itag_serverid=%s """
            cur.execute(sql, (server_id,))
            counting = cur.fetchone()
            if counting:
                if counting['COUNT(*)'] > config.itag.max_per_server:
                    return None
            sql = """ SELECT * FROM discord_itag WHERE itag_serverid = %s AND itag_id=%s """
            cur.execute(sql, (server_id, tag_id.upper(),))
            result = cur.fetchone()
            if result is None:
                sql = """ INSERT INTO discord_itag (`itag_id`, `date_added`, `itag_serverid`, 
                          `added_byname`, `added_byuid`, `original_name`, `stored_name`, `size`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                cur.execute(sql, (tag_id.upper(), int(time.time()), server_id, added_byname, added_byuid, orig_name, stored_name, fsize))
                conn.commit()
                return tag_id.upper()
            else:
                return None
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_itag_by_server_del(server_id: str, tag_id: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT * FROM discord_itag WHERE itag_serverid = %s AND itag_id=%s """
            cur.execute(sql, (server_id, tag_id.upper(),))
            result = cur.fetchone()
            if result is None:
                return None
            else:
                if os.path.exists(config.itag.path + result['stored_name']):
                    os.remove(config.itag.path + result['stored_name'])
                sql = """ DELETE FROM discord_itag WHERE `itag_id`=%s AND `itag_serverid`=%s """
                cur.execute(sql, (tag_id.upper(), server_id,))
                conn.commit()
                return tag_id.upper()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_get_allguild():
    global conn
    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ SELECT * FROM discord_server """
            cur.execute(sql,)
            result = cur.fetchall()
            return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_info_by_server(server_id: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ SELECT * FROM discord_server WHERE serverid = %s LIMIT 1 """
            cur.execute(sql, (server_id,))
            result = cur.fetchone()
            return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_addinfo_by_server(server_id: str, servername: str, prefix: str, default_coin: str, rejoin: bool = True):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            if rejoin:
                sql = """ INSERT INTO `discord_server` (`serverid`, `servername`, `prefix`, `default_coin`)
                          VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE 
                          `servername` = %s, `prefix` = %s, `default_coin` = %s, `status` = %s """
                cur.execute(sql, (server_id, servername[:28], prefix, default_coin, servername[:28], prefix, default_coin, "REJOINED", ))
                conn.commit()
            else:
                sql = """ INSERT INTO `discord_server` (`serverid`, `servername`, `prefix`, `default_coin`)
                          VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE 
                          `servername` = %s, `prefix` = %s, `default_coin` = %s"""
                cur.execute(sql, (server_id, servername[:28], prefix, default_coin, servername[:28], prefix, default_coin,))
                conn.commit()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_add_messages(list_messages):
    if len(list_messages) == 0:
        return 0
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT IGNORE INTO `discord_messages` (`serverid`, `server_name`, `channel_id`, `channel_name`, `user_id`, 
                      `message_author`, `message_id`, `message_content`, `message_time`)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
            cur.executemany(sql, list_messages)
            conn.commit()
            return cur.rowcount
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_get_messages(server_id: str, channel_id: str, time_int: int, num_user: int=None):
    global conn
    lapDuration = int(time.time()) - time_int
    try:
        openConnection()
        with conn.cursor() as cur:
            list_talker = []
            if num_user is None:
                sql = """ SELECT DISTINCT `user_id` FROM discord_messages 
                          WHERE `serverid` = %s AND `channel_id` = %s AND `message_time`>%s """
                cur.execute(sql, (server_id, channel_id, lapDuration,))
                result = cur.fetchall()
                if result:
                    for item in result:
                        if int(item['user_id']) not in list_talker:
                            list_talker.append(int(item['user_id']))
            else:
                sql = """ SELECT `user_id` FROM discord_messages WHERE `serverid` = %s AND `channel_id` = %s 
                          GROUP BY `user_id` ORDER BY max(`message_time`) DESC LIMIT %s """
                cur.execute(sql, (server_id, channel_id, num_user,))
                result = cur.fetchall()
                if result:
                    for item in result:
                        if int(item['user_id']) not in list_talker:
                            list_talker.append(int(item['user_id']))
            return list_talker
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


def sql_changeinfo_by_server(server_id: str, what: str, value: str):
    global conn
    if what.lower() in ["servername", "prefix", "default_coin", "tiponly", "numb_user", "numb_bot", "numb_channel", "react_tip", "react_tip_100", "lastUpdate", "botchan"]:
        try:
            #print(f"ok try to change {what} to {value}")
            openConnection()
            with conn.cursor() as cur:
                print((value, server_id))
                sql = """ UPDATE discord_server SET `""" + what.lower() + """` = %s WHERE `serverid` = %s """
                cur.execute(sql, (value, server_id,))
                conn.commit()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


def sql_updatestat_by_server(server_id: str, numb_user: int, numb_bot: int, numb_channel: int, numb_online: int):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ UPDATE discord_server SET `numb_user` = %s, 
                      `numb_bot`= %s, `numb_channel` = %s, `numb_online` = %s, 
                     `lastUpdate` = %s WHERE `serverid` = %s """
            cur.execute(sql, (numb_user, numb_bot, numb_channel, numb_online, int(time.time()), server_id,))
            conn.commit()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_discord_userinfo_get(user_id: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            # select first
            sql = """ SELECT * FROM discord_userinfo 
                      WHERE `user_id` = %s """
            cur.execute(sql, (user_id,))
            result = cur.fetchone()
            return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


def sql_userinfo_locked(user_id: str, locked: str, locked_reason: str, locked_by: str):
    global conn
    if locked.upper() not in ["YES", "NO"]:
        return
    try:
        openConnection()
        with conn.cursor() as cur:
            # select first
            sql = """ SELECT `user_id` FROM discord_userinfo 
                      WHERE `user_id` = %s """
            cur.execute(sql, (user_id,))
            result = cur.fetchone()
            if result is None:
                sql = """ INSERT INTO `discord_userinfo` (`user_id`, `locked`, `locked_reason`, `locked_by`, `locked_date`)
                      VALUES (%s, %s, %s, %s, %s) """
                cur.execute(sql, (user_id, locked.upper(), locked_reason, locked_by, int(time.time())))
                conn.commit()
            else:
                sql = """ UPDATE `discord_userinfo` SET `locked`= %s, `locked_reason` = %s, `locked_by` = %s, `locked_date` = %s
                      WHERE `user_id` = %s """
                cur.execute(sql, (locked.upper(), locked_reason, locked_by, int(time.time()), user_id))
                conn.commit()
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_roach_add(main_id: str, roach_id: str, roach_name: str, main_name: str):
    try:
        openConnection()
        with conn.cursor() as cur:
            # select first
            sql = """ SELECT `roach_id`, `main_id`, `date` FROM discord_faucetroach 
                      WHERE `roach_id` = %s AND `main_id` = %s """
            cur.execute(sql, (roach_id, main_id,))
            result = cur.fetchone()
            if result is None:
                sql = """ INSERT INTO `discord_faucetroach` (`roach_id`, `main_id`, `roach_name`, `main_name`, `date`)
                      VALUES (%s, %s, %s, %s, %s) """
                cur.execute(sql, (roach_id, main_id, roach_name, main_name, int(time.time())))
                conn.commit()
                return True
            else:
                return None
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_roach_get_by_id(roach_id: str, user_server: str = 'DISCORD'):
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    try:
        openConnection()
        with conn.cursor() as cur:
            # select first
            sql = """ SELECT `roach_id`, `main_id`, `date` FROM discord_faucetroach 
                      WHERE (`roach_id` = %s OR `main_id` = %s) AND `user_server`=%s """
            cur.execute(sql, (roach_id, roach_id, user_server))
            result = cur.fetchall()
            if result is None:
                return None
            else:
                roaches = []
                for each in result:
                    roaches.append(each['roach_id'])
                    roaches.append(each['main_id'])
                return set(roaches)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_userinfo_2fa_insert(user_id: str, twofa_secret: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            # select first
            sql = """ SELECT `user_id` FROM discord_userinfo 
                      WHERE `user_id` = %s """
            cur.execute(sql, (user_id,))
            result = cur.fetchone()
            if result is None:
                sql = """ INSERT INTO `discord_userinfo` (`user_id`, `twofa_secret`, `twofa_activate_ts`)
                      VALUES (%s, %s, %s) """
                cur.execute(sql, (user_id, encrypt_string(twofa_secret), int(time.time())))
                conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_userinfo_2fa_update(user_id: str, twofa_secret: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            # select first
            sql = """ SELECT `user_id` FROM discord_userinfo 
                      WHERE `user_id` = %s """
            cur.execute(sql, (user_id,))
            result = cur.fetchone()
            if result:
                sql = """ UPDATE `discord_userinfo` SET `twofa_secret` = %s, `twofa_activate_ts` = %s 
                      WHERE `user_id`=%s """
                cur.execute(sql, (encrypt_string(twofa_secret), int(time.time()), user_id))
                conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_userinfo_2fa_verify(user_id: str, verify: str):
    if verify.upper() not in ["YES", "NO"]:
        return
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            # select first
            sql = """ SELECT `user_id` FROM discord_userinfo 
                      WHERE `user_id` = %s """
            cur.execute(sql, (user_id,))
            result = cur.fetchone()
            if result:
                sql = """ UPDATE `discord_userinfo` SET `twofa_verified` = %s, `twofa_verified_ts` = %s 
                      WHERE `user_id`=%s """
                if verify.upper() == "NO":
                    # if unverify, need to clear secret code as well, and disactivate other related 2FA.
                    sql = """ UPDATE `discord_userinfo` SET `twofa_verified` = %s, `twofa_verified_ts` = %s, `twofa_secret` = %s, `twofa_activate_ts` = %s, 
                          `twofa_onoff` = %s, `twofa_active` = %s
                          WHERE `user_id`=%s """
                    cur.execute(sql, (verify.upper(), int(time.time()), '', int(time.time()), 'OFF', 'NO', user_id))
                    conn.commit()
                else:
                    cur.execute(sql, (verify.upper(), int(time.time()), user_id))
                    conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_change_userinfo_single(user_id: str, what: str, value: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            # select first
            sql = """ SELECT `user_id` FROM discord_userinfo 
                      WHERE `user_id` = %s """
            cur.execute(sql, (user_id,))
            result = cur.fetchone()
            if result:
                sql = """ UPDATE discord_userinfo SET `""" + what.lower() + """` = %s WHERE `user_id` = %s """
                cur.execute(sql, (value, user_id))
                conn.commit()
            else:
                sql = """ INSERT INTO `discord_userinfo` (`user_id`, `""" + what.lower() + """`)
                      VALUES (%s, %s) """
                cur.execute(sql, (user_id, value))
                conn.commit()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_addignorechan_by_server(server_id: str, ignorechan: str, by_userid: str, by_name: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT IGNORE INTO `discord_ignorechan` (`serverid`, `ignorechan`, `set_by_userid`, `by_author`, `set_when`)
                      VALUES (%s, %s, %s, %s, %s) """
            cur.execute(sql, (server_id, ignorechan, by_userid, by_name, int(time.time())))
            conn.commit()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_delignorechan_by_server(server_id: str, ignorechan: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ DELETE FROM `discord_ignorechan` WHERE `serverid` = %s AND `ignorechan` = %s """
            cur.execute(sql, (server_id, ignorechan,))
            conn.commit()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_listignorechan():
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT `serverid`, `ignorechan`, `set_by_userid`, `by_author`, `set_when` FROM discord_ignorechan """
            cur.execute(sql)
            result = cur.fetchall()
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
        traceback.print_exc(file=sys.stdout)
    return None


def sql_add_logs_tx(list_tx):
    if len(list_tx) == 0:
        return 0
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT IGNORE INTO `action_tx_logs` (`uuid`, `action`, `user_id`, `user_name`, 
                      `event_date`, `msg_content`, `user_server`, `end_point`)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
            cur.executemany(sql, list_tx)
            conn.commit()
            return cur.rowcount
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_add_failed_tx(coin: str, user_id: str, user_author: str, amount: int, tx_type: str):
    global conn
    if tx_type.upper() not in ['TIP','TIPS','TIPALL','DONATE','WITHDRAW','SEND', 'REACTTIP']:
        return None
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT IGNORE INTO `discord_txfail` (`coin_name`, `user_id`, `tx_author`, `amount`, `tx_type`, `fail_time`)
                      VALUES (%s, %s, %s, %s, %s, %s) """
            cur.execute(sql, (coin.upper(), user_id, user_author, amount, tx_type.upper(), int(time.time())))
            conn.commit()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_get_tipnotify():
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT `user_id`, `date` FROM bot_tipnotify_user """
            cur.execute(sql,)
            result = cur.fetchall()
            ignorelist = []
            for row in result:
                ignorelist.append(row['user_id'])
            return ignorelist
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_toggle_tipnotify(user_id: str, onoff: str):
    # Bot will add user_id if it failed to DM
    global conn
    onoff = onoff.upper()
    if onoff == "OFF":
        try:
            openConnection()
            with conn.cursor() as cur:
                sql = """ SELECT * FROM `bot_tipnotify_user` WHERE `user_id` = %s LIMIT 1 """
                cur.execute(sql, (user_id))
                result = cur.fetchone()
                if result is None:
                    sql = """ INSERT INTO `bot_tipnotify_user` (`user_id`, `date`)
                              VALUES (%s, %s) """    
                    cur.execute(sql, (user_id, int(time.time())))
                    conn.commit()
        except pymysql.err.Warning as e:
            traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    elif onoff == "ON":
        try:
            openConnection()
            with conn.cursor() as cur:
                sql = """ DELETE FROM `bot_tipnotify_user` WHERE `user_id` = %s """
                cur.execute(sql, str(user_id))
                conn.commit()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


def sql_updateinfo_by_server(server_id: str, what: str, value: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ SELECT serverid, servername, prefix, default_coin, numb_user, numb_bot, tiponly 
                      FROM discord_server WHERE serverid = %s """
            cur.execute(sql, (server_id,))
            result = cur.fetchone()
            if result is None:
                return None
            else:
                if what in ["servername", "prefix", "default_coin", "tiponly", "status"]:
                    sql = """ UPDATE discord_server SET """+what+"""=%s WHERE serverid=%s """
                    cur.execute(sql, (what, value, server_id,))
                    conn.commit()
                else:
                    return None
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


# DOGE
async def sql_mv_doge_single(user_from: str, to_user: str, amount: float, coin: str, tiptype: str, user_server: str = 'DISCORD'):
    global conn
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN_DOGE:
        return False
    if tiptype.upper() not in ["TIP", "DONATE", "SECRETTIP", "FAUCET"]:
        return False
    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ INSERT INTO doge_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `type`, `date`, `user_server`) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
            cur.execute(sql, (COIN_NAME, user_from, to_user, amount, tiptype.upper(), int(time.time()), user_server))
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_mv_doge_multiple(user_from: str, user_tos, amount_each: float, coin: str, tiptype: str):
    # user_tos is array "account1", "account2", ....
    global conn
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN_DOGE:
        return False
    if tiptype.upper() not in ["TIPS", "TIPALL"]:
        return False
    values_str = []
    currentTs = int(time.time())
    for item in user_tos:
        values_str.append(f"('{COIN_NAME}', '{user_from}', '{item}', {amount_each}, '{tiptype.upper()}', {currentTs})\n")
    values_sql = "VALUES " + ",".join(values_str)
    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ INSERT INTO doge_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `type`, `date`) 
                      """+values_sql+""" """
            cur.execute(sql,)
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_external_doge_single(user_from: str, amount: float, fee: float, to_address: str, coin: str, tiptype: str, user_server: str = 'DISCORD'):
    global conn
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN_DOGE:
        return False
    if tiptype.upper() not in ["SEND", "WITHDRAW"]:
        return False
    try:
        openConnection()
        print("DOGE EXTERNAL: ")
        print((to_address, amount, user_from, COIN_NAME))
        txHash = await wallet.doge_sendtoaddress(to_address, amount, user_from, COIN_NAME)
        print("COMPLETE DOGE EXTERNAL TX")
        with conn.cursor() as cur: 
            sql = """ INSERT INTO doge_external_tx (`coin_name`, `user_id`, `amount`, `fee`, `to_address`, 
                      `type`, `date`, `tx_hash`, `user_server`) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
            cur.execute(sql, (COIN_NAME, user_from, amount, fee, to_address, tiptype.upper(), int(time.time()), txHash, user_server))
            conn.commit()
        return txHash
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_doge_balance(userID: str, coin: str, user_server: str = 'DISCORD'):
    global conn
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN_DOGE:
        return False
    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ SELECT SUM(amount) AS Expense FROM doge_mv_tx WHERE `from_userid`=%s AND `coin_name`=%s AND `user_server`=%s """
            cur.execute(sql, (userID, COIN_NAME, user_server))
            result = cur.fetchone()
            if result:
                Expense = result['Expense']
            else:
                Expense = 0

            sql = """ SELECT SUM(amount) AS Income FROM doge_mv_tx WHERE `to_userid`=%s AND `coin_name`=%s AND `user_server`=%s """
            cur.execute(sql, (userID, COIN_NAME, user_server))
            result = cur.fetchone()
            if result:
                Income = result['Income']
            else:
                Income = 0

            sql = """ SELECT SUM(amount) AS TxExpense FROM doge_external_tx WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s """
            cur.execute(sql, (userID, COIN_NAME, user_server))
            result = cur.fetchone()
            if result:
                TxExpense = result['TxExpense']
            else:
                TxExpense = 0

            sql = """ SELECT SUM(fee) AS FeeExpense FROM doge_external_tx WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s """
            cur.execute(sql, (userID, COIN_NAME, user_server))
            result = cur.fetchone()
            if result:
                FeeExpense = result['FeeExpense']
            else:
                FeeExpense = 0

            sql = """ SELECT SUM(amount) AS SwapIn FROM discord_swap_balance WHERE `owner_id`=%s AND `coin_name` = %s AND `to` = %s AND `user_server`=%s """
            cur.execute(sql, (userID, COIN_NAME, 'TIPBOT', user_server))
            result = cur.fetchone()
            if result:
                SwapIn = result['SwapIn']
            else:
                SwapIn = 0

            sql = """ SELECT SUM(amount) AS SwapOut FROM discord_swap_balance WHERE `owner_id`=%s AND `coin_name` = %s AND `from` = %s AND `user_server`=%s """
            cur.execute(sql, (userID, COIN_NAME, 'TIPBOT', user_server))
            result = cur.fetchone()
            if result:
                SwapOut = result['SwapOut']
            else:
                SwapOut = 0

            # Credit by admin is positive (Positive)
            sql = """ SELECT SUM(amount) AS Credited FROM credit_balance WHERE `coin_name`=%s AND `to_userid`=%s 
                  AND `user_server`=%s """
            cur.execute(sql, (COIN_NAME, userID, user_server))
            result = cur.fetchone()
            if result:
                Credited = result['Credited']
            else:
                Credited = 0

            # Voucher create (Negative)
            sql = """ SELECT SUM(amount+reserved_fee) AS Expended_Voucher FROM cn_voucher 
                      WHERE `coin_name`=%s AND `user_id`=%s AND `user_server`=%s """
            cur.execute(sql, (COIN_NAME, userID, user_server))
            result = cur.fetchone()
            if result:
                Expended_Voucher = result['Expended_Voucher']
            else:
                Expended_Voucher = 0

            balance = {}
            balance['Expense'] = Expense or 0
            balance['Expense'] = round(balance['Expense'], 4)
            balance['Income'] = Income or 0
            balance['TxExpense'] = TxExpense or 0
            balance['FeeExpense'] = FeeExpense or 0
            balance['SwapIn'] = SwapIn or 0
            balance['SwapOut'] = SwapOut or 0
            balance['Credited'] = Credited if Credited else 0
            balance['Expended_Voucher'] = Expended_Voucher if Expended_Voucher else 0
            balance['Adjust'] = float(balance['Credited']) + float(balance['Income']) + float(balance['SwapIn']) - float(balance['Expense']) \
            - float(balance['TxExpense']) - float(balance['FeeExpense']) - float(balance['SwapOut']) - float(balance['Expended_Voucher'])
            return balance
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


# XMR Based
def sql_mv_xmr_single(user_from: str, to_user: str, amount: float, coin: str, tiptype: str):
    global conn
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family != "XMR":
        return False
    if tiptype.upper() not in ["TIP", "DONATE", "SECRETTIP", "FAUCET"]:
        return False
    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ INSERT INTO xmroff_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
            cur.execute(sql, (COIN_NAME, user_from, to_user, amount, wallet.get_decimal(COIN_NAME), tiptype.upper(), int(time.time()),))
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


def sql_mv_xmr_multiple(user_from: str, user_tos, amount_each: float, coin: str, tiptype: str):
    # user_tos is array "account1", "account2", ....
    global conn
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family != "XMR":
        return False
    if tiptype.upper() not in ["TIPS", "TIPALL"]:
        return False
    values_str = []
    currentTs = int(time.time())
    for item in user_tos:
        values_str.append(f"('{COIN_NAME}', '{user_from}', '{item}', {amount_each}, {wallet.get_decimal(COIN_NAME)}, '{tiptype.upper()}', {currentTs})\n")
    values_sql = "VALUES " + ",".join(values_str)
    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ INSERT INTO xmroff_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`) 
                      """+values_sql+""" """
            cur.execute(sql,)
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_external_xmr_single(user_from: str, amount: float, to_address: str, coin: str, tiptype: str):
    global conn
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family != "XMR":
        return False
    if tiptype.upper() not in ["SEND", "WITHDRAW"]:
        return False
    try:
        openConnection()
        tx_hash = None
        if coin_family == "XMR":
            tx_hash = await wallet.send_transaction('TIPBOT', to_address, 
                                                    amount, COIN_NAME, 0)
            if tx_hash:
                updateTime = int(time.time())
                with conn.cursor() as cur: 
                    sql = """ INSERT INTO xmroff_external_tx (`coin_name`, `user_id`, `amount`, `fee`, `decimal`, `to_address`, 
                              `type`, `date`, `tx_hash`, `tx_key`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    cur.execute(sql, (COIN_NAME, user_from, amount, tx_hash['fee'], wallet.get_decimal(COIN_NAME), to_address, tiptype.upper(), int(time.time()), tx_hash['tx_hash'], tx_hash['tx_key'],))
                    conn.commit()
        return tx_hash
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_cnoff_balance(userID: str, coin: str, user_server: str = 'DISCORD'):
    global conn, redis_conn, redis_expired
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family != "TRTL":
        return False

    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ SELECT SUM(amount) AS Expense FROM cnoff_mv_tx WHERE `from_userid`=%s AND `coin_name` = %s AND `user_server` = %s """
            cur.execute(sql, (userID, COIN_NAME, user_server))
            result = cur.fetchone()
            if result:
                Expense = result['Expense']
            else:
                Expense = 0

            sql = """ SELECT SUM(amount) AS Income FROM cnoff_mv_tx WHERE `to_userid`=%s AND `coin_name` = %s AND `user_server` = %s """
            cur.execute(sql, (userID, COIN_NAME, user_server))
            result = cur.fetchone()
            if result:
                Income = result['Income']
            else:
                Income = 0

            sql = """ SELECT SUM(amount) AS TxExpense FROM cnoff_external_tx WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s """
            cur.execute(sql, (userID, COIN_NAME, user_server))
            result = cur.fetchone()
            if result:
                TxExpense = result['TxExpense']
            else:
                TxExpense = 0

            sql = """ SELECT SUM(fee) AS FeeExpense FROM cnoff_external_tx WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s """
            cur.execute(sql, (userID, COIN_NAME, user_server))
            result = cur.fetchone()
            if result:
                FeeExpense = result['FeeExpense']
            else:
                FeeExpense = 0

            sql = """ SELECT SUM(amount) AS SwapIn FROM discord_swap_balance WHERE `owner_id`=%s AND `coin_name` = %s and `to` = %s """
            cur.execute(sql, (userID, COIN_NAME, 'TIPBOT'))
            result = cur.fetchone()
            if result:
                SwapIn = result['SwapIn']
            else:
                SwapIn = 0

            sql = """ SELECT SUM(amount) AS SwapOut FROM discord_swap_balance WHERE `owner_id`=%s AND `coin_name` = %s and `from` = %s """
            cur.execute(sql, (userID, COIN_NAME, 'TIPBOT'))
            result = cur.fetchone()
            if result:
                SwapOut = result['SwapOut']
            else:
                SwapOut = 0

            # Credit by admin is positive (Positive)
            sql = """ SELECT SUM(amount) AS Credited FROM credit_balance WHERE `coin_name`=%s AND `to_userid`=%s 
                  AND `user_server`=%s """
            cur.execute(sql, (COIN_NAME, userID, user_server))
            result = cur.fetchone()
            if result:
                Credited = result['Credited']
            else:
                Credited = 0

            # Voucher create (Negative)
            sql = """ SELECT SUM(amount+reserved_fee) AS Expended_Voucher FROM cn_voucher 
                      WHERE `coin_name`=%s AND `user_id`=%s AND `user_server`=%s """
            cur.execute(sql, (COIN_NAME, userID, user_server))
            result = cur.fetchone()
            if result:
                Expended_Voucher = result['Expended_Voucher']
            else:
                Expended_Voucher = 0

            balance = {}
            balance['Expense'] = float(Expense) if Expense else 0
            balance['Expense'] = float(round(balance['Expense'], 4))
            balance['Income'] = float(Income) if Income else 0
            balance['TxExpense'] = float(TxExpense) if TxExpense else 0
            balance['FeeExpense'] = float(FeeExpense) if FeeExpense else 0
            balance['SwapIn'] = float(SwapIn) if SwapIn else 0
            balance['SwapOut'] = float(SwapOut) if SwapOut else 0
            balance['Credited'] = float(Credited) if Credited else 0
            balance['Expended_Voucher'] = float(Expended_Voucher) if Expended_Voucher else 0
            balance['Adjust'] = balance['Credited'] + balance['Income'] + balance['SwapIn'] - balance['Expense'] \
            - balance['TxExpense'] - balance['FeeExpense'] - balance['SwapOut'] - balance['Expended_Voucher']

            return balance
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def sql_xmr_balance(userID: str, coin: str, redis_reset: bool = True):
    global conn, redis_conn, redis_expired
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family != "XMR":
        return False
    # Check if exist in redis
    try:
        openRedis()
        if redis_conn and redis_conn.exists(f'TIPBOT:BALANCE_{str(userID)}_{COIN_NAME}'):
            if redis_reset == False:
                return json.loads(redis_conn.get(f'TIPBOT:BALANCE_{str(userID)}_{COIN_NAME}').decode())
            else:
                redis_conn.delete(f'TIPBOT:BALANCE_{str(userID)}_{COIN_NAME}')
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ SELECT SUM(amount) AS Expense FROM xmroff_mv_tx WHERE `from_userid`=%s AND `coin_name` = %s """
            cur.execute(sql, (userID, COIN_NAME))
            result = cur.fetchone()
            if result:
                Expense = result['Expense']
            else:
                Expense = 0

            sql = """ SELECT SUM(amount) AS Income FROM xmroff_mv_tx WHERE `to_userid`=%s AND `coin_name` = %s """
            cur.execute(sql, (userID, COIN_NAME))
            result = cur.fetchone()
            if result:
                Income = result['Income']
            else:
                Income = 0

            sql = """ SELECT SUM(amount) AS TxExpense FROM xmroff_external_tx WHERE `user_id`=%s AND `coin_name` = %s """
            cur.execute(sql, (userID, COIN_NAME))
            result = cur.fetchone()
            if result:
                TxExpense = result['TxExpense']
            else:
                TxExpense = 0

            sql = """ SELECT SUM(fee) AS FeeExpense FROM xmroff_external_tx WHERE `user_id`=%s AND `coin_name` = %s """
            cur.execute(sql, (userID, COIN_NAME))
            result = cur.fetchone()
            if result:
                FeeExpense = result['FeeExpense']
            else:
                FeeExpense = 0

            sql = """ SELECT SUM(amount) AS SwapIn FROM discord_swap_balance WHERE `owner_id`=%s AND `coin_name` = %s and `to` = %s """
            cur.execute(sql, (userID, COIN_NAME, 'TIPBOT'))
            result = cur.fetchone()
            if result:
                SwapIn = result['SwapIn']
            else:
                SwapIn = 0

            sql = """ SELECT SUM(amount) AS SwapOut FROM discord_swap_balance WHERE `owner_id`=%s AND `coin_name` = %s and `from` = %s """
            cur.execute(sql, (userID, COIN_NAME, 'TIPBOT'))
            result = cur.fetchone()
            if result:
                SwapOut = result['SwapOut']
            else:
                SwapOut = 0

            # Credit by admin is positive (Positive)
            sql = """ SELECT SUM(amount) AS Credited FROM credit_balance WHERE `coin_name`=%s AND `to_userid`=%s  
                  """
            cur.execute(sql, (COIN_NAME, userID))
            result = cur.fetchone()
            if result:
                Credited = result['Credited']
            else:
                Credited = 0

            # Voucher create (Negative)
            sql = """ SELECT SUM(amount+reserved_fee) AS Expended_Voucher FROM cn_voucher 
                      WHERE `coin_name`=%s AND `user_id`=%s """
            cur.execute(sql, (COIN_NAME, userID))
            result = cur.fetchone()
            if result:
                Expended_Voucher = result['Expended_Voucher']
            else:
                Expended_Voucher = 0

            balance = {}
            balance['Expense'] = float(Expense) if Expense else 0
            balance['Expense'] = float(round(balance['Expense'], 4))
            balance['Income'] = float(Income) if Income else 0
            balance['TxExpense'] = float(TxExpense) if TxExpense else 0
            balance['FeeExpense'] = float(FeeExpense) if FeeExpense else 0
            balance['Credited'] = float(Credited) if Credited else 0
            balance['SwapIn'] = float(SwapIn) if SwapIn else 0
            balance['SwapOut'] = float(SwapOut) if SwapOut else 0
            balance['Expended_Voucher'] = float(Expended_Voucher) if Expended_Voucher else 0
            balance['Adjust'] = balance['Credited'] + balance['Income'] + balance['SwapIn'] - balance['Expense'] - balance['TxExpense'] \
            - balance['FeeExpense'] - balance['SwapOut'] - balance['Expended_Voucher']
            # add to redis
            try:
                if redis_conn:
                    redis_conn.set(f'TIPBOT:BALANCE_{str(userID)}_{COIN_NAME}', json.dumps(balance), ex=redis_expired)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return balance
    except Exception as e:
        traceback.print_exc(file=sys.stdout)



async def sql_get_userwallet_by_paymentid(paymentid: str, coin: str, user_server: str = 'DISCORD'):
    global conn
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    try:
        openConnection()
        with conn.cursor() as cur:
            result = None
            if coin_family == "TRTL":
                sql = """ SELECT * FROM cnoff_user_paymentid WHERE `paymentid`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                cur.execute(sql, (paymentid, COIN_NAME, user_server))
                result = cur.fetchone()
            # TODO: XMR family to be in one table
            elif coin_family == "DOGE":
                # if doge family, address is paymentid
                sql = """ SELECT * FROM doge_user WHERE `balance_wallet_address`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                cur.execute(sql, (paymentid, COIN_NAME, user_server))
                result = cur.fetchone()
            return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_get_new_tx_table(notified: str = 'NO', failed_notify: str = 'NO'):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT * FROM discord_notify_new_tx WHERE `notified`=%s AND `failed_notify`=%s """
            cur.execute(sql, (notified, failed_notify,))
            result = cur.fetchall()
            return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def sql_update_notify_tx_table(payment_id: str, owner_id: str, owner_name: str, notified: str = 'YES', failed_notify: str = 'NO'):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ UPDATE discord_notify_new_tx SET `owner_id`=%s, `owner_name`=%s, `notified`=%s, `failed_notify`=%s, 
                      `notified_time`=%s WHERE `payment_id`=%s """
            cur.execute(sql, (owner_id, owner_name, notified, failed_notify, float("%.3f" % time.time()), payment_id,))
            conn.commit()
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_get_deposit_alluser(user: str = 'ALL', coin: str = 'ANY'):
    global conn
    COIN_NAME = coin.upper()
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT * FROM cn_get_transfers """
            has_userall = True
            if user != 'ALL':
                sql += """ WHERE `user_id`='"""+user+"""' """
                has_userall = False
            if COIN_NAME != 'ANY':
                if has_userall:
                    sql += """ WHERE `coin_name`='"""+COIN_NAME+"""' """
                else:
                    sql += """ AND `coin_name`='"""+COIN_NAME+"""' """
            cur.execute(sql,)
            result1 = cur.fetchall()

            sql = """ SELECT * FROM xmr_get_transfers """
            has_userall = True
            if user != 'ALL':
                sql += """ WHERE `user_id`='"""+user+"""' """
                has_userall = False
            if COIN_NAME != 'ANY':
                if has_userall:
                    sql += """ WHERE `coin_name`='"""+COIN_NAME+"""' """
                else:
                    sql += """ AND `coin_name`='"""+COIN_NAME+"""' """
            cur.execute(sql,)
            result2 = cur.fetchall()

            sql = """ SELECT * FROM doge_get_transfers """
            has_userall = True
            if user != 'ALL':
                sql += """ WHERE `user_id`='"""+user+"""' """
                has_userall = False
            if COIN_NAME != 'ANY':
                if has_userall:
                    sql += """ WHERE `coin_name`='"""+COIN_NAME+"""' """
                else:
                    sql += """ AND `coin_name`='"""+COIN_NAME+"""' """
            cur.execute(sql,)
            result3 = cur.fetchall()

            return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_swap_balance(coin: str, owner_id: str, owner_name: str, from_: str, to_: str, amount: float):
    global conn, ENABLE_SWAP
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_SWAP:
        return False
    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ INSERT INTO discord_swap_balance (`coin_name`, `owner_id`, `owner_name`, `from`, `to`, `amount`, `decimal`) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
            cur.execute(sql, (COIN_NAME, owner_id, owner_name, from_, to_, amount, wallet.get_decimal(COIN_NAME)))
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_get_new_swap_table(notified: str = 'NO', failed_notify: str = 'NO'):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT * FROM discord_swap_balance WHERE `notified`=%s AND `failed_notify`=%s AND `to` = %s """
            cur.execute(sql, (notified, failed_notify, 'TIPBOT',))
            result = cur.fetchall()
            return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def sql_update_notify_swap_table(id: int, notified: str = 'YES', failed_notify: str = 'NO'):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ UPDATE discord_swap_balance SET `notified`=%s, `failed_notify`=%s, 
                      `notified_time`=%s WHERE `id`=%s """
            cur.execute(sql, (notified, failed_notify, float("%.3f" % time.time()), id,))
            conn.commit()
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


def sql_feedback_add(user_id: str, user_name:str, feedback_id: str, text_in: str, feedback_text: str, howto_contact_back: str):
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT INTO `discord_feedback` (`user_id`, `user_name`, `feedback_id`, `text_in`, `feedback_text`, `feedback_date`, `howto_contact_back`)
                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
            cur.execute(sql, (user_id, user_name, feedback_id, text_in, feedback_text, int(time.time()), howto_contact_back))
            conn.commit()
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


def sql_get_feedback_count_last(userID, lastDuration: int):
    global conn
    lapDuration = int(time.time()) - lastDuration
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT * FROM discord_feedback WHERE `user_id` = %s AND `feedback_date`>%s 
                      ORDER BY `feedback_date` DESC LIMIT 100 """
            cur.execute(sql, (userID, lapDuration,))
            result = cur.fetchall()
            if result is None:
                return 0
            return len(result) if result else 0
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_feedback_by_ref(ref: str):
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT * FROM discord_feedback WHERE `feedback_id`=%s """
            cur.execute(sql, (ref,))
            result = cur.fetchone()
            return result if result else None
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


def sql_feedback_list_by_user(userid: str, last: int):
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT * FROM discord_feedback WHERE `user_id`=%s 
                      ORDER BY `feedback_date` DESC LIMIT """+str(last)
            cur.execute(sql, (userid,))
            result = cur.fetchall()
            return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


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
