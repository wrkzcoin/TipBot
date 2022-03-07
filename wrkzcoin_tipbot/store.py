from typing import List, Dict
from datetime import datetime
import time, json
import aiohttp, asyncio, aiomysql
from aiomysql.cursors import DictCursor
from discord_webhook import DiscordWebhook
import disnake
from decimal import Decimal

from config import config
import sys, traceback
import os.path

# redis
import redis

from tronpy import AsyncTron
from tronpy.async_contract import AsyncContract, ShieldedTRC20, AsyncContractMethod
from tronpy.providers.async_http import AsyncHTTPProvider
from tronpy.exceptions import AddressNotFound
from tronpy.keys import PrivateKey


from httpx import AsyncClient, Timeout, Limits

from web3 import Web3
from web3.middleware import geth_poa_middleware
from ethtoken.abi import EIP20_ABI
from eth_utils import is_checksum_address
from eth_utils import is_hex_address # Check hex only

# For seed to key
from eth_account import Account
Account.enable_unaudited_hdwallet_features()

from Bot import decrypt_string

redis_pool = None
redis_conn = None
redis_expired = 10
pool = None
sys.path.append("..")


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


async def openConnection():
    global pool
    try:
        if pool is None:
            pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=8, maxsize=16, 
                                                   user=config.mysql.user, password=config.mysql.password,
                                                   db=config.mysql.db, cursorclass=DictCursor, autocommit=True)
    except:
        print("ERROR: Unexpected error: Could not connect to MySql instance.")
        sys.exit()


