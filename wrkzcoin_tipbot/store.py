from typing import List
from datetime import datetime
import time
import json

import sys
sys.path.append("..")
import wallet, daemonrpc_client
from config import config

# MySQL
import pymysql
conn = None

## OpenConnection
def openConnection():
    global conn
    try:
        if(conn is None):
            conn = pymysql.connect(config.mysql.host, user=config.mysql.user, passwd=config.mysql.password, db=config.mysql.db, connect_timeout=5)
        elif (not conn.open):
            conn = pymysql.connect(config.mysql.host, user=config.mysql.user, passwd=config.mysql.password, db=config.mysql.db, connect_timeout=5)
    except:
        print("ERROR: Unexpected error: Could not connect to MySql wrkz instance.")
        sys.exit()

def sql_update_balances():
    print('SQL: Updating all wallet balances')
    balances = wallet.get_all_balances_all()
    updateTime = int(time.time())
    try:
        openConnection()
        with conn.cursor() as cur:
            for details in balances:
                #print(details)
                sql = """ INSERT INTO wrkz_walletapi (`balance_wallet_address`, `actual_balance`, `locked_balance`, `lastUpdate`) 
                          VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE `actual_balance`=%s, `locked_balance`=%s, `lastUpdate`=%s """
                cur.execute(sql, (details['address'], details['unlocked'], details['locked'], updateTime, details['unlocked'], details['locked'], updateTime,))
                conn.commit()
    except Exception as e:
        print(e)
    finally:
        conn.close()

def sql_update_some_balances(wallet_addresses: List[str]):
    print('SQL: Updating some wallet balances')
    balances = wallet.get_some_balances(wallet_addresses)
    updateTime = int(time.time())
    try:
        openConnection()
        with conn.cursor() as cur:
            for details in balances:
                #print(details)
                sql = """ INSERT INTO wrkz_walletapi (`balance_wallet_address`, `actual_balance`, `locked_balance`, `lastUpdate`) 
                          VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE `actual_balance`=%s, `locked_balance`=%s, `lastUpdate`=%s """
                cur.execute(sql, (details['address'], details['unlocked'], details['locked'], updateTime, details['unlocked'], details['locked'], updateTime,))
                conn.commit()
    except Exception as e:
        print(e)
    finally:
        conn.close()

def sql_register_user(userID):
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT user_id, balance_wallet_address, user_wallet_address FROM wrkz_user WHERE `user_id`=%s LIMIT 1 """
            cur.execute(sql, (userID))
            result = cur.fetchone()
            if (result is None):
                ##
                balance_address = wallet.register()
                if (balance_address is None):
                   print('Internal error during call register wallet-api')
                   return
                else:
                   ##
                   walletStatus = daemonrpc_client.getWalletStatus()
                   print(walletStatus)
                   if (walletStatus is None):
                       print('Can not reach wallet-api during sql_register_user')
                       chainHeight = 0
                   else:
                       chainHeight = int(walletStatus['blockCount']) ## reserve 20
                   sql = """ INSERT INTO wrkz_user (`user_id`, `balance_wallet_address`, `balance_wallet_address_ts`, `balance_wallet_address_ch`, `privateSpendKey`) 
                             VALUES (%s, %s, %s, %s, %s) """
                   cur.execute(sql, (str(userID), balance_address['address'], int(time.time()), chainHeight, balance_address['privateSpendKey'], ))
                   conn.commit()
                   result2 = {}
                   result2['balance_wallet_address'] = balance_address
                   result2['user_wallet_address'] = ''
                   ## TODO need to save wallet.
                   #wallet.save_walletapi()
                   return result2
            else:
                ##
                result2 = {}
                result2['user_id'] = result[0]
                result2['balance_wallet_address'] = result[1]
                if (2 in result):
                    result2['user_wallet_address'] = result[2]
                return result2
    except Exception as e:
        print(e)
    finally:
        conn.close()

def sql_update_user(userID, user_wallet_address):
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT user_id, user_wallet_address, balance_wallet_address FROM wrkz_user WHERE `user_id`=%s LIMIT 1 """
            cur.execute(sql, (userID))
            result = cur.fetchone()
            if (result is None):
                balance_address = wallet.register()
                if (balance_address is None):
                   print('Internal error during call register wallet-api')
                   return
            else:
                sql = """ UPDATE wrkz_user SET user_wallet_address=%s WHERE user_id=%s """
                cur.execute(sql, (user_wallet_address, str(userID),))
                conn.commit()
                result2 = {}
                result2['balance_wallet_address'] = result[2]
                result2['user_wallet_address'] = user_wallet_address
                print('.register...'+result2)
                return result2 ## return userwallet
    except Exception as e:
        print(e)
    finally:
        conn.close()

