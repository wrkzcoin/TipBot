from typing import List, Dict
from datetime import datetime
import time
import json
import asyncio

import daemonrpc_client, wallet, walletapi
from config import config
import sys, traceback
import os.path

# Encrypt
from cryptography.fernet import Fernet

# MySQL
import pymysql, pymysqlpool
import pymysql.cursors

pymysqlpool.logger.setLevel('DEBUG')
myconfig = {
    'host': config.mysql.host,
    'user':config.mysql.user,
    'password':config.mysql.password,
    'database':config.mysql.db,
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit':True
    }

connPool = pymysqlpool.ConnectionPool(size=5, name='connPool', **myconfig)
conn = connPool.get_connection(timeout=5, retry_num=2)


#conn = None
sys.path.append("..")

ENABLE_COIN = config.Enable_Coin.split(",")
ENABLE_COIN_DOGE = ["DOGE"]

# Coin using wallet-api
WALLET_API_COIN = ["DEGO"]


# openConnection_cursors 
def openConnection():
    global conn, connPool
    try:
        if conn is None:
            conn = connPool.get_connection(timeout=5, retry_num=2)
    except:
        print("ERROR: Unexpected error: Could not connect to MySql instance.")
        sys.exit()


def sql_get_walletinfo():
    global conn
    wallet_service = {}
    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ SELECT `coin_name`, `coin_family`, `host`, `port`, `wallethost`, `walletport`, `mixin`, 
                      `tx_fee`, `min_tx_amount`, `max_tx_amount`, `DonateAddress`, `prefix`, `prefixChar`, `decimal`, 
                      `AddrLen`, `IntAddrLen`, `DiffTarget`, `MinToOptimize`, `IntervalOptimize`, 
                      `withdraw_enable`, `deposit_enable`, `send_enable`, `tip_enable`, `tipall_enable`, `donate_enable`, 
                      `maintenance` 
                      FROM discord_walletservice """
            cur.execute(sql,)
            result = cur.fetchall()
            if result is None:
                return None
            else:
                for row in result:
                    wallet_service[str(row[0].upper())] = {'coin_name': row[0], 'coin_family': row[1], 'host': row[2], 
                        'port': str(row[3]), 'wallethost': row[4], 'walletport': str(row[5]), 'mixin': int(row[6]), 'tx_fee': int(row[7]), 
                        'min_tx_amount': int(row[8]), 'max_tx_amount': int(row[9]), 'DonateAddress': row[10], 'prefix': str(row[11]), 'prefixChar': str(row[12]), 
                        'decimal': int(row[13]), 'AddrLen': int(row[14]), 'IntAddrLen': int(row[15]), 'DiffTarget': int(row[16]), 'MinToOptimize': int(row[17]), 
                        'IntervalOptimize': int(row[18]), 'withdraw_enable': row[19], 'deposit_enable': row[20], 'send_enable': row[21], 'tip_enable': row[22], 
                        'tipall_enable': row[23], 'donate_enable': row[24], 'maintenance': row[25]}
                return wallet_service
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


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
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family == "TRTL" or coin_family == "CCX":
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
    if coin_family == "XMR":
        print('SQL: Updating get_transfers '+COIN_NAME)
        get_transfers = await wallet.get_transfers_xmr(COIN_NAME)
        if len(get_transfers) >= 1:
            try:
                openConnection()
                with conn.cursor() as cur:
                    sql = """ SELECT * FROM """+coin.lower()+"""_get_transfers WHERE `coin_name` = %s """
                    cur.execute(sql, (COIN_NAME,))
                    result = cur.fetchall()
                    d = [i['txid'] for i in result]
                    # print('=================='+COIN_NAME+'===========')
                    # print(d)
                    # print('=================='+COIN_NAME+'===========')
                    list_balance_user = {}
                    for tx in get_transfers['in']:
                        if ('payment_id' in tx) and (tx['payment_id'] in list_balance_user):
                            list_balance_user[tx['payment_id']] += tx['amount']
                        elif ('payment_id' in tx) and (tx['payment_id'] not in list_balance_user):
                            list_balance_user[tx['payment_id']] = tx['amount']
                        try:
                            if tx['txid'] not in d:
                                sql = """ INSERT IGNORE INTO """+coin.lower()+"""_get_transfers (`coin_name`, `in_out`, `txid`, 
                                `payment_id`, `height`, `timestamp`, `amount`, `fee`, `decimal`, `address`, time_insert) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                cur.execute(sql, (COIN_NAME, tx['type'].upper(), tx['txid'], tx['payment_id'], tx['height'], tx['timestamp'],
                                                  tx['amount'], tx['fee'], wallet.get_decimal(COIN_NAME), tx['address'], int(time.time())))
                                conn.commit()
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    if len(list_balance_user) > 0:
                        list_update = []
                        timestamp = int(time.time())
                        for key, value in list_balance_user.items():
                            list_update.append((value, timestamp, key))
                        cur.executemany(""" UPDATE """+coin.lower()+"""_user_paymentid SET `actual_balance` = %s, `lastUpdate` = %s 
                                        WHERE paymentid = %s """, list_update)
                        conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)


async def sql_update_some_balances(wallet_addresses: List[str], coin: str):
    global conn
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    updateTime = int(time.time())
    if coin_family == "TRTL" or coin_family == "CCX":
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


