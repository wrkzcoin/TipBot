from typing import List, Dict
from datetime import datetime
import time, json
import aiohttp, asyncio, aiomysql
from aiomysql.cursors import DictCursor
from discord_webhook import DiscordWebhook
import disnake

from config import config
import sys, traceback
import os.path

# redis
import redis

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
async def sql_user_balance(userID: str, coin: str, user_server: str = 'DISCORD'):
    global pool
    TOKEN_NAME = coin.upper()
    user_server = user_server.upper()
    token_info = (await get_all_token())[TOKEN_NAME]
    confirmed_depth = token_info['deposit_confirm_depth']
    try:
        await openConnection()
        async with pool.acquire() as conn:
            
            async with conn.cursor() as cur:
                # When sending tx out, (negative)
                sql = """ SELECT SUM(real_amount+real_external_fee) AS SendingOut FROM erc20_external_tx 
                          WHERE `user_id`=%s AND `token_name` = %s """
                await cur.execute(sql, (userID, TOKEN_NAME))
                result = await cur.fetchone()
                if result:
                    SendingOut = result['SendingOut']
                else:
                    SendingOut = 0

                sql = """ SELECT SUM(real_amount) AS Expense FROM `user_balance_mv` WHERE `from_userid`=%s AND `token_name` = %s """
                await cur.execute(sql, (userID, TOKEN_NAME))
                result = await cur.fetchone()
                if result:
                    Expense = result['Expense']
                else:
                    Expense = 0

                sql = """ SELECT SUM(real_amount) AS Income FROM `user_balance_mv` WHERE `to_userid`=%s AND `token_name` = %s """
                await cur.execute(sql, (userID, TOKEN_NAME))
                result = await cur.fetchone()
                if result:
                    Income = result['Income']
                else:
                    Income = 0
                # in case deposit fee -real_deposit_fee
                sql = """ SELECT SUM(real_amount-real_deposit_fee) AS Deposit FROM `erc20_move_deposit` WHERE `user_id`=%s 
                          AND `token_name` = %s AND `confirmed_depth`> %s """
                await cur.execute(sql, (userID, TOKEN_NAME, confirmed_depth))
                result = await cur.fetchone()
                if result:
                    Deposit = result['Deposit']
                else:
                    Deposit = 0

                # pending airdrop
                sql = """ SELECT SUM(real_amount) AS airdropping FROM `discord_airdrop_tmp` WHERE `from_userid`=%s 
                          AND `token_name` = %s AND (`status`=%s OR `status`=%s) """
                await cur.execute(sql, (userID, TOKEN_NAME, "ONGOING", "FAST"))
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

            balance = {}
            balance['Adjust'] = 0
            balance['Expense'] = float("%.3f" % Expense) if Expense else 0
            balance['Income'] = float("%.3f" % Income) if Income else 0
            balance['SendingOut'] = float("%.3f" % SendingOut) if SendingOut else 0
            balance['Deposit'] = float("%.3f" % Deposit) if Deposit else 0
            balance['airdropping'] = float("%.3f" % airdropping) if airdropping else 0
            balance['mathtip'] = float("%.4f" % mathtip) if mathtip else 0
            balance['triviatip'] = float("%.4f" % triviatip) if triviatip else 0
            balance['Adjust'] = float("%.3f" % (balance['Income'] - balance['SendingOut'] - balance['Expense'] + balance['Deposit'] - balance['airdropping'] - balance['mathtip'] - balance['triviatip']))
            # Negative check
            try:
                if balance['Adjust'] < 0:
                    msg_negative = 'Negative balance detected:\nServer:'+user_server+'\nUser: '+str(username)+'\nToken: '+TOKEN_NAME+'\nBalance: '+str(balance['Adjust'])
                    await logchanbot(msg_negative)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return balance
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


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