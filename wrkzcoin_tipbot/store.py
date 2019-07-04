from typing import List
from datetime import datetime
import time
import json
import asyncio

import daemonrpc_client, wallet
from config import config
import sys

# Encrypt
from cryptography.fernet import Fernet

# MySQL
import pymysql
conn = None
sys.path.append("..")

ENABLE_COIN = config.Enable_Coin.split(",")
ENABLE_COIN_DOGE = ["DOGE"]

# OpenConnection
def openConnection():
    global conn
    try:
        if conn is None:
            conn = pymysql.connect(config.mysql.host, user=config.mysql.user, passwd=config.mysql.password,
                                   db=config.mysql.db, connect_timeout=5)
        elif not conn.open:
            conn = pymysql.connect(config.mysql.host, user=config.mysql.user, passwd=config.mysql.password,
                                   db=config.mysql.db, connect_timeout=5)
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
        print(e)
    finally:
        conn.close()


async def sql_update_balances(coin: str = None):
    global conn
    updateTime = int(time.time())
    if coin is None:
        coin = "WRKZ"
    if coin.upper() in ENABLE_COIN:
        print('SQL: Updating all wallet balances '+coin.upper())
        balances = await wallet.get_all_balances_all(coin.upper())
        try:
            openConnection()
            with conn.cursor() as cur:
                for details in balances:
                    sql = """ INSERT INTO """+coin.lower()+"""_walletapi (`balance_wallet_address`, `actual_balance`, 
                    `locked_balance`, `lastUpdate`) VALUES (%s, %s, %s, %s) 
                    ON DUPLICATE KEY UPDATE `actual_balance`=%s, `locked_balance`=%s, `lastUpdate`=%s """
                    cur.execute(sql, (details['address'], details['unlocked'], details['locked'], updateTime,
                                      details['unlocked'], details['locked'], updateTime,))
                    conn.commit()
        except Exception as e:
            print(e)
        finally:
            conn.close()


async def sql_update_some_balances(wallet_addresses: List[str], coin: str = None):
    global conn
    updateTime = int(time.time())
    if coin is None:
        coin = "WRKZ"
    if coin.upper() in ENABLE_COIN:
        print('SQL: Updating some wallet balances '+coin.upper())
        balances = await wallet.get_some_balances(wallet_addresses, coin.upper())   
        try:
            openConnection()
            with conn.cursor() as cur:
                for details in balances:
                    sql = """ INSERT INTO """+coin.lower()+"""_walletapi (`balance_wallet_address`, `actual_balance`, 
                              `locked_balance`, `lastUpdate`) VALUES (%s, %s, %s, %s) 
                              ON DUPLICATE KEY UPDATE `actual_balance`=%s, `locked_balance`=%s, `lastUpdate`=%s """
                    cur.execute(sql, (details['address'], details['unlocked'], details['locked'], updateTime,
                                      details['unlocked'], details['locked'], updateTime,))
                    conn.commit()
        except Exception as e:
            print(e)
        finally:
            conn.close()


async def sql_register_user(userID, coin: str = None):
    global conn
    if coin is None:
        coin = "WRKZ"
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = None
            COIN_NAME = None
            if coin.upper() in ENABLE_COIN:
                sql = """ SELECT user_id, balance_wallet_address, user_wallet_address FROM """+coin.lower()+"""_user 
                          WHERE `user_id`=%s LIMIT 1 """
                COIN_NAME = coin.upper()
            elif coin.upper() in ENABLE_COIN_DOGE:
                sql = """ SELECT user_id, balance_wallet_address, user_wallet_address FROM """+coin.lower()+"""_user
                          WHERE `user_id`=%s LIMIT 1 """
                COIN_NAME = coin.upper()
            cur.execute(sql, userID)
            result = cur.fetchone()
            if result is None:
                balance_address = {}
                if coin.upper() in ENABLE_COIN:
                    balance_address = await wallet.registerOTHER(coin.upper())
                elif coin.upper() in ENABLE_COIN_DOGE:
                    balance_address = await wallet.DOGE_LTC_register(str(userID), coin.upper())
                if balance_address is None:
                    print('Internal error during call register wallet-api')
                    return
                else:
                    chainHeight = 0
                    walletStatus = None
                    if coin.upper() in ENABLE_COIN:
                        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
                    elif coin.upper() in ENABLE_COIN_DOGE:
                        walletStatus = await daemonrpc_client.getDaemonRPCStatus(COIN_NAME)
                    if walletStatus is None:
                        print('Can not reach wallet-api during sql_register_user')
                        chainHeight = 0
                    else:
                        if coin.upper() in ENABLE_COIN:
                            chainHeight = int(walletStatus['blockCount'])
                        elif coin.upper() in ENABLE_COIN_DOGE:
                            chainHeight = int(walletStatus['blocks'])
                    if coin.upper() in ENABLE_COIN:
                        sql = """ INSERT INTO """+coin.lower()+"""_user (`user_id`, `balance_wallet_address`, 
                                  `balance_wallet_address_ts`, `balance_wallet_address_ch`, `privateSpendKey`) 
                                  VALUES (%s, %s, %s, %s, %s) """
                        cur.execute(sql, (str(userID), balance_address['address'], int(time.time()), chainHeight,
                                          encrypt_string(balance_address['privateSpendKey']), ))
                    elif coin.upper() in ENABLE_COIN_DOGE:
                        sql = """ INSERT INTO """+coin.lower()+"""_user (`user_id`, `balance_wallet_address`, 
                                  `balance_wallet_address_ts`, `balance_wallet_address_ch`, `privateKey`) 
                                  VALUES (%s, %s, %s, %s, %s) """
                        cur.execute(sql, (str(userID), balance_address['address'], int(time.time()),
                                          chainHeight, encrypt_string(balance_address['privateKey']), ))
                    conn.commit()
                    result2 = {}
                    result2['balance_wallet_address'] = balance_address
                    result2['user_wallet_address'] = ''
                    return result2
            else:
                result2 = {}
                result2['user_id'] = result[0]
                result2['balance_wallet_address'] = result[1]
                try:
                    result2['user_wallet_address'] = result[2]
                except IndexError:
                    result2['user_wallet_address'] = ''
                return result2
    except Exception as e:
        print(e)
    finally:
        conn.close()