async def sql_register_user(userID, coin: str, user_server: str = 'DISCORD'):
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    global conn
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = None
            result = None
            if coin_family == "TRTL" or coin_family == "CCX":
                sql = """ SELECT user_id, balance_wallet_address, user_wallet_address FROM cn_user 
                          WHERE `user_id`=%s AND `coin_name` = %s LIMIT 1 """
                cur.execute(sql, (userID, COIN_NAME,))
                result = cur.fetchone()
            elif coin_family == "XMR":
                sql = """ SELECT * FROM """+coin.lower()+"""_user_paymentid WHERE `user_id`=%s AND `coin_name` = %s LIMIT 1 """
                cur.execute(sql, (str(userID), COIN_NAME))
                result = cur.fetchone()
            elif COIN_NAME in ENABLE_COIN_DOGE:
                sql = """ SELECT user_id, balance_wallet_address, user_wallet_address FROM """+coin.lower()+"""_user
                          WHERE `user_id`=%s LIMIT 1 """
                cur.execute(sql, userID)
                result = cur.fetchone()
            if result is None:
                balance_address = {}
                man_address = None
                if coin_family == "TRTL" or coin_family == "CCX":
                    if COIN_NAME in WALLET_API_COIN:
                        balance_address = await walletapi.walletapi_registerOTHER(COIN_NAME)
                    else:
                        balance_address = await wallet.registerOTHER(COIN_NAME)
                if coin_family == "XMR":
                    main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
                    balance_address = await wallet.make_integrated_address_xmr(main_address, COIN_NAME)
                elif COIN_NAME in ENABLE_COIN_DOGE:
                    balance_address = await wallet.DOGE_LTC_register(str(userID), COIN_NAME)

                if balance_address is None:
                    print('Internal error during call register wallet-api')
                    return
                else:
                    chainHeight = 0
                    walletStatus = None
                    if coin_family == "TRTL" or coin_family == "CCX":
                        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
                    elif COIN_NAME in ENABLE_COIN_DOGE:
                        walletStatus = await daemonrpc_client.getDaemonRPCStatus(COIN_NAME)
                    if (walletStatus is None) and (coin_family != "XMR"):
                        print('Can not reach wallet-api during sql_register_user')
                        chainHeight = 0
                    else:
                        if coin_family == "TRTL" or coin_family == "CCX":
                            chainHeight = int(walletStatus['blockCount'])
                        elif COIN_NAME in ENABLE_COIN_DOGE:
                            chainHeight = int(walletStatus['blocks'])
                    if coin_family == "TRTL" or coin_family == "CCX":
                        sql = """ INSERT INTO cn_user (`coin_name`, `user_id`, `balance_wallet_address`, 
                                  `balance_wallet_address_ts`, `balance_wallet_address_ch`, `privateSpendKey`) 
                                  VALUES (%s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, str(userID), balance_address['address'], int(time.time()), chainHeight,
                                          encrypt_string(balance_address['privateSpendKey']), ))
                    elif coin_family == "XMR":
                        sql = """ INSERT INTO """+coin.lower()+"""_user_paymentid (`coin_name`, `user_id`, `main_address`, `paymentid`, 
                                  `int_address`, `paymentid_ts`) 
                                  VALUES (%s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, str(userID), main_address, balance_address['payment_id'], balance_address['integrated_address'], int(time.time())))
                    elif COIN_NAME in ENABLE_COIN_DOGE:
                        sql = """ INSERT INTO """+coin.lower()+"""_user (`user_id`, `balance_wallet_address`, 
                                  `balance_wallet_address_ts`, `balance_wallet_address_ch`, `privateKey`) 
                                  VALUES (%s, %s, %s, %s, %s) """
                        cur.execute(sql, (str(userID), balance_address['address'], int(time.time()),
                                          chainHeight, encrypt_string(balance_address['privateKey']), ))
                    conn.commit()
                    return balance_address
            else:
                return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def sql_update_user(userID, user_wallet_address, coin: str):
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            if coin_family == "TRTL" or coin_family == "CCX":
                sql = """ UPDATE cn_user SET user_wallet_address=%s WHERE user_id=%s AND `coin_name` = %s LIMIT 1 """               
                cur.execute(sql, (user_wallet_address, str(userID), COIN_NAME, ))
                conn.commit()
            elif coin_family == "XMR":
                sql = """ UPDATE """+coin.lower()+"""_user_paymentid SET user_wallet_address=%s WHERE `user_id`=%s AND `coin_name` = %s LIMIT 1 """               
                cur.execute(sql, (user_wallet_address, str(userID), COIN_NAME))
                conn.commit()
            elif coin_family == "DOGE":
                sql = """ UPDATE """+coin.lower()+"""_user SET user_wallet_address=%s WHERE `user_id`=%s AND `coin_name` = %s LIMIT 1 """               
                cur.execute(sql, (user_wallet_address, str(userID), COIN_NAME))
                conn.commit()
            return user_wallet_address  # return userwallet
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def sql_get_userwallet(userID, coin: str = None):
    global conn
    COIN_NAME = None
    if coin is None:
        coin = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    try:
        openConnection()
        sql = None
        with conn.cursor() as cur:
            result = None
            if coin_family == "TRTL" or coin_family == "CCX":
                sql = """ SELECT user_id, balance_wallet_address, user_wallet_address, balance_wallet_address_ts, 
                          balance_wallet_address_ch, lastOptimize, forwardtip 
                          FROM cn_user WHERE `user_id`=%s AND `coin_name` = %s LIMIT 1 """
                cur.execute(sql, (str(userID), COIN_NAME,))
                result = cur.fetchone()
            elif coin_family == "XMR":
                sql = """ SELECT * FROM """+coin.lower()+"""_user_paymentid WHERE `user_id`=%s AND `coin_name` = %s LIMIT 1 """
                cur.execute(sql, (str(userID), COIN_NAME))
                result = cur.fetchone()
            elif COIN_NAME in ENABLE_COIN_DOGE:
                sql = """ SELECT user_id, balance_wallet_address, user_wallet_address, balance_wallet_address_ts, 
                          balance_wallet_address_ch, lastUpdate 
                          FROM """+coin.lower()+"""_user WHERE `user_id`=%s LIMIT 1 """
                cur.execute(sql, (str(userID),))
                result = cur.fetchone()
            if result is None:
                if COIN_NAME in ENABLE_COIN_DOGE:
                    # Sometimes balance account exists
                    depositAddress = await wallet.DOGE_LTC_getaccountaddress(str(userID), COIN_NAME)
                    walletStatus = await daemonrpc_client.getDaemonRPCStatus(COIN_NAME)
                    chainHeight = int(walletStatus['blocks'])
                    privateKey = await wallet.DOGE_LTC_dumpprivkey(depositAddress, COIN_NAME)
                    sql = """ INSERT INTO """+coin.lower()+"""_user (`coin_name`, `user_id`, `balance_wallet_address`, 
                              `balance_wallet_address_ts`, `balance_wallet_address_ch`, `privateKey`) 
                              VALUES (%s, %s, %s, %s, %s, %s) """
                    cur.execute(sql, (COIN_NAME, str(userID), depositAddress, int(time.time()), chainHeight, encrypt_string(privateKey), ))
                    conn.commit()               
                else:
                    return None
            else:
                userwallet = result
                if COIN_NAME in ENABLE_COIN_DOGE:
                    depositAddress = await wallet.DOGE_LTC_getaccountaddress(str(userID), coin.upper())
                    userwallet['balance_wallet_address'] = depositAddress
                if coin_family == "XMR":
                    userwallet['balance_wallet_address'] = userwallet['int_address']
                    return userwallet
                with conn.cursor() as cur:
                    result2 = None
                    if coin_family == "TRTL" or coin_family == "CCX":
                        sql = """ SELECT `balance_wallet_address`, `actual_balance`, `locked_balance`, `decimal`, `lastUpdate` FROM cn_walletapi 
                                  WHERE `balance_wallet_address` = %s AND `coin_name` = %s LIMIT 1 """
                        cur.execute(sql, (userwallet['balance_wallet_address'], COIN_NAME,))
                        result2 = cur.fetchone()
                if coin_family == "TRTL" or coin_family == "CCX":
                    if result2:
                        userwallet['actual_balance'] = int(result2['actual_balance'])
                        userwallet['locked_balance'] = int(result2['locked_balance'])
                        userwallet['lastUpdate'] = int(result2['lastUpdate'])
                    else:
                        userwallet['actual_balance'] = 0
                        userwallet['locked_balance'] = 0
                        userwallet['lastUpdate'] = int(time.time())
                if COIN_NAME in ENABLE_COIN_DOGE:
                    # Call to API instead
                    actual = float(await wallet.DOGE_LTC_getbalance_acc(str(userID), coin.upper(), 6))
                    locked = float(await wallet.DOGE_LTC_getbalance_acc(str(userID), coin.upper(), 1))
                    if actual == locked:
                        balance_actual = '{:,.8f}'.format(actual)
                        balance_locked = '{:,.8f}'.format(0)
                    else:
                        balance_actual = '{:,.8f}'.format(actual)
                        balance_locked = '{:,.8f}'.format(locked - actual)
                    userwallet['actual_balance'] = balance_actual
                    userwallet['locked_balance'] = balance_locked
                    userwallet['lastUpdate'] = int(time.time())
                #print(userwallet)
                return userwallet
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


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
            if result is None:
                return 0
            else:
                return len(result)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def sql_send_tip(user_from: str, user_to: str, amount: int, tiptype: str, coin: str = None):
    global conn
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    user_from_wallet = None
    user_to_wallet = None
    address_to = None
    #print('sql_send_tip')
    if coin_family == "TRTL" or coin_family == "CCX" or coin_family == "XMR":
        user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME)
        user_to_wallet = await sql_get_userwallet(user_to, COIN_NAME)
        if user_to_wallet['forwardtip'] == "ON" and user_to_wallet['user_wallet_address']:
            address_to = user_to_wallet['user_wallet_address']
        else:
            address_to = user_to_wallet['balance_wallet_address']
    if all(v is not None for v in [user_from_wallet['balance_wallet_address'], address_to]):
        tx_hash = None
        if coin_family == "TRTL" or coin_family == "CCX":
            if COIN_NAME in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transaction(user_from_wallet['balance_wallet_address'],
                                                                     address_to, amount, COIN_NAME)
            else:
                tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'],
                                                        address_to, amount, COIN_NAME)
        if tx_hash:
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    sql = None
                    if coin_family == "TRTL" or coin_family == "CCX":
                        sql = """ INSERT INTO cn_tip (`coin_name`, `from_user`, `to_user`, `amount`, `decimal`, `date`, `tx_hash`, `tip_tips_tipall`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, user_from, user_to, amount, wallet.get_decimal(COIN_NAME), timestamp, tx_hash, tiptype.upper(),))
                        conn.commit()
                        await sql_update_some_balances([user_from_wallet['balance_wallet_address'], user_to_wallet['balance_wallet_address']], COIN_NAME)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        return tx_hash
    else:
        return None


async def sql_send_secrettip(user_from: str, user_to: str, amount: int, coin: str):
    global conn
    coin = coin.upper()
    user_from_wallet = None
    user_to_wallet = None
    address_to = None
    #print('sql_send_secrettip')
    if coin in ENABLE_COIN:
        user_from_wallet = await sql_get_userwallet(user_from, coin)
        user_to_wallet = await sql_get_userwallet(user_to, coin)
        if user_to_wallet['forwardtip'] == "ON" and user_to_wallet['user_wallet_address']:
            address_to = user_to_wallet['user_wallet_address']
        else:
            address_to = user_to_wallet['balance_wallet_address']
    if all(v is not None for v in [user_from_wallet['balance_wallet_address'], address_to]):
        tx_hash = None
        if coin.upper() in ENABLE_COIN:
            if coin.upper() in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transaction(user_from_wallet['balance_wallet_address'],
                                                                     address_to, amount, coin.upper())
            else:
                tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'],
                                                        address_to, amount, coin.upper())
        if tx_hash:
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    sql = None
                    updateBalance = None
                    if coin.upper() in ENABLE_COIN:
                        sql = """ INSERT INTO bot_secrettip (`coin_name`, `from_user`, `to_user`, `amount`, `decimal_coin`, `date`, `tx_hash`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (coin.upper(), user_from, user_to, amount, wallet.get_decimal(coin.upper()), timestamp, tx_hash,))
                        conn.commit()
                        if coin.upper() in WALLET_API_COIN:
                            updateBalance = await walletapi.walletapi_get_balance_address(user_from_wallet['balance_wallet_address'],
                                                                                          coin)
                        else:
                            updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'],
                                                                             coin)
                    if updateBalance:
                        if coin in ENABLE_COIN:
                            sql = """ UPDATE cn_walletapi SET `actual_balance`=%s, `locked_balance`=%s, 
                                      `lastUpdate`=%s, `decimal`=%s WHERE `balance_wallet_address`=%s AND `coin_name` = %s LIMIT 1 """
                            cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'],
                                              updateTime, wallet.get_decimal(coin.upper()), user_from_wallet['balance_wallet_address'], coin.upper(),))
                            conn.commit()
                            if coin in WALLET_API_COIN:
                                updateBalance = await walletapi.walletapi_get_balance_address(user_to_wallet['balance_wallet_address'],
                                                                                              coin)

                            else:
                                updateBalance = await wallet.get_balance_address(user_to_wallet['balance_wallet_address'],
                                                                                 coin)

                            sql = """ UPDATE cn_walletapi SET `actual_balance`=%s, 
                                      `locked_balance`=%s, `lastUpdate`=%s, `decimal`=%s 
                                      WHERE `balance_wallet_address`=%s AND `coin_name` = %s LIMIT 1 """
                            cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'],
                                        updateTime, wallet.get_decimal(coin.upper()), user_to_wallet['balance_wallet_address'], coin.upper(),))
                            conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        return tx_hash
    else:
        return None