def sql_get_userwallet(userID):
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT user_id, balance_wallet_address, user_wallet_address, balance_wallet_address_ts, balance_wallet_address_ch, lastOptimize 
                      FROM wrkz_user WHERE `user_id`=%s LIMIT 1 """
            cur.execute(sql, (str(userID),))
            result = cur.fetchone()
            if (result is None):
                return None
            else:
                ##
                userwallet = {}
                userwallet['balance_wallet_address'] = result[1]
                if(result[2] is not None):
                    userwallet['user_wallet_address'] = result[2]
                if(result[3] is not None):
                    userwallet['balance_wallet_address_ts'] = result[3]
                if(result[4] is not None):
                    userwallet['balance_wallet_address_ch'] = result[4]
                if(result[5] is not None):
                    userwallet['lastOptimize'] = result[5]
                sql = """ SELECT balance_wallet_address, actual_balance, locked_balance, lastUpdate FROM wrkz_walletapi 
                          WHERE `balance_wallet_address`=%s LIMIT 1 """
                cur.execute(sql, (userwallet['balance_wallet_address'],))
                result2 = cur.fetchone()
                if (result2 is not None):
                    userwallet['actual_balance'] = int(result2[1])
                    userwallet['locked_balance'] = int(result2[2])
                    userwallet['lastUpdate'] = int(result2[3])
                else:
                    userwallet['actual_balance'] = 0
                    userwallet['locked_balance'] = 0
                return userwallet
    except Exception as e:
        print(e)
    finally:
        conn.close()

def sql_get_countLastTip(userID, lastDuration: int):
    lapDuration = int(time.time()) - lastDuration
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ (SELECT `from_user`,`amount`,`date` FROM wrkz_tip WHERE `from_user` = %s AND `date`>%s )
                      UNION
                      (SELECT `from_user`,`amount_total`,`date` FROM wrkz_tipall WHERE `from_user` = %s AND `date`>%s )
                      UNION
                      (SELECT `from_user`,`amount`,`date` FROM wrkz_send WHERE `from_user` = %s AND `date`>%s )
                      UNION
                      (SELECT `user_id`,`amount`,`date` FROM wrkz_withdraw WHERE `user_id` = %s AND `date`>%s )
                      UNION
                      (SELECT `from_user`,`amount`,`date` FROM wrkz_donate WHERE `from_user` = %s AND `date`>%s )
                      ORDER BY `date` DESC LIMIT 10 """
            cur.execute(sql, (str(userID), lapDuration, str(userID), lapDuration, str(userID), lapDuration, str(userID), lapDuration, str(userID), lapDuration,))
            result = cur.fetchall()
            if (result is None):
                return 0
            else:
                return len(result)
    except Exception as e:
        print(e)
    finally:
        conn.close()