async def sql_update_user(userID, user_wallet_address, coin: str = None):
    if coin is None:
        coin = "WRKZ"
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = None
            if (coin.upper() in ENABLE_COIN) or (coin.upper() in ENABLE_COIN_DOGE):
                sql = """ SELECT user_id, user_wallet_address, balance_wallet_address FROM """+coin.lower()+"""_user 
                          WHERE `user_id`=%s LIMIT 1 """
            cur.execute(sql, userID)
            result = cur.fetchone()
            if result is None:
                balance_address = None
                if coin.upper() in ENABLE_COIN:
                    balance_address = await wallet.registerOTHER(coin.upper())
                elif coin.upper() == "DOGE" or coin.upper() == "LTC":
                    balance_address = await wallet.DOGE_LTC_getaccountaddress(str(userID), coin.upper())
                if balance_address is None:
                    print('Internal error during call register wallet-api')
                    return
            else:
                if (coin.upper() in ENABLE_COIN) or (coin.upper() in ENABLE_COIN_DOGE):
                    sql = """ UPDATE """+coin.lower()+"""_user SET user_wallet_address=%s WHERE user_id=%s """               
                    cur.execute(sql, (user_wallet_address, str(userID),))
                    conn.commit()
                result2 = {}
                result2['balance_wallet_address'] = result[2]
                result2['user_wallet_address'] = user_wallet_address
                return result2  # return userwallet
    except Exception as e:
        print(e)
    finally:
        conn.close()


async def sql_get_userwallet(userID, coin: str = None):
    global conn
    if coin is None:
        coin = "WRKZ"
    try:
        openConnection()
        sql = None
        with conn.cursor() as cur:
            if coin.upper() in ENABLE_COIN:
                sql = """ SELECT user_id, balance_wallet_address, user_wallet_address, balance_wallet_address_ts, 
                          balance_wallet_address_ch, lastOptimize, forwardtip 
                          FROM """+coin.lower()+"""_user WHERE `user_id`=%s LIMIT 1 """
            elif coin.upper() in ENABLE_COIN_DOGE:
                sql = """ SELECT user_id, balance_wallet_address, user_wallet_address, balance_wallet_address_ts, 
                          balance_wallet_address_ch, lastUpdate 
                          FROM """+coin.lower()+"""_user WHERE `user_id`=%s LIMIT 1 """
            cur.execute(sql, (str(userID),))
            result = cur.fetchone()
            if result is None:
                if coin.upper() in ENABLE_COIN_DOGE:
                    # Sometimes balance account exists
                    depositAddress = await wallet.DOGE_LTC_getaccountaddress(str(userID), coin.upper())
                    walletStatus = await daemonrpc_client.getDaemonRPCStatus(coin.upper())
                    chainHeight = int(walletStatus['blocks'])
                    privateKey = await wallet.DOGE_LTC_dumpprivkey(depositAddress, coin.upper())
                    sql = """ INSERT INTO """+coin.lower()+"""_user (`user_id`, `balance_wallet_address`, 
                              `balance_wallet_address_ts`, `balance_wallet_address_ch`, `privateKey`) 
                              VALUES (%s, %s, %s, %s, %s) """
                    cur.execute(sql, (str(userID), depositAddress, int(time.time()), chainHeight, encrypt_string(privateKey), ))
                    conn.commit()               
                else:
                    return None
            else:
                userwallet = {}
                if result[1]:
                    userwallet['balance_wallet_address'] = result[1] 

                if coin.upper() in ENABLE_COIN_DOGE:
                    depositAddress = await wallet.DOGE_LTC_getaccountaddress(str(userID), coin.upper())
                    userwallet['balance_wallet_address'] = depositAddress
              
                if result[2] is not None:
                    userwallet['user_wallet_address'] = result[2]
                if result[3] is not None:
                    userwallet['balance_wallet_address_ts'] = result[3]
                if result[4] is not None:
                    userwallet['balance_wallet_address_ch'] = result[4]
                if coin.upper() in ENABLE_COIN:
                    if result[5]:
                        userwallet['lastOptimize'] = result[5]
                    if result[6]:
                        userwallet['forwardtip'] = result[6]
                with conn.cursor() as cur:
                    result2 = None
                    if coin.upper() in ENABLE_COIN:
                        sql = """ SELECT balance_wallet_address, actual_balance, locked_balance, lastUpdate 
                                  FROM """+coin.lower()+"""_walletapi 
                                  WHERE `balance_wallet_address`=%s LIMIT 1 """
                        cur.execute(sql, (userwallet['balance_wallet_address'],))
                        result2 = cur.fetchone()
                if coin.upper() in ENABLE_COIN:
                    if result2:
                        userwallet['actual_balance'] = int(result2[1])
                        userwallet['locked_balance'] = int(result2[2])
                        userwallet['lastUpdate'] = int(result2[3])
                    else:
                        userwallet['actual_balance'] = 0
                        userwallet['locked_balance'] = 0
                        userwallet['lastUpdate'] = int(time.time())
                if coin.upper() in ENABLE_COIN_DOGE:
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
        print(e)
    finally:
        conn.close()