async def logchanbot(content: str):
    try:
        webhook = DiscordWebhook(url=config.discord.webhook_url, content=f'```{disnake.utils.escape_markdown(content)}```')
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


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
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_addinfo_by_server(server_id: str, servername: str, prefix: str, default_coin: str, rejoin: bool = True):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if rejoin:
                    sql = """ INSERT INTO `discord_server` (`serverid`, `servername`, `prefix`, `default_coin`, `status`)
                              VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY 
                              UPDATE 
                              `servername`=VALUES(`servername`),
                              `prefix`=VALUES(`prefix`), 
                              `default_coin`=VALUES(`default_coin`), 
                              `status`=VALUES(`status`)
                              """
                    await cur.execute(sql, (server_id, servername[:28], prefix, default_coin, "REJOINED", ))
                    await conn.commit()
                else:
                    sql = """ INSERT INTO `discord_server` (`serverid`, `servername`, `prefix`, `default_coin`)
                              VALUES (%s, %s, %s, %s) ON DUPLICATE KEY  
                              UPDATE 
                              `servername`=VALUES(`servername`),
                              `prefix`=VALUES(`prefix`), 
                              `default_coin`=VALUES(`default_coin`)
                              """
                    await cur.execute(sql, (server_id, servername[:28], prefix, default_coin))
                    await conn.commit()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


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
        traceback.print_exc(file=sys.stdout)
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
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_changeinfo_by_server(server_id: str, what: str, value: str):
    global pool
    if what.lower() in ["servername", "prefix", "default_coin", "tiponly", "numb_user", "numb_bot", "numb_channel", \
    "react_tip", "react_tip_100", "react_tip_coin", "lastUpdate", "botchan", "raffle_channel", "enable_faucet", "enable_game", "enable_market", "enable_trade", "tip_message", \
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
            traceback.print_exc(file=sys.stdout)


# TODO: get balance based on various coin, external withdraw, other expenses, tipping out, etc
async def sql_user_balance_single(userID: str, coin: str, address: str, coin_family: str, top_block: int, confirmed_depth: int=0, user_server: str = 'DISCORD'):
    global pool
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
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # moving tip + / -
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

                # Each coin
                if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    sql = """ SELECT SUM(amount+withdraw_fee) AS tx_expense FROM `cn_external_tx` WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s """
                    await cur.execute(sql, (userID, TOKEN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        tx_expense = result['tx_expense']
                    else:
                        tx_expense = 0

                    if top_block is None:
                        sql = """ SELECT SUM(amount) AS incoming_tx FROM `cn_get_transfers` WHERE `payment_id`=%s AND `coin_name` = %s 
                                  AND `amount`>0 AND `time_insert`< %s """
                        await cur.execute(sql, (address, TOKEN_NAME, int(time.time())-nos_block)) # seconds
                    else:
                        sql = """ SELECT SUM(amount) AS incoming_tx FROM `cn_get_transfers` WHERE `payment_id`=%s AND `coin_name` = %s 
                                  AND `amount`>0 AND `height`< %s """
                        await cur.execute(sql, (address, TOKEN_NAME, nos_block))
                    result = await cur.fetchone()
                    if result and result['incoming_tx']:
                        incoming_tx = result['incoming_tx']
                    else:
                        incoming_tx = 0
                elif coin_family == "BTC":
                    sql = """ SELECT SUM(amount+withdraw_fee) AS tx_expense FROM `doge_external_tx` WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s """
                    await cur.execute(sql, (userID, TOKEN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        tx_expense = result['tx_expense']
                    else:
                        tx_expense = 0

                    sql = """ SELECT SUM(amount) AS incoming_tx FROM `doge_get_transfers` WHERE `address`=%s AND `coin_name` = %s AND (`category` = %s or `category` = %s) 
                              AND `confirmations`>=%s AND `amount`>0 """
                    await cur.execute(sql, (address, TOKEN_NAME, 'receive', 'generate', confirmed_depth))
                    result = await cur.fetchone()
                    if result and result['incoming_tx']:
                        incoming_tx = result['incoming_tx']
                    else:
                        incoming_tx = 0
                elif coin_family == "NANO":
                    sql = """ SELECT SUM(amount) AS tx_expense FROM `nano_external_tx` WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s """
                    await cur.execute(sql, (userID, TOKEN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        tx_expense = result['tx_expense']
                    else:
                        tx_expense = 0

                    sql = """ SELECT SUM(amount) AS incoming_tx FROM `nano_move_deposit` WHERE `user_id`=%s AND `coin_name` = %s 
                              AND `amount`>0 AND `time_insert`< %s """
                    await cur.execute(sql, (userID, TOKEN_NAME, int(time.time())-confirmed_inserted))
                    result = await cur.fetchone()
                    if result and result['incoming_tx']:
                        incoming_tx = result['incoming_tx']
                    else:
                        incoming_tx = 0
                elif coin_family == "CHIA":
                    sql = """ SELECT SUM(amount+withdraw_fee) AS tx_expense FROM `xch_external_tx` WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s """
                    await cur.execute(sql, (userID, TOKEN_NAME, user_server))
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
                              WHERE `user_id`=%s AND `token_name` = %s """
                    await cur.execute(sql, (userID, TOKEN_NAME))
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
                              WHERE `user_id`=%s AND `token_name` = %s """
                    await cur.execute(sql, (userID, TOKEN_NAME))
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


            balance = {}
            balance['adjust'] = 0

            balance['mv_balance'] = float("%.4f" % mv_balance) if mv_balance else 0

            balance['airdropping'] = float("%.4f" % airdropping) if airdropping else 0
            balance['mathtip'] = float("%.4f" % mathtip) if mathtip else 0
            balance['triviatip'] = float("%.4f" % triviatip) if triviatip else 0

            balance['tx_expense'] = float("%.4f" % tx_expense) if tx_expense else 0
            balance['incoming_tx'] = float("%.4f" % incoming_tx) if incoming_tx else 0

            balance['adjust'] = float("%.4f" % ( balance['mv_balance']+balance['incoming_tx']-balance['airdropping']-balance['mathtip']-balance['triviatip']-balance['tx_expense'] ))
            # Negative check
            try:
                if balance['adjust'] < 0:
                    msg_negative = 'Negative balance detected:\nServer:'+user_server+'\nUser: '+str(username)+'\nToken: '+TOKEN_NAME+'\nBalance: '+str(balance['adjust'])
                    await logchanbot(msg_negative)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return balance
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())


# owner message to delete (which bot respond)
async def add_discord_bot_message(message_id: str, guild_id: str, owner_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_bot_message_owner (`message_id`, `guild_id`, `owner_id`, `stored_time`) 
                          VALUES (%s, %s, %s, %s) """
                await cur.execute(sql, (message_id, guild_id, owner_id, int(time.time())))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def get_discord_bot_message(message_id: str, is_deleted: str="NO"):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_bot_message_owner` WHERE `message_id`=%s AND `is_deleted`=%s LIMIT 1 """
                await cur.execute(sql, (message_id, is_deleted))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None

async def delete_discord_bot_message(message_id: str, owner_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `discord_bot_message_owner` SET `is_deleted`=%s, `date_deleted`=%s WHERE `message_id`=%s AND `owner_id`=%s LIMIT 1 """
                await cur.execute(sql, ("YES", int(time.time()), message_id, owner_id))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None
# End owner message

# get coin_setting
async def get_coin_settings(coin_type: str=None):
    global pool
    try:
        sql_coin_type = ""
        if coin_type: sql_coin_type = """ AND `type`='""" + coin_type.upper() + """'"""
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `coin_settings` WHERE `is_maintenance`=%s """ + sql_coin_type
                await cur.execute(sql, (0))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return []


async def sql_nano_get_user_wallets(coin: str):
    global pool
    COIN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM nano_user WHERE `coin_name` = %s """
                await cur.execute(sql, (COIN_NAME,))
                result = await cur.fetchall()
                return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return []


async def sql_get_new_tx_table(notified: str = 'NO', failed_notify: str = 'NO'):
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_notify_new_tx` WHERE `notified`=%s AND `failed_notify`=%s """
                await cur.execute(sql, (notified, failed_notify,))
                result = await cur.fetchall()
                return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return []


async def sql_update_notify_tx_table(payment_id: str, owner_id: str, owner_name: str, notified: str = 'YES', failed_notify: str = 'NO'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `discord_notify_new_tx` SET `owner_id`=%s, `owner_name`=%s, `notified`=%s, `failed_notify`=%s, 
                          `notified_time`=%s WHERE `payment_id`=%s """
                await cur.execute(sql, (owner_id, owner_name, notified, failed_notify, float("%.3f" % time.time()), payment_id,))
                await conn.commit()
                return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return False


async def sql_get_userwallet_by_paymentid(paymentid: str, coin: str, coin_family: str, user_server: str):
    COIN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                result = None
                if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    sql = """ SELECT * FROM `cn_user_paymentid` WHERE `paymentid`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (paymentid, COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "CHIA":
                    sql = """ SELECT * FROM `xch_user` WHERE `balance_wallet_address`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (paymentid, COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "BTC":
                    # if doge family, address is paymentid
                    sql = """ SELECT * FROM `doge_user` WHERE `balance_wallet_address`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (paymentid, COIN_NAME, user_server))
                    result = await cur.fetchone()
                elif coin_family == "NANO":
                    # if doge family, address is paymentid
                    sql = """ SELECT * FROM `nano_user` WHERE `balance_wallet_address`=%s AND `coin_name` = %s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (paymentid, COIN_NAME, user_server))
                    result = await cur.fetchone()
                return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


# ERC, TRC scan
async def get_txscan_stored_list_erc(net_name: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if net_name == "TRX":
                    sql = """ SELECT * FROM `trc20_contract_scan` WHERE `net_name`=%s ORDER BY `blockNumber` DESC LIMIT 500 """
                    await cur.execute(sql, (net_name))
                    result = await cur.fetchall()
                    if result and len(result) > 0: return {'txHash_unique': [item['contract_blockNumber_Tx_from_to_uniq'] for item in result]}
                else:
                    sql = """ SELECT * FROM `erc20_contract_scan` WHERE `net_name`=%s ORDER BY `blockNumber` DESC LIMIT 500 """
                    await cur.execute(sql, (net_name))
                    result = await cur.fetchall()
                    if result and len(result) > 0: return {'txHash_unique': [item['contract_blockNumber_Tx_from_to_uniq'] for item in result]}
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return {'txHash_unique': []}


async def get_latest_stored_scanning_height_erc(net_name: str, contract: str=None):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if net_name == "TRX":
                    sql = """ SELECT MAX(`blockNumber`) as TopBlock FROM `trc20_contract_scan` WHERE `net_name`=%s AND `contract`=%s """
                    await cur.execute(sql, (net_name, contract))
                    result = await cur.fetchone()
                    if result and result['TopBlock']: return int(result['TopBlock'])
                else:
                    sql = """ SELECT MAX(`blockNumber`) as TopBlock FROM `erc20_contract_scan` WHERE `net_name`=%s """
                    await cur.execute(sql, (net_name))
                    result = await cur.fetchone()
                    if result and result['TopBlock']: return int(result['TopBlock'])
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return 1


async def get_monit_contract_tx_insert_erc(list_data):
    global pool
    if len(list_data) == 0:
        return 0
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT IGNORE INTO `erc20_contract_scan` (`net_name`, `contract`, `topics_dump`, `from_addr`, `to_addr`, `blockNumber`, `blockTime`, `transactionHash`, `contract_blockNumber_Tx_from_to_uniq`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.executemany(sql, list_data)
                await conn.commit()
                return cur.rowcount
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        pass
    return 0


async def get_monit_contract_tx_insert_trc(list_data):
    global pool
    if len(list_data) == 0:
        return 0
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT IGNORE INTO `trc20_contract_scan` (`net_name`, `contract`, `from_addr`, `to_addr`, `blockNumber`, `blockTime`, `transactionHash`, `contract_blockNumber_Tx_from_to_uniq`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.executemany(sql, list_data)
                await conn.commit()
                return cur.rowcount
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        pass
    return 0


async def get_monit_scanning_net_name_update_height(net_name: str, new_height: int, coin_name: str=None):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if net_name == "TRX":
                    sql = """ UPDATE `coin_settings` SET `scanned_from_height`=%s WHERE `net_name`=%s AND (`scanned_from_height`<%s OR `scanned_from_height` IS NULL) AND `coin_name`=%s LIMIT 1 """
                    await cur.execute(sql, (new_height, net_name, new_height, coin_name))
                    await conn.commit()
                    return new_height
                else:
                    sql = """ UPDATE `coin_ethscan_setting` SET `scanned_from_height`=%s WHERE `net_name`=%s AND `scanned_from_height`<%s  LIMIT 1 """
                    await cur.execute(sql, (new_height, net_name, new_height))
                    await conn.commit()
                    return new_height
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def trx_get_block_number(timeout: int = 64):
    height = 0
    url = config.Tron_Node.fullnode + "/wallet/getnowblock"
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
    except asyncio.TimeoutError:
        print('TRX: get block number {}s for TOKEN {}'.format(timeout, "TRX"))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return height


async def trx_get_block_info(url: str, height: int, timeout: int=32):
    try:
        _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                   timeout=Timeout(timeout=10, connect=5, read=5))
        TronClient = AsyncTron(provider=AsyncHTTPProvider(url, client=_http_client))
        getBlock = await TronClient.get_block(height)
        await TronClient.close()
        if getBlock:
            return getBlock['block_header']['raw_data']
            # Example: {'raw_data': {'number': 38321740, 'txTrieRoot': '2e6b6b527669ae016dae6f6985226c8e8114680386449e25a741fd7d981fde4b', 'witness_address': 'TVrdyw1qCMzW59QycTytDXVbbXFDBgBj42', 'parentHash': '000000000248be4bca00fffc2d72d2e134e9d3dba2e3a5bf4272d615e7bb76a4', 'version': 23, 'timestamp': 1645510917000}
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


async def erc_get_block_number(url: str, timeout: int=64):
    data = '{"jsonrpc":"2.0", "method":"eth_blockNumber", "params":[], "id":1}'
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
        print('TIMEOUT: get block number {}s'.format(timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def erc_get_block_info(url: str, height: int, timeout: int=32):
    try:
        data = '{"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["'+str(hex(height))+'", false],"id":1}'
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
            print('TIMEOUT: erc_get_block_info for {}s'.format(timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    except ValueError:
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_get_all_erc_user(type_coin_user: str, called_Update: int=0):
    # Check update only who has recently called for balance
    # If called_Update = 3600, meaning who called balance for last 1 hr
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if called_Update == 0:
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `seed`, `user_server` FROM `erc20_user` WHERE `type`=%s """
                    await cur.execute(sql, (type_coin_user))
                    result = await cur.fetchall()
                    if result: return result
                elif called_Update > 0:
                    lap = int(time.time()) - called_Update
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `seed`, `user_server` FROM erc20_user 
                              WHERE (`called_Update`>%s OR `is_discord_guild`=1) AND `type`=%s """
                    await cur.execute(sql, (lap, type_coin_user))
                    result = await cur.fetchall()
                    if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return []


# TODO: this is for ERC-20 only
async def http_wallet_getbalance(url: str, address: str, coin: str, contract: str=None, timeout: int = 64) -> Dict:
    TOKEN_NAME = coin.upper()
    if contract is None:
        data = '{"jsonrpc":"2.0","method":"eth_getBalance","params":["'+address+'", "latest"],"id":1}'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers={'Content-Type': 'application/json'}, json=json.loads(data), timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        decoded_data = json.loads(res_data)
                        if decoded_data and 'result' in decoded_data:
                            return int(decoded_data['result'], 16)
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
                        decoded_data = json.loads(res_data)
                        if decoded_data and 'result' in decoded_data:
                            return int(decoded_data['result'], 16)
        except asyncio.TimeoutError:
            print('TIMEOUT: get balance {} for {}s'.format(TOKEN_NAME, timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
    return None


async def sql_check_minimum_deposit_erc20(url: str, net_name: str, coin: str, contract: str, coin_decimal: int, min_move_deposit: float, min_gas_tx: float, gas_ticker: str, move_gas_amount: float, chainId: str, real_deposit_fee: float, time_lap: int=0):
    global pool
    TOKEN_NAME = coin.upper()
    if net_name == TOKEN_NAME:
        list_user_addresses = await sql_get_all_erc_user(net_name, time_lap)
    else:
        list_user_addresses = await sql_get_all_erc_user("ERC-20", time_lap)
    if contract is None:
        # Main Token
        # we do not need gas, we move straight
        balance_below_min = 0
        balance_above_min = 0
        msg_deposit = ""
        if len(list_user_addresses) > 0:
            # OK check them one by one
            for each_address in list_user_addresses:
                deposited_balance = await http_wallet_getbalance(url, each_address['balance_wallet_address'], TOKEN_NAME, None, 64)
                if deposited_balance is None:
                    continue
                real_deposited_balance = float("%.6f" % (int(deposited_balance) / 10**coin_decimal))
                if real_deposited_balance < min_move_deposit:
                    balance_below_min += 1
                    # skip balance move below this
                    # print("Skipped {}, {}. Having {}, minimum {}".format(TOKEN_NAME, each_address['balance_wallet_address'], real_deposited_balance, min_move_deposit))
                    pass
                # config.eth.MainAddress => each_address['balance_wallet_address']
                else:
                    balance_above_min += 1
                    try:
                        w3 = Web3(Web3.HTTPProvider(url))

                        # inject the poa compatibility middleware to the innermost layer
                        # w3.middleware_onion.inject(geth_poa_middleware, layer=0)

                        if net_name == "MATIC":
                            nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(each_address['balance_wallet_address']), 'pending')
                        else:
                            nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(each_address['balance_wallet_address']))

                        # get gas price
                        gasPrice = int(w3.eth.gasPrice * 1.0)

                        estimateGas = w3.eth.estimateGas({'to': w3.toChecksumAddress(config.eth.MainAddress), 'from': w3.toChecksumAddress(each_address['balance_wallet_address']), 'value':  deposited_balance})
                        print("TX {} deposited_balance: {}, gasPrice*estimateGas: {}*{}={}, ".format(TOKEN_NAME, deposited_balance/10**coin_decimal, gasPrice, estimateGas, gasPrice*estimateGas/10**coin_decimal))
                        transaction = {
                                'from': w3.toChecksumAddress(each_address['balance_wallet_address']),
                                'to': w3.toChecksumAddress(config.eth.MainAddress),
                                'value': deposited_balance - gasPrice*estimateGas,
                                'nonce': nonce,
                                'gasPrice': gasPrice,
                                'gas': estimateGas,
                                'chainId': chainId
                            }
                        acct = Account.from_mnemonic(mnemonic=decrypt_string(each_address['seed']))
                        signed_txn = w3.eth.account.sign_transaction(transaction, private_key=acct.key)

                        # send Transaction for gas:
                        sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
                        if signed_txn and sent_tx:
                            # Add to SQL
                            try:
                                inserted = await sql_move_deposit_for_spendable(TOKEN_NAME, None, each_address['user_id'], each_address['balance_wallet_address'], config.eth.MainAddress, real_deposited_balance, real_deposit_fee,  coin_decimal, sent_tx.hex(), each_address['user_server'], net_name)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                                #await logchanbot(traceback.format_exc())
                    except Exception as e:
                        print("ERROR TOKEN: {} - from {} to {}".format(TOKEN_NAME, each_address['balance_wallet_address'], config.eth.MainAddress))
                        traceback.print_exc(file=sys.stdout)
                        #await logchanbot(traceback.format_exc())
            msg_deposit += "TOKEN {}: Total deposit address: {}: Below min.: {} Above min. {}".format(TOKEN_NAME, len(list_user_addresses), balance_below_min, balance_above_min)
        else:
            msg_deposit += "TOKEN {}: No deposit address.".format(TOKEN_NAME)
    else:
        # ERC
        # get withdraw gas balance    
        gas_main_balance = await http_wallet_getbalance(url, config.eth.MainAddress, TOKEN_NAME, None, 64)
        
        # main balance has gas?
        main_balance_gas_sufficient = True
        if gas_main_balance and gas_main_balance / 10**18 >= min_gas_tx:
            pass
        else:
            main_balance_gas_sufficient = False
            pass
        # If zero gas enable_zero_gas
        if config.eth.enable_zero_gas == 1:
            main_balance_gas_sufficient = True

        if list_user_addresses and len(list_user_addresses) > 0:
            # OK check them one by one
            # print("{} addresses for updating balance".format(len(list_user_addresses)))
            for each_address in list_user_addresses:
                deposited_balance = await http_wallet_getbalance(url, each_address['balance_wallet_address'], TOKEN_NAME, contract, 64)
                if deposited_balance is None:
                    continue
                real_deposited_balance = deposited_balance / 10**coin_decimal
                if real_deposited_balance < min_move_deposit:
                    pass
                else:
                    # Check if there is gas remaining to spend there
                    gas_of_address = await http_wallet_getbalance(url, each_address['balance_wallet_address'], gas_ticker, None, 64)
                    if (gas_of_address / 10**18 >= min_gas_tx and config.eth.enable_zero_gas != 1) or config.eth.enable_zero_gas == 1:
                        print('Address {} still has gas {}{} or Zero gas is needed.'.format(each_address['balance_wallet_address'], gas_ticker, gas_of_address / 10**18))
                        # TODO: Let's move balance from there to withdraw address and save Tx
                        # HTTPProvider:
                        w3 = Web3(Web3.HTTPProvider(url))

                        # inject the poa compatibility middleware to the innermost layer
                        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

                        unicorns = w3.eth.contract(address=w3.toChecksumAddress(contract), abi=EIP20_ABI)
                        nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(each_address['balance_wallet_address']))
                        
                        unicorn_txn = unicorns.functions.transfer(
                             w3.toChecksumAddress(config.eth.MainAddress),
                             deposited_balance # amount to send
                         ).buildTransaction({
                             'from': w3.toChecksumAddress(each_address['balance_wallet_address']),
                             'gasPrice': w3.eth.gasPrice,
                             'nonce': nonce
                         })

                        acct = Account.from_mnemonic(
                            mnemonic=decrypt_string(each_address['seed']))
                        signed_txn = w3.eth.account.signTransaction(unicorn_txn, private_key=acct.key)
                        sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
                        if signed_txn and sent_tx:
                            # Add to SQL
                            try:
                                inserted = await sql_move_deposit_for_spendable(TOKEN_NAME, contract, each_address['user_id'], each_address['balance_wallet_address'], config.eth.MainAddress, real_deposited_balance, real_deposit_fee,  coin_decimal, sent_tx.hex(), each_address['user_server'], net_name)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                                await logchanbot(traceback.format_exc())
                    elif gas_of_address / 10**18 < min_gas_tx and main_balance_gas_sufficient and config.eth.enable_zero_gas != 1:
                        # HTTPProvider:
                        w3 = Web3(Web3.HTTPProvider(url))

                        # inject the poa compatibility middleware to the innermost layer
                        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                        # TODO: Let's move gas from main to have sufficient to move
                        nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config.eth.MainAddress))

                        # get gas price
                        gasPrice = w3.eth.gasPrice

                        estimateGas = w3.eth.estimateGas({'to': w3.toChecksumAddress(each_address['balance_wallet_address']), 'from': w3.toChecksumAddress(config.eth.MainAddress), 'value':  int(move_gas_amount * 10**18)})

                        amount_gas_move = int(move_gas_amount * 10**18)
                        if amount_gas_move < move_gas_amount * 10**18: amount_gas_move = int(move_gas_amount * 10**18)
                        transaction = {
                                'from': w3.toChecksumAddress(config.eth.MainAddress),
                                'to': w3.toChecksumAddress(each_address['balance_wallet_address']),
                                'value': amount_gas_move,
                                'nonce': nonce,
                                'gasPrice': gasPrice,
                                'gas': estimateGas,
                                'chainId': int(chainId, 16)
                            }
                        acct = Account.from_mnemonic(
                            mnemonic=config.eth.MainAddress_seed)
                        signed = w3.eth.account.sign_transaction(transaction, private_key=acct.key)
                        # send Transaction for gas:
                        send_gas_tx = w3.eth.sendRawTransaction(signed.rawTransaction)
                    elif gas_of_address / 10**18 < min_gas_tx and main_balance_gas_sufficient == False and config.eth.enable_zero_gas != 1:
                        print('Main address has no sufficient balance to supply gas {}'.format(each_address['balance_wallet_address']))
                    elif config.eth.enable_zero_gas != 1:
                        print('Internal error for gas checking {}'.format(each_address['balance_wallet_address']))


async def sql_move_deposit_for_spendable(token_name: str, contract: str, user_id: str, balance_wallet_address: str, to_main_address: str, \
real_amount: float, real_deposit_fee: float, token_decimal: int, txn: str, user_server: str, network: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO erc20_move_deposit (`token_name`, `contract`, `user_id`, `balance_wallet_address`, 
                          `to_main_address`, `real_amount`, `real_deposit_fee`, `token_decimal`, `txn`, `time_insert`, 
                          `user_server`, `network`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (token_name, contract, user_id, balance_wallet_address, to_main_address, real_amount, 
                                        real_deposit_fee, token_decimal, txn, int(time.time()), user_server.upper(), network))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False


async def sql_get_pending_move_deposit_erc20(net_name: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM erc20_move_deposit 
                          WHERE `status`=%s AND `network`=%s 
                          AND `notified_confirmation`=%s """
                await cur.execute(sql, ('PENDING', net_name, 'NO'))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def sql_get_tx_info_erc20(url: str, tx: str, timeout: int=64):
    data = '{"jsonrpc":"2.0", "method": "eth_getTransactionReceipt", "params":["'+tx+'"], "id":1}'
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
        print('TIMEOUT: get block number {}s'.format(timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def sql_check_pending_move_deposit_erc20(url: str, net_name: str, deposit_confirm_depth: int):
    global pool
    topBlock = await erc_get_block_number(url, 64)
    if topBlock is None:
        print('Can not get top block.')
        return
    
    list_pending = await sql_get_pending_move_deposit_erc20(net_name)
    if list_pending and len(list_pending) > 0:
        # Have pending, let's check
        for each_tx in list_pending:
            # Check tx from RPC
            check_tx = await sql_get_tx_info_erc20(url, each_tx['txn'], 64)
            if check_tx is not None:
                tx_block_number = int(check_tx['blockNumber'], 16)
                status = "CONFIRMED"                    
                if 'status' in check_tx and int(check_tx['status'], 16) == 0:
                    status = "FAILED"
                if topBlock - deposit_confirm_depth > tx_block_number:
                    confirming_tx = await sql_update_confirming_move_tx_erc20(each_tx['txn'], tx_block_number, topBlock - tx_block_number, status)
            elif check_tx is None:
                # None found
                if int(time.time()) - 4*3600 > each_tx['time_insert']:
                    status = "FAILED"
                    tx_block_number = 0
                    failed_tx = await sql_update_confirming_move_tx_erc20(each_tx['txn'], tx_block_number, topBlock - tx_block_number, status)


async def sql_update_confirming_move_tx_erc20(tx: str, blockNumber: int, confirmed_depth: int, status):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE erc20_move_deposit SET `status`=%s, `blockNumber`=%s, `confirmed_depth`=%s WHERE `txn`=%s """
                await cur.execute(sql, (status, blockNumber, confirmed_depth, tx))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def get_monit_scanning_contract_balance_address_erc20(net_name: str, called_Update: int=1200):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                lap = int(time.time()) - called_Update
                sql = """ SELECT * FROM erc20_contract_scan WHERE `net_name`=%s AND `blockTime`>%s """
                await cur.execute(sql, (net_name, lap,))
                result = await cur.fetchall()
                if result and len(result) > 0: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return []


async def sql_update_erc_user_update_call_many_erc20(list_data):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE erc20_user SET `called_Update`=%s WHERE `balance_wallet_address`=%s """
                await cur.executemany(sql, list_data)
                await conn.commit()
                return cur.rowcount
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return 0


async def sql_get_pending_notification_users_erc20(user_server: str='DISCORD'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `erc20_move_deposit` 
                          WHERE `status`=%s 
                          AND `notified_confirmation`=%s 
                          AND `user_server`=%s """
                await cur.execute(sql, ('CONFIRMED', 'NO', user_server))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return []


async def sql_updating_pending_move_deposit_erc20(notified_confirmation: bool, failed_notification: bool, txn: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            
            async with conn.cursor() as cur:
                sql = """ UPDATE erc20_move_deposit 
                          SET `notified_confirmation`=%s, `failed_notification`=%s, `time_notified`=%s
                          WHERE `txn`=%s """
                await cur.execute(sql, ('YES' if notified_confirmation else 'NO', 'YES' if failed_notification else 'NO', int(time.time()), txn))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def trx_check_minimum_deposit(coin: str, type_coin: str, contract: str, coin_decimal: int, min_move_deposit: float, min_gas_tx: float, gas_ticker: str, move_gas_amount: float, chainId: str, real_deposit_fee: float, time_lap: int=0, user_server: str='DISCORD'):
    global pool
    TOKEN_NAME = coin.upper()
    list_user_addresses = await sql_get_all_trx_user(TOKEN_NAME, time_lap)
    msg_deposit = ""
    balance_below_min = 0
    balance_above_min = 0
    if list_user_addresses and len(list_user_addresses) > 0:
        # OK check them one by one
        for each_address in list_user_addresses:
            deposited_balance = float(await trx_wallet_getbalance(each_address['balance_wallet_address'], TOKEN_NAME, coin_decimal, type_coin, contract))
            if deposited_balance is None or deposited_balance == 0:
                continue
            
            if deposited_balance < min_move_deposit:
                balance_below_min += 1
                pass
            else:
                balance_above_min += 1
                await asyncio.sleep(1.0)
                if TOKEN_NAME == "TRX":
                    real_deposited_balance = deposited_balance-min_gas_tx
                    try:
                        _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                                   timeout=Timeout(timeout=10, connect=5, read=5))
                        TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
                        txb = (
                            TronClient.trx.transfer(each_address['balance_wallet_address'], config.trc.MainAddress, int(real_deposited_balance*10**coin_decimal))
                            #.memo("test memo")
                            #.fee_limit(100_000_000)
                            .fee_limit(int(min_gas_tx*10**coin_decimal))
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
                                inserted = await trx_move_deposit_for_spendable(TOKEN_NAME, contract, each_address['user_id'], each_address['balance_wallet_address'], config.trc.MainAddress, real_deposited_balance, real_deposit_fee,  coin_decimal, txn_ret['txid'], in_block['blockNumber'], user_server)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                        await asyncio.sleep(3)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                else:
                    # Let's move to main address
                    if type_coin == "TRC-20":
                        try:
                            _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                                       timeout=Timeout(timeout=10, connect=5, read=5))
                            TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
                            cntr = await TronClient.get_contract(contract)
                            precision = await cntr.functions.decimals()
                            balance = await cntr.functions.balanceOf(each_address['balance_wallet_address']) / 10**precision
                            # Check balance and Transfer gas to it
                            try:
                                gas_balance = await trx_wallet_getbalance(each_address['balance_wallet_address'], TOKEN_NAME, coin_decimal, type_coin, contract)
                                if gas_balance < min_gas_tx:
                                    txb_gas = (
                                        TronClient.trx.transfer(config.trc.MainAddress, each_address['balance_wallet_address'], int(move_gas_amount*10**coin_decimal))
                                        .fee_limit(int(min_gas_tx*10**coin_decimal))
                                    )
                                    txn_gas = await txb_gas.build()
                                    priv_key_gas = PrivateKey(bytes.fromhex(config.trc.MainAddress_key))
                                    txn_ret_gas = await txn_gas.sign(priv_key_gas).broadcast()
                                    await asyncio.sleep(3)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            txb = await cntr.functions.transfer(config.trc.MainAddress, int(balance*10**6))
                            txb = txb.with_owner(each_address['balance_wallet_address']).fee_limit(int(min_gas_tx*10**coin_decimal))
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
                                    inserted = await trx_move_deposit_for_spendable(TOKEN_NAME, contract, each_address['user_id'], each_address['balance_wallet_address'], config.trc.MainAddress, balance, real_deposit_fee, coin_decimal, txn_ret['txid'], in_block['blockNumber'], user_server)
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                            await asyncio.sleep(3)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    elif type_coin == "TRC-10":
                        try:
                            _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                                       timeout=Timeout(timeout=10, connect=5, read=5))
                            TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))                            
                            balance = await trx_wallet_getbalance(each_address['balance_wallet_address'], TOKEN_NAME, coin_decimal, type_coin, contract)
                            # Check balance and Transfer gas to it
                            try:
                                gas_balance = await trx_wallet_getbalance(each_address['balance_wallet_address'], TOKEN_NAME, coin_decimal, type_coin, contract)
                                if gas_balance < min_gas_tx:
                                    txb_gas = (
                                        TronClient.trx.transfer(config.trc.MainAddress, each_address['balance_wallet_address'], int(move_gas_amount*10**coin_decimal))
                                        .fee_limit(int(min_gas_tx*10**coin_decimal))
                                    )
                                    txn_gas = await txb_gas.build()
                                    priv_key_gas = PrivateKey(bytes.fromhex(config.trc.MainAddress_key))
                                    txn_ret_gas = await txn_gas.sign(priv_key_gas).broadcast()
                                    await asyncio.sleep(3)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            ### here
                            precision = 10**coin_decimal
                            amount = int(precision*balance)
                            txb = (
                                TronClient.trx.asset_transfer(
                                    each_address['balance_wallet_address'], config.trc.MainAddress, amount, token_id=int(contract)
                                )
                                .fee_limit(int(min_gas_tx*10**coin_decimal))
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
                                    inserted = await trx_move_deposit_for_spendable(TOKEN_NAME, str(contract), each_address['user_id'], each_address['balance_wallet_address'], config.trc.MainAddress, balance, real_deposit_fee,  coin_decimal, txn_ret['txid'], in_block['blockNumber'], user_server)
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                            await asyncio.sleep(3)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
        msg_deposit += "TOKEN {}: Total deposit address: {}: Below min.: {} Above min. {}".format(TOKEN_NAME, len(list_user_addresses), balance_below_min, balance_above_min)
    else:
        msg_deposit += "TOKEN {}: No deposit address.\n".format(TOKEN_NAME)
    return msg_deposit


async def sql_check_pending_move_deposit_trc20(net_name: str, deposit_confirm_depth: int, option: str='PENDING'):
    global pool
    topBlock = await trx_get_block_number(timeout=64)
    if topBlock is None:
        await logchanbot('Can not get top block for {}.'.format(net_name))
        return

    list_pending = await trx_get_pending_move_deposit(option.upper())

    if len(list_pending) > 0:
        # Have pending, let's check
        for each_tx in list_pending:
            try:
                tx_block_number = each_tx['blockNumber']
                #if option.upper() == "ALL":
                #    print("Checking tx: {}... for {}".format(each_tx['txn'][0:10], net_name))
                #    print("topBlock: {}, Conf Depth: {}, Tx Block Numb: {}".format(topBlock, deposit_confirm_depth , tx_block_number))
                if topBlock - deposit_confirm_depth > tx_block_number:
                    check_tx = await trx_get_tx_info(each_tx['txn'])
                    if check_tx:
                        confirming_tx = await trx_update_confirming_move_tx(each_tx['txn'], topBlock - tx_block_number, 'CONFIRMED')
                    else:
                        confirming_tx = await trx_update_confirming_move_tx(each_tx['txn'], topBlock - tx_block_number, 'FAILED')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())


async def trx_get_tx_info(tx: str):
    timeout = 64
    try:
        _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                   timeout=Timeout(timeout=10, connect=5, read=5))
        TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
        getTx = await TronClient.get_transaction(tx)
        await TronClient.close()
        if getTx['ret'][0]['contractRet'] != "SUCCESS":
            # That failed.
            await logchanbot("TRX {} not succeeded with tx: {}".format(tx))
            return False
        else:
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


async def trx_wallet_getbalance(address: str, coin: str, coin_decimal: int, type_coin: str, contract: str=None):
    TOKEN_NAME = coin.upper()
    balance = 0.0
    try:
        _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                   timeout=Timeout(timeout=10, connect=5, read=5))
        TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
        if contract is None:
            try:
                balance = await TronClient.get_account_balance(address)
            except AddressNotFound:
                balance = 0.0
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        else:
            if type_coin == "TRC-20":
                try:
                    cntr = await TronClient.get_contract(contract)
                    SYM = await cntr.functions.symbol()
                    if TOKEN_NAME == SYM:
                        precision = await cntr.functions.decimals()
                        balance = await cntr.functions.balanceOf(address) / 10**precision
                    else:
                        await logchanbot("Mis-match SYM vs TOKEN NAME: {} vs {}".format(SYM, TOKEN_NAME))
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            elif type_coin == "TRC-10":
                try:
                    precision = coin_decimal
                    balance = await TronClient.get_account_asset_balance(addr=address, token_id=int(contract)) / 10**precision
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


async def trx_update_confirming_move_tx(tx: str, confirmed_depth: int, status: str='CONFIRMED'):
    global pool
    status = status.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ UPDATE trc20_move_deposit SET `status`=%s, `confirmed_depth`=%s WHERE `txn`=%s """
                await cur.execute(sql, (status, confirmed_depth, tx))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def sql_get_pending_notification_users_trc20(user_server: str='DISCORD'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `trc20_move_deposit` 
                          WHERE `status`=%s 
                          AND `notified_confirmation`=%s 
                          AND `user_server`=%s """
                await cur.execute(sql, ('CONFIRMED', 'NO', user_server))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def trx_get_pending_move_deposit(option: str='PENDING'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                if option.upper() == "PENDING":
                    sql = """ SELECT * FROM trc20_move_deposit 
                              WHERE `status`=%s AND `notified_confirmation`=%s """
                    await cur.execute(sql, (option.upper(), 'NO'))
                    result = await cur.fetchall()
                    if result: return result
                elif option.upper() == "ALL":
                    sql = """ SELECT * FROM trc20_move_deposit 
                              WHERE `status`<>%s AND `status`<>%s """
                    await cur.execute(sql, ('FAILED', 'CONFIRMED'))
                    result = await cur.fetchall()
                    if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return []


async def sql_updating_pending_move_deposit_trc20(notified_confirmation: bool, failed_notification: bool, txn: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE trc20_move_deposit 
                          SET `notified_confirmation`=%s, `failed_notification`=%s, `time_notified`=%s
                          WHERE `txn`=%s """
                await cur.execute(sql, ('YES' if notified_confirmation else 'NO', 'YES' if failed_notification else 'NO', int(time.time()), txn))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def sql_get_all_trx_user(coin: str, called_Update: int=0):
    # Check update only who has recently called for balance
    # If called_Update = 3600, meaning who called balance for last 1 hr
    global pool
    TOKEN_NAME = coin.upper()
    extra_str = ""
    if TOKEN_NAME == "TRX":
        extra_str = """ WHERE (`type`='TRX' """
    else:
        extra_str = """ WHERE (`type`='TRC-20' """
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                if called_Update == 0:
                    sql = """ SELECT `user_id`, `user_id_trc20`, `balance_wallet_address`, `hex_address`, `private_key` FROM trc20_user 
                               """ + extra_str + """ ) OR `is_discord_guild`=1 """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result: return result
                elif called_Update > 0:
                    lap = int(time.time()) - called_Update
                    sql = """ SELECT `user_id`, `user_id_trc20`, `balance_wallet_address`, `hex_address`, `private_key` FROM trc20_user 
                              """+extra_str+""" AND `called_Update`>%s) OR `is_discord_guild`=1 """
                    await cur.execute(sql, (lap))
                    result = await cur.fetchall()
                    if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return []


async def get_all_coin_token_addresses():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """   (SELECT t1.balance_wallet_address as addresses FROM erc20_user t1)
                            UNION
                            (SELECT t2.balance_wallet_address FROM trc20_user t2)
                            UNION
                            (SELECT t3.balance_wallet_address FROM cn_user_paymentid t3)
                            UNION
                            (SELECT t4.balance_wallet_address FROM xch_user t4)
                            UNION
                            (SELECT t5.balance_wallet_address FROM doge_user t5)
                            UNION
                            (SELECT t6.balance_wallet_address FROM nano_user t6)  """
                await cur.execute(sql, ())
                result = await cur.fetchall()
                if result and len(result) > 0: return [each['addresses'] for each in result]
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return []


async def contract_tx_remove_after(type_coin: str, duration: int=1200):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            lap = int(time.time()) - duration
            async with conn.cursor() as cur:
                if type_coin == "TRC-20":
                    sql = """ DELETE FROM `trc20_contract_scan` WHERE `blockTime`<%s """
                    await cur.execute(sql, (lap))
                    return True
                else:
                    sql = """ DELETE FROM `erc20_contract_scan` WHERE `blockTime`<%s """
                    await cur.execute(sql, (lap))
                    return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


## math tip
async def insert_discord_mathtip(token_name: str, contract: str, from_userid: str, from_username: str, message_id: str, eval_content: str, eval_answer: float, wrong_answer_1: float, wrong_answer_2: float, wrong_answer_3: float, guild_id: str, channel_id: str, real_amount: float, token_decimal: int, math_endtime: int, network: str, status: str="ONGOING"):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_mathtip_tmp (`token_name`, `contract`, `from_userid`, `from_username`, `message_id`, `eval_content`, `eval_answer`, `wrong_answer_1`, `wrong_answer_2`, `wrong_answer_3`, `guild_id`, `channel_id`, `real_amount`, `token_decimal`, `message_time`, `math_endtime`, `network`, `status`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (token_name, contract, from_userid, from_username, message_id, eval_content, eval_answer, wrong_answer_1, wrong_answer_2, wrong_answer_3, guild_id, channel_id, real_amount, token_decimal, int(time.time()), math_endtime, network, status))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False


async def get_discord_mathtip_by_msgid(msg_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_mathtip_tmp` WHERE `message_id`=%s """
                await cur.execute(sql, (msg_id))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def get_discord_mathtip_by_chanid(chan_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_mathtip_tmp` WHERE `channel_id`=%s AND `status`=%s ORDER BY `math_endtime` ASC LIMIT 10 """
                await cur.execute(sql, (chan_id, "ONGOING"))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return []


async def discord_mathtip_update(message_id: str, status: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `discord_mathtip_tmp` SET `status`=%s WHERE `message_id`=%s AND `status`<>%s LIMIT 1 """
                await cur.execute(sql, (status, message_id, status))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def get_math_responders_by_message_id(message_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_mathtip_responder` WHERE `message_id`=%s """
                await cur.execute(sql, (message_id))
                result = await cur.fetchall()
                if result and len(result) > 0:
                    wrong_ids = []
                    right_ids = []
                    wrong_names = []
                    right_names = []
                    for each in result:
                        if each['result'] == "RIGHT":
                            right_ids.append(each['responder_id'])
                            right_names.append(each['responder_name'])
                        else:
                            wrong_ids.append(each['responder_id'])
                            wrong_names.append(each['responder_name'])
                        
                    return {'total': len(result), 'wrong_ids': wrong_ids, 'wrong_names': wrong_names, 'right_ids': right_ids, 'right_names': right_names}
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return {'total': 0, 'wrong_ids': [], 'wrong_names': [], 'right_ids': [], 'right_names': []}


async def check_if_mathtip_responder_in(message_id: str, from_userid: str, responder_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_mathtip_responder` WHERE `message_id`=%s AND `from_userid`=%s AND `responder_id`=%s LIMIT 1 """
                await cur.execute(sql, (message_id, from_userid, responder_id))
                result = await cur.fetchone()
                if result and len(result) > 0: return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False


async def insert_mathtip_responder(message_id: str, guild_id: str, from_userid: str, responder_id: str, responder_name: str, result: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT IGNORE INTO discord_mathtip_responder (`message_id`, `guild_id`, `from_userid`, `responder_id`, `responder_name`, `from_and_responder_uniq`, `result`, `inserted_time`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (message_id, guild_id, from_userid, responder_id, responder_name, "{}-{}-{}".format(message_id, from_userid, responder_id), result, int(time.time())))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False
# end of math tip

## Trivia
async def get_random_q_db(level: str):
    # level = EASY, MEDIUM, HARD
    difficulty = ""
    if level in ["EASY", "MEDIUM", "HARD"]:
        difficulty = "`difficulty`='"+level+"'"
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `trivia_db` WHERE `is_enable`=%s """+difficulty+""" ORDER BY RAND() LIMIT 1 """
                await cur.execute(sql, (1))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def get_q_db(q_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `trivia_db` WHERE `id`=%s LIMIT 1 """
                await cur.execute(sql, (q_id))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def get_active_discord_triviatip():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_triviatip_tmp` WHERE `status`=%s """
                await cur.execute(sql, ("ONGOING"))
                result = await cur.fetchall()
                if result and len(result) > 0: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return []


async def get_discord_triviatip_by_msgid(message_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_triviatip_tmp` WHERE `message_id`=%s LIMIT 1 """
                await cur.execute(sql, (message_id))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def check_if_trivia_responder_in(message_id: str, from_userid: str, responder_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_triviatip_responder` WHERE `message_id`=%s AND `from_userid`=%s AND `responder_id`=%s LIMIT 1 """
                await cur.execute(sql, (message_id, from_userid, responder_id))
                result = await cur.fetchone()
                if result and len(result) > 0: return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False


async def get_responders_by_message_id(message_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_triviatip_responder` WHERE `message_id`=%s """
                await cur.execute(sql, (message_id))
                result = await cur.fetchall()
                if result and len(result) > 0:
                    wrong_ids = []
                    right_ids = []
                    wrong_names = []
                    right_names = []
                    for each in result:
                        if each['result'] == "RIGHT":
                            right_ids.append(each['responder_id'])
                            right_names.append(each['responder_name'])
                        else:
                            wrong_ids.append(each['responder_id'])
                            wrong_names.append(each['responder_name'])
                        
                    return {'total': len(result), 'wrong_ids': wrong_ids, 'wrong_names': wrong_names, 'right_ids': right_ids, 'right_names': right_names}
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return {'total': 0, 'wrong_ids': [], 'wrong_names': [], 'right_ids': [], 'right_names': []}


async def insert_discord_triviatip(token_name: str, contract: str, from_userid: str, from_owner_name: str, message_id: str, question_content: str, question_id: int, button_correct_answer: str, guild_id: str, channel_id: str, real_amount: float, token_decimal: int, trivia_endtime: int, network: str, status: str="ONGOING"):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_triviatip_tmp (`token_name`, `contract`, `from_userid`, `from_owner_name`, `message_id`, `question_content`, `question_id`, `button_correct_answer`, `guild_id`, `channel_id`, `real_amount`, `token_decimal`, `message_time`, `trivia_endtime`, `network`, `status`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (token_name, contract, from_userid, from_owner_name, message_id, question_content, question_id, button_correct_answer, guild_id, channel_id, real_amount, token_decimal, int(time.time()), trivia_endtime, network, status))
                await conn.commit()
                sql = """ UPDATE trivia_db SET numb_asked=numb_asked+1 WHERE `id`=%s """
                await cur.execute(sql, (question_id))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False


async def insert_trivia_responder(message_id: str, guild_id: str, question_id: str, from_userid: str, responder_id: str, responder_name: str, result: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT IGNORE INTO discord_triviatip_responder (`message_id`, `guild_id`, `question_id`, `from_userid`, `responder_id`, `responder_name`, `from_and_responder_uniq`, `result`, `inserted_time`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (message_id, guild_id, question_id, from_userid, responder_id, responder_name, "{}-{}-{}".format(message_id, from_userid, responder_id), result, int(time.time())))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False


async def discord_triviatip_update(message_id: str, status: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `discord_triviatip_tmp` SET `status`=%s WHERE `message_id`=%s AND `status`<>%s LIMIT 1 """
                await cur.execute(sql, (status, message_id, status))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None
## End of Trivia


async def sql_user_balance_mv_single(from_userid: str, to_userid: str, guild_id: str, channel_id: str, real_amount: float, coin: str, tiptype: str, token_decimal: int, user_server: str, contract: str):
    global pool
    TOKEN_NAME = coin.upper()
    currentTs = int(time.time())
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO user_balance_mv 
                          (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`, `real_amount`, `token_decimal`, `type`, `date`, `user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s, %s, %s, %s);

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
                await cur.execute(sql, ( TOKEN_NAME, contract, from_userid, to_userid, guild_id, channel_id, real_amount, token_decimal, tiptype, currentTs, user_server, from_userid, TOKEN_NAME, user_server, -real_amount, currentTs, to_userid, TOKEN_NAME, user_server, real_amount, currentTs ))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def sql_user_balance_mv_multiple(user_from: str, user_tos, guild_id: str, channel_id: str, amount_each: float, coin: str, tiptype: str, token_decimal: int, user_server: str, contract: str):
    # user_tos is array "account1", "account2", ....
    global pool
    TOKEN_NAME = coin.upper()
    values_list = []
    currentTs = int(time.time())
    #type_list = []
    for item in user_tos:
        values_list.append(( TOKEN_NAME, contract, user_from, item, guild_id, channel_id, amount_each, token_decimal, tiptype.upper(), currentTs, user_server, user_from, TOKEN_NAME, user_server, -amount_each, currentTs, item, TOKEN_NAME, user_server, amount_each, currentTs, ))
        #type_list.append((type(TOKEN_NAME), type(contract), type(user_from), type(item), type(guild_id), type(channel_id), type(float(amount_each)), type(token_decimal), type(tiptype.upper()), type(currentTs), type(user_server), type(user_from) , type(-float(amount_each))))
        
    if len(values_list) == 0:
        print("sql_user_balance_mv_multiple: got 0 data inserting. return...")
        return
    print(values_list)
    #print(type_list)
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO user_balance_mv (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`, `real_amount`, `token_decimal`, `type`, `date`, `user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s, %s, %s, %s);
                        
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
                await cur.executemany(sql, values_list)
                
                # [('WRKZ', None, '386761001808166912', '386761001808166912', '422968579454140426', '905302454365741066', 10.0, 2, 'MATHTIP', 1646634269, 'DISCORD', '386761001808166912', 'WRKZ', 'DISCORD', -10.0, 1646634269, '386761001808166912', 'WRKZ', 'DISCORD', 10.0, 1646634269)]
                # [(<class 'str'>, <class 'NoneType'>, <class 'str'>, <class 'str'>, <class 'str'>, <class 'str'>, <class 'float'>, <class 'int'>, <class 'str'>, <class 'int'>, <class 'str'>, <class 'str'>, <class 'float'>)]
                
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False


async def sql_update_erc20_user_update_call(userID: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `erc20_user` SET `called_Update`=%s WHERE `user_id`=%s """
                await cur.execute(sql, (int(time.time()), userID))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None


async def sql_update_trc20_user_update_call(userID: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `trc20_user` SET `called_Update`=%s WHERE `user_id`=%s """
                await cur.execute(sql, (int(time.time()), userID))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None

async def trx_move_deposit_for_spendable(token_name: str, contract: str, user_id: str, balance_wallet_address: str, to_main_address: str, \
real_amount: float, real_deposit_fee: float, token_decimal: int, txn: str, blockNumber: int, user_server: str='DISCORD'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ INSERT INTO trc20_move_deposit (`token_name`, `contract`, `user_id`, `balance_wallet_address`, 
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


async def sql_get_tipnotify():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT `user_id`, `date` FROM `bot_tipnotify_user` """
                await cur.execute(sql,)
                result = await cur.fetchall()
                ignorelist = []
                for row in result:
                    ignorelist.append(row['user_id'])
                return ignorelist
    except Exception as e:
        await logchanbot(traceback.format_exc())