def sql_send_tip(user_from: str, user_to: str, amount: int):
    user_from_wallet = sql_get_userwallet(user_from)
    user_to_wallet = sql_get_userwallet(user_to)
    if all(v is not None for v in [user_from_wallet['balance_wallet_address'], user_to_wallet['balance_wallet_address']]):
        tx_hash = wallet.send_transaction(user_from_wallet['balance_wallet_address'],
                      user_to_wallet['balance_wallet_address'], amount)
        if (tx_hash is not None):
            ## add to MySQL
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                   timestamp = int(time.time())
                   sql = """ INSERT INTO wrkz_tip (`from_user`, `to_user`, `amount`, `date`, `tx_hash`) VALUES (%s, %s, %s, %s, %s) """
                   cur.execute(sql, (user_from, user_to, amount, timestamp, tx_hash,))
                   conn.commit()
                   updateBalance = wallet.get_balance_address(user_from_wallet['balance_wallet_address'])
                   if (updateBalance):
                       sql = """ UPDATE wrkz_walletapi SET `actual_balance`=%s, `locked_balance`=%s, `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                       cur.execute(sql, (updateBalance['availableBalance'], updateBalance['lockedAmount'], updateTime, user_from_wallet['balance_wallet_address'],))
                       conn.commit()
                   updateBalance = wallet.get_balance_address(user_to_wallet['balance_wallet_address'])
                   if (updateBalance):
                       sql = """ UPDATE wrkz_walletapi SET `actual_balance`=%s, `locked_balance`=%s, `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                       cur.execute(sql, (updateBalance['availableBalance'], updateBalance['lockedAmount'], updateTime, user_to_wallet['balance_wallet_address'],))
                       conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
        return tx_hash
    else:
        return None

def sql_send_tipall(user_from: str, user_tos, amount: int):
    user_from_wallet = sql_get_userwallet(user_from)
    if ('balance_wallet_address' in user_from_wallet):
        tx_hash = wallet.send_transactionall(user_from_wallet['balance_wallet_address'], user_tos)
        if (tx_hash is not None):
            ## add to MySQL
            try:
                openConnection()
                with conn.cursor() as cur:
                   timestamp = int(time.time())
                   sql = """ INSERT INTO wrkz_tipall (`from_user`, `amount_total`, `date`, `tx_hash`) VALUES (%s, %s, %s, %s) """
                   cur.execute(sql, (user_from, amount, timestamp, tx_hash,))
                   conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
        return tx_hash
    else:
        return None

def sql_send_tip_Ex(user_from: str, address_to: str, amount: int):
    user_from_wallet = sql_get_userwallet(user_from)
    if ('balance_wallet_address' in user_from_wallet):
        tx_hash = wallet.send_transaction(user_from_wallet['balance_wallet_address'], address_to, amount)
        if (tx_hash is not None):
            ## add to MySQL
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                   timestamp = int(time.time())
                   sql = """ INSERT INTO wrkz_send (`from_user`, `to_address`, `amount`, `date`, `tx_hash`) VALUES (%s, %s, %s, %s, %s) """
                   cur.execute(sql, (user_from, address_to, amount, timestamp, tx_hash,))
                   conn.commit()
                   updateBalance = wallet.get_balance_address(user_from_wallet['balance_wallet_address'])
                   if (updateBalance):
                       sql = """ UPDATE wrkz_walletapi SET `actual_balance`=%s, `locked_balance`=%s, `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                       cur.execute(sql, (updateBalance['availableBalance'], updateBalance['lockedAmount'], updateTime, user_from_wallet['balance_wallet_address'],))
                       conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
        return tx_hash
    else:
        return None