def sql_get_countLastTip(userID, lastDuration: int, coin: str = None):
    global conn
    if coin is None:
        coin = "WRKZ"
    lapDuration = int(time.time()) - lastDuration
    try:
        openConnection()
        sql = None
        with conn.cursor() as cur:
            if coin.upper() in ENABLE_COIN:
                sql = """ (SELECT `from_user`,`amount`,`date` FROM """+coin.lower()+"""_tip WHERE `from_user` = %s AND `date`>%s )
                          UNION
                          (SELECT `from_user`,`amount_total`,`date` FROM """+coin.lower()+"""_tipall WHERE `from_user` = %s AND `date`>%s )
                          UNION
                          (SELECT `from_user`,`amount`,`date` FROM """+coin.lower()+"""_send WHERE `from_user` = %s AND `date`>%s )
                          UNION
                          (SELECT `user_id`,`amount`,`date` FROM """+coin.lower()+"""_withdraw WHERE `user_id` = %s AND `date`>%s )
                          UNION
                          (SELECT `from_user`,`amount`,`date` FROM """+coin.lower()+"""_donate WHERE `from_user` = %s AND `date`>%s )
                          ORDER BY `date` DESC LIMIT 10 """
            cur.execute(sql, (str(userID), lapDuration, str(userID), lapDuration, str(userID), lapDuration,
                              str(userID), lapDuration, str(userID), lapDuration,))
            result = cur.fetchall()
            if result is None:
                return 0
            else:
                return len(result)
    except Exception as e:
        print(e)
    finally:
        conn.close()