async def sql_send_tipall(user_from: str, user_tos, amount: int, amount_div: int, user_ids, tiptype: str, coin: str):
    global conn
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    if tiptype.upper() not in ["TIPS", "TIPALL"]:
        return None

    user_from_wallet = None
    if coin_family == "TRTL" or coin_family == "CCX" or coin_family == "XMR":
        user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME)
    if user_from_wallet['balance_wallet_address']:
        tx_hash = None
        if coin_family == "TRTL" or coin_family == "CCX":
            if COIN_NAME in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transactionall(user_from_wallet['balance_wallet_address'], user_tos, COIN_NAME)
            else:
                tx_hash = await wallet.send_transactionall(user_from_wallet['balance_wallet_address'], user_tos, COIN_NAME)
        if tx_hash:
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    if coin_family == "TRTL" or coin_family == "CCX":
                        sql = """ INSERT INTO cn_tipall (`coin_name`, `from_user`, `amount_total`, `decimal`, `date`, `tx_hash`, `numb_receivers`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, user_from, amount, wallet.get_decimal(COIN_NAME), timestamp, tx_hash, len(user_tos),))
                        conn.commit()

                        values_str = []
                        for item in user_ids:
                            values_str.append(f"('{COIN_NAME}', '{user_from}', '{item}', {amount_div}, {int(wallet.get_decimal(COIN_NAME))}, {timestamp}, '{tx_hash}', '{tiptype.upper()}')\n")
                        values_sql = "VALUES " + ",".join(values_str)
                        sql = """ INSERT INTO cn_tip (`coin_name`, `from_user`, `to_user`, `amount`, `decimal`, `date`, `tx_hash`, `tip_tips_tipall`) 
                                  """+values_sql+""" """
                        cur.execute(sql,)
                        conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        return tx_hash
    else:
        return None


async def sql_send_tip_Ex(user_from: str, address_to: str, amount: int, coin: str):
    global conn
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    user_from_wallet = None
    if coin_family == "TRTL" or coin_family == "CCX" or coin_family == "XMR":
        user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME)
    if user_from_wallet['balance_wallet_address']:
        tx_hash = None
        if coin_family == "TRTL" or coin_family == "CCX":
            if COIN_NAME in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transaction(user_from_wallet['balance_wallet_address'], address_to, 
                                                                     amount, COIN_NAME)

            else:
                tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'], address_to, 
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
                    if coin_family == "TRTL" or coin_family == "CCX":
                        sql = """ INSERT INTO cn_send (`coin_name`, `from_user`, `to_address`, `amount`, `decimal`, `date`, 
                                  `tx_hash`) VALUES (%s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, user_from, address_to, amount, wallet.get_decimal(COIN_NAME), timestamp, tx_hash,))
                        conn.commit()
                        if COIN_NAME in WALLET_API_COIN:
                            updateBalance = await walletapi.walletapi_get_balance_address(user_from_wallet['balance_wallet_address'], 
                                                                                          COIN_NAME)
                        else:
                            updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], 
                                                                             COIN_NAME)
                    if updateBalance:
                        if coin_family == "TRTL" or coin_family == "CCX":
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