def sql_send_tip_Ex_id(user_from: str, address_to: str, amount: int, paymentid):
    user_from_wallet = sql_get_userwallet(user_from)
    if ('balance_wallet_address' in user_from_wallet):
        tx_hash = wallet.send_transaction_id(user_from_wallet['balance_wallet_address'], address_to, amount, paymentid)
        if (tx_hash is not None):
            ## add to MySQL
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                   timestamp = int(time.time())
                   sql = """ INSERT INTO wrkz_send (`from_user`, `to_address`, `amount`, `date`, `tx_hash`, `paymentid`) VALUES (%s, %s, %s, %s, %s, %s) """
                   cur.execute(sql, (user_from, address_to, amount, timestamp, tx_hash, paymentid, ))
                   conn.commit()
                   updateBalance = wallet.get_balance_address(user_from_wallet['balance_wallet_address'])
                   if (updateBalance):
                       sql = """ UPDATE wrkz_walletapi SET `actual_balance`=%s, `locked_balance`=%s, `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                       cur.execute(sql, (updateBalance['availableBalance'], updateBalance['lockedAmount'], updateTime, user_from_wallet['balance_wallet_address'],))
                       conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
        return tx_hash
    else:
        return None

def sql_withdraw(user_from: str, amount: int):
    user_from_wallet = sql_get_userwallet(user_from)
    if all(v is not None for v in [user_from_wallet['balance_wallet_address'], user_from_wallet['user_wallet_address']]):
        tx_hash = wallet.send_transaction(user_from_wallet['balance_wallet_address'], user_from_wallet['user_wallet_address'], amount)
        if (tx_hash is not None):
            ## add to MySQL
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                   timestamp = int(time.time())
                   sql = """ INSERT INTO wrkz_withdraw (`user_id`, `to_address`, `amount`, `date`, `tx_hash`) VALUES (%s, %s, %s, %s, %s) """
                   cur.execute(sql, (user_from, user_from_wallet['user_wallet_address'], amount, timestamp, tx_hash,))
                   conn.commit()
                   updateBalance = wallet.get_balance_address(user_from_wallet['balance_wallet_address'])
                   if (updateBalance):
                       sql = """ UPDATE wrkz_walletapi SET `actual_balance`=%s, `locked_balance`=%s, `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                       cur.execute(sql, (updateBalance['availableBalance'], updateBalance['lockedAmount'], updateTime, user_from_wallet['balance_wallet_address'],))
                       conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
        return tx_hash
    else:
        return None

def sql_donate(user_from: str, address_to: str, amount: int) -> str:
    user_from_wallet = sql_get_userwallet(user_from)
    if all(v is not None for v in [user_from_wallet['balance_wallet_address'], address_to]):
        tx_hash = wallet.send_transaction(user_from_wallet['balance_wallet_address'], address_to, amount)
        if (tx_hash is not None):
            ## add to MySQL
            updateTime = int(time.time())
            try:
                openConnection()
                with conn.cursor() as cur:
                   timestamp = int(time.time())
                   sql = """ INSERT INTO wrkz_donate (`from_user`, `to_address`, `amount`, `date`, `tx_hash`) VALUES (%s, %s, %s, %s, %s) """
                   cur.execute(sql, (user_from, address_to, amount, timestamp, tx_hash,))
                   conn.commit()
                   updateBalance = wallet.get_balance_address(user_from_wallet['balance_wallet_address'])
                   print(updateBalance)
                   if (updateBalance):
                       sql = """ UPDATE wrkz_walletapi SET `actual_balance`=%s, `locked_balance`=%s, `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                       cur.execute(sql, (updateBalance['availableBalance'], updateBalance['lockedAmount'], updateTime, user_from_wallet['balance_wallet_address'],))
                       conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
        #print(tx_hash)
        return tx_hash
    else:
        return None

def sql_optimize_check():
    ## need to return string of message
    try:
        openConnection()
        with conn.cursor() as cur:
            timeNow=int(time.time())-1800
            sql = """ SELECT COUNT(*) FROM wrkz_user WHERE lastOptimize>%s """
            cur.execute(sql, timeNow, )
            result = cur.fetchone()
            #print(result)
            return result[0]
    except Exception as e:
        print(e)
    finally:
        conn.close()