async def sql_send_tip(user_from: str, user_to: str, amount: int, coin: str = None):
    global conn
    if coin is None:
        coin = "WRKZ"
    else:
        coin = coin.upper()
    user_from_wallet = None
    user_to_wallet = None
    address_to = None
    #print('sql_send_tip')
    if coin.upper() in ENABLE_COIN:
        user_from_wallet = await sql_get_userwallet(user_from, coin.upper())
        user_to_wallet = await sql_get_userwallet(user_to, coin.upper())
        if (user_to_wallet['forwardtip'] == "ON") and ('user_wallet_address' in user_to_wallet):
            address_to = user_to_wallet['user_wallet_address']
        else:
            address_to = user_to_wallet['balance_wallet_address']
    if all(v is not None for v in [user_from_wallet['balance_wallet_address'], address_to]):
        tx_hash = None
        if coin.upper() in ENABLE_COIN:
            tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'],
                                                    address_to, amount, coin.upper())
        if tx_hash:
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    sql = None
                    if coin.upper() in ENABLE_COIN:
                        sql = """ INSERT INTO """+coin.lower()+"""_tip (`from_user`, `to_user`, `amount`, `date`, `tx_hash`) 
                                  VALUES (%s, %s, %s, %s, %s) """
                        cur.execute(sql, (user_from, user_to, amount, timestamp, tx_hash,))
                        conn.commit()
                    updateBalance = None
                    if coin.upper() in ENABLE_COIN:
                        updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'],
                                                                         coin.upper())
                    if updateBalance:
                        if coin.upper() in ENABLE_COIN:
                            sql = """ UPDATE """+coin.lower()+"""_walletapi SET `actual_balance`=%s, `locked_balance`=%s, 
                                      `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                            cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'],
                                              updateTime, user_from_wallet['balance_wallet_address'],))
                            conn.commit()
                            updateBalance = await wallet.get_balance_address(user_to_wallet['balance_wallet_address'],
                                                                             coin.upper())
                    if updateBalance:
                        if coin.upper() in ENABLE_COIN:
                            sql = """ UPDATE """+coin.lower()+"""_walletapi SET `actual_balance`=%s, 
                                      `locked_balance`=%s, `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                            cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'],
                                        updateTime, user_to_wallet['balance_wallet_address'],))
                            conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
        return tx_hash
    else:
        return None


async def sql_send_tipall(user_from: str, user_tos, amount: int, amount_div: int, user_ids, tiptype: str, coin: str = None):
    global conn
    if tiptype.upper() not in ["TIPS", "TIPALL"]:
        return None
    if coin is None:
        coin = "WRKZ"
    else:
        coin = coin.upper()
    user_from_wallet = None
    if coin.upper() in ENABLE_COIN:
        user_from_wallet = await sql_get_userwallet(user_from, coin.upper())
    if 'balance_wallet_address' in user_from_wallet:
        tx_hash = None
        if coin.upper() in ENABLE_COIN:
            tx_hash = await wallet.send_transactionall(user_from_wallet['balance_wallet_address'], user_tos, coin.upper())
            print('tx_hash: ')
            print(tx_hash)
        if tx_hash:
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    if coin.upper() in ENABLE_COIN:
                        sql = """ INSERT INTO """+coin.lower()+"""_tipall (`from_user`, `amount_total`, `date`, `tx_hash`, `numb_receivers`) 
                                  VALUES (%s, %s, %s, %s, %s) """
                        cur.execute(sql, (user_from, amount, timestamp, tx_hash, len(user_tos),))
                        conn.commit()

                        values_str = []
                        for item in user_ids:
                            values_str.append(f"('{user_from}', '{item}', {amount_div}, {timestamp}, '{tx_hash}', '{tiptype.upper()}')\n")
                        values_sql = "VALUES " + ",".join(values_str)
                        print(values_sql)
                        sql = """ INSERT INTO """+coin.lower()+"""_tip (`from_user`, `to_user`, `amount`, `date`, `tx_hash`, `tip_tips_tipall`) 
                                  """+values_sql+""" """
                        cur.execute(sql,)
                        conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
        return tx_hash
    else:
        return None


async def sql_send_tip_Ex(user_from: str, address_to: str, amount: int, coin: str = None):
    global conn
    if coin is None:
        coin = "WRKZ"
    else:
        coin = coin.upper()
    user_from_wallet = None
    if coin.upper() in ENABLE_COIN:
        user_from_wallet = await sql_get_userwallet(user_from, coin.upper())
    if 'balance_wallet_address' in user_from_wallet:
        tx_hash = None
        if coin.upper() in ENABLE_COIN:
            tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'], address_to, 
                                                    amount, coin.upper())
        if tx_hash is not None:
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    updateBalance = None
                    if coin.upper() in ENABLE_COIN:
                        sql = """ INSERT INTO """+coin.lower()+"""_send (`from_user`, `to_address`, `amount`, `date`, 
                                  `tx_hash`) VALUES (%s, %s, %s, %s, %s) """
                        cur.execute(sql, (user_from, address_to, amount, timestamp, tx_hash,))
                        conn.commit()
                        updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], 
                                                                      coin.upper())
                    if updateBalance:
                        if coin.upper() in ENABLE_COIN:
                            sql = """ UPDATE """+coin.lower()+"""_walletapi SET `actual_balance`=%s, 
                                      `locked_balance`=%s, `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                            cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'],
                                        updateTime, user_from_wallet['balance_wallet_address'],))
                            conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
        return tx_hash
    else:
        return None


async def sql_send_tip_Ex_id(user_from: str, address_to: str, amount: int, paymentid, coin: str = None):
    global conn
    if coin is None:
        coin = "WRKZ"
    else:
        coin = coin.upper()
    user_from_wallet = None
    if coin.upper() in ENABLE_COIN:
        user_from_wallet = await sql_get_userwallet(user_from, coin.upper())
    if 'balance_wallet_address' in user_from_wallet:
        tx_hash = None
        if coin.upper() in ENABLE_COIN:
            tx_hash = await wallet.send_transaction_id(user_from_wallet['balance_wallet_address'], address_to,
                                                       amount, paymentid, coin.upper())
        if tx_hash:
            updateTime = int(time.time())
            try:
                openConnection()
                updateBalance = None
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    if coin.upper() in ENABLE_COIN:
                        sql = """ INSERT INTO """+coin.lower()+"""_send (`from_user`, `to_address`, `amount`, `date`, 
                                  `tx_hash`, `paymentid`) VALUES (%s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (user_from, address_to, amount, timestamp, tx_hash, paymentid, ))
                        conn.commit()
                        updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], coin.upper())
                    if updateBalance:
                        if coin.upper() in ENABLE_COIN:
                            sql = """ UPDATE """+coin.lower()+"""_walletapi SET `actual_balance`=%s, 
                                      `locked_balance`=%s, `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                            cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'], 
                                        updateTime, user_from_wallet['balance_wallet_address'],))
                            conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
        return tx_hash
    else:
        return None


async def sql_withdraw(user_from: str, amount: int, coin: str=None):
    global conn
    if coin is None:
        coin = "WRKZ"
    tx_hash = None
    user_from_wallet = None
    if coin.upper() in ENABLE_COIN:
        user_from_wallet = await sql_get_userwallet(user_from, coin.upper())
    if all(v is not None for v in [user_from_wallet['balance_wallet_address'], user_from_wallet['user_wallet_address']]):
        if coin.upper() in ENABLE_COIN:
            tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'],
                                                    user_from_wallet['user_wallet_address'], amount, coin.upper())
        if tx_hash:
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    updateBalance = None
                    if coin.upper() in ENABLE_COIN:
                        sql = """ INSERT INTO """+coin.lower()+"""_withdraw (`user_id`, `to_address`, `amount`, 
                                  `date`, `tx_hash`) VALUES (%s, %s, %s, %s, %s) """
                        cur.execute(sql, (user_from, user_from_wallet['user_wallet_address'], amount, timestamp, tx_hash,))
                        conn.commit()
                        updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], coin.upper())
                    if updateBalance:
                        if coin.upper() in ENABLE_COIN:
                            sql = """ UPDATE """+coin.lower()+"""_walletapi SET `actual_balance`=%s, 
                                      `locked_balance`=%s, `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                            cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'], 
                                        updateTime, user_from_wallet['balance_wallet_address'],))
                            conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
        return tx_hash
    else:
        return None