async def sql_send_tip_Ex_id(user_from: str, address_to: str, amount: int, paymentid, coin: str = None):
    global conn
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()
    user_from_wallet = None
    if COIN_NAME in ENABLE_COIN:
        user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME)
    if 'balance_wallet_address' in user_from_wallet:
        tx_hash = None
        if COIN_NAME in ENABLE_COIN:
            if COIN_NAME in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transaction_id(user_from_wallet['balance_wallet_address'], address_to,
                                                                        amount, paymentid, COIN_NAME)
            else:
                tx_hash = await wallet.send_transaction_id(user_from_wallet['balance_wallet_address'], address_to,
                                                           amount, paymentid, COIN_NAME)
        if tx_hash:
            updateTime = int(time.time())
            try:
                openConnection()
                updateBalance = None
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    if COIN_NAME in ENABLE_COIN:
                        sql = """ INSERT INTO cn_send (`coin_name`, `from_user`, `to_address`, `amount`, `decimal`, `date`, 
                                  `tx_hash`, `paymentid`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, user_from, address_to, amount, wallet.get_decimal(COIN_NAME), timestamp, tx_hash, paymentid, ))
                        conn.commit()
                        if COIN_NAME in WALLET_API_COIN:
                            updateBalance = await walletapi.walletapi_get_balance_address(user_from_wallet['balance_wallet_address'], COIN_NAME)
                        else:
                            updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], COIN_NAME)
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


async def sql_withdraw(user_from: str, amount: int, coin: str):
    global conn
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    tx_hash = None
    user_from_wallet = None
    if coin_family == "TRTL" or coin_family == "CCX" or coin_family == "XMR":
        user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME)
    if all(v is not None for v in [user_from_wallet['balance_wallet_address'], user_from_wallet['user_wallet_address']]):
        if coin_family == "TRTL" or coin_family == "CCX":
            if COIN_NAME in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transaction(user_from_wallet['balance_wallet_address'],
                                                                     user_from_wallet['user_wallet_address'], amount, COIN_NAME)

            else:
                tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'],
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
                    if coin_family == "TRTL" or coin_family == "CCX":
                        sql = """ INSERT INTO cn_withdraw (`coin_name`, `user_id`, `to_address`, `amount`, 
                                  `decimal`, `date`, `tx_hash`) VALUES (%s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, user_from, user_from_wallet['user_wallet_address'], amount, wallet.get_decimal(COIN_NAME), timestamp, tx_hash,))
                        conn.commit()
                        if COIN_NAME in WALLET_API_COIN:
                            updateBalance = await walletapi.walletapi_get_balance_address(user_from_wallet['balance_wallet_address'], COIN_NAME)
                        else:
                            updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], COIN_NAME)
                    if coin_family == "XMR":
                        sql = """ INSERT INTO """+coin.lower()+"""_withdraw (`coin_name`, `user_id`, `to_address`, `amount`, 
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


async def sql_donate(user_from: str, address_to: str, amount: int, coin: str) -> str:
    global conn
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    user_from_wallet = None
    if coin_family == "TRTL" or coin_family == "CCX" or coin_family == "XMR":
        user_from_wallet = await sql_get_userwallet(user_from, COIN_NAME)
    if all(v is not None for v in [user_from_wallet['balance_wallet_address'], address_to]):
        tx_hash = None
        if coin_family == "TRTL" or coin_family == "CCX":
            if COIN_NAME in WALLET_API_COIN:
                tx_hash = await walletapi.walletapi_send_transaction(user_from_wallet['balance_wallet_address'], address_to, amount, COIN_NAME)
            else:
                tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'], address_to, amount, COIN_NAME)
        if tx_hash:
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    updateBalance = None
                    if coin_family == "TRTL" or coin_family == "CCX":
                        sql = """ INSERT INTO cn_donate (`coin_name`, `from_user`, `to_address`, `amount`, 
                                  `decimal`, `date`, `tx_hash`) VALUES (%s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, user_from, address_to, amount, wallet.get_decimal(COIN_NAME), timestamp, tx_hash,))
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
            for coin in ENABLE_COIN:
                sql = """ SELECT SUM(amount) AS donate FROM cn_donate WHERE `coin_name`= %s """
                cur.execute(sql, (coin.upper()))
                result = cur.fetchone()
                if result['donate'] is None:
                   donate_list.update({coin: 0})
                else:
                   donate_list.update({coin: float(result['donate'])})
            # DOGE
            coin = "DOGE"
            sql = """ SELECT SUM(amount) AS donate FROM """+coin.lower()+"""_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # XTOR
            coin = "XTOR"
            sql = """ SELECT SUM(amount) AS donate FROM """+coin.lower()+"""_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # LOKI
            coin = "LOKI"
            sql = """ SELECT SUM(amount) AS donate FROM """+coin.lower()+"""_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # XMR
            coin = "XMR"
            sql = """ SELECT SUM(amount) AS donate FROM """+coin.lower()+"""_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # XEQ
            coin = "XEQ"
            sql = """ SELECT SUM(amount) AS donate FROM """+coin.lower()+"""_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # ARQ
            coin = "ARQ"
            sql = """ SELECT SUM(amount) AS donate FROM """+coin.lower()+"""_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # MSR
            coin = "MSR"
            sql = """ SELECT SUM(amount) AS donate FROM """+coin.lower()+"""_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
            # BLOG
            coin = "BLOG"
            sql = """ SELECT SUM(amount) AS donate FROM """+coin.lower()+"""_mv_tx as donate WHERE `type`='DONATE' AND `to_userid`= %s """
            cur.execute(sql, (wallet.get_donate_address(coin)))
            result = cur.fetchone()
            if result['donate'] is None:
                donate_list.update({coin: 0})
            else:
                donate_list.update({coin: float(result['donate'])})
        return donate_list
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_optimize_check(coin: str):
    global conn
    COIN_NAME = coin.upper()
    try:
        openConnection()
        with conn.cursor() as cur:
            timeNow = int(time.time()) - 600
            if COIN_NAME in ENABLE_COIN:
                sql = """ SELECT COUNT(*) FROM cn_user WHERE lastOptimize>%s AND `coin_name` = %s """
                cur.execute(sql, (timeNow, COIN_NAME,))
                result = cur.fetchone()
                return result['COUNT(*)'] if (result and 'COUNT(*)' in result) else 0
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def sql_optimize_do(userID: str, coin: str):
    global conn
    COIN_NAME = coin.upper()
    user_from_wallet = None
    if COIN_NAME in ENABLE_COIN:
        user_from_wallet = await sql_get_userwallet(userID, COIN_NAME)
    if COIN_NAME in WALLET_API_COIN:
        OptimizeCount = 0
        try:
            OptimizeCount = await walletapi.walletapi_wallet_optimize_single(user_from_wallet['balance_wallet_address'], COIN_NAME)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if OptimizeCount > 0:
            updateTime = int(time.time())
            sql_optimize_update(str(userID), COIN_NAME)
            try:
                openConnection()
                updateBalance = await walletapi.walletapi_get_balance_address(user_from_wallet['balance_wallet_address'], COIN_NAME)
                with conn.cursor() as cur:
                    sql = """ UPDATE cn_walletapi SET `actual_balance`=%s, 
                             `locked_balance`=%s, `lastUpdate`=%s, `decimal` = %s 
                             WHERE `balance_wallet_address`=%s AND `coin_name`=%s LIMIT 1 """
                    cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'], 
                                updateTime, wallet.get_decimal(COIN_NAME), user_from_wallet['balance_wallet_address'], COIN_NAME,))
                    conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return OptimizeCount
        else:
            return 0

    estimate = await wallet.wallet_estimate_fusion(user_from_wallet['balance_wallet_address'], 
                                             user_from_wallet['actual_balance'], COIN_NAME)
    if estimate:
        if 'fusionReadyCount' in estimate:
            print('fusionReadyCount: '+ str(estimate['fusionReadyCount']))
            print('totalOutputCount: '+ str(estimate['totalOutputCount']))
            if estimate['fusionReadyCount'] == 0:
                return 0
    else:
        print('fusionReadyCount check error.')
        return 0

    print('store.sql_optimize_do: ' + COIN_NAME)
    if user_from_wallet:
        OptimizeCount = 0
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
        if coin_family == "TRTL":
            OptimizeCount = await wallet.wallet_optimize_single(user_from_wallet['balance_wallet_address'], 
                                                                int(user_from_wallet['actual_balance']), COIN_NAME)
        else:
            return      
        if OptimizeCount > 0:
            updateTime = int(time.time())
            sql_optimize_update(str(userID), COIN_NAME)
            try:
                openConnection()
                updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], COIN_NAME)
                with conn.cursor() as cur:
                    sql = """ UPDATE cn_walletapi SET `actual_balance`=%s, 
                             `locked_balance`=%s, `lastUpdate`=%s, `decimal` = %s 
                             WHERE `balance_wallet_address`=%s AND `coin_name`=%s LIMIT 1 """
                    cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'], 
                                updateTime, wallet.get_decimal(COIN_NAME), user_from_wallet['balance_wallet_address'], COIN_NAME,))
                    conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        return OptimizeCount


def sql_optimize_update(userID: str, coin: str = None):
    global conn
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()
    try:
        openConnection()
        with conn.cursor() as cur:
            timeNow = int(time.time())
            if COIN_NAME in ENABLE_COIN:
                sql = """ UPDATE cn_user SET `lastOptimize`=%s 
                          WHERE `user_id`=%s AND `coin_name`=%s LIMIT 1 """
                cur.execute(sql, (timeNow, str(userID), COIN_NAME,))
                conn.commit()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def sql_optimize_admin_do(coin: str, opt_num: int = None):
    global conn
    if opt_num is None:
        opt_num = 5
    if coin is None:
        coin = "WRKZ"
    if coin.upper() in ENABLE_COIN:
        addresses = await wallet.get_all_balances_all(coin.upper())
    else:
        return None
    AccumOpt = 0
    for address in addresses:
        if address['unlocked'] > 0:
            estimate = None
            # TODO: walletapi
            estimate = await wallet.wallet_estimate_fusion(address['address'], address['unlocked'], coin.upper())
            if estimate:
                if 'fusionReadyCount' in estimate:
                    #print('fusionReadyCount: '+ str(estimate['fusionReadyCount']))
                    #print('totalOutputCount: '+ str(estimate['totalOutputCount']))
                    if estimate['fusionReadyCount'] >= 2:
                        print(f'Optimize {coin.upper()}: ' + address['address'])
                        OptimizeCount = 0
                        try:
                            # TODO: walletapi
                            OptimizeCount = await wallet.wallet_optimize_single(address['address'], int(round(address['unlocked']/2)), coin.upper())
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        if OptimizeCount > 0:
                            AccumOpt = AccumOpt + 1
                        if AccumOpt >= opt_num:
                            break
                        return AccumOpt
    return None


async def sql_send_to_voucher(user_id: str, user_name: str, message_creating: str, amount: int, reserved_fee: int, secret_string: str, voucher_image_name: str, coin: str = None):
    global conn
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()
    user_from_wallet = None
    if COIN_NAME in ENABLE_COIN:
        user_from_wallet = await sql_get_userwallet(user_id, COIN_NAME)
    if user_from_wallet['balance_wallet_address']:
        tx_hash = None
        if COIN_NAME in ENABLE_COIN:
            # TODO: with walletapi
            tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'], wallet.get_voucher_address(COIN_NAME), 
                                                    amount + reserved_fee, COIN_NAME)
        if tx_hash:
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    updateBalance = None
                    if COIN_NAME in ENABLE_COIN:
                        sql = """ INSERT INTO cn_voucher (`coin_name`, `user_id`, `user_name`, `message_creating`, `amount`, 
                                  `decimal`, `reserved_fee`, `date_create`, `secret_string`, `voucher_image_name`, `tx_hash_deposit`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (COIN_NAME, user_id, user_name, message_creating, amount, wallet.get_decimal(COIN_NAME), reserved_fee, int(time.time()), secret_string, voucher_image_name, tx_hash,))
                        conn.commit()
                        # TODO with walletapi also
                        updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], 
                                                                         COIN_NAME)
                    if updateBalance:
                        if COIN_NAME in ENABLE_COIN:
                            sql = """ UPDATE cn_walletapi SET `actual_balance`=%s, 
                                      `locked_balance`=%s, `decimal` = %s, `lastUpdate`=%s 
                                      WHERE `balance_wallet_address`=%s AND `coin_name` = %s LIMIT 1"""
                            cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'],
                                        wallet.get_decimal(COIN_NAME), int(time.time()), 
                                        user_from_wallet['balance_wallet_address'], COIN_NAME))
                            conn.commit()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        return tx_hash
    else:
        return None