def sql_optimize_do(userID: str):
    user_from_wallet = sql_get_userwallet(userID)
    print('store.sql_optimize_do')
    if (user_from_wallet):
        OptimizeCount = wallet.wallet_optimize_single(user_from_wallet['balance_wallet_address'], user_from_wallet['actual_balance'])
        if (OptimizeCount>0):
            updateTime = int(time.time())
            sql_optimize_update(str(userID))
            try:
                openConnection()
                with conn.cursor() as cur:
                   updateBalance = wallet.get_balance_address(user_from_wallet['balance_wallet_address'])
                   if (updateBalance):
                       sql = """ UPDATE wrkz_walletapi SET `actual_balance`=%s, `locked_balance`=%s, `lastUpdate`=%s WHERE `balance_wallet_address`=%s """
                       cur.execute(sql, (updateBalance['availableBalance'], updateBalance['lockedAmount'], updateTime, user_from_wallet['balance_wallet_address'],))
                       conn.commit()
            except Exception as e:
                print(e)
            finally:
                conn.close()
        return OptimizeCount

def sql_optimize_update(userID: str):
    try:
        openConnection()
        with conn.cursor() as cur:
            timeNow=int(time.time())
            sql = """ UPDATE wrkz_user SET `lastOptimize`=%s WHERE `user_id`=%s LIMIT 1 """
            cur.execute(sql, (timeNow, str(userID),))
            conn.commit()
    except Exception as e:
        print(e)
    finally:
        conn.close()

def sql_tag_by_server(server_id: str, tag_id: str=None):
    try:
        openConnection()
        with conn.cursor() as cur:
            if (tag_id is None): 
                sql = """ SELECT tag_id, tag_desc, date_added, tag_serverid, added_byname, added_byuid, num_trigger FROM wrkz_tag WHERE tag_serverid = %s """
                cur.execute(sql, (server_id,))
                result = cur.fetchall()
                tag_list = []
                for row in result:
                    tag_list.append({'tag_id':row[0], 'tag_desc':row[1], 'date_added':row[2], 'tag_serverid':row[3], 'added_byname':row[4], 'added_byuid':row[5], 'num_trigger':row[6]})
                return tag_list
            else:
                sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, `added_byuid`, `num_trigger` FROM wrkz_tag WHERE tag_serverid = %s AND tag_id=%s """
                cur.execute(sql, (server_id, tag_id,))
                result = cur.fetchone()
                if (result is not None):
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
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT COUNT(tag_serverid) FROM wrkz_tag WHERE tag_serverid=%s """
            cur.execute(sql, (server_id,))
            counting = cur.fetchone()
            if (counting is not None):
                if (counting[0]>50):
                    return None
            sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, `added_byuid`, `num_trigger` 
                      FROM wrkz_tag WHERE tag_serverid = %s AND tag_id=%s """
            cur.execute(sql, (server_id, tag_id.upper(),))
            result = cur.fetchone()
            if (result is None):
                sql = """ INSERT INTO wrkz_tag (`tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, `added_byuid`) 
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
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, `added_byuid`, `num_trigger` 
                      FROM wrkz_tag WHERE tag_serverid = %s AND tag_id=%s """
            cur.execute(sql, (server_id, tag_id.upper(),))
            result = cur.fetchone()
            if (result is None):
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

def sql_get_nodeinfo():
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT `url`, `fee`, `lastUpdate`, `alt_blocks_count`, `difficulty`, `incoming_connections_count`,
                  `last_known_block_index`, `network_height`, `outgoing_connections_count`, `start_time`, `tx_count`, `tx_pool_size`,
                  `version`, `white_peerlist_size`, `synced`, `height` FROM wrkz_nodes """
            cur.execute(sql,)
            result = cur.fetchall()
            return result
    except Exception as e:
        print(e)
    finally:
        conn.close()

def sql_get_poolinfo():
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT `name`, `url_api`, `fee`, `minPaymentThreshold`, `pool_stats_lastBlockFound`, `pool_stats_totalBlocks`,
                  `pool_totalMinersPaid`, `pool_totalPayments`, `pool_payment_last`, `pool_miners`, `pool_hashrate`, `net_difficulty`,
                  `net_height`, `net_timestamp`, `net_reward`, `net_hash`, `lastUpdate`, `pool_blocks_last` FROM wrkz_pools """
            cur.execute(sql,)
            result = cur.fetchall()
            return result
    except Exception as e:
        print(e)
    finally:
        conn.close()