async def sql_donate(user_from: str, address_to: str, amount: int, coin: str = None) -> str:
    global conn
    if coin is None:
        coin = "WRKZ"
    else:
        coin = coin.upper()
    user_from_wallet = None
    if coin.upper() in ENABLE_COIN:
        user_from_wallet = await sql_get_userwallet(user_from, coin.upper())
    if all(v is not None for v in [user_from_wallet['balance_wallet_address'], address_to]):
        tx_hash = None
        if coin.upper() in ENABLE_COIN:
            tx_hash = await wallet.send_transaction_donate(user_from_wallet['balance_wallet_address'], address_to, amount, coin.upper())
        if tx_hash is not None:
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    updateBalance = None
                    if coin.upper() in ENABLE_COIN:
                        sql = """ INSERT INTO """+coin.lower()+"""_donate (`from_user`, `to_address`, `amount`, 
                                  `date`, `tx_hash`) VALUES (%s, %s, %s, %s, %s) """
                        cur.execute(sql, (user_from, address_to, amount, timestamp, tx_hash,))
                        conn.commit()
                        updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], coin.upper())
                    if updateBalance:
                        if coin.upper() in ENABLE_COIN:
                            sql = """ UPDATE """+coin.lower()+"""_walletapi SET `actual_balance`=%s, 
                                      `locked_balance`=%s, `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                            cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'], 
                                        updateTime, user_from_wallet['balance_wallet_address'],))
                            conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
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
                sql = """ SELECT SUM(amount) FROM """+coin.lower()+"""_donate"""
                cur.execute(sql,)
                result = cur.fetchone()
                if result is None:
                    donate_list[coin] = 0
                else:
                    donate_list[coin] = result[0]
            # DOGE
            coin = "DOGE"
            sql = """ SELECT SUM(amount) FROM """+coin.lower()+"""_mv_tx WHERE `type`='DONATE' AND `to_userid`='DogeDonateWrkz' """
            cur.execute(sql,)
            result = cur.fetchone()
            if result is None:
                donate_list[coin] = 0
            else:
                donate_list[coin] = result[0]
        return donate_list
    except Exception as e:
        print(e)
    finally:
        conn.close()


def sql_optimize_check(coin: str = None):
    global conn
    if coin is None:
        coin = "WRKZ"
    try:
        openConnection()
        with conn.cursor() as cur:
            timeNow = int(time.time()) - 600
            if coin.upper() in ENABLE_COIN:
                sql = """ SELECT COUNT(*) FROM """+coin.lower()+"""_user WHERE lastOptimize>%s """
                cur.execute(sql, timeNow, )
                result = cur.fetchone()
                return result[0]
    except Exception as e:
        print(e)
    finally:
        conn.close()


async def sql_optimize_do(userID: str, coin: str = None):
    global conn
    if coin is None:
        coin = "WRKZ"
    else:
        coin = coin.upper()
    user_from_wallet = None
    if coin.upper() in ENABLE_COIN:
        user_from_wallet = await sql_get_userwallet(userID, coin.upper())
    #print('store.check estimation fusion first: ' + coin.upper())
    estimate = await wallet.wallet_estimate_fusion(user_from_wallet['balance_wallet_address'], 
                                             user_from_wallet['actual_balance'], coin.upper())
    if estimate:
        if 'fusionReadyCount' in estimate:
            print('fusionReadyCount: '+ str(estimate['fusionReadyCount']))
            print('totalOutputCount: '+ str(estimate['totalOutputCount']))
            if estimate['fusionReadyCount'] == 0:
                return 0
    else:
        print('fusionReadyCount check error.')
        return 0

    print('store.sql_optimize_do: ' + coin.upper())
    if user_from_wallet:
        OptimizeCount = 0
        if coin.upper() in ENABLE_COIN:
            OptimizeCount = await wallet.wallet_optimize_single(user_from_wallet['balance_wallet_address'], 
                                                          int(user_from_wallet['actual_balance']), coin.upper())
        # in case failed for some reason, reduce threshold
        if estimate['fusionReadyCount'] >= 2 and OptimizeCount == 0:
            OptimizeCount = await wallet.wallet_optimize_single(user_from_wallet['balance_wallet_address'], 
                                                          int(round(user_from_wallet['actual_balance']/2)), coin.upper())        
        if OptimizeCount > 0:
            updateTime = int(time.time())
            if coin.upper() in ENABLE_COIN:
                sql_optimize_update(str(userID), coin.upper())
            try:
                openConnection()
                with conn.cursor() as cur:
                    updateBalance = None
                    if coin.upper() in ENABLE_COIN:
                        updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], coin.upper())
                    if updateBalance:
                        sql = None
                        if coin.upper() in ENABLE_COIN:
                            sql = """ UPDATE """+coin.lower()+"""_walletapi SET `actual_balance`=%s, 
                                     `locked_balance`=%s, `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                        cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'], 
                                    updateTime, user_from_wallet['balance_wallet_address'],))
                        conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
        return OptimizeCount


def sql_optimize_update(userID: str, coin: str = None):
    global conn
    if coin is None:
        coin = "WRKZ"
    try:
        openConnection()
        with conn.cursor() as cur:
            timeNow = int(time.time())
            if coin.upper() in ENABLE_COIN:
                sql = """ UPDATE """+coin.lower()+"""_user SET `lastOptimize`=%s WHERE `user_id`=%s LIMIT 1 """
                cur.execute(sql, (timeNow, str(userID),))
                conn.commit()
    except Exception as e:
        print(e)
    finally:
        conn.close()


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
            estimate = await wallet.wallet_estimate_fusion(address['address'], address['unlocked'], coin.upper())
            if estimate:
                if 'fusionReadyCount' in estimate:
                    #print('fusionReadyCount: '+ str(estimate['fusionReadyCount']))
                    #print('totalOutputCount: '+ str(estimate['totalOutputCount']))
                    if estimate['fusionReadyCount'] >= 2:
                        print(f'Optimize {coin.upper()}: ' + address['address'])
                        OptimizeCount = 0
                        try:
                            OptimizeCount = await wallet.wallet_optimize_single(address['address'], int(round(address['unlocked']/2)), coin.upper())
                        except Exception as e:
                            print(e)
                        if OptimizeCount > 0:
                            AccumOpt = AccumOpt + 1
                        if AccumOpt >= opt_num:
                            break
                        return AccumOpt
    return None


async def sql_send_to_voucher(user_id: str, user_name: str, message_creating: str, amount: int, reserved_fee: int, secret_string: str, voucher_image_name: str, coin: str = None):
    global conn
    if coin is None:
        coin = "WRKZ"
    else:
        coin = coin.upper()
    user_from_wallet = None
    if coin.upper() in ENABLE_COIN:
        user_from_wallet = await sql_get_userwallet(user_id, coin.upper())
    if 'balance_wallet_address' in user_from_wallet:
        tx_hash = None
        if coin.upper() in ENABLE_COIN:
            tx_hash = await wallet.send_transaction(user_from_wallet['balance_wallet_address'], wallet.get_voucher_address(coin.upper()), 
                                                    amount + reserved_fee, coin.upper())
        if tx_hash:
            try:
                openConnection()
                with conn.cursor() as cur:
                    timestamp = int(time.time())
                    updateBalance = None
                    if coin.upper() in ENABLE_COIN:
                        sql = """ INSERT INTO """+coin.lower()+"""_voucher (`user_id`, `user_name`, `message_creating`, `amount`, 
                                  `reserved_fee`, `date_create`, `secret_string`, `voucher_image_name`, `tx_hash_deposit`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        cur.execute(sql, (user_id, user_name, message_creating, amount, reserved_fee, int(time.time()), secret_string, voucher_image_name, tx_hash,))
                        conn.commit()
                        updateBalance = await wallet.get_balance_address(user_from_wallet['balance_wallet_address'], 
                                                                         coin.upper())
                    if updateBalance:
                        if coin.upper() in ENABLE_COIN:
                            sql = """ UPDATE """+coin.lower()+"""_walletapi SET `actual_balance`=%s, 
                                      `locked_balance`=%s, `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                            cur.execute(sql, (updateBalance['unlocked'], updateBalance['locked'],
                                        int(time.time()), user_from_wallet['balance_wallet_address'],))
                            conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
        return tx_hash
    else:
        return None