def sql_faucet_add(claimed_user: str, claimed_server: str, coin_name: str, claimed_amount: float, decimal: int, tx_hash: str = None):
    global conn
    tx_hash = tx_hash or 'NULL'
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT INTO discord_faucet (`claimed_user`, `coin_name`, `claimed_amount`, 
                      `decimal`, `tx_hash`, `claimed_at`, `claimed_server`) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
            cur.execute(sql, (claimed_user, coin_name, claimed_amount, decimal, tx_hash, int(time.time()), claimed_server,))
            conn.commit()
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_faucet_checkuser(userID: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT * FROM discord_faucet WHERE claimed_user = %s ORDER BY claimed_at DESC LIMIT 1"""
            cur.execute(sql, (userID,))
            result = cur.fetchone()
            return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_faucet_count_user(userID: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT COUNT(*) FROM discord_faucet WHERE claimed_user = %s """
            cur.execute(sql, (userID,))
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


def sql_tag_by_server(server_id: str, tag_id: str = None):
    global conn
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
                sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, 
                          `added_byuid`, `num_trigger` FROM discord_tag WHERE tag_serverid = %s AND tag_id=%s """
                cur.execute(sql, (server_id, tag_id,))
                result = cur.fetchone()
                if result:
                    tag = result
                    sql = """ UPDATE discord_tag SET num_trigger=num_trigger+1 WHERE tag_serverid = %s AND tag_id=%s """
                    cur.execute(sql, (server_id, tag_id,))
                    conn.commit()
                    return tag
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


def sql_addinfo_by_server(server_id: str, servername: str, prefix: str, default_coin: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT INTO `discord_server` (`serverid`, `servername`, `prefix`, `default_coin`)
                      VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE 
                      servername = %s, prefix = %s, default_coin = %s"""
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


def sql_get_messages(server_id: str, channel_id: str, time_int: int):
    global conn
    lapDuration = int(time.time()) - time_int
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT DISTINCT `user_id` FROM discord_messages 
                      WHERE `serverid` = %s AND `channel_id` = %s AND `message_time`>%s """
            cur.execute(sql, (server_id, channel_id, lapDuration,))
            result = cur.fetchall()
            list_talker = []
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


# not use anywhere
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
                if what in ["servername", "prefix", "default_coin", "tiponly"]:
                    sql = """ UPDATE discord_server SET """+what+"""=%s WHERE serverid=%s """
                    cur.execute(sql, (what, value, server_id,))
                    conn.commit()
                else:
                    return None
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

# DOGE
def sql_mv_doge_single(user_from: str, to_user: str, amount: float, coin: str, tiptype: str):
    global conn
    if coin.upper() not in ENABLE_COIN_DOGE:
        return False
    if tiptype.upper() not in ["TIP", "DONATE", "SECRETTIP", "FAUCET"]:
        return False
    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ INSERT INTO """+coin.lower()+"""_mv_tx (`from_userid`, `to_userid`, `amount`, `type`, `date`) 
                      VALUES (%s, %s, %s, %s, %s) """
            cur.execute(sql, (user_from, to_user, amount, tiptype.upper(), int(time.time()),))
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


def sql_mv_doge_multiple(user_from: str, user_tos, amount_each: float, coin: str, tiptype: str):
    # user_tos is array "account1", "account2", ....
    global conn
    if coin.upper() not in ENABLE_COIN_DOGE:
        return False
    if tiptype.upper() not in ["TIPS", "TIPALL"]:
        return False
    values_str = []
    currentTs = int(time.time())
    for item in user_tos:
        values_str.append(f"('{user_from}', '{item}', {amount_each}, '{tiptype.upper()}', {currentTs})\n")
    values_sql = "VALUES " + ",".join(values_str)
    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ INSERT INTO """+coin.lower()+"""_mv_tx (`from_userid`, `to_userid`, `amount`, `type`, `date`) 
                      """+values_sql+""" """
            cur.execute(sql,)
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_external_doge_single(user_from: str, amount: float, fee: float, to_address: str, coin: str, tiptype: str):
    global conn
    if coin.upper() not in ENABLE_COIN_DOGE:
        return False
    if tiptype.upper() not in ["SEND", "WITHDRAW"]:
        return False
    try:
        openConnection()
        txHash = await wallet.DOGE_LTC_sendtoaddress(to_address, amount, user_from, coin.upper())
        with conn.cursor() as cur: 
            sql = """ INSERT INTO """+coin.lower()+"""_external_tx (`user_id`, `amount`, `fee`, `to_address`, 
                      `type`, `date`, `tx_hash`) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
            cur.execute(sql, (user_from, amount, fee, to_address, tiptype.upper(), int(time.time()), txHash,))
            conn.commit()
        return txHash
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


def sql_doge_balance(userID: str, coin: str):
    global conn
    if coin.upper() not in ENABLE_COIN_DOGE:
        return False
    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ SELECT SUM(amount) AS Expense FROM """+coin.lower()+"""_mv_tx WHERE `from_userid`=%s """
            cur.execute(sql, userID)
            result = cur.fetchone()
            if result:
                Expense = result['Expense']
            else:
                Expense = 0

            sql = """ SELECT SUM(amount) AS Income FROM """+coin.lower()+"""_mv_tx WHERE `to_userid`=%s """
            cur.execute(sql, userID)
            result = cur.fetchone()
            if result:
                Income = result['Income']
            else:
                Income = 0

            sql = """ SELECT SUM(amount) AS TxExpense FROM """+coin.lower()+"""_external_tx WHERE `user_id`=%s """
            cur.execute(sql, userID)
            result = cur.fetchone()
            if result:
                TxExpense = result['TxExpense']
            else:
                TxExpense = 0

            sql = """ SELECT SUM(fee) AS FeeExpense FROM """+coin.lower()+"""_external_tx WHERE `user_id`=%s """
            cur.execute(sql, userID)
            result = cur.fetchone()
            if result:
                FeeExpense = result['FeeExpense']
            else:
                FeeExpense = 0

            balance = {}
            balance['Expense'] = Expense or 0
            balance['Expense'] = round(balance['Expense'], 4)
            balance['Income'] = Income or 0
            balance['TxExpense'] = TxExpense or 0
            balance['FeeExpense'] = FeeExpense or 0
            #print('balance: ')
            #print(balance)
            balance['Adjust'] = float(balance['Income']) - float(balance['Expense']) - float(balance['TxExpense']) - float(balance['FeeExpense'])
            #print(balance['Adjust'])
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
            sql = """ INSERT INTO """+coin.lower()+"""_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`) 
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
            sql = """ INSERT INTO """+coin.lower()+"""_mv_tx (`coin_name`, `from_userid`, `to_userid`, `amount`, `decimal`, `type`, `date`) 
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
                    sql = """ INSERT INTO """+coin.lower()+"""_external_tx (`coin_name`, `user_id`, `amount`, `fee`, `decimal`, `to_address`, 
                              `type`, `date`, `tx_hash`, `tx_key`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    cur.execute(sql, (COIN_NAME, user_from, amount, tx_hash['fee'], wallet.get_decimal(COIN_NAME), to_address, tiptype.upper(), int(time.time()), tx_hash['tx_hash'], tx_hash['tx_key'],))
                    conn.commit()
        return tx_hash
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


def sql_xmr_balance(userID: str, coin: str):
    global conn
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family != "XMR":
        return False
    try:
        openConnection()
        with conn.cursor() as cur: 
            sql = """ SELECT SUM(amount) AS Expense FROM """+coin.lower()+"""_mv_tx WHERE `from_userid`=%s AND `coin_name` = %s """
            cur.execute(sql, (userID, COIN_NAME))
            result = cur.fetchone()
            if result:
                Expense = result['Expense']
            else:
                Expense = 0

            sql = """ SELECT SUM(amount) AS Income FROM """+coin.lower()+"""_mv_tx WHERE `to_userid`=%s AND `coin_name` = %s """
            cur.execute(sql, (userID, COIN_NAME))
            result = cur.fetchone()
            if result:
                Income = result['Income']
            else:
                Income = 0

            sql = """ SELECT SUM(amount) AS TxExpense FROM """+coin.lower()+"""_external_tx WHERE `user_id`=%s AND `coin_name` = %s """
            cur.execute(sql, (userID, COIN_NAME))
            result = cur.fetchone()
            if result:
                TxExpense = result['TxExpense']
            else:
                TxExpense = 0

            sql = """ SELECT SUM(fee) AS FeeExpense FROM """+coin.lower()+"""_external_tx WHERE `user_id`=%s AND `coin_name` = %s """
            cur.execute(sql, (userID, COIN_NAME))
            result = cur.fetchone()
            if result:
                FeeExpense = result['FeeExpense']
            else:
                FeeExpense = 0

            balance = {}
            balance['Expense'] = Expense or 0
            balance['Expense'] = round(balance['Expense'], 4)
            balance['Income'] = Income or 0
            balance['TxExpense'] = TxExpense or 0
            balance['FeeExpense'] = FeeExpense or 0
            balance['Adjust'] = float(balance['Income']) - float(balance['Expense']) - float(balance['TxExpense']) - float(balance['FeeExpense'])
            return balance
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def sql_set_forwardtip(userID: str, coin: str, option: str):
    global conn
    if option.upper() not in ["ON", "OFF"]:
        return None
    if coin.upper() in ENABLE_COIN:
        try:
            openConnection()
            with conn.cursor() as cur: 
                sql = """ UPDATE cn_user SET `forwardtip`='"""+option.upper()+"""' 
                          WHERE `user_id` = %s AND `coin_name` = %s LIMIT 1 """
                cur.execute(sql, (str(userID), coin.upper()))
                conn.commit()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


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