def sql_tag_by_server(server_id: str, tag_id: str = None):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            if tag_id is None: 
                sql = """ SELECT tag_id, tag_desc, date_added, tag_serverid, added_byname, 
                          added_byuid, num_trigger FROM wrkz_tag WHERE tag_serverid = %s """
                cur.execute(sql, (server_id,))
                result = cur.fetchall()
                tag_list = []
                for row in result:
                    tag_list.append({'tag_id':row[0], 'tag_desc':row[1], 'date_added':row[2], 'tag_serverid':row[3],
                                     'added_byname':row[4], 'added_byuid':row[5], 'num_trigger':row[6]})
                return tag_list
            else:
                sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, 
                          `added_byuid`, `num_trigger` FROM wrkz_tag WHERE tag_serverid = %s AND tag_id=%s """
                cur.execute(sql, (server_id, tag_id,))
                result = cur.fetchone()
                if result:
                    tag = {}
                    tag['tag_id'] = result[0]
                    tag['tag_desc'] = result[1]
                    tag['date_added'] = result[2]
                    tag['tag_serverid'] = result[3]
                    tag['added_byname'] = result[4]
                    tag['added_byuid'] = result[5]
                    tag['num_trigger'] = result[6]
                    sql = """ UPDATE wrkz_tag SET num_trigger=num_trigger+1 WHERE tag_serverid = %s AND tag_id=%s """
                    cur.execute(sql, (server_id, tag_id,))
                    conn.commit()
                    return tag
    except Exception as e:
        print(e)
    finally:
        conn.close()


def sql_tag_by_server_add(server_id: str, tag_id: str, tag_desc: str, added_byname: str, added_byuid: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT COUNT(tag_serverid) FROM wrkz_tag WHERE tag_serverid=%s """
            cur.execute(sql, (server_id,))
            counting = cur.fetchone()
            if counting:
                if counting[0] > 50:
                    return None
            sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, `added_byuid`, 
                      `num_trigger` 
                      FROM wrkz_tag WHERE tag_serverid = %s AND tag_id=%s """
            cur.execute(sql, (server_id, tag_id.upper(),))
            result = cur.fetchone()
            if result is None:
                sql = """ INSERT INTO wrkz_tag (`tag_id`, `tag_desc`, `date_added`, `tag_serverid`, 
                          `added_byname`, `added_byuid`) 
                          VALUES (%s, %s, %s, %s, %s, %s) """
                cur.execute(sql, (tag_id.upper(), tag_desc, int(time.time()), server_id, added_byname, added_byuid,))
                conn.commit()
                return tag_id.upper()
            else:
                return None
    except Exception as e:
        print(e)
    finally:
        conn.close()


def sql_tag_by_server_del(server_id: str, tag_id: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, 
                      `added_byuid`, `num_trigger` 
                      FROM wrkz_tag WHERE tag_serverid = %s AND tag_id=%s """
            cur.execute(sql, (server_id, tag_id.upper(),))
            result = cur.fetchone()
            if result is None:
                return None
            else:
                sql = """ DELETE FROM wrkz_tag WHERE `tag_id`=%s AND `tag_serverid`=%s """
                cur.execute(sql, (tag_id.upper(), server_id,))
                conn.commit()
                return tag_id.upper()
    except Exception as e:
        print(e)
    finally:
        conn.close()


def sql_info_by_server(server_id: str):
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
                serverinfo = {}
                serverinfo["serverid"] = result[0]
                serverinfo["servername"] = result[1]
                serverinfo["prefix"] = result[2]
                serverinfo["default_coin"] = result[3]
                serverinfo["numb_user"] = result[4]
                serverinfo["numb_bot"] = result[5]
                serverinfo["tiponly"] = result[6]
                return serverinfo
    except Exception as e:
        print(e)
    finally:
        conn.close()


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
        print(e)
    finally:
        conn.close()


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
        print(e)
    finally:
        conn.close()


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
                    if int(item[0]) not in list_talker:
                        list_talker.append(int(item[0]))
            return list_talker
    except Exception as e:
        print(e)
    finally:
        conn.close()
    return None


def sql_changeinfo_by_server(server_id: str, what: str, value: str):
    global conn
    if what.lower() in ["servername", "prefix", "default_coin", "tiponly"]:
        try:
            #print(f"ok try to change {what} to {value}")
            openConnection()
            with conn.cursor() as cur:
                sql = """ UPDATE discord_server SET `""" + what.lower() + """` = %s WHERE `serverid` = %s """
                cur.execute(sql, (value, server_id,))
                conn.commit()
        except Exception as e:
            print(e)
        finally:
            conn.close()


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
        print(e)
    finally:
        conn.close()


def sql_delignorechan_by_server(server_id: str, ignorechan: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ DELETE FROM `discord_ignorechan` WHERE `serverid` = %s AND `ignorechan` = %s """
            cur.execute(sql, (server_id, ignorechan,))
            conn.commit()
    except Exception as e:
        print(e)
    finally:
        conn.close()


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
                    if str(row[0]) in ignore_chan:
                        ignore_chan[str(row[0])].append(str(row[1]))
                    else:
                        ignore_chan[str(row[0])] = []
                        ignore_chan[str(row[0])].append(str(row[1]))
                return ignore_chan
    except Exception as e:
        print(e)
    finally:
        conn.close()
    return None


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
                ignorelist.append(row[0])
            return ignorelist
    except Exception as e:
        print(e)
    finally:
        conn.close()


def sql_toggle_tipnotify(user_id: str, onoff: str):
    # Bot will add user_id if it failed to DM
    global conn
    onoff = onoff.upper()
    if onoff == "OFF":
        try:
            openConnection()
            with conn.cursor() as cur:
                sql = """ INSERT IGNORE INTO `bot_tipnotify_user` (`user_id`, `date`)
                          VALUES (%s, %s) """
                cur.execute(sql, (user_id, int(time.time())))
                conn.commit()
        except Exception as e:
            print(e)
        finally:
            conn.close()
    elif onoff == "ON":
        try:
            openConnection()
            with conn.cursor() as cur:
                sql = """ DELETE FROM `bot_tipnotify_user` WHERE `user_id` = %s """
                cur.execute(sql, str(user_id))
                conn.commit()
        except Exception as e:
            print(e)
        finally:
            conn.close()


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
        print(e)
    finally:
        conn.close()


def sql_mv_doge_single(user_from: str, to_user: str, amount: float, coin: str, tiptype: str):
    global conn
    if coin.upper() not in ENABLE_COIN_DOGE:
        return False
    if tiptype.upper() not in ["TIP", "DONATE"]:
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
        print(e)
    finally:
        conn.close()
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
        print(e)
    finally:
        conn.close()
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
        #print(txHash)
        with conn.cursor() as cur: 
            sql = """ INSERT INTO """+coin.lower()+"""_external_tx (`user_id`, `amount`, `fee`, `to_address`, 
                      `type`, `date`, `tx_hash`) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
            cur.execute(sql, (user_from, amount, fee, to_address, tiptype.upper(), int(time.time()), txHash,))
            conn.commit()
        return txHash
    except Exception as e:
        print(e)
    finally:
        conn.close()
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
                Expense = result[0]
            else:
                Expense = 0

            sql = """ SELECT SUM(amount) AS Income FROM """+coin.lower()+"""_mv_tx WHERE `to_userid`=%s """
            cur.execute(sql, userID)
            result = cur.fetchone()
            if result:
                Income = result[0]
            else:
                Income = 0

            sql = """ SELECT SUM(amount) AS TxExpense FROM """+coin.lower()+"""_external_tx WHERE `user_id`=%s """
            cur.execute(sql, userID)
            result = cur.fetchone()
            if result:
                TxExpense = result[0]
            else:
                TxExpense = 0

            sql = """ SELECT SUM(fee) AS FeeExpense FROM """+coin.lower()+"""_external_tx WHERE `user_id`=%s """
            cur.execute(sql, userID)
            result = cur.fetchone()
            if result:
                FeeExpense = result[0]
            else:
                FeeExpense = 0

            balance = {}
            balance['Expense'] = Expense or 0
            balance['Expense'] = round(balance['Expense'], 4)
            balance['Income'] = Income or 0
            balance['TxExpense'] = TxExpense or 0
            balance['FeeExpense'] = FeeExpense or 0
            #print(balance)
            balance['Adjust'] = float(balance['Income']) - float(balance['Expense']) - float(balance['TxExpense']) - float(balance['FeeExpense'])
            #print(balance['Adjust'])
            return balance
    except Exception as e:
        print(e)
    finally:
        conn.close()
    return False


def sql_set_forwardtip(userID: str, coin: str, option: str):
    global conn
    if option.upper() not in ["ON", "OFF"]:
        return None
    if coin.upper() in ENABLE_COIN:
        try:
            openConnection()
            with conn.cursor() as cur: 
                sql = """ UPDATE """+coin.lower()+"""_user SET forwardtip='"""+option.upper()+"""' WHERE user_id=%s """
                cur.execute(sql, (str(userID),))
                conn.commit()
        except Exception as e:
            print(e)
        finally:
            conn.close()


def sql_get_nodeinfo():
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT `url`, `fee`, `lastUpdate`, `alt_blocks_count`, `difficulty`, `incoming_connections_count`,
                  `last_known_block_index`, `network_height`, `outgoing_connections_count`, `start_time`, `tx_count`, 
                  `tx_pool_size`,
                  `version`, `white_peerlist_size`, `synced`, `height` FROM wrkz_nodes """
            cur.execute(sql,)
            result = cur.fetchall()
            return result
    except Exception as e:
        print(e)
    finally:
        conn.close()


def sql_get_poolinfo():
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT `name`, `url_api`, `fee`, `minPaymentThreshold`, `pool_stats_lastBlockFound`, 
                  `pool_stats_totalBlocks`,
                  `pool_totalMinersPaid`, `pool_totalPayments`, `pool_payment_last`, `pool_miners`, `pool_hashrate`, 
                  `net_difficulty`,
                  `net_height`, `net_timestamp`, `net_reward`, `net_hash`, `lastUpdate`, `pool_blocks_last` 
                  FROM wrkz_pools """
            cur.execute(sql,)
            result = cur.fetchall()
            return result
    except Exception as e:
        print(e)
    finally:
        conn.close()


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
