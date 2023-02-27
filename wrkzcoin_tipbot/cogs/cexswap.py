import sys, traceback
from aiohttp import web
import uuid
from hashlib import sha256
import json
import asyncio

import disnake
from disnake.ext import commands, tasks
from typing import Optional
from disnake import TextInputStyle
from disnake.enums import ButtonStyle
from decimal import Decimal
from datetime import datetime
import time
import itertools
from string import ascii_uppercase
import random
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

import store
from Bot import get_token_list, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, \
    EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, RowButtonCloseMessage, RowButtonRowCloseAnyMessage, human_format, \
    text_to_num, truncate, seconds_str, EMOJI_HOURGLASS_NOT_DONE, EMOJI_INFORMATION, log_to_channel, \
    encrypt_string, decrypt_string

from cogs.wallet import WalletAPI
from cogs.utils import Utils, num_format_coin

# https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

async def call_cexswap_api(user_id: str, user_server: str, method: str, full_payload):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `bot_users` 
                SET `cexswap_calls`=`cexswap_calls`+1
                WHERE `user_id`=%s AND `user_server`=%s LIMIT 1;

                INSERT INTO `cexswap_api_call` (`user_id`, `user_server`, `method`, `full_json`, `date`)
                VALUES (%s, %s, %s, %s, %s);
                """
                await cur.execute(sql, (user_id, user_server, user_id, user_server, method, full_payload, int(time.time())))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def bot_user_add(user_id: str, user_server: str, api_key: str, hash_key: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `bot_users` 
                (`user_id`, `user_server`, `cexswap_api_key`, `cexswap_api_key_sha256`)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    `cexswap_api_key`=VALUES(`cexswap_api_key`),
                    `cexswap_api_key_sha256`=VALUES(`cexswap_api_key_sha256`)
                """
                await cur.execute(sql, (user_id, user_server, api_key, hash_key))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def find_user_by_id(user_id: str, user_server: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `bot_users` WHERE `user_id`=%s AND `user_server`=%s LIMIT 1
                """
                await cur.execute(sql, (user_id, user_server))
                result = await cur.fetchone()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def find_user_by_apikey(apikey: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `bot_users` WHERE `cexswap_api_key_sha256`=%s LIMIT 1
                """
                await cur.execute(sql, (apikey))
                result = await cur.fetchone()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def cexswap_get_coin_setting(ticker: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * 
                FROM `coin_settings` 
                WHERE `enable`=1 AND `cexswap_enable`=1 AND `coin_name`=%s LIMIT 1
                """
                await cur.execute(sql, ticker.upper())
                result = await cur.fetchone()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def cexswap_get_list_enable_pair_list():
    list_pairs = []
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * 
                FROM `coin_settings` 
                WHERE `enable`=1 AND `cexswap_enable`=1 """
                await cur.execute(sql,)
                result = await cur.fetchall()
                if result:
                    list_coins = sorted([i['coin_name'] for i in result])
                    for pair in itertools.combinations(list_coins, 2):
                        list_pairs.append("{}/{}".format(pair[0], pair[1]))
                    if len(list_pairs) > 0:
                        return {"coins": list_coins, "pairs": list_pairs}
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def cexswap_get_pools(ticker: str=None):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                data_rows = []
                sql = """ SELECT * 
                FROM `cexswap_pools` 
                """
                if ticker is not None:
                    sql += """
                        WHERE `ticker_1_name`=%s OR `ticker_2_name`=%s
                    """
                    data_rows += [ticker]*2
                await cur.execute(sql, tuple(data_rows))
                result = await cur.fetchall()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def cexswap_get_all_poolshares(user_id: str=None, ticker: str=None):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                data_rows = []
                sql = """ SELECT * 
                FROM `cexswap_pools_share` 
                """
                if user_id is not None:
                    sql += """
                    WHERE `user_id`=%s
                    """
                    data_rows += [user_id]
                if ticker is not None:
                    if user_id is not None:
                        sql += """
                            AND (`ticker_1_name`=%s OR `ticker_2_name`=%s)
                        """
                    else:
                        sql += """
                            WHERE `ticker_1_name`=%s OR `ticker_2_name`=%s
                        """
                    data_rows += [ticker]*2
                await cur.execute(sql, tuple(data_rows))
                result = await cur.fetchall()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def cexswap_get_all_lp_pools():
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT SUM(`amount_ticker_1`) as amount_ticker_1, SUM(`amount_ticker_2`) 
                    AS amount_ticker_2, `ticker_1_name`, `ticker_2_name`, `pairs`
                FROM `cexswap_pools`
                GROUP BY `pairs`;
                """
                await cur.execute(sql,)
                result = await cur.fetchall()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def cexswap_get_add_remove_user(user_id: str, user_server: str, pool_id: int=None):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT SUM(a.amount) AS amount, a.`token_name`, a.`user_id`, a.`action`, a.`pool_id`, b.`pairs`
                FROM `cexswap_add_remove_logs` a
                    INNER JOIN `cexswap_pools` b
                        ON a.pool_id= b.pool_id
                WHERE a.`user_id`=%s AND a.`user_server`=%s
                """
                data_rows = [user_id, user_server]
                if pool_id is not None:
                    sql += """ AND a.`pool_id`=%s"""
                    data_rows += [pool_id]

                sql +="""
                GROUP BY a.`action`, a.`token_name`
                """
                if pool_id is None:
                    sql += """, a.`pool_id`"""
                await cur.execute(sql, tuple(data_rows))
                result = await cur.fetchall()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def cexswap_get_pool_details(ticker_1: str, ticker_2: str, user_id: str=None):
    try:
        pool_detail = {}
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * 
                FROM `cexswap_pools` 
                WHERE `enable`=1 
                AND ((`ticker_1_name`=%s AND `ticker_2_name`=%s)
                    OR (`ticker_1_name`=%s AND `ticker_2_name`=%s)) """
                await cur.execute(sql, (ticker_1, ticker_2, ticker_2, ticker_1))
                result = await cur.fetchone()
                if result:
                    pool_detail['pool'] = result
                    pool_detail['pool_share'] = None
                    async with conn.cursor() as cur:
                        detail_res = None
                        if user_id is None:
                            sql = """ SELECT * 
                            FROM `cexswap_pools_share` 
                            WHERE `pool_id`=%s """
                            await cur.execute(sql, (result['pool_id']))
                            detail_res = await cur.fetchall()
                            if detail_res is not None:
                                pool_detail['pool_share'] = detail_res
                        else:
                            sql = """ SELECT * 
                            FROM `cexswap_pools_share` 
                            WHERE `pool_id`=%s AND `user_id`=%s """
                            await cur.execute(sql, (result['pool_id'], user_id))
                            detail_res = await cur.fetchone()
                            if detail_res is not None:
                                pool_detail['pool_share'] = detail_res
                        return pool_detail
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def cexswap_get_poolshare(user_id: str, user_server: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT a.pairs, a.amount_ticker_1 AS pool_amount_1,
                a.amount_ticker_2 AS pool_amount_2, b.* 
                FROM `cexswap_pools_share` b
                INNER JOIN `cexswap_pools` a
                    ON a.pool_id = b.pool_id
                WHERE b.`user_id`=%s AND b.`user_server`=%s
                """
                await cur.execute(sql, (user_id, user_server))
                result = await cur.fetchall()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def get_cexswap_get_sell_logs(user_id: str=None, from_time: int=None, pool_id: int=None):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                extra_sql = ""
                pool_sql = ""
                if user_id is None and from_time is not None:
                    extra_sql = """
                    WHERE a.`time`>%s
                    """
                elif from_time is not None:
                    extra_sql = """
                    AND a.`time`>%s
                    """
                if pool_id is not None:
                    if len(extra_sql) == "":
                        pool_sql = """
                        WHERE a.`pool_id`=%s
                        """
                    else:
                        pool_sql = """
                        AND a.`pool_id`=%s
                        """
                
                if user_id is not None:
                    sql = """
                    SELECT SUM(a.`total_sold_amount`) AS sold, SUM(a.`total_sold_amount_usd`) AS sold_usd,
                    SUM(a.`got_total_amount`) AS got, SUM(a.`got_total_amount_usd`) AS got_usd,
                    a.`sold_ticker`, a.`got_ticker`,
                    COUNT(*) AS `total_swap`, b.`pairs`
                    FROM `cexswap_sell_logs` a
                    INNER JOIN `cexswap_pools` b
                        ON a.pool_id = b.pool_id
                    GROUP BY a.`sold_ticker`, a.`got_ticker`
                    WHERE a.`sell_user_id`=%s """ + extra_sql + """ """ + pool_sql + """
                    """
                    data_rows = [user_id]
                    if len(extra_sql) > 0:
                        data_rows += [from_time]
                    if len(pool_sql) > 0:
                        data_rows += [pool_id]

                    await cur.execute(sql, tuple(data_rows))
                    result = await cur.fetchall()
                    if result:
                        return result
                else:
                    sql = """
                    SELECT SUM(a.`total_sold_amount`) AS sold, SUM(a.`total_sold_amount_usd`) AS sold_usd,
                    SUM(a.`got_total_amount`) AS got, SUM(a.`got_total_amount_usd`) AS got_usd,
                    a.`sold_ticker`, a.`got_ticker`,
                    COUNT(*) AS `total_swap`, b.`pairs`
                    FROM `cexswap_sell_logs` a
                    INNER JOIN `cexswap_pools` b
                        ON a.pool_id = b.pool_id
                     """ + extra_sql + """ """ + pool_sql + """
                    GROUP BY a.`sold_ticker`, a.`got_ticker`
                    """
                    data_rows = []
                    if len(extra_sql) > 0:
                        data_rows += [from_time]
                    if len(pool_sql) > 0:
                        data_rows += [pool_id]
                    await cur.execute(sql, tuple(data_rows))
                    result = await cur.fetchall()
                    if result:
                        return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def get_cexswap_get_coin_sell_logs(coin_name: str=None, user_id: str=None, from_time: int=None):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                extra_sql = ""
                if from_time is not None:
                    extra_sql = """
                    AND `time`>%s
                    """
                if user_id is not None:
                    extra_sql += """
                    AND `sell_user_id`=%s
                    """
                coin_name_sql = ""
                if coin_name is not None:
                    coin_name_sql = "WHERE (`sold_ticker`=%s OR `got_ticker`=%s)"

                sql = """
                SELECT SUM(`total_sold_amount`) AS sold, SUM(`total_sold_amount_usd`) AS sold_usd,
                SUM(`got_total_amount`) AS got, SUM(`got_total_amount_usd`) AS got_usd,
                `sold_ticker`, `got_ticker`, `pairs`,
                SUM(`got_fee_liquidators`) AS `fee_liquidators`,
                COUNT(*) AS total_swap
                FROM `cexswap_sell_logs`
                """+ coin_name_sql + extra_sql + """
                GROUP BY `sold_ticker`, `got_ticker`
                """
                if coin_name is None and (from_time is not None or user_id is not None) and "WHERE" not in sql:
                    sql = sql.replace("AND", "WHERE", 1)
                data_rows = []
                if coin_name is not None:
                    data_rows += [coin_name, coin_name]
                if from_time is not None:
                    data_rows += [from_time]
                if user_id is not None:
                    data_rows += [user_id]
                await cur.execute(sql, tuple(data_rows))
                result = await cur.fetchall()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def get_cexswap_earning(user_id: str=None, from_time: int=None, pool_id: int=None, group_pool: bool=False):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                extra_sql = ""
                pool_sql = ""
                if user_id is None and from_time is not None:
                    extra_sql = """
                    WHERE a.`date`>%s
                    """
                elif from_time is not None:
                    extra_sql = """
                    AND a.`date`>%s
                    """
                if pool_id is not None:
                    if len(extra_sql) == "":
                        pool_sql = """
                        WHERE a.`pool_id`=%s
                        """
                    else:
                        pool_sql = """
                        AND a.`pool_id`=%s
                        """
                
                if user_id is not None:
                    sql = """
                    SELECT b.`pairs`, a.`pool_id`, a.`got_ticker`, a.`distributed_user_id`, a.`distributed_user_server`, 
                        SUM(a.`distributed_amount`) AS collected_amount, SUM(a.`got_total_amount`) AS got_total_amount,
                        COUNT(*) AS total_swap
                    FROM `cexswap_distributing_fee` a
                        INNER JOIN `cexswap_pools` b
                            ON a.pool_id= b.pool_id
                    WHERE a.`distributed_user_id`=%s """ + extra_sql + """ """ + pool_sql + """
                    GROUP BY a.`got_ticker`
                    """
                    if group_pool is True:
                        sql += """
                        , a.`pool_id`
                        """
                    data_rows = [user_id]
                    if len(extra_sql) > 0:
                        data_rows += [from_time]
                    if len(pool_sql) > 0:
                        data_rows += [pool_id]

                    await cur.execute(sql, tuple(data_rows))
                    result = await cur.fetchall()
                    if result:
                        return result
                else:
                    sql = """
                    SELECT `got_ticker`, `distributed_user_id`, `distributed_user_server`, 
                        SUM(`distributed_amount`) AS collected_amount, SUM(`got_total_amount`) AS got_total_amount,
                        COUNT(*) as total_swap
                    FROM `cexswap_distributing_fee`
                     """ + extra_sql + """ """ + pool_sql + """
                    GROUP BY `got_ticker`
                    """
                    data_rows = []
                    if len(extra_sql) > 0:
                        data_rows += [from_time]
                    if len(pool_sql) > 0:
                        data_rows += [pool_id]
                    await cur.execute(sql, tuple(data_rows))
                    result = await cur.fetchall()
                    if result:
                        return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def cexswap_earning_guild(guild_id: str=None):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if guild_id is not None:
                    sql = """
                    SELECT *, SUM(`real_amount`) AS collected_amount, SUM(`real_amount_usd`) AS collected_amount_usd,
                        COUNT(*) as total_swap
                    FROM `user_balance_mv`
                    WHERE `from_userid`=%s AND `to_userid`=%s AND `type`=%s
                    GROUP BY `token_name`
                    """
                    await cur.execute(sql, ("SYSTEM", guild_id, "CEXSWAPLP"))
                    result = await cur.fetchall()
                    if result:
                        return result
                else:
                    sql = """
                    SELECT *, SUM(`real_amount`) AS collected_amount, SUM(`real_amount_usd`) AS collected_amount_usd,
                        COUNT(*) as total_swap
                    FROM `user_balance_mv`
                    WHERE `type`=%s
                    GROUP BY `token_name`
                    """
                    await cur.execute(sql, ("CEXSWAPLP"))
                    result = await cur.fetchall()
                    if result:
                        return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def cexswap_airdrop_check_op(
    user_id: str, user_server: str, pool_name: str
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `cexswap_airdroper_op`
                WHERE `is_enable`=1 AND `user_id`=%s AND `user_server`=%s AND `pool_name`=%s LIMIT 1
                """
                await cur.execute(sql, (user_id, user_server, pool_name))
                result = await cur.fetchone()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def cexswap_airdrop_count(
    user_id: str, user_server: str, pool_name: str, duration: int=7*24*3600
):
    try:
        lap_time = int(time.time()) - duration
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT COUNT(*) AS counts FROM `cexswap_airdroper_op_logs`
                WHERE `user_id`=%s AND `user_server`=%s AND `pool_name`=%s
                AND `cexswap_airdroper_op_logs`>%s
                """
                await cur.execute(sql, (user_id, user_server, pool_name, lap_time))
                result = await cur.fetchone()
                if result:
                    return result['counts']
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return 0

async def cexswap_airdrop_lp_detail(
    list_balance_updates, list_lp_receivers,
    op_id: str, user_server: str, drop_amount: float, drop_coin: str, pool_name: str
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # deduct from airdroper, plus receivers
                sql = """
                INSERT INTO `user_balance_mv_data`
                (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    `balance`=`balance`+VALUES(`balance`),
                    `update_date`=VALUES(`update_date`);
                """
                await cur.executemany(sql, list_balance_updates)
                await conn.commit()

                # airdrop table
                sql = """
                INSERT INTO `cexswap_airdrop_lp_detail`
                (`pool_id`, `pairs`, `from_userid`, `to_userid`, `token_name`, 
                `total_airdrop_amount`, `user_airdrop_amount`, `user_pool_percentage`, `date`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                await cur.executemany(sql, list_lp_receivers)
                await conn.commit()

                # Update log
                sql = """
                INSERT INTO `cexswap_airdroper_op_logs`
                (`user_id`, `user_server`, `drop_amount`, `drop_coin`, `drop_time`, `pool_name`)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                await cur.execute(sql, (op_id, user_server, drop_amount, drop_coin, int(time.time()), pool_name))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def cexswap_admin_remove_pool(
    pool_id: int, user_id: str, user_server: str,
    amount_1: float, ticker_1: str, amount_2: float, ticker_2: str,
    liq_users
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                DELETE FROM `cexswap_pools` 
                WHERE `pool_id`=%s LIMIT 1;
                """
                data_rows = [pool_id]

                sql += """
                INSERT INTO `cexswap_add_remove_logs`
                (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                VALUES (%s, %s, %s, %s, %s, %s, %s);

                INSERT INTO `cexswap_add_remove_logs`
                (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """
                data_rows += [pool_id, user_id, user_server, "removepool", int(time.time()), amount_1, ticker_1]
                data_rows += [pool_id, user_id, user_server, "removepool", int(time.time()), amount_2, ticker_2]

                sql += """
                DELETE FROM `cexswap_pools_share` 
                WHERE `pool_id`=%s;
                """
                data_rows += [pool_id]

                if len(liq_users) > 0:
                    add_sql = """
                    UPDATE `user_balance_mv_data`
                    SET `balance`=`balance`+%s, `update_date`=%s
                    WHERE `user_id`=%s AND `token_name`=%s AND `user_server`=%s LIMIT 1;
                    """ * int(len(liq_users)/5) # because the list is exploded and 5 elements to insert
                    sql += add_sql
                    data_rows += liq_users

                await cur.execute(sql, tuple(data_rows))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def cexswap_remove_pool_share(
    pool_id: int, amount_1: float, ticker_1: str, amount_2: float, ticker_2: str,
    user_id: str, user_server: str, complete: bool=False, delete_pool: bool=False
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if delete_pool is True:
                    extra = """
                    DELETE FROM `cexswap_pools` 
                    WHERE `pool_id`=%s LIMIT 1;
                    """
                else:
                    extra = """
                    UPDATE `cexswap_pools`
                        SET `amount_ticker_1`=`amount_ticker_1`-%s,
                            `amount_ticker_2`=`amount_ticker_2`-%s
                        WHERE `pool_id`=%s AND `ticker_1_name`=%s AND `ticker_2_name`=%s;
                    """
                if complete is True:
                    sql = extra + """
                    DELETE FROM `cexswap_pools_share`
                    WHERE `pool_id`=%s AND `ticker_1_name`=%s AND `ticker_2_name`=%s 
                        AND `user_id`=%s AND `user_server`=%s LIMIT 1;

                    INSERT INTO `user_balance_mv_data`
                    (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        `balance`=`balance`+VALUES(`balance`),
                        `update_date`=VALUES(`update_date`);

                    INSERT INTO `user_balance_mv_data`
                    (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        `balance`=`balance`+VALUES(`balance`),
                        `update_date`=VALUES(`update_date`);

                    INSERT INTO `cexswap_add_remove_logs`
                    (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);

                    INSERT INTO `cexswap_add_remove_logs`
                    (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """
                    data_rows = [
                        pool_id, ticker_1, ticker_2, user_id, user_server,
                        user_id, ticker_1, user_server, amount_1, int(time.time()),
                        user_id, ticker_2, user_server, amount_2, int(time.time()),
                        pool_id, user_id, user_server, "remove", int(time.time()), amount_1, ticker_1,
                        pool_id, user_id, user_server, "remove", int(time.time()), amount_2, ticker_2,
                    ]
                    if delete_pool is True:
                        data_rows = [pool_id] + data_rows
                    else:
                        data_rows = [amount_1, amount_2, pool_id, ticker_1, ticker_2] + data_rows
                    await cur.execute(sql, tuple(data_rows))
                    await conn.commit()
                    return True
                else:
                    sql = extra + """
                    UPDATE `cexswap_pools_share`
                        SET `amount_ticker_1`=`amount_ticker_1`-%s, `amount_ticker_2`=`amount_ticker_2`-%s
                    WHERE `pool_id`=%s AND `ticker_1_name`=%s AND `ticker_2_name`=%s AND `user_id`=%s 
                        AND `user_server`=%s LIMIT 1;

                    INSERT INTO `user_balance_mv_data`
                    (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        `balance`=`balance`+VALUES(`balance`),
                        `update_date`=VALUES(`update_date`);

                    INSERT INTO `user_balance_mv_data`
                    (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        `balance`=`balance`+VALUES(`balance`),
                        `update_date`=VALUES(`update_date`);

                    INSERT INTO `cexswap_add_remove_logs`
                    (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);

                    INSERT INTO `cexswap_add_remove_logs`
                    (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """
                    data_rows = [
                        amount_1, amount_2, pool_id, ticker_1, ticker_2, user_id, user_server,
                        user_id, ticker_1, user_server, amount_1, int(time.time()),
                        user_id, ticker_2, user_server, amount_2, int(time.time()),
                        pool_id, user_id, user_server, "remove", int(time.time()), amount_1, ticker_1,
                        pool_id, user_id, user_server, "remove", int(time.time()), amount_2, ticker_2
                    ]
                    if delete_pool is True:
                        data_rows = [pool_id] + data_rows
                    else:
                        data_rows = [amount_1, amount_2, pool_id, ticker_1, ticker_2] + data_rows
                    await cur.execute(sql, tuple(data_rows))
                    await conn.commit()
                    return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def cexswap_route_trade(
    from_coin: str, to_coin: str
):
    try:
        # Select all pair where there is from_coin
        # Need A->B, Find A->C, C->B .. A->D, D->B, so on
        possible_trade = []
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                from_coin_pairs = []
                to_coin_pairs = []
                sql = """
                SELECT * FROM `cexswap_pools`
                WHERE (`ticker_1_name`=%s AND `ticker_2_name`<>%s)
                    OR (`ticker_2_name`=%s AND `ticker_1_name`<>%s)
                """
                # FROM
                await cur.execute(sql, (
                    from_coin, to_coin, from_coin, to_coin
                ))
                result = await cur.fetchall()

                if result:
                    from_coin_pairs = result

                # TO
                sql = """
                SELECT * FROM `cexswap_pools`
                WHERE (`ticker_1_name`=%s AND `ticker_2_name`<>%s)
                    OR (`ticker_2_name`=%s AND `ticker_1_name`<>%s)
                """
                await cur.execute(sql, (to_coin, from_coin, to_coin, from_coin))
                result = await cur.fetchall()

                if result:
                    to_coin_pairs = result
                if len(from_coin_pairs) == 0 or len(to_coin_pairs) == 0:
                    return possible_trade
                else:
                    # check if a coin in from_coin_pairs exist in to_coin_pairs
                    for each in from_coin_pairs:
                        middle_coin = each['ticker_2_name']
                        if from_coin == each['ticker_2_name']:
                            middle_coin = each['ticker_1_name']

                        for target in to_coin_pairs:
                            if target['ticker_1_name'] == middle_coin or target['ticker_2_name'] == middle_coin :
                                possible_trade.append(middle_coin)

                    return list(set(possible_trade))
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return possible_trade

async def cexswap_find_possible_trade(
    from_coin: str, to_coin: str, from_amount: float,
    old_amount_get: float
):
    try:
        # Select all pair where there is from_coin
        # Need A->B, Find A->C, C->B .. A->D, D->B, so on
        possible_profits = []
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                from_coin_pairs = []
                to_coin_pairs = []
                sql = """
                SELECT * FROM `cexswap_pools`
                WHERE (`ticker_1_name`=%s AND `amount_ticker_1`>%s AND `ticker_2_name`<>%s)
                    OR (`ticker_2_name`=%s AND `amount_ticker_2`>%s AND `ticker_1_name`<>%s)
                """
                # FROM
                await cur.execute(sql, (
                    from_coin, from_amount, to_coin, from_coin, from_amount, to_coin
                ))
                result = await cur.fetchall()
                if result:
                    from_coin_pairs = result

                # TO
                sql = """
                SELECT * FROM `cexswap_pools`
                WHERE (`ticker_1_name`=%s AND `ticker_2_name`<>%s)
                    OR (`ticker_2_name`=%s AND `ticker_1_name`<>%s)
                """
                await cur.execute(sql, (to_coin, from_coin, to_coin, from_coin))
                result = await cur.fetchall()
                if result:
                    to_coin_pairs = result
                if len(from_coin_pairs) == 0 or len(to_coin_pairs) ==0:
                    return possible_profits
                else:
                    # check if a coin in from_coin_pairs exist in to_coin_pairs
                    for each in from_coin_pairs:
                        coin = each['ticker_1_name']
                        middle_coin = each['ticker_2_name']
                        middle_amount = each['amount_ticker_2'] / each['amount_ticker_1'] * Decimal(from_amount) * Decimal(0.99)
                        if coin != from_coin:
                            coin = each['ticker_2_name']
                            middle_coin = each['ticker_1_name']
                            middle_amount = each['amount_ticker_1'] / each['amount_ticker_2'] * Decimal(from_amount) * Decimal(0.99)
                        for target in to_coin_pairs:
                            target_coin = target['ticker_1_name']
                            middle_coin_check = target['ticker_2_name']
                            midle_rate = target['amount_ticker_2'] / target['amount_ticker_1']
                            if target_coin != to_coin:
                                target_coin = target['ticker_2_name']
                                middle_coin_check = target['ticker_1_name']
                                middle_coin_rate = target['amount_ticker_1'] / target['amount_ticker_2']
                                if middle_coin != middle_coin_check:
                                    continue
                                else:
                                    got_amount = middle_amount / middle_coin_rate * Decimal(0.99)
                                    msg = "{}/{} = {} {} => {}/{} got: {} {}".format(
                                        from_coin, middle_coin, middle_amount, middle_coin,
                                        middle_coin, to_coin, got_amount, to_coin)
                                    if old_amount_get < got_amount:
                                        # print("PROFIT=>{}".format(msg))
                                        possible_profits.append("  ⚆ {}=>{}, {}=>{}".format(
                                            from_coin, middle_coin, middle_coin, to_coin
                                        ))
                                    else:
                                        # print("NO PROFIT=>{}".format(msg))
                                        pass
                    return possible_profits
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return possible_profits

async def cexswap_estimate(
    ref_log: str, pool_id: int, pairs: str, amount_sell: float, sell_ticker: str,
    amount_get: float, got_ticker: str,
    got_fee_dev: float, got_fee_liquidators: float,
    got_fee_guild: float, price_impact_percent: float,
    user_id: str, user_server: str, use_api: int
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                INSERT INTO `cexswap_estimate`
                (`pool_id`, `pairs`, `ref_log`, `sold_ticker`, `total_sold_amount`,
                `got_total_amount`,  `got_fee_dev`, `got_fee_liquidators`, `got_fee_guild`, 
                `got_ticker`, `price_impact_percent`, `time`, `user_id`, `user_server`, `use_api`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                data_rows = [
                    pool_id, pairs, ref_log, sell_ticker, float(amount_sell),
                    float(amount_get), float(got_fee_dev), float(got_fee_liquidators), float(got_fee_guild),
                    got_ticker, price_impact_percent, int(time.time()), user_id, user_server, use_api
                ]
                await cur.execute(sql, tuple(data_rows))
                await conn.commit()
        return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def cexswap_count_api_usage(
    user_id: str, user_server: int, use_api: int=1, duration: int=1*3600
):
    lap = int(time.time()) - duration
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT COUNT(*) AS numb FROM `cexswap_estimate` WHERE `user_id`=%s AND `user_server`=%s AND `use_api`=%s
                AND `time`>%s
                """
                await cur.execute(sql, (user_id, user_server, use_api, lap))
                result = await cur.fetchone()
                if result:
                    return result['numb']
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return 0

async def cexswap_sold_by_api(
    ref_log: str, amount_sell: float, sell_token: str, 
    for_token: str, user_id: str, user_server: str,
    coin_list, config
):
    """
    coin_list: list of all coin to get params
    config: configuration file
    """
    amount_sell = float(amount_sell)
    try:
        cexswap_enable = getattr(getattr(coin_list, sell_token), "cexswap_enable")
        if cexswap_enable != 1:
            return {
                "success": False,
                "error": f"{sell_token} not enable CEXSwap!",
            }
        cexswap_enable = getattr(getattr(coin_list, for_token), "cexswap_enable")
        if cexswap_enable != 1:
            return {
                "success": False,
                "error": f"{for_token} not enable CEXSwap!",
            }
        # check amount
        min_swap = truncate(getattr(getattr(coin_list, sell_token), "cexswap_min"), 8)
        if truncate(amount_sell, 8) < min_swap:
            return {
                "success": False,
                "error": "Sell amount is below minimum!",
            }
        # find LP amount
        liq_pair = await cexswap_get_pool_details(sell_token, for_token, None)
        if liq_pair is None:
            return {
                "success": False,
                "error": f"There is no pair {sell_token}/{for_token}",
            }
        else:
            # check if coin sell is enable
            is_sellable = getattr(getattr(coin_list, sell_token), "cexswap_sell_enable")
            if is_sellable != 1:
                return {
                    "success": False,
                    "error": f"Coin/token `{sell_token}` is currently disable for CEXSwap.",
                }
            is_sellable = getattr(getattr(coin_list, for_token), "cexswap_sell_enable")
            if is_sellable != 1:
                return {
                    "success": False,
                    "error": f"Coin/token `{for_token}` is currently disable for CEXSwap.",
                }
            try:
                # check amount
                amount_liq_sell = liq_pair['pool']['amount_ticker_1']
                if sell_token == liq_pair['pool']['ticker_2_name']:
                    amount_liq_sell = liq_pair['pool']['amount_ticker_2']
                cexswap_min = getattr(getattr(coin_list, sell_token), "cexswap_min")
                token_display = getattr(getattr(coin_list, sell_token), "display_name")
                cexswap_max_swap_percent_sell = getattr(getattr(coin_list, sell_token), "cexswap_max_swap_percent")
                max_swap_sell_cap = cexswap_max_swap_percent_sell * float(amount_liq_sell)

                # Check if amount is more than liquidity
                if truncate(float(amount_sell), 8) > truncate(float(max_swap_sell_cap), 8):
                    msg = f"The given amount {amount_sell}"\
                        f" is more than allowable 10% of liquidity {num_format_coin(max_swap_sell_cap)} {sell_token}." \
                        f" Current LP: {num_format_coin(liq_pair['pool']['amount_ticker_1'])} "\
                        f"{liq_pair['pool']['ticker_1_name']} and "\
                        f"{num_format_coin(liq_pair['pool']['amount_ticker_2'])} "\
                        f"{liq_pair['pool']['ticker_2_name']} for LP {liq_pair['pool']['ticker_1_name']}/{liq_pair['pool']['ticker_2_name']}."
                    return {
                        "success": False,
                        "error": msg,
                    }

                # Check if too big rate gap
                try:
                    rate_ratio = liq_pair['pool']['amount_ticker_1'] / liq_pair['pool']['amount_ticker_2']
                    if rate_ratio > 10**12 or rate_ratio < 1/10**12:
                        msg = "Rate ratio is out of range. Try with other pairs."
                        return {
                            "success": False,
                            "error": msg,
                        }
                except Exception:
                    traceback.print_exc(file=sys.stdout)

                # check slippage first
                slippage = 1.0 - amount_sell / float(liq_pair['pool']['amount_ticker_1']) - config['cexswap_slipage']['reserve']
                amount_get = amount_sell * float(liq_pair['pool']['amount_ticker_2'] / liq_pair['pool']['amount_ticker_1'])

                amount_qty_1 = liq_pair['pool']['amount_ticker_2']
                amount_qty_2 = liq_pair['pool']['amount_ticker_1']

                if sell_token == liq_pair['pool']['ticker_2_name']:
                    amount_get = amount_sell * float(liq_pair['pool']['amount_ticker_1'] / liq_pair['pool']['amount_ticker_2'])
                    slippage = 1.0 - amount_sell / float(liq_pair['pool']['amount_ticker_2']) - config['cexswap_slipage']['reserve']

                    amount_qty_1 = liq_pair['pool']['amount_ticker_1']
                    amount_qty_2 = liq_pair['pool']['amount_ticker_2']

                # adjust slippage
                amount_get = slippage * amount_get
                if slippage > 1 or slippage < 0.88:
                    msg = "Internal error with slippage. Try again later!"
                    return {
                        "success": False,
                        "error": msg,
                    }

                # price impact = unit price now / unit price after sold
                price_impact_text = ""
                price_impact_percent = 0.0
                new_impact_ratio = (float(amount_qty_2) + amount_sell) / (float(amount_qty_1) - amount_get)
                old_impact_ratio = float(amount_qty_2) / float(amount_qty_1)
                impact_ratio = abs(old_impact_ratio - new_impact_ratio) / max(old_impact_ratio, new_impact_ratio)
                if 0.0001 < impact_ratio < 1:
                    price_impact_text = "\nPrice impact: ~{:,.2f}{}".format(impact_ratio * 100, "%")
                    price_impact_percent = impact_ratio * 100
                
                # If the amount get is too small.
                if amount_get < config['cexswap']['minimum_receive_or_reject']:
                    num_receive = num_format_coin(amount_get)
                    msg = f"The received amount is too small "\
                        f"{num_receive} {for_token}. Please increase your sell amount!"
                    return {
                        "success": False,
                        "error": msg,
                    }
                else:
                    # OK, sell..
                    got_fee_dev = amount_get * config['cexswap']['dev_fee'] / 100
                    got_fee_liquidators = amount_get * config['cexswap']['liquidator_fee'] / 100
                    got_fee_guild = 0.0
                    guild_id = "CEXSWAP API"
                    got_fee_dev += amount_get * config['cexswap']['guild_fee'] / 100
                    liq_users = []
                    if len(liq_pair['pool_share']) > 0:
                        for each_s in liq_pair['pool_share']:
                            distributed_amount = None
                            if for_token == each_s['ticker_1_name']:
                                distributed_amount = float(each_s['amount_ticker_1']) / float(liq_pair['pool']['amount_ticker_1']) * float(truncate(got_fee_liquidators, 12))
                            elif for_token == each_s['ticker_2_name']:
                                distributed_amount = float(each_s['amount_ticker_2']) / float(liq_pair['pool']['amount_ticker_2']) * float(truncate(got_fee_liquidators, 12))
                            if distributed_amount is not None:
                                liq_users.append([distributed_amount, each_s['user_id'], each_s['user_server']])
                    contract = getattr(getattr(coin_list, for_token), "contract")
                    channel_id = "CEXSWAP API"
                    # get price per unit
                    per_unit_sell = 0.0 # TODO
                    per_unit_get = 0.0 # TODO

                    fee = truncate(got_fee_dev, 12) + truncate(got_fee_liquidators, 12) + truncate(got_fee_guild, 12)
                    user_amount_get = num_format_coin(truncate(amount_get - float(fee), 12))
                    user_amount_sell = num_format_coin(amount_sell)
                    coin_decimal = getattr(getattr(coin_list, for_token), "decimal")

                    pool_amount_get = liq_pair['pool']['amount_ticker_2']
                    pool_amount_sell = liq_pair['pool']['amount_ticker_1']
                    if sell_token == liq_pair['pool']['ticker_2_name']:
                        pool_amount_get = liq_pair['pool']['amount_ticker_1']
                        pool_amount_sell = liq_pair['pool']['amount_ticker_2']

                    api_message = "[CEXSWAP API]: A user sold {} {} for {} {}.".format(
                        user_amount_sell, sell_token, user_amount_get, for_token
                    )
                    selling = await cexswap_sold(
                        ref_log, liq_pair['pool']['pool_id'], truncate(amount_sell, 12), sell_token, 
                        truncate(amount_get, 12), for_token, user_id, user_server,
                        guild_id,
                        truncate(got_fee_dev, 12), truncate(got_fee_liquidators, 12), truncate(got_fee_guild, 12),
                        liq_users, contract, coin_decimal, channel_id, per_unit_sell, per_unit_get,
                        pool_amount_sell, pool_amount_get,
                        1, api_message
                    )
                    if selling is True:
                        msg = f"Successfully traded! "\
                            f"Get {user_amount_get} {for_token} "\
                            f"from selling {user_amount_sell} {sell_token}{price_impact_text} Ref: {ref_log}"
                        del_users_cache =  ["{}_{}_{}".format(i[1], sell_token, i[2]) for i in liq_users]
                        del_users_cache +=  ["{}_{}_{}".format(i[1], for_token, i[2]) for i in liq_users]
                        del_users_cache += ["{}_{}_{}".format(user_id, sell_token, user_server)]
                        del_users_cache += ["{}_{}_{}".format(user_id, for_token, user_server)]
                        return {
                            "success": True,
                            "sell": user_amount_sell,
                            "sell_token": sell_token,
                            "get": user_amount_get,
                            "for_token": for_token,
                            "price_impact_percent": price_impact_percent,
                            "delete_cache_balance":del_users_cache,
                            "message": msg,
                            "ref": ref_log
                        }
            except Exception:
                traceback.print_exc(file=sys.stdout)
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {
        "success": False,
        "error": "Internal error!",
    }

async def cexswap_sold(
    ref_log: str, pool_id: int, amount_sell: float, sell_ticker: str,
    amount_get: float, got_ticker: str,
    user_id: str, user_server: str,
    guild_id: str,
    got_fee_dev: float, got_fee_liquidators: float,
    got_fee_guild: float, liquidators, contract: str, coin_decimal: int,
    channel_id: str, per_unit_sell: float, per_unit_get: float,
    pool_amount_sell: float, pool_amount_get: float,
    api: int=0, api_message: str=None
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Add sell coin to liq
                # Remove got coin from liq
                # Update pool_share
                # Add got coin to user
                # Remove sell coin from user
                # Distribute %
                sql = """
                UPDATE `cexswap_pools`
                SET `amount_ticker_1`=`amount_ticker_1`+%s
                WHERE `ticker_1_name`=%s AND `pool_id`=%s;

                UPDATE `cexswap_pools`
                SET `amount_ticker_2`=`amount_ticker_2`+%s
                WHERE `ticker_2_name`=%s AND `pool_id`=%s;

                UPDATE `cexswap_pools`
                SET `amount_ticker_1`=`amount_ticker_1`-%s
                WHERE `ticker_1_name`=%s AND `pool_id`=%s;

                UPDATE `cexswap_pools`
                SET `amount_ticker_2`=`amount_ticker_2`-%s
                WHERE `ticker_2_name`=%s AND `pool_id`=%s;
                """
                data_rows = [
                    float(amount_sell), sell_ticker, pool_id, float(amount_sell), sell_ticker, pool_id, 
                    float(amount_get), got_ticker, pool_id, float(amount_get), got_ticker, pool_id
                ]

                sql += """
                UPDATE `cexswap_pools_share`
                SET `amount_ticker_1`=`amount_ticker_1`+%s*`amount_ticker_1`
                WHERE `ticker_1_name`=%s AND `pool_id`=%s;

                UPDATE `cexswap_pools_share`
                SET `amount_ticker_2`=`amount_ticker_2`+%s*`amount_ticker_2`
                WHERE `ticker_2_name`=%s AND `pool_id`=%s;
                """
                data_rows += [
                    float(amount_sell)/float(pool_amount_sell), sell_ticker, pool_id,
                    float(amount_sell)/float(pool_amount_sell), sell_ticker, pool_id
                ]

                sql += """
                UPDATE `cexswap_pools_share`
                SET `amount_ticker_1`=`amount_ticker_1`-%s*`amount_ticker_1`
                WHERE `ticker_1_name`=%s AND `pool_id`=%s;

                UPDATE `cexswap_pools_share`
                SET `amount_ticker_2`=`amount_ticker_2`-%s*`amount_ticker_2`
                WHERE `ticker_2_name`=%s AND `pool_id`=%s;
                """
                data_rows += [
                    float(amount_get)/float(pool_amount_get), got_ticker, pool_id,
                    float(amount_get)/float(pool_amount_get), got_ticker, pool_id
                ]

                sql += """
                INSERT INTO `user_balance_mv_data`
                (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    `balance`=`balance`+VALUES(`balance`),
                    `update_date`=VALUES(`update_date`);

                INSERT INTO `user_balance_mv_data`
                (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    `balance`=`balance`+VALUES(`balance`),
                    `update_date`=VALUES(`update_date`);
                """
                data_rows += [
                    user_id, sell_ticker, SERVER_BOT, -float(amount_sell), int(time.time()),
                    user_id, got_ticker, SERVER_BOT,  float(amount_get)-float(got_fee_dev)-float(got_fee_liquidators)-float(got_fee_guild), int(time.time())                            
                ]

                sql += """
                INSERT INTO `user_balance_mv_data`
                (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    `balance`=`balance`+VALUES(`balance`),
                    `update_date`=VALUES(`update_date`);

                INSERT INTO `user_balance_mv_data`
                (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    `balance`=`balance`+VALUES(`balance`),
                    `update_date`=VALUES(`update_date`);

                """
                data_rows += [
                    "SYSTEM", got_ticker, SERVER_BOT, float(got_fee_dev), int(time.time()),
                    guild_id, got_ticker, SERVER_BOT, float(got_fee_guild), int(time.time())
                ]

                sql += """
                INSERT INTO `cexswap_sell_logs`
                (`pool_id`, `pairs`, `ref_log`, `sold_ticker`, `total_sold_amount`, `total_sold_amount_usd`,
                `guild_id`, `got_total_amount`, `got_total_amount_usd`,
                `got_fee_dev`, `got_fee_liquidators`, `got_fee_guild`, `got_ticker`,
                `sell_user_id`, `user_server`, `api`, `api_messsage`, `time`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                data_rows += [
                    pool_id, "{}->{}".format(sell_ticker, got_ticker), ref_log, sell_ticker, float(amount_sell),
                    float(amount_sell)*float(per_unit_sell), guild_id, float(amount_get),float(amount_get)*float(per_unit_get),
                    float(got_fee_dev), float(got_fee_liquidators), float(got_fee_guild), got_ticker, user_id,
                    user_server, api, api_message, int(time.time())
                ]
                await cur.execute(sql, tuple(data_rows))
                await conn.commit()

                sql = """ SELECT * 
                    FROM `cexswap_sell_logs` 
                    WHERE `ref_log`=%s LIMIT 1
                    """
                sell_id = cur.lastrowid
                await cur.execute(sql, ref_log)
                result = await cur.fetchone()
                if result:
                    sell_id = result['log_id']

                # add to distributed fee
                sql = """
                    INSERT INTO `cexswap_distributing_fee`
                    (`sell_log_id`, `pool_id`, `got_ticker`, `got_total_amount`, 
                    `distributed_amount`, `distributed_amount_usd`, `distributed_user_id`, `distributed_user_server`, `date`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                liq_rows = []
                for each in liquidators:
                    liq_rows.append((
                        sell_id, pool_id, got_ticker, float(amount_get),
                        each[0], float(each[0])*float(per_unit_get), each[1], each[2], int(time.time())
                    ))
                await cur.executemany(sql, liq_rows)

                # add to mv_data # user_balance_mv_data
                sql = """
                    INSERT INTO `user_balance_mv`
                    (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`,
                    `real_amount`, `real_amount_usd`, `token_decimal`, `type`, `date`, `user_server`, `extra_message`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                liq_rows = []
                credit_lp = []
                for each in liquidators:
                    liq_rows.append((
                        got_ticker, contract, "SYSTEM", each[1], guild_id, channel_id,
                        each[0], each[0]*float(per_unit_get), coin_decimal, "CEXSWAPLP", int(time.time()), each[2],
                        ref_log
                    ))
                    credit_lp.append(
                        (each[1], got_ticker, each[2], each[0], int(time.time()))
                    )

                if guild_id != "DM":
                    liq_rows.append((
                        got_ticker, contract, "SYSTEM", guild_id, guild_id, channel_id,
                        float(got_fee_guild), float(got_fee_guild)*float(per_unit_get), coin_decimal, "CEXSWAPLP", int(time.time()), each[2],
                        ref_log
                    ))
                await cur.executemany(sql, liq_rows)
                # add mv distribution fee
                sql = """
                INSERT INTO `user_balance_mv_data`
                (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    `balance`=`balance`+VALUES(`balance`),
                    `update_date`=VALUES(`update_date`);
                """
                if len(credit_lp) > 0:
                    await cur.executemany(sql, credit_lp)
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def cexswap_insert_new(
    pairs: str, amount_ticker_1: str, ticker_1_name: str,
    amount_ticker_2: str, ticker_2_name: str, user_id: str, user_server: str
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                pool_id = None
                existing_pool = False
                sql = """ SELECT * 
                    FROM `cexswap_pools` 
                    WHERE `enable`=1 
                    AND ((`ticker_1_name`=%s AND `ticker_2_name`=%s)
                        OR (`ticker_1_name`=%s AND `ticker_2_name`=%s)) """
                await cur.execute(sql, (ticker_1_name, ticker_2_name, ticker_2_name, ticker_1_name))
                result = await cur.fetchone()
                if result:
                    pool_id = result['pool_id']
                    existing_pool = True
                else:
                    sql = """ INSERT INTO `cexswap_pools` 
                        (`pairs`, `amount_ticker_1`, `ticker_1_name`, `amount_ticker_2`,
                        `ticker_2_name`, `initialized_by`, `initialized_date`, `updated_date`)
                        VALUES 
                        (%s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (
                        pairs, amount_ticker_1, ticker_1_name, amount_ticker_2, ticker_2_name,
                        user_id, int(time.time()), int(time.time())
                    ))
                    await conn.commit()
                    pool_id = cur.lastrowid
                
                if pool_id is not None:
                    sql = """
                    INSERT INTO `cexswap_pools_share`
                    (`pool_id`, `pairs`, `amount_ticker_1`, `ticker_1_name`,
                    `amount_ticker_2`, `ticker_2_name`, `user_id`, `user_server`,
                    `updated_date`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY 
                        UPDATE 
                        `amount_ticker_1`=amount_ticker_1+VALUES(`amount_ticker_1`),
                        `amount_ticker_2`=amount_ticker_2+VALUES(`amount_ticker_2`),
                        `updated_date`=VALUES(`updated_date`);
                    
                    INSERT INTO `cexswap_add_remove_logs`
                    (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);

                    INSERT INTO `cexswap_add_remove_logs`
                    (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """
                    data_row = [pool_id, pairs, amount_ticker_1, ticker_1_name,
                        amount_ticker_2, ticker_2_name, user_id, user_server, int(time.time()),
                        pool_id, user_id, user_server, "add", int(time.time()), amount_ticker_1, ticker_1_name,
                        pool_id, user_id, user_server, "add", int(time.time()), amount_ticker_2, ticker_2_name
                    ]
                    # Insert new pool share
                    sql += """
                    INSERT INTO `user_balance_mv_data`
                    (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        `balance`=`balance`+VALUES(`balance`),
                        `update_date`=VALUES(`update_date`);

                    INSERT INTO `user_balance_mv_data`
                    (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        `balance`=`balance`+VALUES(`balance`),
                        `update_date`=VALUES(`update_date`);
                    """
                    data_row += [
                        user_id, ticker_1_name, user_server, -amount_ticker_1, int(time.time()),
                        user_id, ticker_2_name, user_server, -amount_ticker_2, int(time.time())
                    ]
                    if existing_pool is True:
                        sql += """ UPDATE `cexswap_pools` 
                        SET `amount_ticker_1`=`amount_ticker_1`+%s,
                            `amount_ticker_2`=`amount_ticker_2`+%s,
                            `updated_date`=%s
                        WHERE `pool_id`=%s LIMIT 1;"""
                        data_row += [amount_ticker_1, amount_ticker_2, int(time.time()), pool_id]
                    await cur.execute(sql, tuple(data_row))
                    await conn.commit()
                    return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

# Single coin of /selectpool
class SelectPoolSingle(disnake.ui.View):
    def __init__(
        self, timeout, ctx, bot, owner_id: int, embed_rate, embed_lp, embed_30d=None, embed_7d=None
    ):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.bot = bot
        self.owner_id = owner_id
        self.embed_rate = embed_rate
        self.embed_lp = embed_lp
        self.embed_30d = embed_30d
        self.embed_7d = embed_7d
        if embed_30d is None:
            self.btn_vol30d.disabled = True
        if embed_7d is None:
            self.btn_vol7d.disabled = True
    
    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True
        await self.ctx.edit_original_message(
            view=self
        )

    @disnake.ui.button(label="1️⃣ Rate", style=ButtonStyle.red, custom_id="cexswap_selectpool_rate")
    async def btn_rate(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not your menu!", ephemeral=True)
        else:
            await self.ctx.edit_original_message(
                content=None,
                embed=self.embed_rate,
                view=self
            )
            await interaction.response.defer()

    @disnake.ui.button(label="2️⃣ Top LP", style=ButtonStyle.gray, custom_id="cexswap_selectpool_toplp")
    async def btn_top(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not your menu!", ephemeral=True)
        else:
            await self.ctx.edit_original_message(
                content=None,
                embed=self.embed_lp,
                view=self
            )
            await interaction.response.defer()

    @disnake.ui.button(label="Volume 7d", style=ButtonStyle.primary, custom_id="cexswap_selectpool_vol7d")
    async def btn_vol7d(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not your menu!", ephemeral=True)
        else:
            await self.ctx.edit_original_message(
                content=None,
                embed=self.embed_7d,
                view=self
            )
            await interaction.response.defer()

    @disnake.ui.button(label="Volume 30d", style=ButtonStyle.secondary, custom_id="cexswap_selectpool_vol30d")
    async def btn_vol30d(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not your menu!", ephemeral=True)
        else:
            await self.ctx.edit_original_message(
                content=None,
                embed=self.embed_30d,
                view=self
            )
            await interaction.response.defer()

# DropdownSummary Viewer
class DropdownSummaryLP(disnake.ui.StringSelect):
    def __init__(self, ctx, bot, embed, list_fields, lp_list_coins, lp_in_usd, lp_sorted_key, selected_menu):
        self.ctx = ctx
        self.bot = bot
        self.embed = embed
        self.list_fields = list_fields
        self.lp_list_coins = lp_list_coins
        self.lp_in_usd = lp_in_usd
        self.lp_sorted_key = lp_sorted_key
        self.selected_menu = selected_menu
        self.utils = Utils(self.bot)

        options = [
            disnake.SelectOption(
                label=each, description="Show {}".format(each.lower())
            ) for each in ["TOP POOLS", "LIQUIDITY", "VOLUME", "FEE TO LIQUIDATORS"]
        ]

        super().__init__(
            placeholder="Choose menu..." if self.selected_menu is None else self.selected_menu,
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.ctx.user.id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        else:
            try:
                self.embed.clear_fields()
                self.embed.add_field(
                    name="Coins with CEXSwap: {}".format(len(self.bot.cexswap_coins)),
                    value="{}".format(", ".join(self.bot.cexswap_coins)),
                    inline=False
                )
                if self.values[0] == "TOP POOLS":
                    for i in self.lp_sorted_key[:self.bot.config['cexswap_summary']['top_pool']]:
                        self.embed.add_field(
                            name=i,
                            value="{} {}\n{} {}{}".format(
                                self.lp_in_usd[i]['amount_ticker_1'], self.lp_in_usd[i]['ticker_1_name'],
                                self.lp_in_usd[i]['amount_ticker_2'], self.lp_in_usd[i]['ticker_2_name'],
                                "\n~{}{}".format(truncate(self.lp_in_usd[i]['value_usd'], 2), " USD") if self.lp_in_usd[i]['value_usd'] > 0 else ""
                            ),
                            inline=True
                        )
                elif self.values[0] == "LIQUIDITY":
                    list_lp = []
                    for k, v in self.lp_list_coins.items():
                        coin_emoji = getattr(getattr(self.bot.coin_list, k), "coin_emoji_discord")
                        amount_str = num_format_coin(v)
                        list_lp.append("{} {} {}".format(coin_emoji, amount_str, k))
                    list_lp_chunks = list(chunks(list_lp, 12))
                    for i in list_lp_chunks:
                        self.embed.add_field(
                            name=self.values[0],
                            value="{}".format("\n".join(i)),
                            inline=False
                        )
                elif self.values[0] == "VOLUME":
                    for key in ['1d', '7d']:
                        list_vol = list(chunks(self.list_fields[key]['volume_value'], 12))
                        for i in list_vol:
                            self.embed.add_field(
                                name=self.list_fields[key]['volume_title'],
                                value="{}".format("\n".join(i)),
                                inline=False
                            )
                elif self.values[0] == "FEE TO LIQUIDATORS":
                    for key in ['1d', '7d']:
                        list_fee = list(chunks(self.list_fields[key]['fee_value'], 12))
                        for i in list_fee:
                            self.embed.add_field(
                                name=self.list_fields[key]['fee_title'],
                                value="{}".format("\n".join(i)),
                                inline=False
                            )
                # Create the view containing our dropdown
                view = DropdownViewSummary(
                    self.ctx, self.bot, self.embed, self.list_fields,
                    self.lp_list_coins, self.lp_in_usd, self.lp_sorted_key,
                    selected_menu=self.values[0]
                )
                await self.ctx.edit_original_message(
                    content=None,
                    embed=self.embed,
                    view=view
                )
                await inter.response.defer()
            except Exception:
                traceback.print_exc(file=sys.stdout)

class DropdownViewSummary(disnake.ui.View):
    def __init__(self, ctx, bot, embed, list_fields, lp_list_coins, lp_in_usd, lp_sorted_key, selected_menu: str):
        super().__init__(timeout=120.0)
        self.ctx = ctx
        self.bot = bot
        self.embed = embed
        self.list_fields = list_fields
        self.lp_list_coins = lp_list_coins
        self.lp_in_usd = lp_in_usd
        self.lp_sorted_key = lp_sorted_key
        self.selected_menu = selected_menu

        self.add_item(DropdownSummaryLP(
            self.ctx, self.bot, self.embed, self.list_fields,
            self.lp_list_coins, self.lp_in_usd, self.lp_sorted_key,
            self.selected_menu
        ))

    async def on_timeout(self):
        original_message = await self.ctx.original_message()
        await original_message.edit(view=None)

# DropdownLP Viewer
class DropdownLP(disnake.ui.StringSelect):
    def __init__(self, ctx, bot, list_chunks, list_coins, active_coin):
        self.ctx = ctx
        self.bot = bot
        self.list_chunks = list_chunks
        self.list_coins = list_coins
        self.active_coin = active_coin
        self.utils = Utils(self.bot)

        options = [
            disnake.SelectOption(
                label=each,
                description="Select {}".format(each),
                emoji=getattr(getattr(self.bot.coin_list, each), "coin_emoji_discord")
            ) for each in self.list_chunks
        ]

        super().__init__(
            placeholder="Choose coin/token..." if self.active_coin is None or self.active_coin not in self.list_chunks else "You selected {}".format(self.active_coin),
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.ctx.user.id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=5.0)
            return
        else:
            testing = self.bot.config['cexswap']['testing_msg']
            embed = disnake.Embed(
                title="Liquidity Pool of TipBot's CEXSwap",
                description=f"{self.ctx.author.mention}, {testing}Available Liquidity Pools.",
                timestamp=datetime.now(),
            )
            embed.set_footer(text="Requested by: {}#{}".format(self.ctx.author.name, self.ctx.author.discriminator))
            embed.set_thumbnail(url=self.bot.user.display_avatar)
            # get LP by coin
            get_pools = await cexswap_get_pools(self.values[0])
            showing_num = 8
            if len(get_pools) > 0:
                embed.add_field(
                    name="Selected Coin {}".format(self.values[0]),
                    value="There {} LP with {}".format(
                        "is {}".format(len(get_pools)) if len(get_pools) == 1 else "are {}".format(len(get_pools)), self.values[0]
                    ),
                    inline = False
                )
                for each_p in get_pools[0:showing_num]:
                    rate_1 = num_format_coin(
                        each_p['amount_ticker_2']/each_p['amount_ticker_1']
                    )
                    rate_2 = num_format_coin(
                        each_p['amount_ticker_1']/each_p['amount_ticker_2']
                    )
                    rate_coin_12 = "{} {} = {} {}\n{} {} = {} {}".format(
                        1, each_p['ticker_1_name'], rate_1, each_p['ticker_2_name'], 1, each_p['ticker_2_name'], rate_2, each_p['ticker_1_name']
                    )

                    embed.add_field(
                        name="Active LP {}{}".format(
                            each_p['pairs'], " {} / {}".format(
                                self.utils.get_coin_emoji(each_p['ticker_1_name']),
                                self.utils.get_coin_emoji(each_p['ticker_2_name'])
                            )
                        ),
                        value="{} {}\n{} {}\n{}".format(
                            num_format_coin(each_p['amount_ticker_1']), each_p['ticker_1_name'],
                            num_format_coin(each_p['amount_ticker_2']), each_p['ticker_2_name'],
                            rate_coin_12
                        ),
                        inline=False
                    )
                if len(get_pools) > showing_num:
                    list_remaining = [i['ticker_1_name'] for i in get_pools[showing_num:]] + [i['ticker_2_name'] for i in get_pools[showing_num:]]
                    list_remaining = list(set(list_remaining))
                    if self.values[0] in list_remaining:
                        list_remaining.remove(self.values[0])
                    if len(list_remaining) > 0:
                        embed.add_field(
                            name="More with {} coin/token(s)".format(len(list_remaining)),
                            value="{}".format(", ".join(list_remaining)),
                            inline=False
                        )
            # Create the view containing our dropdown
            view = DropdownViewLP(self.ctx, self.bot, self.list_coins, active_coin=self.values[0])
            await self.ctx.edit_original_message(
                content=None,
                embed=embed,
                view=view
            )
            await inter.response.defer()

class DropdownViewLP(disnake.ui.View):
    def __init__(self, ctx, bot, list_coins, active_coin: str):
        super().__init__(timeout=300.0)
        self.ctx = ctx
        self.bot = bot
        self.list_coins = list_coins
        self.active_coin = active_coin

        # split to small chunks
        list_chunks = list(chunks(self.list_coins, 20))
        for i in list_chunks:
            self.add_item(DropdownLP(self.ctx, self.bot, i, self.list_coins, self.active_coin))

    async def on_timeout(self):
        original_message = await self.ctx.original_message()
        await original_message.edit(view=None)
# End of DropdownLP Viewer

# Dropdown mypool
class DropdownMyPool(disnake.ui.StringSelect):
    def __init__(self, ctx, bot, list_chunks, list_pairs, total_liq, pool_share, add, remove, gain_lose, list_earnings, active_pair):
        self.ctx = ctx
        self.bot = bot
        self.list_chunks = list_chunks
        self.list_pairs = list_pairs
        self.total_liq = total_liq
        self.pool_share = pool_share
        self.add = add
        self.remove = remove
        self.gain_lose = gain_lose
        self.list_earnings = list_earnings
        self.active_pair = active_pair
        self.utils = Utils(self.bot)

        options = [
            disnake.SelectOption(
                label=each,
                description="Select {}".format(each),
            ) for each in self.list_chunks
        ]

        super().__init__(
            placeholder="Choose pairs..." if self.active_pair is None or self.active_pair not in self.list_chunks else "You selected {}".format(self.active_pair),
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.ctx.user.id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=5.0)
            return
        else:
            testing = self.bot.config['cexswap']['testing_msg']
            embed = disnake.Embed(
                title="Your LP Pool of TipBot's CEXSwap",
                description=f"{self.ctx.author.mention}, {testing}Your Liquidity Pools.",
                timestamp=datetime.now(),
            )
            embed.set_footer(text="Requested by: {}#{}".format(self.ctx.author.name, self.ctx.author.discriminator))
            embed.set_thumbnail(url=self.bot.user.display_avatar)
            # Add embed here
            if self.values[0] in self.total_liq:
                embed.add_field(
                    name="Total liquidity",
                    value=self.total_liq[self.values[0]],
                    inline=False
                )
            if self.values[0] in self.add:
                embed.add_field(
                    name="You added (Original)",
                    value=self.add[self.values[0]],
                    inline=False
                )
            if self.values[0] in self.remove:
                embed.add_field(
                    name="You removed",
                    value=self.remove[self.values[0]],
                    inline=False
                )
            if self.values[0] in self.pool_share:
                embed.add_field(
                    name="Your current LP (Share %)",
                    value=self.pool_share[self.values[0]],
                    inline=False
                )
            if self.values[0] in self.gain_lose:
                embed.add_field(
                    name="Inc./Decr.",
                    value="\n".join(self.gain_lose[self.values[0]]),
                    inline=False
                )
            if self.values[0] in self.list_earnings:
                embed.add_field(
                    name="Earning (LP Distribution Fee)",
                    value="\n".join(self.list_earnings[self.values[0]]),
                    inline=False
                )
                embed.add_field(
                    name="Note",
                    value="Earning from LP Distribution fee isn't added to the LP. "\
                        "It always go to you balance from each successful trade. You can check with `/recent cexswaplp <tokenn>`.",
                    inline=False
                )
            view = DropdownViewMyPool(
                self.ctx, self.bot, self.list_pairs, self.total_liq, self.pool_share,
                self.add, self.remove, self.gain_lose, self.list_earnings, active_pair=self.values[0]
            )
            # Create the view containing our dropdown
            await self.ctx.edit_original_message(
                content=None,
                embed=embed,
                view=view
            )
            await inter.response.defer()

class DropdownViewMyPool(disnake.ui.View):
    def __init__(self, ctx, bot, list_pairs, total_liq, pool_share, add, remove, gain_lose, list_earnings, active_pair: str):
        super().__init__(timeout=300.0)
        self.ctx = ctx
        self.bot = bot
        self.list_pairs = list_pairs
        self.active_pair = active_pair
        self.gain_lose = gain_lose
        self.list_earnings = list_earnings

        # split to small chunks
        list_chunks = list(chunks(self.list_pairs, 20))
        for i in list_chunks:
            self.add_item(DropdownMyPool(
                self.ctx, self.bot, i, self.list_pairs, total_liq, 
                pool_share, add, remove, gain_lose, list_earnings, self.active_pair
            ))

    async def on_timeout(self):
        original_message = await self.ctx.original_message()
        await original_message.edit(view=None)
# End of dropdown mypool

class ConfirmSell(disnake.ui.View):
    def __init__(self, bot, owner_id: int):
        super().__init__(timeout=30.0)
        self.value: Optional[bool] = None
        self.bot = bot
        self.owner_id = owner_id

    @disnake.ui.button(label="Confirm", style=disnake.ButtonStyle.green)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, this is not your menu!", delete_after=5.0)
        else:
            if str(inter.author.id) in self.bot.tipping_in_progress and \
                int(time.time()) - self.bot.tipping_in_progress[str(inter.author.id)] < 30:
                msg = f"{EMOJI_ERROR} {inter.author.mention}, you have another transaction in progress."
                await inter.response.send_message(content=msg, ephemeral=True)
                return
            else:
                self.bot.tipping_in_progress[str(inter.author.id)] = int(time.time())
            await inter.response.send_message(f"{inter.author.mention}, confirming...", delete_after=3.0)
            self.value = True
            self.stop()

    @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.grey)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, this is not your menu!", delete_after=5.0)
        else:
            await inter.response.send_message(f"{inter.author.mention}, cancelling...", delete_after=3.0)
            self.value = False
            self.stop()

class add_liqudity(disnake.ui.Modal):
    def __init__(self, ctx, bot, ticker_1: str, ticker_2: str, owner_userid: str, balances_str) -> None:
        self.ctx = ctx
        self.bot = bot
        self.ticker_1 = ticker_1.upper()
        self.ticker_2 = ticker_2.upper()
        self.wallet_api = WalletAPI(self.bot)
        self.owner_userid = owner_userid
        self.balances_str = balances_str

        components = [
            disnake.ui.TextInput(
                label="{} | Having {}".format(ticker_1.upper(), self.balances_str[0]),
                placeholder="10000",
                custom_id="cexswap_amount_coin_id_1",
                style=TextInputStyle.short,
                max_length=16
            ),
            disnake.ui.TextInput(
                label="{} | Having {}".format(ticker_2.upper(), self.balances_str[1]),
                placeholder="10000",
                custom_id="cexswap_amount_coin_id_2",
                style=TextInputStyle.short,
                max_length=16
            )
        ]
        super().__init__(title="Add a new liqudity", custom_id="modal_add_new_liqudity", components=components)

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        try:
            # await interaction.response.defer()
            await interaction.response.send_message(content=f"{interaction.author.mention}, checking liquidity...", ephemeral=True)

            liq_pair = await cexswap_get_pool_details(self.ticker_1, self.ticker_2, self.owner_userid)
            testing = self.bot.config['cexswap']['testing_msg']
            embed = disnake.Embed(
                title="Add Liquidity to TipBot's CEXSwap",
                description=f"{interaction.author.mention}, {testing}Please click on add liquidity and confirm later.",
                timestamp=datetime.now(),
            )
            amount_1 = interaction.text_values['cexswap_amount_coin_id_1'].strip()
            amount_1 = amount_1.replace(",", "")
            amount_1 = text_to_num(amount_1)

            amount_2 = interaction.text_values['cexswap_amount_coin_id_2'].strip()
            amount_2 = amount_2.replace(",", "")
            amount_2 = text_to_num(amount_2)

            min_initialized_liq_1 = getattr(getattr(self.bot.coin_list, self.ticker_1), "cexswap_min_initialized_liq")
            min_initialized_liq_2 = getattr(getattr(self.bot.coin_list, self.ticker_2), "cexswap_min_initialized_liq")

            accepted = False
            text_adjust_1 = ""
            text_adjust_2 = ""
            error_msg = f"{EMOJI_RED_NO} {interaction.author.mention}, Please check amount!"
            if amount_1 and amount_2:
                accepted = True
                if amount_1 < 0 or amount_2 < 0:
                    accepted = False
                    error_msg = "Amount can't be negative!"

                # check user balance
                # self.ticker_1
                net_name = getattr(getattr(self.bot.coin_list, self.ticker_1), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, self.ticker_1), "type")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, self.ticker_1), "deposit_confirm_depth")
                contract = getattr(getattr(self.bot.coin_list, self.ticker_1), "contract")
                height = await self.wallet_api.get_block_height(type_coin, self.ticker_1, net_name)
                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(interaction.author.id), self.ticker_1, net_name, type_coin, SERVER_BOT, 0
                )
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(interaction.author.id), self.ticker_1, net_name, type_coin, SERVER_BOT, 0, 0
                    )

                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                elif type_coin in ["XRP"]:
                    wallet_address = get_deposit['destination_tag']

                height = await self.wallet_api.get_block_height(type_coin, self.ticker_1, net_name)
                userdata_balance = await self.wallet_api.user_balance(
                    str(interaction.author.id), self.ticker_1, wallet_address, 
                    type_coin, height, deposit_confirm_depth, SERVER_BOT
                )
                actual_balance = float(userdata_balance['adjust'])
                if actual_balance < 0 or truncate(actual_balance, 8) < truncate(amount_1, 8):
                    accepted = False
                    error_msg = f"{EMOJI_RED_NO}, You don't have sufficient balance for {self.ticker_1}!"

                # self.ticker_2
                net_name = getattr(getattr(self.bot.coin_list, self.ticker_2), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, self.ticker_2), "type")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, self.ticker_2), "deposit_confirm_depth")
                contract = getattr(getattr(self.bot.coin_list, self.ticker_2), "contract")
                height = await self.wallet_api.get_block_height(type_coin, self.ticker_2, net_name)
                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(interaction.author.id), self.ticker_2, net_name, type_coin, SERVER_BOT, 0
                )
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(interaction.author.id), self.ticker_2, net_name, type_coin, SERVER_BOT, 0, 0
                    )

                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                elif type_coin in ["XRP"]:
                    wallet_address = get_deposit['destination_tag']

                height = await self.wallet_api.get_block_height(type_coin, self.ticker_2, net_name)
                userdata_balance = await self.wallet_api.user_balance(
                    str(interaction.author.id), self.ticker_2, wallet_address, 
                    type_coin, height, deposit_confirm_depth, SERVER_BOT
                )
                actual_balance = float(userdata_balance['adjust'])
                if actual_balance < 0 or truncate(actual_balance, 8) < truncate(amount_2, 8):
                    accepted = False
                    error_msg = f"{EMOJI_RED_NO}, You don't have sufficient balance for {self.ticker_2}!"
                # end of check user balance

                if liq_pair is None:
                    embed.add_field(
                        name="New Pool",
                        value="This is a new pair and a start price will be based on yours.",
                        inline=False
                    )

                    if amount_1 < min_initialized_liq_1 and interaction.author.id != self.bot.config['discord']['owner_id']:
                        accepted = False
                        error_msg = f"{EMOJI_INFORMATION} New pool requires minimum amount to initialize!"
                    elif amount_2 < min_initialized_liq_2 and interaction.author.id != self.bot.config['discord']['owner_id']:
                        accepted = False
                        error_msg = f"{EMOJI_INFORMATION} New pool requires minimum amount to initialize!"
                else:
                    # if existing pool, check rate and set it to which one lower.
                    new_amount_1 = amount_2 * liq_pair['pool']['amount_ticker_1']/liq_pair['pool']['amount_ticker_2']
                    new_amount_2 = amount_1 * liq_pair['pool']['amount_ticker_2']/liq_pair['pool']['amount_ticker_1']
                    if amount_1 > new_amount_1:
                        amount_1 = new_amount_1
                        text_adjust_1 = " (Adjusted based on rate)"
                    elif amount_2 > new_amount_2:
                        amount_2 = new_amount_2
                        text_adjust_2 = " (Adjusted based on rate)"
                    rate_1 = num_format_coin(
                        liq_pair['pool']['amount_ticker_2']/liq_pair['pool']['amount_ticker_1']
                    )
                    rate_2 = num_format_coin(
                        liq_pair['pool']['amount_ticker_1']/liq_pair['pool']['amount_ticker_2']
                    )
                    rate_coin_12 = "{} {} = {} {}\n{} {} = {} {}".format(
                        1, self.ticker_1, rate_1, self.ticker_2, 1, self.ticker_2, rate_2, self.ticker_1
                    )
                    embed.add_field(
                        name="Total liquidity",
                        value="{} {}\n{} {}".format(
                            num_format_coin(liq_pair['pool']['amount_ticker_1']), liq_pair['pool']['ticker_1_name'],
                            num_format_coin(liq_pair['pool']['amount_ticker_2']), liq_pair['pool']['ticker_2_name']
                        ),
                        inline=False
                    )
                    embed.add_field(
                        name="Existing Pool | Rate",
                        value="{}".format(rate_coin_12),
                        inline=False
                    )
                    # If a user has already some liq
                    percent_1 = ""
                    percent_2 = ""
                    if liq_pair['pool_share'] is not None:
                        try:
                            percent_1 = " - {:,.2f} {}".format(liq_pair['pool_share']['amount_ticker_1']/ liq_pair['pool']['amount_ticker_1']*100, "%")
                            percent_2 = " - {:,.2f} {}".format(liq_pair['pool_share']['amount_ticker_1']/ liq_pair['pool']['amount_ticker_1']*100, "%")
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        embed.add_field(
                            name="Your existing liquidity",
                            value="{} {}{}\n{} {}{}".format(
                                num_format_coin(liq_pair['pool_share']['amount_ticker_1']), liq_pair['pool_share']['ticker_1_name'], percent_1, 
                                num_format_coin(liq_pair['pool_share']['amount_ticker_2']), liq_pair['pool_share']['ticker_2_name'], percent_2
                            ),
                            inline=False
                        )
                if accepted is True:
                    embed.add_field(
                        name="Adding Ticker {}".format(self.ticker_1),
                        value="Amount: {} {}{}".format(num_format_coin(amount_1), self.ticker_1, text_adjust_1),
                        inline=False
                    )
                    embed.add_field(
                        name="Adding Ticker {}".format(self.ticker_2),
                        value="Amount: {} {}{}".format(num_format_coin(amount_2), self.ticker_2, text_adjust_2),
                        inline=False
                    )
                else:
                    if liq_pair is not None:
                        cexswap_min_add_liq_1 = getattr(getattr(self.bot.coin_list, self.ticker_1), "cexswap_min_add_liq")
                        cexswap_min_add_liq_2 = getattr(getattr(self.bot.coin_list, self.ticker_2), "cexswap_min_add_liq")
                    else:
                        cexswap_min_add_liq_1 = getattr(getattr(self.bot.coin_list, self.ticker_1), "cexswap_min_initialized_liq")
                        cexswap_min_add_liq_2 = getattr(getattr(self.bot.coin_list, self.ticker_2), "cexswap_min_initialized_liq")

                    init_liq_text = "{} {}\n{} {}".format(
                        num_format_coin(cexswap_min_add_liq_1), self.ticker_1,
                        num_format_coin(cexswap_min_add_liq_2), self.ticker_2
                    )
                    embed.add_field(
                        name="Minimum adding",
                        value=f"{init_liq_text}",
                        inline=False
                    )
                    embed.add_field(
                        name="Error",
                        value=error_msg,
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Error",
                    value=error_msg,
                    inline=False
                )
    
            await interaction.message.edit(
                content = None,
                embed = embed,
                view = add_liquidity_btn(self.ctx, self.bot, self.owner_userid, "{}/{}".format(
                    self.ticker_1, self.ticker_2), self.balances_str, accepted,  amount_1, amount_2
                )
            )

            await interaction.delete_original_message()
        except Exception:
            traceback.print_exc(file=sys.stdout)
            return

# Defines a simple view of row buttons.
class add_liquidity_btn(disnake.ui.View):
    def __init__(
        self, ctx, bot, owner_id: str, pool_name: str, balances_str, accepted: bool=False,
        amount_1: float=None, amount_2: float=None,
    ):
        super().__init__(timeout=42.0)
        self.ctx = ctx
        self.bot = bot
        self.utils = Utils(self.bot)
        self.wallet_api = WalletAPI(self.bot)
        self.owner_id = owner_id
        self.pool_name = pool_name
        self.balances_str = balances_str
        self.accepted = accepted
        self.amount_1 = amount_1
        self.amount_2 = amount_2

        if self.accepted is False:
            self.accept_click.disabled = True
        else:
            self.accept_click.disabled = False
            self.add_click.disabled = True

    async def on_timeout(self):
        original_message = await self.ctx.original_message()
        await original_message.edit(view=None)
        try:
            del self.bot.tipping_in_progress[str(self.ctx.author.id)]
        except Exception:
            pass

    @disnake.ui.button(label="Add", style=disnake.ButtonStyle.red, custom_id="cexswap_addliquidity_btn")
    async def add_click(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        # await inter.response.send_message("This is the first button.")
        # await inter.response.defer()
        if inter.author.id != self.ctx.author.id:
            await inter.response.send_message(f"{inter.author.mention}, that's not your menu!", ephemeral=True)
            return
        ticker = self.pool_name.split("/")
        await inter.response.send_modal(
                modal=add_liqudity(inter, self.bot, ticker[0], ticker[1], self.owner_id, self.balances_str))

    @disnake.ui.button(label="Accept", style=disnake.ButtonStyle.green, custom_id="cexswap_acceptliquidity_btn")
    async def accept_click(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.ctx.author.id:
            await inter.response.send_message(f"{inter.author.mention}, that's not your menu!", ephemeral=True)
            return
        else:
            await inter.response.send_message(f"{inter.author.mention}, checking liquidity.")
        # add liquidity

        # Check if tx in progress
        if str(inter.author.id) in self.bot.tipping_in_progress and \
            int(time.time()) - self.bot.tipping_in_progress[str(inter.author.id)] < 42:
            msg = f"{EMOJI_ERROR} {inter.author.mention}, you have another transaction in progress."
            await inter.edit_original_message(content=msg)
            return
        else:
            self.bot.tipping_in_progress[str(inter.author.id)] = int(time.time())
        # end checking tx in progress

        try:
            if self.amount_1 is None or self.amount_2 is None:
                msg = f"{EMOJI_ERROR} {inter.author.mention}, invalid given amount(s) or too fast."
                await inter.edit_original_message(content=msg)
                try:
                    del self.bot.tipping_in_progress[str(inter.author.id)]
                except Exception:
                    pass
                return
            # re-check negative
            elif self.amount_1 < 0 or self.amount_2 < 0:
                msg = f"{EMOJI_ERROR} {inter.author.mention}, invalid given amount(s). (Negative)"
                await inter.edit_original_message(content=msg)
                try:
                    del self.bot.tipping_in_progress[str(inter.author.id)]
                except Exception:
                    pass
                return
            ticker = self.pool_name.split("/")
            # re-check rate
            liq_pair = await cexswap_get_pool_details(ticker[0], ticker[1], self.owner_id)
            if liq_pair is not None:
                rate_1 = liq_pair['pool']['amount_ticker_2']/liq_pair['pool']['amount_ticker_1']
                if truncate(float(rate_1), 8) != truncate(float(self.amount_2 / self.amount_1), 8):
                    msg = f"{EMOJI_INFORMATION} {inter.author.mention}, ⚠️ Price updated! Try again!"
                    await inter.edit_original_message(content=msg)
                    self.accept_click.disabled = True
                    self.add_click.disabled = True
                    await inter.message.edit(view=None)
                    try:
                        del self.bot.tipping_in_progress[str(inter.author.id)]
                    except Exception:
                        pass
                    return
            # end of re-check rate

            # re-check balance
            # ticker[0]
            coin_name = ticker[0]
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)

            get_deposit = await self.wallet_api.sql_get_userwallet(
                str(inter.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(
                    str(inter.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                )
            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

            userdata_balance = await self.wallet_api.user_balance(
                str(inter.author.id), coin_name, wallet_address, 
                type_coin, height, deposit_confirm_depth, SERVER_BOT
            )
            actual_balance = float(userdata_balance['adjust'])
            if actual_balance <= self.amount_1:
                msg = f"{EMOJI_RED_NO} {inter.author.mention}, ⚠️ Please get more {coin_name}."
                await inter.edit_original_message(content=msg)
                try:
                    del self.bot.tipping_in_progress[str(inter.author.id)]
                except Exception:
                    pass
                return

            # ticker[1]
            coin_name = ticker[1]
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)

            get_deposit = await self.wallet_api.sql_get_userwallet(
                str(inter.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(
                    str(inter.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                )
            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

            userdata_balance = await self.wallet_api.user_balance(
                str(inter.author.id), coin_name, wallet_address, 
                type_coin, height, deposit_confirm_depth, SERVER_BOT
            )
            actual_balance = float(userdata_balance['adjust'])
            if actual_balance <= self.amount_2:
                msg = f"{EMOJI_RED_NO} {inter.author.mention}, ⚠️ Please get more {coin_name}."
                await inter.edit_original_message(content=msg)
                try:
                    del self.bot.tipping_in_progress[str(inter.author.id)]
                except Exception:
                    pass
                return
            # end of re-check balance

            add_liq = await cexswap_insert_new(
                self.pool_name, self.amount_1, ticker[0], self.amount_2, ticker[1],
                str(inter.author.id), SERVER_BOT
            )
            if add_liq is True:
                # disable buttons first
                try:
                    self.accept_click.disabled = True
                    self.add_click.disabled = True
                    await inter.message.edit(view=None)
                except Exception:
                    pass
                # Delete if has key
                try:
                    key = str(inter.author.id) + "_" + ticker[0] + "_" + SERVER_BOT
                    if key in self.bot.user_balance_cache:
                        del self.bot.user_balance_cache[key]
                    key = str(inter.author.id) + "_" + ticker[1] + "_" + SERVER_BOT
                    if key in self.bot.user_balance_cache:
                        del self.bot.user_balance_cache[key]
                except Exception:
                    pass
                # End of del key
                add_msg = "{} {} and {} {}".format(
                    num_format_coin(self.amount_1), ticker[0],
                    num_format_coin(self.amount_2), ticker[1]
                )
                msg = f'{EMOJI_INFORMATION} {inter.author.mention}, successfully added.```{add_msg}```'
                await inter.edit_original_message(content=msg)
                self.accept_click.disabled = True
                self.add_click.disabled = True
                await inter.message.edit(view=None)
                try:
                    del self.bot.tipping_in_progress[str(inter.author.id)]
                except Exception:
                    pass
                await log_to_channel(
                    "cexswap",
                    f"[ADD LIQUIDITY]: User {inter.author.mention} add new liquidity to pool `{self.pool_name}`! {add_msg}",
                    self.bot.config['discord']['cexswap']
                )
                # Find guild where there is trade channel assign
                get_guilds = await self.utils.get_trade_channel_list()
                if len(get_guilds) > 0 and self.bot.config['cexswap']['disable'] == 0:
                    list_guild_ids = [i.id for i in self.bot.guilds]
                    for item in get_guilds:
                        if int(item['serverid']) not in list_guild_ids:
                            continue
                        try:
                            get_guild = self.bot.get_guild(int(item['serverid']))
                            if get_guild:
                                channel = get_guild.get_channel(int(item['trade_channel']))
                                if channel is None:
                                    continue
                                if hasattr(inter, "guild") and hasattr(inter.guild, "id") and channel.id != inter.channel.id:
                                    continue
                                elif channel is not None:
                                    await channel.send(f"[CEXSWAP]: A user added more liquidity pool `{self.pool_name}`! {add_msg}")
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
            else:
                msg = f'{EMOJI_INFORMATION} {inter.author.mention}, internal error.'
                await inter.edit_original_message(content=msg)
                self.accept_click.disabled = True
                self.add_click.disabled = True
                await inter.message.edit(view=None)
                try:
                    del self.bot.tipping_in_progress[str(inter.author.id)]
                except Exception:
                    pass
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.gray, custom_id="cexswap_cancelliquidity_btn")
    async def cancel_click(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.ctx.author.id:
            await inter.response.send_message(f"{inter.author.mention}, that's not your menu!", ephemeral=True)
            return
        else:
            try:
                del self.bot.tipping_in_progress[str(inter.author.id)]
            except Exception:
                pass
            await inter.message.delete()

class Cexswap(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

        self.botLogChan = None
        self.enable_logchan = True
        # if user try to sell or buy for this, Bot give info to wrap
        self.wrapped_coin = {
            "PWRKZ": "WRKZ",
            "BWRKZ": "WRKZ",
            "XWRKZ": "WRKZ"
        }

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)


    # Cexswap
    async def placeholder_balances(self, user_id: str, user_server: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                    FROM `user_balance_mv_data` 
                    WHERE `user_id`=%s AND `user_server`=%s """
                    await cur.execute(sql, (user_id, user_server))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []
        
    async def cexswap_get_list_enable_pairs(self):
        list_pairs = []
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                    FROM `coin_settings` 
                    WHERE `enable`=1 AND `cexswap_enable`=1 """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        list_coins = sorted([i['coin_name'] for i in result])
                        self.bot.cexswap_coins = list_coins
                        for pair in itertools.combinations(list_coins, 2):
                            list_pairs.append("{}/{}".format(pair[0], pair[1]))
                        if len(list_pairs) > 0:
                            self.bot.cexswap_pairs = list_pairs
                            return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    # End of Cexswap

    @commands.slash_command(
        name="cexswap",
        description="Various crypto cexswap commands."
    )
    async def cexswap(self, ctx):
        await self.bot_log()
        try:
            if self.bot.config['cexswap']['is_private'] == 1 and ctx.author.id not in self.bot.config['cexswap']['private_user_list']:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, this command is not public yet. "\
                    "Please try again later!"
                await ctx.response.send_message(msg)
                return
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                if serverinfo and 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "NO":
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, cexswap/market function is not ENABLE yet in this guild. "\
                        "Please request Guild owner to enable by `/SETTING TRADE`"
                    await ctx.response.send_message(msg)
                    if self.enable_logchan:
                        await self.botLogChan.send(
                            f"{ctx.author.name} / {ctx.author.id} tried **cexswap/market command** in "\
                            f"{ctx.guild.name} / {ctx.guild.id} which is not ENABLE."
                        )
                    return
                elif serverinfo and serverinfo['trade_channel'] is not None and \
                    int(serverinfo['trade_channel']) != ctx.channel.id and ctx.author.id != self.bot.config['discord']['owner']:
                    channel = ctx.guild.get_channel(int(serverinfo['trade_channel']))
                    if channel is not None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, cexswap/trade channel was assigned to {channel.mention}."
                        await ctx.response.send_message(msg)
            is_user_locked = self.utils.is_locked_user(str(ctx.author.id), SERVER_BOT)
            if is_user_locked is True:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, your account is locked for using the Bot. Please contact bot dev by /about link."
                await ctx.response.send_message(msg)
                return
            if self.bot.config['cexswap']['disable'] == 1 and ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, CEXSwap is currently on maintenance. Be back soon!"
                await ctx.response.send_message(msg)
                return
        except Exception:
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                return

    @cexswap.sub_command(
        name="intro",
        usage="cexswap intro",
        description="Introduction of /cexswap."
    )
    async def cexswap_intro(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /cexswap loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/cexswap intro", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            testing = self.bot.config['cexswap']['testing_msg']
            embed = disnake.Embed(
                title="TipBot's CEXSwap",
                description=f"{ctx.author.mention}, {testing}You can join our supported guild for #help.",
                timestamp=datetime.now(),
            )
            embed.add_field(
                name="BRIEF",
                value=self.bot.config['cexswap']['brief_msg'],
                inline=False
            )        
            embed.add_field(
                name="FEE?",
                value=self.bot.config['cexswap']['fee_msg'],
                inline=False
            )
            embed.add_field(
                name="NOTE",
                value=self.bot.config['cexswap']['note_msg'],
                inline=False
            )
            embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
            embed.set_thumbnail(url=self.bot.user.display_avatar)
            await ctx.edit_original_message(content=None, embed=embed)
        except Exception:
            traceback.print_exc(file=sys.stdout)
    
    @cexswap.sub_command(
        name="summary",
        usage="cexswap summary",
        description="Summary of /cexswap."
    )
    async def cexswap_summary(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /cexswap loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/cexswap summary", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            testing = self.bot.config['cexswap']['testing_msg']
            embed = disnake.Embed(
                title="TipBot's CEXSwap",
                description=f"{ctx.author.mention}, {testing}You can join our supported guild for #help.",
                timestamp=datetime.now(),
            )
            # Available coin
            embed.add_field(
                name="Coins with CEXSwap: {}".format(len(self.bot.cexswap_coins)),
                value="{}".format(", ".join(self.bot.cexswap_coins)),
                inline=False
            )
            # LP available
            get_pools = await cexswap_get_pools()
            if len(get_pools) > 0:
                list_pairs = [i['pairs'] for i in get_pools]
                some_active_lp = list_pairs.copy()
                random.shuffle(some_active_lp)
                list_pair_msg = "{}".format(
                    ", ".join(some_active_lp)
                ) if len(some_active_lp) < self.bot.config['cexswap_summary']['show_max_pair'] else \
                    "{} and {} more..".format(
                        ", ".join(some_active_lp[0:self.bot.config['cexswap_summary']['show_max_pair']]),
                        len(some_active_lp) - self.bot.config['cexswap_summary']['show_max_pair']
                    )
                embed.add_field(
                    name="Active LP: {}".format(len(list_pairs)),
                    value=list_pair_msg,
                    inline=False
                )

            # List distributed fee
            earning = {}
            earning['7d'] = await get_cexswap_get_coin_sell_logs(coin_name=None, user_id=None, from_time=int(time.time())-7*24*3600)
            earning['1d'] = await get_cexswap_get_coin_sell_logs(coin_name=None, user_id=None, from_time=int(time.time())-1*24*3600)
            list_fields = {}
            get_pools = await cexswap_get_all_lp_pools()
            lp_list_coins = {}
            lp_in_usd = {}
            for each_lp in get_pools:
                if each_lp['pairs'] not in lp_in_usd:
                    sub_1 = 0.0
                    sub_2 = 0.0
                    single_pair_amount = 0.0
                    pair_amount = 0.0
                    per_unit = self.utils.get_usd_paprika(each_lp['ticker_1_name'])
                    if per_unit > 0:
                        sub_1 = float(Decimal(each_lp['amount_ticker_1']) * Decimal(per_unit))
                    per_unit = self.utils.get_usd_paprika(each_lp['ticker_2_name'])
                    if per_unit > 0:
                        sub_2 = float(Decimal(each_lp['amount_ticker_2']) * Decimal(per_unit))
                    # check max price
                    if sub_1 >= 0.0 and sub_2 >= 0.0:
                        single_pair_amount = max(sub_1, sub_2)
                    if single_pair_amount > 0:
                        pair_amount = 2 * single_pair_amount
                    lp_in_usd[each_lp['pairs']] = {
                        'ticker_1_name': each_lp['ticker_1_name'],
                        'amount_ticker_1': num_format_coin(each_lp['amount_ticker_1']),
                        'ticker_2_name': each_lp['ticker_2_name'],
                        'amount_ticker_2': num_format_coin(each_lp['amount_ticker_2']),
                        'value_usd': pair_amount
                    }

                if each_lp['ticker_1_name'] not in lp_list_coins:
                    lp_list_coins[each_lp['ticker_1_name']] = each_lp['amount_ticker_1']
                else:
                    lp_list_coins[each_lp['ticker_1_name']] += each_lp['amount_ticker_1']
                if each_lp['ticker_2_name'] not in lp_list_coins:
                    lp_list_coins[each_lp['ticker_2_name']] = each_lp['amount_ticker_2']
                else:
                    lp_list_coins[each_lp['ticker_2_name']] += each_lp['amount_ticker_2']

            # sort LP
            # https://stackoverflow.com/questions/16412563/python-sorting-dictionary-of-dictionaries
            lp_sorted_key = lp_in_usd.copy()
            lp_sorted_key = sorted(lp_sorted_key, key=lambda k: lp_sorted_key[k]['value_usd'], reverse=True)

            if len(earning) > 0:
                for k, v in earning.items():
                    list_coin_set = []
                    earning_list = []
                    volume_list = []
                    list_earning_dict = {}
                    list_volume_dict = {}
                    for each in v:
                        if each['got_ticker'] not in list_earning_dict.keys():
                            list_earning_dict[each['got_ticker']] = each['fee_liquidators']
                        else:
                            list_earning_dict[each['got_ticker']] += each['fee_liquidators']
                        if each['got_ticker'] not in list_volume_dict.keys():
                            list_volume_dict[each['got_ticker']] = each['got']
                        else:
                            list_volume_dict[each['got_ticker']] += each['got']
                        if each['got_ticker'] not in list_coin_set:
                            list_coin_set.append(each['got_ticker'])
                    for i in list_coin_set:
                        if i not in list_volume_dict.keys():
                            continue
                        coin_emoji = getattr(getattr(self.bot.coin_list, i), "coin_emoji_discord")
                        coin_emoji = coin_emoji + " " if coin_emoji else ""
                        earning_amount = num_format_coin(
                            list_earning_dict[i]
                        )
                        traded_amount = num_format_coin(
                            list_volume_dict[i]
                        )
                        earning_list.append("{}{} {}".format(coin_emoji, earning_amount, i))
                        volume_list.append("{}{} {}".format(coin_emoji, traded_amount, i))

                    if len(v) > 0:
                        list_fields[k] = {}
                        list_fields[k]['fee_title'] = "Fee to liquidator(s) [{}]".format(k.upper())
                        list_fields[k]['fee_value'] = earning_list
                        list_fields[k]['volume_title'] = "Total volume [{}]".format(k.upper())
                        list_fields[k]['volume_value'] = volume_list
            embed.add_field(
                name="Select Menu",
                value="Please select from dropdown",
                inline=False
            )  
            embed.add_field(
                name="Remark",
                value="Please often check this summary.",
                inline=False
            )  
            embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
            embed.set_thumbnail(url=self.bot.user.display_avatar)
            # Create the view containing our dropdown
            view = DropdownViewSummary(ctx, self.bot, embed, list_fields, lp_list_coins, lp_in_usd, lp_sorted_key, selected_menu=None)
            await ctx.edit_original_message(
                content=None,
                embed=embed,
                view=view
            )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @cexswap.sub_command(
        name="listpools",
        usage="cexswap listpools",
        description="List opened pools in cexswap."
    )
    async def cexswap_listpools(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /cexswap loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/cexswap listpools", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            get_pools = await cexswap_get_pools()
            if len(get_pools) == 0:
                msg = f"{ctx.author.mention}, thank you for checking. There is no pools yet. Try again later."
                await ctx.edit_original_message(content=msg)
            else:
                testing = self.bot.config['cexswap']['testing_msg']
                embed = disnake.Embed(
                    title="Liquidity Pool of TipBot's CEXSwap",
                    description=f"{ctx.author.mention}, {testing}Available Liquidity Pools.",
                    timestamp=datetime.now(),
                )
                embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
                embed.set_thumbnail(url=self.bot.user.display_avatar)
                for each_p in get_pools[0:5]:
                    rate_1 = num_format_coin(
                        each_p['amount_ticker_2']/each_p['amount_ticker_1']
                    )
                    rate_2 = num_format_coin(
                        each_p['amount_ticker_1']/each_p['amount_ticker_2']
                    )
                    rate_coin_12 = "{} {} = {} {}\n{} {} = {} {}".format(
                        1, each_p['ticker_1_name'], rate_1, each_p['ticker_2_name'], 1, each_p['ticker_2_name'], rate_2, each_p['ticker_1_name']
                    )
                    
                    embed.add_field(
                        name="Active LP {}{}".format(each_p['pairs'], " {} / {}".format(
                                self.utils.get_coin_emoji(each_p['ticker_1_name']),
                                self.utils.get_coin_emoji(each_p['ticker_2_name'])
                            )
                        ),
                        value="{} {}\n{} {}\n{}".format(
                            num_format_coin(each_p['amount_ticker_1']), each_p['ticker_1_name'],
                            num_format_coin(each_p['amount_ticker_2']), each_p['ticker_2_name'],
                            rate_coin_12
                        ),
                        inline=False
                    )

                # filter uniq tokens
                list_coins = list(set([i['ticker_1_name'] for i in get_pools] + [i['ticker_2_name'] for i in get_pools]))

                # Create the view containing our dropdown
                # list_coins can be more than 25 - limit of Discord
                view = DropdownViewLP(ctx, self.bot, list_coins, active_coin=None)
                await ctx.edit_original_message(
                    content=None,
                    embed=embed,
                    view=view
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @cexswap.sub_command(
        name="sell",
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('sell_token', 'sell_token', OptionType.string, required=True),
            Option('for_token', 'for_token', OptionType.string, required=True),
        ],
        usage="cexswap sell <amount> <token> <for token>",
        description="Sell an amount of coins for another."
    )
    async def cexswap_sell(
        self,
        ctx,
        amount: str,
        sell_token: str,
        for_token: str
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /cexswap loading..."
        await ctx.response.send_message(msg)
        sell_amount_old = amount

        if self.bot.config['cexswap']['enable_sell'] != 1 and ctx.author.id != self.bot.config['discord']['owner_id']:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, CEXSwap sell is temporarily offline! Check again soon."
            await ctx.edit_original_message(content=msg)
            return

        sell_token = sell_token.upper()
        for_token = for_token.upper()

        if sell_token in self.wrapped_coin.keys():
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you should do `/wrap` from `{sell_token}` to `{self.wrapped_coin[sell_token]}` and trade."
            await ctx.edit_original_message(content=msg)
            return
        if for_token in self.wrapped_coin.keys():
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you should trade with `{self.wrapped_coin[for_token]}` and do `/wrap` from `{self.wrapped_coin[for_token]}` to `{for_token}`."
            await ctx.edit_original_message(content=msg)
            return

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/cexswap sell", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if sell_token == for_token:
            msg = f"{EMOJI_ERROR}, {ctx.author.mention}, you can cexswap for the same token."
            await ctx.edit_original_message(content=msg)
            return

        # check liq
        liq_pair = await cexswap_get_pool_details(sell_token, for_token, None)
        if liq_pair is None:
            # Check if there is other path to trade
            find_route = await cexswap_route_trade(sell_token, for_token)

            additional_msg = ""
            find_other_lp = await cexswap_get_pools(sell_token)
            if len(find_other_lp) > 0:
                items =[i['pairs'] for i in find_other_lp]
                additional_msg = "\n__**More {} LP**__:\n   {}.".format(sell_token, ", ".join(items))
            find_other_lp = await cexswap_get_pools(for_token)
            if len(find_other_lp) > 0:
                items =[i['pairs'] for i in find_other_lp]
                additional_msg += "\n__**More {} LP**__:\n   {}.".format(for_token, ", ".join(items))
            if len(find_route) > 0:
                list_paths = []
                for i in find_route:
                    list_paths.append("  ⚆ {} {} ➡️ {} {} ➡️ {} {}".format(
                        self.utils.get_coin_emoji(sell_token), sell_token,
                        self.utils.get_coin_emoji(i), i,
                        self.utils.get_coin_emoji(for_token), for_token
                    ))
                path_trades = "\n".join(list_paths)
                msg = f"{EMOJI_INFORMATION}, {ctx.author.mention}, there is no liquidity of `{sell_token}/{for_token}` yet." \
                    f"\n__**Possible trade:**__\n{path_trades}{additional_msg}"
                await ctx.edit_original_message(content=msg)
                return
            else:
                msg = f"{EMOJI_ERROR}, {ctx.author.mention}, there is no liquidity of `{sell_token}/{for_token}` yet.{additional_msg}"
                await ctx.edit_original_message(content=msg)
                return
        else:
            # check if coin sell is enable
            is_sellable = getattr(getattr(self.bot.coin_list, sell_token), "cexswap_sell_enable")
            if is_sellable != 1:
                msg = f"{EMOJI_ERROR}, {ctx.author.mention}, coin/token `{sell_token}` is currently disable for cexswap."
                await ctx.edit_original_message(content=msg)
                return
            is_sellable = getattr(getattr(self.bot.coin_list, for_token), "cexswap_sell_enable")
            if is_sellable != 1:
                msg = f"{EMOJI_ERROR}, {ctx.author.mention}, coin/token `{for_token}` is currently disable for cexswap."
                await ctx.edit_original_message(content=msg)
                return
            try:
                # check amount
                amount_liq_sell = liq_pair['pool']['amount_ticker_1']
                if sell_token == liq_pair['pool']['ticker_2_name']:
                    amount_liq_sell = liq_pair['pool']['amount_ticker_2']
                cexswap_min = getattr(getattr(self.bot.coin_list, sell_token), "cexswap_min")
                token_display = getattr(getattr(self.bot.coin_list, sell_token), "display_name")
                cexswap_max_swap_percent_sell = getattr(getattr(self.bot.coin_list, sell_token), "cexswap_max_swap_percent")
                max_swap_sell_cap = cexswap_max_swap_percent_sell * float(amount_liq_sell)

                net_name = getattr(getattr(self.bot.coin_list, sell_token), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, sell_token), "type")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, sell_token), "deposit_confirm_depth")
                contract = getattr(getattr(self.bot.coin_list, sell_token), "contract")

                if "$" in amount[-1] or "$" in amount[0]:  # last is $
                    # Check if conversion is allowed for this coin.
                    amount = amount.replace(",", "").replace("$", "")
                    price_with = getattr(getattr(self.bot.coin_list, sell_token), "price_with")
                    if price_with is None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{sell_token}`."
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        per_unit = await self.utils.get_coin_price(sell_token, price_with)
                        if per_unit and per_unit['price'] and per_unit['price'] > 0:
                            per_unit = per_unit['price']
                            amount = float(Decimal(amount) / Decimal(per_unit))
                        else:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. "\
                                "Try with different method."
                            await ctx.edit_original_message(content=msg)
                            return
                else:
                    amount = amount.replace(",", "")
                    amount = text_to_num(amount)
                    amount = truncate(float(amount), 12)
                    if amount is None:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                        await ctx.edit_original_message(content=msg)
                        return

                amount = float(amount)

                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(ctx.author.id), sell_token, net_name, type_coin, SERVER_BOT, 0
                )
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(ctx.author.id), sell_token, net_name, type_coin, SERVER_BOT, 0, 0
                    )

                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                elif type_coin in ["XRP"]:
                    wallet_address = get_deposit['destination_tag']

                height = await self.wallet_api.get_block_height(type_coin, sell_token, net_name)
                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(ctx.author.id), sell_token, net_name, type_coin, SERVER_BOT, 0
                )
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(ctx.author.id), sell_token, net_name, type_coin, SERVER_BOT, 0, 0
                    )

                height = await self.wallet_api.get_block_height(type_coin, sell_token, net_name)
                userdata_balance = await self.wallet_api.user_balance(
                    str(ctx.author.id), sell_token, wallet_address, 
                    type_coin, height, deposit_confirm_depth, SERVER_BOT
                )
                actual_balance = float(userdata_balance['adjust'])

                # Check if amount is more than liquidity
                if truncate(float(amount), 8) > truncate(float(max_swap_sell_cap), 8):
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, the given amount `{sell_amount_old}`"\
                        f" is more than allowable 10% of liquidity `{num_format_coin(max_swap_sell_cap)} {token_display}`." \
                        f"```Current LP: {num_format_coin(liq_pair['pool']['amount_ticker_1'])} "\
                        f"{liq_pair['pool']['ticker_1_name']} and "\
                        f"{num_format_coin(liq_pair['pool']['amount_ticker_2'])} "\
                        f"{liq_pair['pool']['ticker_2_name']} for LP {liq_pair['pool']['ticker_1_name']}/{liq_pair['pool']['ticker_2_name']}.```"
                    await ctx.edit_original_message(content=msg)
                    return

                # Check if too big rate gap
                try:
                    rate_ratio = liq_pair['pool']['amount_ticker_1'] / liq_pair['pool']['amount_ticker_2']
                    if rate_ratio > 10**12 or rate_ratio < 1/10**12:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, rate ratio is out of range. Try with other pairs."
                        await ctx.edit_original_message(content=msg)
                        await self.botLogChan.send(
                            f"{ctx.author.name} / {ctx.author.id} reject trade ratio out of range: `{sell_token}/{for_token}`"
                        )
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                # check slippage first
                slippage = 1.0 - amount / float(liq_pair['pool']['amount_ticker_1']) - self.bot.config['cexswap_slipage']['reserve']
                amount_get = amount * float(liq_pair['pool']['amount_ticker_2'] / liq_pair['pool']['amount_ticker_1'])

                amount_qty_1 = liq_pair['pool']['amount_ticker_2']
                amount_qty_2 = liq_pair['pool']['amount_ticker_1']

                if sell_token == liq_pair['pool']['ticker_2_name']:
                    amount_get = amount * float(liq_pair['pool']['amount_ticker_1'] / liq_pair['pool']['amount_ticker_2'])
                    slippage = 1.0 - amount / float(liq_pair['pool']['amount_ticker_2']) - self.bot.config['cexswap_slipage']['reserve']

                    amount_qty_1 = liq_pair['pool']['amount_ticker_1']
                    amount_qty_2 = liq_pair['pool']['amount_ticker_2']

                # adjust slippage
                amount_get = slippage * amount_get
                if slippage > 1 or slippage < 0.88:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, internal error with slippage. Try again later!"
                    await ctx.edit_original_message(content=msg)
                    return

                # price impact = unit price now / unit price after sold
                price_impact_text = ""
                price_impact_percent = 0.0
                new_impact_ratio = (float(amount_qty_2) + amount) / (float(amount_qty_1) - amount_get)
                old_impact_ratio = float(amount_qty_2) / float(amount_qty_1)
                impact_ratio = abs(old_impact_ratio - new_impact_ratio) / max(old_impact_ratio, new_impact_ratio)
                if 0.0001 < impact_ratio < 1:
                    price_impact_text = "\nPrice impact: ~{:,.2f}{}".format(impact_ratio * 100, "%")
                    price_impact_percent = impact_ratio * 100
                
                # If the amount get is too small.
                if amount_get < self.bot.config['cexswap']['minimum_receive_or_reject']:
                    num_receive = num_format_coin(amount_get)
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, the received amount is too small "\
                        f"{num_receive} {for_token}. Please increase your sell amount!"
                    await ctx.edit_original_message(content=msg)
                    return

                if truncate(amount, 8) < truncate(cexswap_min, 8):
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, the given amount `{sell_amount_old}`"\
                        f" is below minimum `{num_format_coin(cexswap_min)} {token_display}`."
                    await ctx.edit_original_message(content=msg)
                    return

                elif truncate(actual_balance, 8) < truncate(amount, 8):
                    # Try to see how much user can trade for before checking balance
                    got_fee_dev = amount_get * self.bot.config['cexswap']['dev_fee'] / 100
                    got_fee_liquidators = amount_get * self.bot.config['cexswap']['liquidator_fee'] / 100
                    got_fee_guild = 0.0
                    guild_id = "DM"
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                        got_fee_guild = amount_get * self.bot.config['cexswap']['guild_fee'] / 100
                        guild_id = str(ctx.guild.id)
                    else:
                        got_fee_dev += amount_get * self.bot.config['cexswap']['guild_fee'] / 100
                    fee = truncate(got_fee_dev, 12) + truncate(got_fee_liquidators, 12) + truncate(got_fee_guild, 12)
                    user_amount_get = num_format_coin(truncate(amount_get - float(fee), 12))
                    user_amount_sell = num_format_coin(amount)
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, ⚠️ Please re-check balance {token_display}.\n"\
                        f"```You could get {user_amount_get} {for_token}\n"\
                        f"From selling {user_amount_sell} {sell_token}{price_impact_text}.```"
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    # OK, sell..
                    got_fee_dev = amount_get * self.bot.config['cexswap']['dev_fee'] / 100
                    got_fee_liquidators = amount_get * self.bot.config['cexswap']['liquidator_fee'] / 100
                    got_fee_guild = 0.0
                    guild_id = "DM"
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                        got_fee_guild = amount_get * self.bot.config['cexswap']['guild_fee'] / 100
                        guild_id = str(ctx.guild.id)
                    else:
                        got_fee_dev += amount_get * self.bot.config['cexswap']['guild_fee'] / 100

                    ref_log = ''.join(random.choice(ascii_uppercase) for i in range(16))

                    liq_users = []
                    if len(liq_pair['pool_share']) > 0:
                        for each_s in liq_pair['pool_share']:
                            distributed_amount = None
                            if for_token == each_s['ticker_1_name']:
                                distributed_amount = float(each_s['amount_ticker_1']) / float(liq_pair['pool']['amount_ticker_1']) * float(truncate(got_fee_liquidators, 12))
                            elif for_token == each_s['ticker_2_name']:
                                distributed_amount = float(each_s['amount_ticker_2']) / float(liq_pair['pool']['amount_ticker_2']) * float(truncate(got_fee_liquidators, 12))
                            if distributed_amount is not None:
                                liq_users.append([distributed_amount, each_s['user_id'], each_s['user_server']])
                    contract = getattr(getattr(self.bot.coin_list, for_token), "contract")
                    channel_id = "DM" if guild_id == "DM" else str(ctx.channel.id)
                    # get price per unit
                    per_unit_sell = 0.0
                    price_with = getattr(getattr(self.bot.coin_list, sell_token), "price_with")
                    if price_with:
                        per_unit_sell = await self.utils.get_coin_price(sell_token, price_with)
                        if per_unit_sell and per_unit_sell['price'] and per_unit_sell['price'] > 0:
                            per_unit_sell = per_unit_sell['price']
                        if per_unit_sell and per_unit_sell < 0.0000000001:
                            per_unit_sell = 0.0

                    per_unit_get = 0.0
                    price_with = getattr(getattr(self.bot.coin_list, for_token), "price_with")
                    if price_with:
                        per_unit_get = await self.utils.get_coin_price(for_token, price_with)
                        if per_unit_get and per_unit_get['price'] and per_unit_get['price'] > 0:
                            per_unit_get = per_unit_get['price']
                        if per_unit_get and per_unit_get < 0.0000000001:
                            per_unit_get = 0.0

                    fee = truncate(got_fee_dev, 12) + truncate(got_fee_liquidators, 12) + truncate(got_fee_guild, 12)
                    user_amount_get = num_format_coin(truncate(amount_get - float(fee), 12))
                    user_amount_sell = num_format_coin(amount)

                    suggestion_msg = ""
                    if self.bot.config['cexswap']['enable_better_price'] == 1:
                        try:
                            get_better_price = await cexswap_find_possible_trade(
                                sell_token, for_token, amount * slippage, amount_get - float(fee)
                            )
                            if len(get_better_price) > 0:
                                suggestion_msg = "\n```You may get a better price with:\n{}\n```⚠️ Price can be updated from every trade! ⚠️".format(
                                    "\n".join(get_better_price)
                                )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    # add confirmation
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to trade?\n"\
                        f"```Get {user_amount_get} {for_token}\n"\
                        f"From selling {user_amount_sell} {sell_token}{price_impact_text}```Ref: `{ref_log}`{suggestion_msg}"

                    # If there is progress
                    if str(ctx.author.id) in self.bot.tipping_in_progress and \
                        int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 30:
                        msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
                        await ctx.response.send_message(content=msg, ephemeral=True)
                        return

                    view = ConfirmSell(self.bot, ctx.author.id)
                    await ctx.edit_original_message(content=msg, view=view)

                    try:
                        await cexswap_estimate(
                            ref_log, liq_pair['pool']['pool_id'], "{}->{}".format(sell_token, for_token),
                            truncate(amount, 12), sell_token, truncate(amount_get - float(fee), 12), for_token,
                            got_fee_dev, got_fee_liquidators, got_fee_guild, price_impact_percent,
                            str(ctx.author.id), SERVER_BOT, 0
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)

                    # Wait for the View to stop listening for input...
                    await view.wait()

                    try:
                        del self.bot.tipping_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                    # Check the value to determine which button was pressed, if any.
                    if view.value is None:
                        await ctx.edit_original_message(
                            content=msg + "\n**Timeout!**",
                            view=None
                        )
                        try:
                            del self.bot.tipping_in_progress[str(ctx.author.id)]
                        except Exception:
                            pass
                        return
                    elif view.value:
                        # re-check rate
                        slippage = 1.0 - amount / float(liq_pair['pool']['amount_ticker_1']) - self.bot.config['cexswap_slipage']['reserve']
                        if sell_token == liq_pair['pool']['ticker_2_name']:
                            slippage = 1.0 - amount / float(liq_pair['pool']['amount_ticker_2']) - self.bot.config['cexswap_slipage']['reserve']
                        # adjust slippage
                        if slippage > 1 or slippage < 0.88:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, internal error with slippage. Try again later!"
                            await ctx.edit_original_message(content=msg)
                            return

                        new_liq_pair = await cexswap_get_pool_details(sell_token, for_token, None)
                        new_amount_get = amount * float(new_liq_pair['pool']['amount_ticker_2'] / new_liq_pair['pool']['amount_ticker_1'])
                        new_amount_get = slippage * new_amount_get
                        pool_amount_get = new_liq_pair['pool']['amount_ticker_2']
                        pool_amount_sell = new_liq_pair['pool']['amount_ticker_1']
                        if sell_token == new_liq_pair['pool']['ticker_2_name']:
                            new_amount_get = amount * float(new_liq_pair['pool']['amount_ticker_1'] / new_liq_pair['pool']['amount_ticker_2'])
                            new_amount_get = slippage * new_amount_get
                            pool_amount_get = new_liq_pair['pool']['amount_ticker_1']
                            pool_amount_sell = new_liq_pair['pool']['amount_ticker_2']
                        if truncate(float(new_amount_get), 8) != truncate(float(amount_get), 8):
                            await ctx.edit_original_message(
                                content=msg.replace("Do you want to trade?", "🔴 CEXSwap rejected!") + "\n**⚠️ Price updated! Please try again!**",
                                view=None
                            )
                            try:
                                del self.bot.tipping_in_progress[str(ctx.author.id)]
                            except Exception:
                                pass
                            return
                        # end of re-check rate

                        # re-check balance
                        height = await self.wallet_api.get_block_height(type_coin, sell_token, net_name)
                        userdata_balance = await self.wallet_api.user_balance(
                            str(ctx.author.id), sell_token, wallet_address, 
                            type_coin, height, deposit_confirm_depth, SERVER_BOT
                        )
                        actual_balance = float(userdata_balance['adjust'])
                        if amount <= 0 or actual_balance <= 0:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, ⚠️ Please get more {token_display}."
                            await ctx.edit_original_message(content=msg)
                            try:
                                del self.bot.tipping_in_progress[str(ctx.author.id)]
                            except Exception:
                                pass
                            return

                        if truncate(actual_balance, 8) < truncate(amount, 8):
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, ⚠️ Please re-check balance {token_display}."
                            await ctx.edit_original_message(content=msg)
                            try:
                                del self.bot.tipping_in_progress[str(ctx.author.id)]
                            except Exception:
                                pass
                            return
                        # end: re-check balance
                        try:
                            del self.bot.tipping_in_progress[str(ctx.author.id)]
                        except Exception:
                            pass
                        coin_decimal = getattr(getattr(self.bot.coin_list, for_token), "decimal")
                        selling = await cexswap_sold(
                            ref_log, liq_pair['pool']['pool_id'], truncate(amount, 12), sell_token, 
                            truncate(amount_get, 12), for_token, str(ctx.author.id), SERVER_BOT,
                            guild_id,
                            truncate(got_fee_dev, 12), truncate(got_fee_liquidators, 12), truncate(got_fee_guild, 12),
                            liq_users, contract, coin_decimal, channel_id, per_unit_sell, per_unit_get,
                            pool_amount_sell, pool_amount_get,
                            0, None
                        )
                        try:
                            del self.bot.tipping_in_progress[str(ctx.author.id)]
                        except Exception:
                            pass
                        if selling is True:
                            # Delete if has key
                            try:
                                key = str(ctx.author.id) + "_" + sell_token + "_" + SERVER_BOT
                                if key in self.bot.user_balance_cache:
                                    del self.bot.user_balance_cache[key]
                                key = str(ctx.author.id) + "_" + for_token + "_" + SERVER_BOT
                                if key in self.bot.user_balance_cache:
                                    del self.bot.user_balance_cache[key]
                                if len(liq_users) > 0:
                                    for u in liq_users:
                                        key = u[1] + "_" + sell_token + "_" + u[2]
                                        if key in self.bot.user_balance_cache:
                                            del self.bot.user_balance_cache[key]
                                        key = u[1] + "_" + for_token + "_" + u[2]
                                        if key in self.bot.user_balance_cache:
                                            del self.bot.user_balance_cache[key]
                                if guild_id != "DM":
                                    key = guild_id + "_" + for_token + "_" + SERVER_BOT
                                    if key in self.bot.user_balance_cache:
                                        del self.bot.user_balance_cache[key]
                            except Exception:
                                pass
                            # End of del key
                            # fee_str = num_format_coin(fee)
                            # . Fee {fee_str} {for_token}\n
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, successfully traded!\n"\
                                f"```Get {user_amount_get} {for_token}\n"\
                                f"From selling {user_amount_sell} {sell_token}{price_impact_text}```✅ Ref: `{ref_log}`{suggestion_msg}"
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "cexswap",
                                f"[SOLD]: User {ctx.author.mention} Sold: " \
                                f"{user_amount_sell} {sell_token} Get: {user_amount_get} {for_token}. Ref: `{ref_log}`",
                                self.bot.config['discord']['cexswap']
                            )
                            get_guilds = await self.utils.get_trade_channel_list()
                            if len(get_guilds) > 0 and self.bot.config['cexswap']['disable'] == 0:
                                list_guild_ids = [i.id for i in self.bot.guilds]
                                for item in get_guilds:
                                    if int(item['serverid']) not in list_guild_ids:
                                        continue
                                    get_guild = self.bot.get_guild(int(item['serverid']))
                                    try:
                                        if get_guild:
                                            channel = get_guild.get_channel(int(item['trade_channel']))
                                            if channel is None:
                                                continue
                                            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") and channel.id != ctx.channel.id:
                                                continue
                                            elif channel is not None:
                                                await channel.send(f"[CEXSWAP]: A user sold {user_amount_sell} {sell_token} for "\
                                                    f"{user_amount_get} {for_token}."
                                                )
                                    except disnake.errors.Forbidden:
                                        await self.botLogChan.send(
                                            f"[CEXSwap] failed to message to guild {get_guild.name} / {get_guild.id}."
                                        )
                                        update = await store.sql_changeinfo_by_server(item['serverid'], 'trade_channel', None)
                                        if update is True:
                                            await get_guild.owner.send(f"[CEXSwap] TipBot's failed to send message to <#{str(channel.id)}> "\
                                                f"in guild {get_guild.name} / {get_guild.id}. "\
                                                f"TipBot unassigned that channel from [CEXSwap]'s trading."\
                                                f"You can set again anytime later!\nYou can ignore this message."
                                            )
                                            await self.botLogChan.send(
                                                f"[CEXSwap] informed guild owner {get_guild.name} / {get_guild.id} / <@{get_guild.owner.id}> "\
                                                f"about failed message and unassigned trade channel."
                                            )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                        else:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, internal error!", view=None
                            )
                            return
                    else:
                        await ctx.edit_original_message(
                            content=msg + "\n**🛑 Cancelled!**",
                            view=None
                        )
                        try:
                            del self.bot.tipping_in_progress[str(ctx.author.id)]
                        except Exception:
                            pass
                        return
            except Exception:
                traceback.print_exc(file=sys.stdout)

    @cexswap_sell.autocomplete("sell_token")
    async def cexswap_addliquidity_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.cexswap_coins if string in name.lower()][:12]

    @cexswap_sell.autocomplete("for_token")
    async def cexswap_addliquidity_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.cexswap_coins if string in name.lower()][:12]

    @cexswap.sub_command(
        name="selectpool",
        usage="cexswap selectpool",
        options=[
            Option("pool_name", "Choose pool's name", OptionType.string, required=True)
        ],
        description="Show a pool detail in cexswap."
    )
    async def cexswap_selectpool(
        self,
        ctx,
        pool_name: str,
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /cexswap loading..."
        await ctx.response.send_message(msg)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/cexswap selectpool", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            # check if the given is a single coin/token
            pool_name = pool_name.upper()
            if pool_name in self.bot.cexswap_coins:
                coin_name = pool_name
                coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                testing = self.bot.config['cexswap']['testing_msg']
                embed = disnake.Embed(
                    title="Coin/Token {} {} TipBot's CEXSwap".format(coin_emoji, coin_name),
                    description=f"{ctx.author.mention}, {testing}Summary.",
                    timestamp=datetime.now(),
                )
                embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
                embed.set_thumbnail(url=self.bot.user.display_avatar)
                # Find pool with
                find_other_lp = await cexswap_get_pools(coin_name)
                total_liq = Decimal(0)

                # lp list of this token, then sort them by amount of coin_name
                lp_list_token = []
                if len(find_other_lp) > 0:
                    items =[i['pairs'] for i in find_other_lp]
                    embed.add_field(
                        name="LP with {} {} ({})".format(coin_emoji, coin_name, len(items)),
                        value="{}".format(", ".join(items)),
                        inline=False
                    )
                    # get price of each LP
                    rate_list = []
                    for i in find_other_lp:
                        # get L in LP
                        if coin_name == i['ticker_1_name']:
                            total_liq += i['amount_ticker_1']
                            lp_list_token.append(
                                {
                                    "pairs": i['pairs'],
                                    "amount": i['amount_ticker_1'],
                                    "other_amount": i['amount_ticker_2'],
                                    "other_token": i['ticker_2_name']
                                }
                            )
                        elif coin_name == i['ticker_2_name']:
                            total_liq += i['amount_ticker_2']
                            lp_list_token.append(
                                {
                                    "pairs": i['pairs'],
                                    "amount": i['amount_ticker_2'],
                                    "other_amount": i['amount_ticker_1'],
                                    "other_token": i['ticker_1_name']
                                }
                            )
                        target_coin = i['ticker_1_name']
                        rate_1 = i['amount_ticker_1'] / i['amount_ticker_2']
                        if coin_name == target_coin:
                            target_coin = i['ticker_2_name']
                            rate_1 = i['amount_ticker_2'] / i['amount_ticker_1']
                        coin_emoji_target = getattr(getattr(self.bot.coin_list, target_coin), "coin_emoji_discord")
                        if truncate(rate_1, 10) > 0:
                            rate_list.append("{} {} {}".format(
                                coin_emoji_target,
                                num_format_coin(rate_1),
                                target_coin
                            ))
                    if len(rate_list) > 0:
                        rate_list_chunks = list(chunks(rate_list, 12))
                        j = 1
                        extra_text = ""
                        for i in rate_list_chunks:
                            if len(rate_list_chunks) > 1:
                                extra_text = " / [{}/{}]".format(j, len(rate_list_chunks))
                            embed.add_field(
                                name="RATE LIST {} (Active LP{})".format(coin_name, extra_text),
                                value="{}".format("\n".join(i)),
                                inline=True
                            )
                            j += 1
                    embed.add_field(
                        name="All liquidity {}".format(coin_name),
                        value=num_format_coin(total_liq),
                        inline=False
                    )
                    # Check volume
                    get_coin_vol = {}
                    get_coin_vol['1D'] = await get_cexswap_get_coin_sell_logs(coin_name=coin_name, user_id=None, from_time=int(time.time())-1*24*3600)
                    get_coin_vol['7D'] = await get_cexswap_get_coin_sell_logs(coin_name=coin_name, user_id=None, from_time=int(time.time())-7*24*3600)
                    get_coin_vol['30D'] = await get_cexswap_get_coin_sell_logs(coin_name=coin_name, user_id=None, from_time=int(time.time())-30*24*3600)
                    per_unit = self.utils.get_usd_paprika(coin_name)
                    if len(get_coin_vol) > 0:
                        for k, v in get_coin_vol.items():
                            if len(v) > 0:
                                sum_amount = Decimal(0)
                                for i in v:
                                    if i['got_ticker'] == coin_name:
                                        sum_amount += i['got']
                                if sum_amount > 0:
                                    equi_usd = ""
                                    if per_unit > 0:
                                        sub_total_in_usd = float(Decimal(sum_amount) * Decimal(per_unit))
                                        if sub_total_in_usd > 0.01:
                                            equi_usd = "\n~ {:,.2f}$".format(sub_total_in_usd)
                                    embed.add_field(
                                        name="Volume {} {}".format(k, coin_emoji),
                                        value="{}{}".format(
                                            num_format_coin(sum_amount), equi_usd
                                        ),
                                        inline=True
                                    )

                    # other links
                    other_links = []
                    if getattr(getattr(self.bot.coin_list, coin_name), "explorer_link") and \
                        len(getattr(getattr(self.bot.coin_list, coin_name), "explorer_link")) > 0:
                        other_links.append(
                            "[{}]({})".format("Explorer Link", getattr(getattr(self.bot.coin_list, coin_name), "explorer_link"))
                        )
                    if getattr(getattr(self.bot.coin_list, coin_name), "id_cmc"):
                        other_links.append(
                            "[{}]({})".format("CoinMarketCap", "https://coinmarketcap.com/currencies/" + getattr(getattr(self.bot.coin_list, coin_name), "id_cmc"))
                        )
                    if getattr(getattr(self.bot.coin_list, coin_name), "id_gecko"):
                        other_links.append(
                            "[{}]({})".format("CoinGecko", "https://www.coingecko.com/en/coins/" + getattr(getattr(self.bot.coin_list, coin_name), "id_gecko"))
                        )
                    if getattr(getattr(self.bot.coin_list, coin_name), "id_paprika"):
                        other_links.append(
                            "[{}]({})".format("Coinpaprika", "https://coinpaprika.com/coin/" + getattr(getattr(self.bot.coin_list, coin_name), "id_paprika"))
                        )
                    if len(other_links) > 0:
                        embed.add_field(
                            name="Other links",
                            value="{}".format(" | ".join(other_links)),
                            inline=False
                        )
                    embed.add_field(
                        name="NOTE",
                        value="Please use the command and select LP from the list above for more detail!",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="LP with {} {}".format(coin_emoji, coin_name),
                        value="N/A",
                        inline=False
                    )
                # Make a copy and add liqudity of top pool with this token
                embed_lp = embed.copy()
                embed_lp.clear_fields() 
                # get sell logs
                sell_logs_30d = await get_cexswap_get_sell_logs(user_id=None, from_time=int(time.time()-30*24*3600), pool_id=None)
                sell_logs_7d = await get_cexswap_get_sell_logs(user_id=None, from_time=int(time.time()-7*24*3600), pool_id=None)
                list_sold_30d = []
                list_sold_7d = []
                embed_30d = None
                embed_7d = None
                if sell_logs_30d and len(sell_logs_30d) > 0:
                    for i in sell_logs_30d:
                        if i['got_ticker'] == coin_name:
                            list_sold_30d.append(
                                {
                                    "pairs": i['pairs'],
                                    "amount": i['got'],
                                    "other_amount": i['sold'],
                                    "other_token": i['sold_ticker']
                                }
                            )
                    list_sold_30d = sorted(list_sold_30d, key=lambda d: d['amount'], reverse=True)
                    if len(list_sold_30d) > 0:
                        embed_30d = embed.copy()
                        embed_30d.clear_fields()
                        for i in list_sold_30d:
                            embed_30d.add_field(
                                name=i['pairs'] + " - 30d",
                                value="{} {}\n{} {}".format(
                                    num_format_coin(i['amount']), coin_name,
                                    num_format_coin(i['other_amount']), i['other_token']
                                ),
                                inline=True
                            )
                if sell_logs_7d and len(sell_logs_7d) > 0:
                    for i in sell_logs_7d:
                        if i['got_ticker'] == coin_name:
                            list_sold_7d.append(
                                {
                                    "pairs": i['pairs'],
                                    "amount": i['got'],
                                    "other_amount": i['sold'],
                                    "other_token": i['sold_ticker']
                                }
                            )
                    list_sold_7d = sorted(list_sold_7d, key=lambda d: d['amount'], reverse=True)
                    if len(list_sold_7d) > 0:
                        embed_7d = embed.copy()
                        embed_7d.clear_fields()
                        for i in list_sold_7d:
                            embed_7d.add_field(
                                name=i['pairs'] + " - 7d",
                                value="{} {}\n{} {}".format(
                                    num_format_coin(i['amount']), coin_name,
                                    num_format_coin(i['other_amount']), i['other_token']
                                ),
                                inline=True
                            )
                view = None
                if len(lp_list_token) > 0:
                    lp_list_token = sorted(lp_list_token, key=lambda d: d['amount'], reverse=True) 
                    for i in lp_list_token[:10]: # maximum 10
                        embed_lp.add_field(
                            name=i['pairs'],
                            value="{} {}\n{} {}".format(
                                num_format_coin(i['amount']), coin_name,
                                num_format_coin(i['other_amount']), i['other_token']
                            ),
                            inline=True
                        )
                    view = SelectPoolSingle(60, ctx, self.bot, ctx.author.id, embed, embed_lp, embed_30d, embed_7d)

                await ctx.edit_original_message(
                    content=None,
                    embed=embed,
                    view=view
                )
            else:
                if pool_name not in self.bot.cexswap_pairs:
                    # check if wrong order
                    try:
                        tickers = pool_name.upper().split("/")
                        if len(tickers) == 2:
                            pool_name = "{}/{}".format(tickers[1], tickers[0])
                            if pool_name not in self.bot.cexswap_pairs:
                                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                                    f"Invalid given `{pool_name}`."
                                await ctx.edit_original_message(content=msg)
                                return
                        else:
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                                f"Invalid given `{pool_name}`."
                            await ctx.edit_original_message(content=msg)
                            return
                    except Exception:
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                            f"Invalid given `{pool_name}`."
                        await ctx.edit_original_message(content=msg)
                        traceback.print_exc(file=sys.stdout)
                    # End checking wrong order

                tickers = pool_name.upper().split("/")
                coin_emoji_1 = getattr(getattr(self.bot.coin_list, tickers[0]), "coin_emoji_discord")
                coin_emoji_1 = coin_emoji_1 + " " if coin_emoji_1 else ""
                coin_emoji_2 = getattr(getattr(self.bot.coin_list, tickers[1]), "coin_emoji_discord")
                coin_emoji_2 = coin_emoji_2 + " " if coin_emoji_2 else ""

                min_initialized_liq_1 = getattr(getattr(self.bot.coin_list, tickers[0]), "cexswap_min_initialized_liq")
                min_initialized_liq_2 = getattr(getattr(self.bot.coin_list, tickers[1]), "cexswap_min_initialized_liq")

                testing = self.bot.config['cexswap']['testing_msg']
                embed = disnake.Embed(
                    title="LP Pool {} - {}/{} TipBot's CEXSwap".format(pool_name, coin_emoji_1, coin_emoji_2),
                    description=f"{ctx.author.mention}, {testing}Summary.",
                    timestamp=datetime.now(),
                )
                init_liq_text = "{} {}\n{} {}".format(
                    num_format_coin(min_initialized_liq_1), tickers[0],
                    num_format_coin(min_initialized_liq_2), tickers[1]
                )
                min_liq_1 = getattr(getattr(self.bot.coin_list, tickers[0]), "cexswap_min_add_liq")
                min_liq_2 = getattr(getattr(self.bot.coin_list, tickers[1]), "cexswap_min_add_liq")
                add_liq_text = "{} {}\n{} {}".format(
                    num_format_coin(min_liq_1), tickers[0],
                    num_format_coin(min_liq_2), tickers[1]
                )
                embed.add_field(
                    name="Minimum adding (After POOL)",
                    value=f"{add_liq_text}",
                    inline=False
                )
                embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
                embed.set_thumbnail(url=self.bot.user.display_avatar)
                liq_pair = await cexswap_get_pool_details(tickers[0], tickers[1], None)
                if liq_pair is not None:
                    rate_1 = num_format_coin(
                        liq_pair['pool']['amount_ticker_2']/liq_pair['pool']['amount_ticker_1']
                    )
                    rate_2 = num_format_coin(
                        liq_pair['pool']['amount_ticker_1']/liq_pair['pool']['amount_ticker_2']
                    )
                    rate_coin_12 = "{} {} = {} {}\n{} {} = {} {}".format(
                        1, tickers[0], rate_1, tickers[1], 1, tickers[1], rate_2, tickers[0]
                    )

                    sub_1 = 0.0
                    sub_2 = 0.0
                    single_pair_amount = 0.0
                    pair_amount = 0.0
                    per_unit = self.utils.get_usd_paprika(liq_pair['pool']['ticker_1_name'])
                    if per_unit > 0:
                        sub_1 = float(Decimal(liq_pair['pool']['amount_ticker_1']) * Decimal(per_unit))
                    per_unit = self.utils.get_usd_paprika(liq_pair['pool']['ticker_2_name'])
                    if per_unit > 0:
                        sub_2 = float(Decimal(liq_pair['pool']['amount_ticker_2']) * Decimal(per_unit))
                    # check max price
                    if sub_1 >= 0.0 and sub_2 >= 0.0:
                        single_pair_amount = max(sub_1, sub_2)
                    if single_pair_amount > 0:
                        pair_amount = 2 * single_pair_amount

                    # show total liq
                    embed.add_field(
                        name="Total liquidity (from {} user(s))".format(len(liq_pair['pool_share'])),
                        value="{} {}\n{} {}{}".format(
                            num_format_coin(liq_pair['pool']['amount_ticker_1']), liq_pair['pool']['ticker_1_name'],
                            num_format_coin(liq_pair['pool']['amount_ticker_2']), liq_pair['pool']['ticker_2_name'],
                            "\n~{} {}".format(truncate(pair_amount, 2), "USD") if pair_amount > 0 else ""
                        ),
                        inline=False
                    )
                    embed.add_field(
                        name="Existing Pool | Rate",
                        value="{}".format(rate_coin_12),
                        inline=False
                    )
                    volume = {}
                    volume['7d'] = await get_cexswap_get_sell_logs(user_id=None, from_time=int(time.time()-7*24*3600), pool_id=liq_pair['pool']['pool_id'])
                    volume['1d'] = await get_cexswap_get_sell_logs(user_id=None, from_time=int(time.time()-1*24*3600), pool_id=liq_pair['pool']['pool_id'])
                    if len(volume) > 0:
                        for k, v in volume.items():
                            if len(v) == 0:
                                continue
                            list_volume = []
                            each = v[0]
                            # sold
                            coin_emoji = ""
                            try:
                                coin_emoji = getattr(getattr(self.bot.coin_list, each['sold_ticker']), "coin_emoji_discord")
                                coin_emoji = coin_emoji + " " if coin_emoji else ""
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            sold_amount = num_format_coin(
                                each['sold']
                            )
                            list_volume.append("{}{} {}".format(coin_emoji, sold_amount, each['sold_ticker']))

                            # trade with
                            coin_emoji = ""
                            try:
                                coin_emoji = getattr(getattr(self.bot.coin_list, each['got_ticker']), "coin_emoji_discord")
                                coin_emoji = coin_emoji + " " if coin_emoji else ""
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            traded_amount = num_format_coin(
                                each['got']
                            )
                            list_volume.append("{}{} {}".format(coin_emoji, traded_amount, each['got_ticker']))
                            embed.add_field(
                                name="Volume [{}]".format(k.upper()),
                                value="{}".format("\n".join(list_volume)),
                                inline=False
                            )
                else:
                    embed.add_field(
                        name="Minimum adding (Init POOL)",
                        value=f"{init_liq_text}",
                        inline=False
                    )
                    embed.add_field(
                        name="NOTE",
                        value="This LP doesn't exist yet!",
                        inline=False
                    )
                await ctx.edit_original_message(
                    content=None,
                    embed=embed
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @cexswap_selectpool.autocomplete("pool_name")
    async def cexswap_selectpool_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.cexswap_pairs if string in name.lower()][:12]

    @cexswap.sub_command(
        name="mypool",
        usage="cexswap mypool",
        options=[
            Option("pool_name", "Choose pool's name", OptionType.string, required=False)
        ],
        description="Show your liquidated pool detail in cexswap."
    )
    async def cexswap_mypool(
        self,
        ctx,
        pool_name: str=None,
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /cexswap mypool loading..."
        await ctx.response.send_message(msg, ephemeral=True)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/cexswap mypool", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            if pool_name is None:
                get_poolshare = await cexswap_get_poolshare(str(ctx.author.id), SERVER_BOT)
                if len(get_poolshare) == 0:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, sorry! You don't have any liquidity in any pools."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    user_ar = await cexswap_get_add_remove_user(str(ctx.author.id), SERVER_BOT, None)
                    total_liq = {}
                    your_pool_share = {}
                    your_pool_share_num = {}
                    for i in get_poolshare:
                        sub_1 = 0.0
                        sub_2 = 0.0
                        single_pair_amount = 0.0
                        pair_amount = 0.0
                        per_unit = self.utils.get_usd_paprika(i['ticker_1_name'])
                        if per_unit > 0:
                            sub_1 = float(Decimal(i['amount_ticker_1']) * Decimal(per_unit))
                        per_unit = self.utils.get_usd_paprika(i['ticker_2_name'])
                        if per_unit > 0:
                            sub_2 = float(Decimal(i['amount_ticker_2']) * Decimal(per_unit))
                        # check max price
                        if sub_1 >= 0.0 and sub_2 >= 0.0:
                            single_pair_amount = max(sub_1, sub_2)
                        if single_pair_amount > 0:
                            pair_amount = 2 * single_pair_amount
                        total_liq[i['pairs']] = "{} {}\n{} {}{}".format(
                            num_format_coin(i['pool_amount_1']), i['ticker_1_name'],
                            num_format_coin(i['pool_amount_2']), i['ticker_2_name'],
                            "\n~{} {}".format(truncate(pair_amount, 2), "USD") if pair_amount > 0 else ""
                        )
                        if i['amount_ticker_1'] > 0 and i['amount_ticker_2'] > 0:
                            # If a user has already some liq
                            percent_1 = ""
                            percent_2 = ""
                            try:
                                percent_1 = " - {:,.2f} {}".format(i['amount_ticker_1']/ i['pool_amount_1']*100, "%")
                                percent_2 = " - {:,.2f} {}".format(i['amount_ticker_2']/ i['pool_amount_2']*100, "%")
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            your_pool_share[i['pairs']] = "{} {}{}\n{} {}{}".format(
                                    num_format_coin(i['amount_ticker_1']), i['ticker_1_name'], percent_1, 
                                    num_format_coin(i['amount_ticker_2']), i['ticker_2_name'], percent_2
                                )
                            your_pool_share_num[i['pairs']] = {
                                i['ticker_1_name']: i['amount_ticker_1'],
                                i['ticker_2_name']: i['amount_ticker_2'],
                            }

                    add_dict = {}
                    remove_dict = {}
                    list_add = {}
                    list_remove = {}
                    adding_list_num = {}
                    remove_list_num = {}
                    gain_lose = {}
                    if len(user_ar) > 0:
                        for i in user_ar:
                            if i['pairs'] not in list_add:
                                list_add[i['pairs']] = {}
                            if i['pairs'] not in list_remove:
                                list_remove[i['pairs']] = {}
                            if i['pairs'] not in adding_list_num:
                                adding_list_num[i['pairs']] = {}
                            if i['pairs'] not in remove_list_num:
                                remove_list_num[i['pairs']] = {}
                            tickers = i['pairs'].split("/")
                            coin_1 = tickers[0]
                            coin_2 = tickers[1]
                            sum_add_1 = Decimal(0)
                            sum_remove_1 = Decimal(0)
                            sum_add_2 = Decimal(0)
                            sum_remove_2 = Decimal(0)

                            if coin_1 == i['token_name']:
                                if i['action'] == "add":
                                    sum_add_1 += i['amount']
                                elif i['action'] in ['removepool', 'remove']:
                                    sum_remove_1 += i['amount']
                            elif coin_2 == i['token_name']:
                                if i['action'] == "add":
                                    sum_add_2 += i['amount']
                                elif i['action'] in ['removepool', 'remove']:
                                    sum_remove_2 += i['amount']
                            if sum_add_1 > 0 or sum_add_2 > 0:
                                if coin_1 not in list_add[i['pairs']]:
                                    list_add[i['pairs']][coin_1] = []
                                    adding_list_num[i['pairs']][coin_1] = Decimal(0)
                                if coin_2 not in list_add[i['pairs']]:
                                    list_add[i['pairs']][coin_2] = []
                                    adding_list_num[i['pairs']][coin_2] = Decimal(0)
                                if sum_add_1 > 0:
                                    list_add[i['pairs']][coin_1].append("+ {} {}".format(num_format_coin(sum_add_1), coin_1))
                                    adding_list_num[i['pairs']][coin_1] += sum_add_1
                                if sum_add_2 > 0:
                                    list_add[i['pairs']][coin_2].append("+ {} {}".format(num_format_coin(sum_add_2), coin_2))
                                    adding_list_num[i['pairs']][coin_2] += sum_add_2
                            if sum_remove_1 > 0 or sum_remove_2 > 0:
                                if coin_1 not in list_remove[i['pairs']]:
                                    list_remove[i['pairs']][coin_1] = []
                                    remove_list_num[i['pairs']][coin_1] = Decimal(0)
                                if coin_2 not in list_remove[i['pairs']]:
                                    list_remove[i['pairs']][coin_2] = []
                                    remove_list_num[i['pairs']][coin_2] = Decimal(0)
                                if sum_remove_1 > 0:
                                    list_remove[i['pairs']][coin_1].append("- {} {}".format(num_format_coin(sum_remove_1), coin_1))
                                    remove_list_num[i['pairs']][coin_1] -= sum_remove_1
                                if sum_remove_2 > 0:
                                    list_remove[i['pairs']][coin_2].append("- {} {}".format(num_format_coin(sum_remove_2), coin_2))
                                    remove_list_num[i['pairs']][coin_2] -= sum_remove_2
                    # filter uniq tokens
                    list_pairs = list(set([i['pairs'] for i in get_poolshare]))
                    for i in list_pairs:
                        tickers = i.split("/")
                        if i in list_add:
                            add_dict[i] = "{}".format("\n".join(list_add[i][tickers[0]] + list_add[i][tickers[1]]))
                        if i in list_remove:
                            if tickers[0] in list_remove[i]:
                                remove_dict[i] = "{}".format("\n".join(list_remove[i][tickers[0]] + list_remove[i][tickers[1]]))
                        if i in remove_list_num or i in your_pool_share_num:
                            for coin_name in tickers:
                                a_add = adding_list_num[i][coin_name] if coin_name in adding_list_num[i] else Decimal(0)
                                a_remove = remove_list_num[i][coin_name] if coin_name in remove_list_num[i] else Decimal(0)
                                a_share = your_pool_share_num[i][coin_name] if coin_name in your_pool_share_num[i] else Decimal(0)
                                tmp_gain_lose = a_share - (a_add - a_remove)
                                if abs(truncate(tmp_gain_lose, 4)) != 0:
                                    if i not in gain_lose:
                                        gain_lose[i] = []
                                    gain_lose[i].append("{}{} {}".format(
                                        "+" if tmp_gain_lose > 0 else "-",
                                        num_format_coin(abs(tmp_gain_lose)),
                                        coin_name
                                    ))

                    list_earnings = {}
                    get_user_earning = await get_cexswap_earning(user_id=str(ctx.author.id), from_time=None, pool_id=None, group_pool=True)
                    if len(get_user_earning) > 0:
                        for i in get_user_earning:
                            tickers = i['pairs'].split("/")
                            if i['pairs'] not in list_earnings:
                                list_earnings[i['pairs']] = []
                            if i['got_ticker'] in tickers:
                                list_earnings[i['pairs']].append("{} {}".format(num_format_coin(i['collected_amount']), i['got_ticker']))
                            
                    # Create the view containing our dropdown
                    # list_pairs can be more than 25 - limit of Discord
                    view = DropdownViewMyPool(
                        ctx, self.bot, list_pairs, total_liq, your_pool_share,
                        add_dict, remove_dict, gain_lose, list_earnings, active_pair=None
                    )
                    testing = self.bot.config['cexswap']['testing_msg']
                    embed = disnake.Embed(
                        title="Your LP Pool in TipBot's CEXSwap",
                        description=f"{ctx.author.mention}, {testing}Please select from list.",
                        timestamp=datetime.now(),
                    )
                    embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
                    embed.set_thumbnail(url=ctx.author.display_avatar)

                    await ctx.edit_original_message(
                        content=None,
                        embed=embed,
                        view=view
                    )
            else:
                # check if the given is a single coin/token
                pool_name = pool_name.upper()
                if pool_name not in self.bot.cexswap_pairs:
                    # check if wrong order
                    try:
                        tickers = pool_name.upper().split("/")
                        if len(tickers) == 2:
                            pool_name = "{}/{}".format(tickers[1], tickers[0])
                            if pool_name not in self.bot.cexswap_pairs:
                                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                                    f"Invalid given `{pool_name}`."
                                await ctx.edit_original_message(content=msg)
                                return
                        else:
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                                f"Invalid given `{pool_name}`."
                            await ctx.edit_original_message(content=msg)
                            return
                    except Exception:
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                            f"Invalid given `{pool_name}`."
                        await ctx.edit_original_message(content=msg)
                        traceback.print_exc(file=sys.stdout)
                    # End checking wrong order

                tickers = pool_name.upper().split("/")
                coin_emoji_1 = getattr(getattr(self.bot.coin_list, tickers[0]), "coin_emoji_discord")
                coin_emoji_1 = coin_emoji_1 + " " if coin_emoji_1 else ""
                coin_emoji_2 = getattr(getattr(self.bot.coin_list, tickers[1]), "coin_emoji_discord")
                coin_emoji_2 = coin_emoji_2 + " " if coin_emoji_2 else ""

                testing = self.bot.config['cexswap']['testing_msg']
                embed = disnake.Embed(
                    title="LP Pool {} - {}/{} TipBot's CEXSwap".format(pool_name, coin_emoji_1, coin_emoji_2),
                    description=f"{ctx.author.mention}, {testing}Summary.",
                    timestamp=datetime.now(),
                )
                embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
                embed.set_thumbnail(url=ctx.author.display_avatar)
                liq_pair = await cexswap_get_pool_details(tickers[0], tickers[1], str(ctx.author.id))
                if liq_pair is not None:
                    sub_1 = 0.0
                    sub_2 = 0.0
                    single_pair_amount = 0.0
                    pair_amount = 0.0
                    per_unit = self.utils.get_usd_paprika(liq_pair['pool']['ticker_1_name'])
                    if per_unit > 0:
                        sub_1 = float(Decimal(liq_pair['pool']['amount_ticker_1']) * Decimal(per_unit))
                    per_unit = self.utils.get_usd_paprika(liq_pair['pool']['ticker_2_name'])
                    if per_unit > 0:
                        sub_2 = float(Decimal(liq_pair['pool']['amount_ticker_2']) * Decimal(per_unit))
                    # check max price
                    if sub_1 >= 0.0 and sub_2 >= 0.0:
                        single_pair_amount = max(sub_1, sub_2)
                    if single_pair_amount > 0:
                        pair_amount = 2 * single_pair_amount

                    # show total liq
                    embed.add_field(
                        name="Total liquidity",
                        value="{} {}\n{} {}{}".format(
                            num_format_coin(liq_pair['pool']['amount_ticker_1']), liq_pair['pool']['ticker_1_name'],
                            num_format_coin(liq_pair['pool']['amount_ticker_2']), liq_pair['pool']['ticker_2_name'],
                            "\n~{} {}".format(truncate(pair_amount, 2), "USD") if pair_amount > 0 else ""
                        ),
                        inline=False
                    )

                    # get activities sum
                    user_ar = await cexswap_get_add_remove_user(str(ctx.author.id), SERVER_BOT, liq_pair['pool']['pool_id'])
                    if len(user_ar) > 0:
                        coin_1 = tickers[0]
                        coin_2 = tickers[1]
                        sum_add_1 = Decimal(0)
                        sum_remove_1 = Decimal(0)
                        sum_add_2 = Decimal(0)
                        sum_remove_2 = Decimal(0)
                        for i in user_ar:
                            if coin_1 == i['token_name']:
                                if i['action'] == "add":
                                    sum_add_1 += i['amount']
                                elif i['action'] in ['removepool', 'remove']:
                                    sum_remove_1 += i['amount']
                            elif coin_2 == i['token_name']:
                                if i['action'] == "add":
                                    sum_add_2 += i['amount']
                                elif i['action'] in ['removepool', 'remove']:
                                    sum_remove_2 += i['amount']
                        if sum_add_1 > 0 or sum_add_2 > 0:
                            list_act = []
                            if sum_add_1 > 0:
                                list_act.append("+ {} {}".format(num_format_coin(sum_add_1), coin_1))
                            if sum_add_2 > 0:
                                list_act.append("+ {} {}".format(num_format_coin(sum_add_2), coin_2))
                            embed.add_field(
                                name="You added (Original)",
                                value="{}".format("\n".join(list_act)),
                                inline=False
                            )
                        if sum_remove_1 > 0 or sum_remove_2 > 0:
                            list_act = []
                            if sum_remove_1 > 0:
                                list_act.append("- {} {}".format(num_format_coin(sum_remove_1), coin_1))
                            if sum_remove_2 > 0:
                                list_act.append("- {} {}".format(num_format_coin(sum_remove_2), coin_2))
                            embed.add_field(
                                name="You removed",
                                value="{}".format("\n".join(list_act)),
                                inline=False
                            )
                    if liq_pair['pool_share'] is not None:
                        # If a user has already some liq
                        percent_1 = ""
                        percent_2 = ""
                        try:
                            percent_1 = " - {:,.2f} {}".format(liq_pair['pool_share']['amount_ticker_1']/ liq_pair['pool']['amount_ticker_1']*100, "%")
                            percent_2 = " - {:,.2f} {}".format(liq_pair['pool_share']['amount_ticker_1']/ liq_pair['pool']['amount_ticker_1']*100, "%")
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        embed.add_field(
                            name="Your current LP (Share %)",
                            value="{} {}{}\n{} {}{}".format(
                                num_format_coin(liq_pair['pool_share']['amount_ticker_1']), liq_pair['pool_share']['ticker_1_name'], percent_1, 
                                num_format_coin(liq_pair['pool_share']['amount_ticker_2']), liq_pair['pool_share']['ticker_2_name'], percent_2
                            ),
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="Your current LP (Share %)",
                            value="N/A",
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="NOTE",
                        value="This LP doesn't exist yet!",
                        inline=False
                    )
                await ctx.edit_original_message(
                    content=None,
                    embed=embed
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @cexswap_mypool.autocomplete("pool_name")
    async def cexswap_mypool_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.cexswap_pairs if string in name.lower()][:12]

    @cexswap.sub_command(
        name="addliquidity",
        usage="cexswap addliquidity",
        options=[
            Option("pool_name", "Choose pool's name", OptionType.string, required=True)
        ],
        description="Add a liquidity pool in cexswap."
    )
    async def cexswap_addliquidity(
        self,
        ctx,
        pool_name: str,
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /cexswap loading..."
        await ctx.response.send_message(msg)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/cexswap addliquidity", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if self.bot.config['cexswap']['enable_add_liq'] != 1 and ctx.author.id != self.bot.config['discord']['owner_id']:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, CEXSwap's adding liquidity is temporarily offline! Check again soon."
            await ctx.response.send_message(msg)
            return

        try:
            testing = self.bot.config['cexswap']['testing_msg']
            embed = disnake.Embed(
                title="Add Liquidity to TipBot's CEXSwap",
                description=f"{ctx.author.mention}, {testing}Please click on add liquidity and confirm later.",
                timestamp=datetime.now(),
            )
            pool_name = pool_name.upper()
            if pool_name not in self.bot.cexswap_pairs:
                # check if wrong order
                try:
                    tickers = pool_name.upper().split("/")
                    if len(tickers) == 2:
                        pool_name = "{}/{}".format(tickers[1], tickers[0])
                        if pool_name not in self.bot.cexswap_pairs:
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                                f"Invalid given `{pool_name}`."
                            await ctx.edit_original_message(content=msg)
                            return
                    else:
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                            f"Invalid given `{pool_name}`."
                        await ctx.edit_original_message(content=msg)
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                        f"Invalid given `{pool_name}`."
                    await ctx.edit_original_message(content=msg)
                    return
                # End checking wrong order

            tickers = pool_name.upper().split("/")

            coin_emoji_1 = getattr(getattr(self.bot.coin_list, tickers[0]), "coin_emoji_discord")
            coin_emoji_1 = coin_emoji_1 + " " if coin_emoji_1 else ""
            coin_emoji_2 = getattr(getattr(self.bot.coin_list, tickers[1]), "coin_emoji_discord")
            coin_emoji_2 = coin_emoji_2 + " " if coin_emoji_2 else ""

            min_initialized_liq_1 = getattr(getattr(self.bot.coin_list, tickers[0]), "cexswap_min_initialized_liq")
            min_initialized_liq_2 = getattr(getattr(self.bot.coin_list, tickers[1]), "cexswap_min_initialized_liq")

            init_liq_text = "{} {} and {} {}".format(
                num_format_coin(min_initialized_liq_1), tickers[0],
                num_format_coin(min_initialized_liq_2), tickers[1]
            )

            liq_pair = await cexswap_get_pool_details(tickers[0], tickers[1], str(ctx.author.id))
            if liq_pair is None:
                # check number of pools with these two tokens
                can_init_lp = True
                cant_init_reason = ""
                get_pools = await cexswap_get_pools(tickers[0])
                get_max_pair_allow = getattr(getattr(self.bot.coin_list, tickers[0]), "cexswap_max_pairs")
                max_lp = min(len(get_pools), get_max_pair_allow)
                if len(get_pools) >= get_max_pair_allow or len(get_pools) >= self.bot.config['cexswap']['max_pair_with']:
                    can_init_lp = False
                    cant_init_reason = "{} already reached max. number of LP: **{}**. Contact Bot dev if you would like more.".format(tickers[0], max_lp)

                get_pools = await cexswap_get_pools(tickers[1])
                get_max_pair_allow = getattr(getattr(self.bot.coin_list, tickers[1]), "cexswap_max_pairs")
                max_lp = min(len(get_pools), get_max_pair_allow)
                if len(get_pools) >= get_max_pair_allow or len(get_pools) >= self.bot.config['cexswap']['max_pair_with']:
                    if can_init_lp is True:
                        can_init_lp = False
                        cant_init_reason = "{} already reached max. number of LP: **{}**. Contact Bot dev if you would like more.".format(tickers[1], max_lp)

                if can_init_lp is False:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, {cant_init_reason}"
                    await ctx.edit_original_message(content=msg)
                    await log_to_channel(
                        "cexswap",
                        f"[REJECT ADDING LIQUIDITY]: User {ctx.author.mention} try to add LP to pool `{pool_name}`!"\
                        f" but rejected with reason: {cant_init_reason}",
                        self.bot.config['discord']['cexswap']
                    )
                    return
                embed.add_field(
                    name="New Pool",
                    value="This is a new pair and a start price will be based on yours.",
                    inline=False
                )
            else:
                rate_1 = num_format_coin(
                    liq_pair['pool']['amount_ticker_2']/liq_pair['pool']['amount_ticker_1']
                )
                rate_2 = num_format_coin(
                    liq_pair['pool']['amount_ticker_1']/liq_pair['pool']['amount_ticker_2']
                )
                rate_coin_12 = "{} {} = {} {}\n{} {} = {} {}".format(
                    1, tickers[0], rate_1, tickers[1], 1, tickers[1], rate_2, tickers[0]
                )
                
                # show total liq
                embed.add_field(
                    name="Total liquidity",
                    value="{} {}\n{} {}".format(
                        num_format_coin(liq_pair['pool']['amount_ticker_1']), liq_pair['pool']['ticker_1_name'],
                        num_format_coin(liq_pair['pool']['amount_ticker_2']), liq_pair['pool']['ticker_2_name']
                    ),
                    inline=False
                )
                embed.add_field(
                    name="Existing Pool | Rate",
                    value="{}".format(rate_coin_12),
                    inline=False
                )
                # If a user has already some liq
                percent_1 = ""
                percent_2 = ""

                if liq_pair['pool_share'] is not None:
                    try:
                        percent_1 = " - {:,.2f} {}".format(liq_pair['pool_share']['amount_ticker_1']/ liq_pair['pool']['amount_ticker_1']*100, "%")
                        percent_2 = " - {:,.2f} {}".format(liq_pair['pool_share']['amount_ticker_1']/ liq_pair['pool']['amount_ticker_1']*100, "%")
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    embed.add_field(
                        name="Your existing liquidity",
                        value="{} {}{}\n{} {}{}".format(
                            num_format_coin(liq_pair['pool_share']['amount_ticker_1']), liq_pair['pool_share']['ticker_1_name'], percent_1, 
                            num_format_coin(liq_pair['pool_share']['amount_ticker_2']), liq_pair['pool_share']['ticker_2_name'], percent_2
                        ),
                        inline=False
                    )

                min_liq_1 = getattr(getattr(self.bot.coin_list, tickers[0]), "cexswap_min_add_liq")
                min_liq_2 = getattr(getattr(self.bot.coin_list, tickers[1]), "cexswap_min_add_liq")
                init_liq_text = "{} {}\n{} {}".format(
                    num_format_coin(min_liq_1), tickers[0],
                    num_format_coin(min_liq_2), tickers[1]
                )
            embed.add_field(
                name="Minimum adding",
                value=f"{init_liq_text}",
                inline=False
            )

            embed.add_field(
                name="Adding Ticker {}".format(tickers[0]),
                value="Amount: .. {}{}".format(coin_emoji_1, tickers[0]),
                inline=False
            )
            embed.add_field(
                name="Adding Ticker {}".format(tickers[1]),
                value="Amount: .. {}{}".format(coin_emoji_2, tickers[1]),
                inline=False
            )

            # Check if tx in progress
            if str(ctx.author.id) in self.bot.tipping_in_progress and \
                int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 42:
                msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
                await ctx.edit_original_message(content=msg)
                return
            # end checking tx in progress

            # Check user's balance for both,
            # ticker 0
            balances = []
            balances_str = []
            for coin_name in tickers:
                net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
                )
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                    )

                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                elif type_coin in ["XRP"]:
                    wallet_address = get_deposit['destination_tag']

                height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
                )
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                    )

                height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                userdata_balance = await self.wallet_api.user_balance(
                    str(ctx.author.id), coin_name, wallet_address, 
                    type_coin, height, deposit_confirm_depth, SERVER_BOT
                )
                if float(userdata_balance['adjust']) <= 0:
                    msg = f"{EMOJI_ERROR} {ctx.author.mention}, please check your {coin_name}'s balance!"
                    await ctx.edit_original_message(content=msg)
                    return

                balances.append(float(userdata_balance['adjust']))
                balances_str.append(
                    num_format_coin(float(userdata_balance['adjust']))
                )
            # ticker 1
            await ctx.edit_original_message(
                content=None,
                embed=embed,
                view=add_liquidity_btn(ctx, self.bot, str(ctx.author.id), pool_name, balances_str, accepted=False,
                amount_1=None, amount_2=None)
            )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @cexswap_addliquidity.autocomplete("pool_name")
    async def cexswap_addliquidity_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.cexswap_pairs if string in name.lower()][:12]

    @cexswap.sub_command(
        name="removepools",
        usage="cexswap removepools",
        options=[
            Option("pool_name", "Choose pool's name", OptionType.string, required=True),
        ],
        description="Admin to remove pools and return all balance to liquidators."
    )
    async def cexswap_removepools(
        self,
        ctx,
        pool_name: str
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /cexswap loading..."
        await ctx.response.send_message(msg, ephemeral=True)

        if ctx.author.id != self.bot.config['discord']['owner']:
            await ctx.edit_original_message(content=f"{ctx.auhtor.mention}, you don't have permission!")
            await log_to_channel(
                "cexswap",
                f"[REMOVEPOOL]: User {ctx.author.mention} tried /cexswap removepools. Permission denied!",
                self.bot.config['discord']['cexswap']
            )
            return

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/cexswap removepools", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            pool_name = pool_name.upper()
            if pool_name not in self.bot.cexswap_pairs:
                # check if wrong order
                try:
                    tickers = pool_name.upper().split("/")
                    if len(tickers) == 2:
                        pool_name = "{}/{}".format(tickers[1], tickers[0])
                        if pool_name not in self.bot.cexswap_pairs:
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                                f"Invalid given `{pool_name}`."
                            await ctx.edit_original_message(content=msg)
                            return
                    else:
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                            f"Invalid given `{pool_name}`."
                        await ctx.edit_original_message(content=msg)
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                        f"Invalid given `{pool_name}`."
                    await ctx.edit_original_message(content=msg)
                    return
                # End checking wrong order
            tickers = pool_name.split("/")

            liq_pair = await cexswap_get_pool_details(tickers[0], tickers[1], None)
            if liq_pair is None:
                msg = f"{EMOJI_ERROR}, {ctx.author.mention}, there is no liquidity for that pool `{pool_name}`. "
                await ctx.edit_original_message(content=msg)
                return
            else:
                liq_users = []
                notifying_u = []
                if len(liq_pair['pool_share']) > 0:
                    balance_user = {}
                    for each_s in liq_pair['pool_share']:
                        try:
                            if truncate(float(each_s['amount_ticker_1']), 12) > 0:
                                liq_users += [
                                    float(each_s['amount_ticker_1']), int(time.time()),
                                    each_s['user_id'], each_s['ticker_1_name'], each_s['user_server']
                                ]
                                if each_s['user_server'] == SERVER_BOT:
                                    notifying_u.append(int(each_s['user_id']))
                            if truncate(float(each_s['amount_ticker_2']), 12) > 0:
                                liq_users += [
                                    float(each_s['amount_ticker_2']), int(time.time()),
                                    each_s['user_id'], each_s['ticker_2_name'], each_s['user_server']
                                ]
                                if int(each_s['user_id']) not in notifying_u:
                                    notifying_u.append(int(each_s['user_id']))
                            amount_1_str = num_format_coin(each_s['amount_ticker_1'])
                            amount_2_str = num_format_coin(each_s['amount_ticker_2'])
                            balance_user[each_s['user_id']] = "{} {} and {} {}".format(
                                amount_1_str, each_s['ticker_1_name'],
                                amount_2_str, each_s['ticker_2_name']
                            )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                removing = await cexswap_admin_remove_pool(
                    liq_pair['pool']['pool_id'], str(ctx.author.id), SERVER_BOT,
                    liq_pair['pool']['amount_ticker_1'], liq_pair['pool']['ticker_1_name'],
                    liq_pair['pool']['amount_ticker_2'], liq_pair['pool']['ticker_2_name'],
                    liq_users
                )
                if removing is True:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, successfully removed pool:" \
                        f"```{pool_name}```"
                    num_notifying = 0
                    for liq_u in notifying_u:
                        try:
                            member = self.bot.get_user(liq_u)
                            if member is not None:
                                try:
                                    # Delete if has key
                                    try:
                                        key = str(liq_u) + "_" + liq_pair['pool']['ticker_1_name'] + "_" + SERVER_BOT
                                        if key in self.bot.user_balance_cache:
                                            del self.bot.user_balance_cache[key]
                                        key = str(liq_u) + "_" + liq_pair['pool']['ticker_2_name'] + "_" + SERVER_BOT
                                        if key in self.bot.user_balance_cache:
                                            del self.bot.user_balance_cache[key]
                                    except Exception:
                                        pass
                                    # End of del key
                                    msg_sending = f"Admin removed pool `{pool_name}`. You pool shared return to your balance:"\
                                        f"```{balance_user[str(liq_u)]}```"
                                    await member.send(msg_sending)
                                    num_notifying += 1
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    msg += "And notified {} user(s).".format(num_notifying)
                    await ctx.edit_original_message(content=msg)
                    await log_to_channel(
                        "cexswap",
                        f"[REMOVEPOOL]: User {ctx.author.mention} removed pools `{pool_name}`!",
                        self.bot.config['discord']['cexswap']
                    )
                else:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, internal error."
                    await ctx.edit_original_message(content=msg)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @cexswap_removepools.autocomplete("pool_name")
    async def cexswap_removepools_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.cexswap_pairs if string in name.lower()][:12]

    @cexswap.sub_command(
        name="removeliquidity",
        usage="cexswap removeliquidity",
        options=[
            Option("pool_name", "Choose pool's name", OptionType.string, required=True),
            Option('percentage', 'percentage', OptionType.string, required=True, choices=[
                OptionChoice("10%", "10%"),
                OptionChoice("25%", "25%"),
                OptionChoice("50%", "50%"),
                OptionChoice("75%", "75%"),
                OptionChoice("100%", "100%")
            ])
        ],
        description="Remove your liquidity pool from cexswap."
    )
    async def cexswap_removeliquidity(
        self,
        ctx,
        pool_name: str,
        percentage: str
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /cexswap loading..."
        await ctx.response.send_message(msg)

        if self.bot.config['cexswap']['enable_remove_liq'] != 1 and ctx.author.id != self.bot.config['discord']['owner_id']:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, CEXSwap's removing liquidity is temporarily offline! Check again soon."
            await ctx.response.send_message(msg)
            return

        percentage = int(percentage.replace("%", ""))
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/cexswap removeliquidity", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        pool_name = pool_name.upper()
        get_poolshare = await cexswap_get_poolshare(str(ctx.author.id), SERVER_BOT)
        if len(get_poolshare) == 0:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, sorry! You don't have any liquidity in any pools."
            await ctx.edit_original_message(content=msg)
        else:
            pool_name = pool_name.upper()
            tickers = pool_name.upper().split("/")
            if pool_name not in self.bot.cexswap_pairs:
                # check if wrong order
                try:
                    if len(tickers) == 2:
                        pool_name = "{}/{}".format(tickers[1], tickers[0])
                        if pool_name not in self.bot.cexswap_pairs:
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                                f"Invalid given `{pool_name}`."
                            await ctx.edit_original_message(content=msg)
                            return
                    else:
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                            f"Invalid given `{pool_name}`."
                        await ctx.edit_original_message(content=msg)
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                        f"Invalid given `{pool_name}`."
                    await ctx.edit_original_message(content=msg)
                    return
                # End checking wrong order
            try:
                tickers = pool_name.split("/")
                liq_pair = await cexswap_get_pool_details(tickers[0], tickers[1], str(ctx.author.id))
                if liq_pair is None:
                    msg = f"{EMOJI_ERROR}, {ctx.author.mention}, there is no liquidity for that pool `{pool_name}`. "
                    await ctx.edit_original_message(content=msg)
                    return
                elif liq_pair and liq_pair['pool_share'] is None:
                    msg = f"{EMOJI_ERROR}, {ctx.author.mention}, you own nothing for that pool `{pool_name}`. "
                    await ctx.edit_original_message(content=msg)
                    return
                elif liq_pair and liq_pair['pool_share'] is not None:
                    amount_remove_1 = percentage / 100 * float(liq_pair['pool_share']['amount_ticker_1'])
                    ticker_1 = liq_pair['pool_share']['ticker_1_name']
                    amount_remove_2 = percentage / 100 * float(liq_pair['pool_share']['amount_ticker_2'])
                    ticker_2 = liq_pair['pool_share']['ticker_2_name']
                    complete_remove = False
                    delete_pool = False
                    if percentage == 100:
                        complete_remove = True
                        amount_remove_1 = liq_pair['pool_share']['amount_ticker_1']
                        amount_remove_2 = liq_pair['pool_share']['amount_ticker_2']
                    else:
                        # if the liquidity is too low
                        try:
                            cexswap_min_add_liq_1 = getattr(getattr(self.bot.coin_list, tickers[0]), "cexswap_min")
                            cexswap_min_add_liq_2 = getattr(getattr(self.bot.coin_list, tickers[1]), "cexswap_min")
                            if float(amount_remove_1) < float(cexswap_min_add_liq_1) or float(amount_remove_2) < float(cexswap_min_add_liq_2):
                                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, your current LP is too low. "\
                                    "Please consider to remove 100%."
                                await ctx.edit_original_message(content=msg)
                                return
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    # if you own all pair and amout remove is all.
                    if truncate(float(amount_remove_1), 8) == \
                        truncate(float(liq_pair['pool']['amount_ticker_1']), 8):
                        delete_pool = True
                    if truncate(float(amount_remove_2), 8) == \
                        truncate(float(liq_pair['pool']['amount_ticker_2']), 8):
                        delete_pool = True

                    # Check if tx in progress
                    if str(ctx.author.id) in self.bot.tipping_in_progress and \
                        int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 42:
                        msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
                        await ctx.edit_original_message(content=msg)
                        return
                    if str(ctx.author.id) not in self.bot.tipping_in_progress:
                        self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())
                    # end checking tx in progress

                    removing = await cexswap_remove_pool_share(
                        liq_pair['pool']['pool_id'], amount_remove_1, ticker_1, amount_remove_2, ticker_2,
                        str(ctx.author.id), SERVER_BOT, complete_remove, delete_pool
                    )
                    amount_1_str = num_format_coin(amount_remove_1)
                    amount_2_str = num_format_coin(amount_remove_2)

                    try:
                        del self.bot.tipping_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                    if removing is True:
                        # Delete if has key
                        try:
                            key = str(ctx.author.id) + "_" + ticker_1 + "_" + SERVER_BOT
                            if key in self.bot.user_balance_cache:
                                del self.bot.user_balance_cache[key]
                            key = str(ctx.author.id) + "_" + ticker_2 + "_" + SERVER_BOT
                            if key in self.bot.user_balance_cache:
                                del self.bot.user_balance_cache[key]
                        except Exception:
                            pass
                        # End of del key
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, successfully remove liqudity:" \
                            f"```{amount_1_str} {ticker_1}\n{amount_2_str} {ticker_2}```"
                        await ctx.edit_original_message(content=msg)
                        await log_to_channel(
                            "cexswap",
                            f"[REMOVING LIQUIDITY]: User {ctx.author.mention} removed liquidity from `{pool_name}`!" \
                            f"{amount_1_str} {ticker_1} and {amount_2_str} {ticker_2}",
                            self.bot.config['discord']['cexswap']
                        )
                        get_guilds = await self.utils.get_trade_channel_list()
                        if len(get_guilds) > 0 and self.bot.config['cexswap']['disable'] == 0:
                            list_guild_ids = [i.id for i in self.bot.guilds]
                            for item in get_guilds:
                                if int(item['serverid']) not in list_guild_ids:
                                    continue
                                try:
                                    get_guild = self.bot.get_guild(int(item['serverid']))
                                    if get_guild:
                                        channel = get_guild.get_channel(int(item['trade_channel']))
                                        if channel is None:
                                            continue
                                        if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") and channel.id != ctx.channel.id:
                                            continue
                                        else:
                                            await channel.send(
                                                f"[CEXSWAP]: A user removed liquidity from `{pool_name}`. "\
                                                f"{amount_1_str} {ticker_1} and {amount_2_str} {ticker_2}"
                                            )
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                    else:
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, internal error."
                        await ctx.edit_original_message(content=msg)
            except Exception:
                traceback.print_exc(file=sys.stdout)

    @cexswap_removeliquidity.autocomplete("pool_name")
    async def cexswap_removeliquidity_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.cexswap_pairs if string in name.lower()][:12]

    @cexswap.sub_command(
        name="airdrop",
        usage="cexswap airdrop",
        options=[
            Option("pool_name", "Choose pool's name", OptionType.string, required=True),
            Option("amount", "Choose amount", OptionType.string, required=True),
            Option("token", "Choose token/coin name", OptionType.string, required=True),
            Option("max_alert", "Number of max notification", OptionType.integer, required=True),
            Option('testing', 'If testing or real', OptionType.string, required=False, choices=[
                OptionChoice("Testing Only", "YES"),
                OptionChoice("Do airdrop", "NO")
            ])
        ],
        description="Admin to airdrop to all liquidators."
    )
    async def cexswap_airdrop(
        self,
        ctx,
        pool_name: str,
        amount: str,
        token: str,
        max_alert: int,
        testing: str="NO"
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /cexswap loading aidrop..."
        await ctx.response.send_message(msg, ephemeral=False)

        # check if he's op and own that pool
        check_op = await cexswap_airdrop_check_op(str(ctx.author.id), SERVER_BOT, pool_name)
        if ctx.author.id != self.bot.config['discord']['owner'] and check_op is None:
            await ctx.edit_original_message(content=f"{ctx.auhtor.mention}, you don't have permission with `{pool_name}` or invalid!")
            await log_to_channel(
                "cexswap",
                f"[AIRDROP]: User {ctx.author.mention} tried /cexswap airdrop `{pool_name}`. Permission denied!",
                self.bot.config['discord']['cexswap']
            )
            return
        if ctx.author.id != self.bot.config['discord']['owner'] and check_op is not None:
            # Check number he done airdrop
            max_aidrop = check_op['limit_drop_per_week']
            count_airdrop = await cexswap_airdrop_count(str(ctx.author.id), SERVER_BOT, pool_name, 7*24*3600) # 1 week
            if count_airdrop >= max_aidrop:
                await ctx.edit_original_message(
                    content=f"{ctx.auhtor.mention}, you reached maximum airdrop per week for `{pool_name}` max. **{str(max_aidrop)}**!")
                await log_to_channel(
                    "cexswap",
                    f"[AIRDROP]: User {ctx.author.mention} tried /cexswap reach maximum airdrop `{pool_name}` max. **{str(max_aidrop)}**!",
                    self.bot.config['discord']['cexswap']
                )
                return
        elif ctx.author.id != self.bot.config['discord']['owner']:
            await ctx.edit_original_message(content=f"{ctx.auhtor.mention}, you don't have permission!")
            await log_to_channel(
                "cexswap",
                f"[AIRDROP]: User {ctx.author.mention} tried /cexswap airdrop `{pool_name}`. Permission denied!",
                self.bot.config['discord']['cexswap']
            )
            return
        try:
            coin_name = token.upper()
            if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                coin_name = self.bot.coin_alias_names[coin_name]
            # Token name check
            if not hasattr(self.bot.coin_list, coin_name):
                msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
                await ctx.edit_original_message(content=msg)
                return
            else:
                if getattr(getattr(self.bot.coin_list, coin_name), "enable_tip") != 1:
                    msg = f'{ctx.author.mention}, **{coin_name}** tipping is disable.'
                    await ctx.edit_original_message(content=msg)
                    return
            # End token name check

            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
            max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")

            if "$" in amount[-1] or "$" in amount[0]:  # last is $
                # Check if conversion is allowed for this coin.
                amount = amount.replace(",", "").replace("$", "")
                price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                if price_with is None:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{coin_name}`."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    per_unit = await self.utils.get_coin_price(coin_name, price_with)
                    if per_unit and per_unit['price'] and per_unit['price'] > 0:
                        per_unit = per_unit['price']
                        amount = float(Decimal(amount) / Decimal(per_unit))
                    else:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. "\
                            "Try with different method."
                        await ctx.edit_original_message(content=msg)
                        return
            else:
                amount = amount.replace(",", "")
                amount = text_to_num(amount)
                if amount is None:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount."
                    await ctx.edit_original_message(content=msg)
                    return
            # end of check if amount is all

            liq_users = []
            balance_rows = []
            lp_details = []
            lp_discord_users = []
            liq_user_percentages = {}
            balance_user = {}

            # owner
            balance_rows.append((
                str(ctx.author.id), coin_name, SERVER_BOT, -float(truncate(amount, 8)), int(time.time())
            ))

            pool_name = pool_name.upper()
            # check if the given is a single coin/token
            single_coin = False
            if pool_name in self.bot.cexswap_coins:
                single_coin = True
                # that is one coin only
                # Find pool with
                find_other_lp = await cexswap_get_all_poolshares(user_id=None, ticker=pool_name)
                # We'll get a list of that
                if len(find_other_lp) == 0:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, there's not any pool share with `{pool_name}`."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    list_user_with_amount = {}
                    total_amount = 0
                    server_user_list = {}
                    for i in find_other_lp:
                        if i['user_id'] not in server_user_list:
                            server_user_list[i['user_id']] = i['user_server']
                        if i['ticker_1_name'] == pool_name:
                            if i['user_id'] not in list_user_with_amount:
                                list_user_with_amount[i['user_id'] ] = i['amount_ticker_1']
                            else:
                                list_user_with_amount[i['user_id'] ] += i['amount_ticker_1']
                            total_amount += i['amount_ticker_1']
                        elif i['ticker_2_name'] == pool_name:
                            if i['user_id'] not in list_user_with_amount:
                                list_user_with_amount[i['user_id'] ] = i['amount_ticker_2']
                            else:
                                list_user_with_amount[i['user_id'] ] += i['amount_ticker_2']
                            total_amount += i['amount_ticker_2']
                    for k, v in list_user_with_amount.items():
                        distributed_amount = truncate(
                            float(v) / float(total_amount) * float(truncate(amount, 12)), 8
                        )
                        if distributed_amount > 0:
                            liq_users.append([float(distributed_amount), k, server_user_list[k]])
                            if float(distributed_amount) / float(amount) * 100 > 0.01:
                                liq_user_percentages[k] = "{:,.2f} {}".format(float(distributed_amount) / float(amount)*100, "%")
                                balance_rows.append((
                                    k, coin_name, server_user_list[k], float(truncate(distributed_amount, 8)), int(time.time())
                                ))
                                lp_details.append((
                                    None, pool_name, str(ctx.author.id), k, coin_name,
                                    float(truncate(amount, 8)), float(truncate(distributed_amount, 8)),
                                    float(truncate(distributed_amount, 8)) / float(truncate(amount, 8)) * 100,
                                    int(time.time())
                                ))
                                if server_user_list[k] == SERVER_BOT:
                                    lp_discord_users.append(k)
                                    balance_user[k] = num_format_coin(distributed_amount)

            elif pool_name not in self.bot.cexswap_pairs:
                # check if wrong order
                try:
                    tickers = pool_name.upper().split("/")
                    if len(tickers) == 2:
                        pool_name = "{}/{}".format(tickers[1], tickers[0])
                        if pool_name not in self.bot.cexswap_pairs:
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                                f"Invalid given `{pool_name}`."
                            await ctx.edit_original_message(content=msg)
                            return
                    else:
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                            f"Invalid given `{pool_name}`."
                        await ctx.edit_original_message(content=msg)
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                        f"Invalid given `{pool_name}`."
                    await ctx.edit_original_message(content=msg)
                    return
                # End checking wrong order

            if pool_name not in self.bot.cexswap_pairs and single_coin is False:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, please select from pair list!  "\
                    f"Invalid given `{pool_name}`."
                await ctx.edit_original_message(content=msg)
                return
            elif pool_name in self.bot.cexswap_pairs and single_coin is False:
                tickers = pool_name.split("/")
                liq_pair = await cexswap_get_pool_details(tickers[0], tickers[1], None)
                if liq_pair is None:
                    msg = f"{EMOJI_ERROR}, {ctx.author.mention}, there is no liquidity of `{pool_name}` yet."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    if len(liq_pair['pool_share']) > 0:
                        for each_s in liq_pair['pool_share']:
                            distributed_amount = truncate(
                                float(each_s['amount_ticker_1']) / float(liq_pair['pool']['amount_ticker_1']) * \
                                float(truncate(amount, 12)), 8
                            )
                            if distributed_amount > 0:
                                liq_users.append([float(distributed_amount), each_s['user_id'], each_s['user_server']])
                                if float(each_s['amount_ticker_1']) / float(liq_pair['pool']['amount_ticker_1']) * 100 > 0.01:
                                    liq_user_percentages[each_s['user_id']] = "{:,.2f} {}".format(
                                        float(each_s['amount_ticker_1']) / float(liq_pair['pool']['amount_ticker_1'])*100, "%"
                                    )
                    if len(liq_users) == 0:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention} internal error, found 0 liquidator."
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        # lp users
                        for i in liq_users:
                            try:
                                if float(truncate(amount, 8)) > 0.0:
                                    balance_rows.append((
                                        i[1], coin_name, i[2], float(truncate(i[0], 8)), int(time.time())
                                    ))
                                    lp_details.append((
                                        liq_pair['pool']['pool_id'], pool_name, str(ctx.author.id), i[1], coin_name,
                                        float(truncate(amount, 8)), float(truncate(i[0], 8)),
                                        float(truncate(i[0], 8)) / float(truncate(amount, 8)) * 100,
                                        int(time.time())
                                    ))
                                    if i[2] == SERVER_BOT:
                                        lp_discord_users.append(i[1])
                                        balance_user[str(i[1])] = num_format_coin(i[0])
                            except Exception:
                                traceback.print_exc(file=sys.stdout)

            if max_alert <= 0:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, `max_alert` must be bigger than 0."
                await ctx.edit_original_message(content=msg)
                return
            elif max_alert > self.bot.config['cexswap']['max_airdrop_lp']:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, `max_alert` must be smaller than "\
                    f"{self.bot.config['cexswap']['max_airdrop_lp']}."
                await ctx.edit_original_message(content=msg)
                return

            amount = float(amount)
            get_deposit = await self.wallet_api.sql_get_userwallet(
                str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(
                    str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                )

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
            userdata_balance = await self.wallet_api.user_balance(
                str(ctx.author.id), coin_name, wallet_address, type_coin,
                height, deposit_confirm_depth, SERVER_BOT
            )
            actual_balance = float(userdata_balance['adjust'])
            if amount <= 0 or actual_balance <= 0:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
                await ctx.edit_original_message(content=msg)
                return

            if amount > max_tip or amount < min_tip:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, transactions cannot be bigger than "\
                    f"**{num_format_coin(max_tip)} {token_display}** or smaller than "\
                    f"**{num_format_coin(min_tip)} {token_display}**."
                await ctx.edit_original_message(content=msg)
                return
            elif amount > actual_balance:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to do a airdrop LP of "\
                    f"**{num_format_coin(amount)} {token_display}**."
                await ctx.edit_original_message(content=msg)
                return

            if len(liq_users) > 0:
                if testing == "NO":
                    airdroping = await cexswap_airdrop_lp_detail(
                        balance_rows, lp_details,
                        str(ctx.author.id), SERVER_BOT, amount, coin_name, pool_name
                    )
                else:
                    airdroping = True
                num_notifying = 0
                list_receivers_str = []
                if airdroping is True and len(lp_discord_users) > 0:
                    random.shuffle(lp_discord_users)
                    lp_discord_users = lp_discord_users[0:max_alert]
                    # Delete if has key
                    try:
                        key = str(ctx.author.id) + "_" + coin_name + "_" + SERVER_BOT
                        if key in self.bot.user_balance_cache:
                            del self.bot.user_balance_cache[key]
                    except Exception:
                        pass
                    # End of del key
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, successfully airdrop for pool: `{pool_name}`. Testing: `{testing}`"
                    for each_u in lp_discord_users:
                        list_receivers_str.append("UserID {}: {} {}".format(each_u, balance_user[str(each_u)], coin_name))
                        if testing == "NO":
                            try:
                                member = self.bot.get_user(int(each_u))
                                if member is not None and each_u in liq_user_percentages:
                                    try:
                                        # Delete if has key
                                        try:
                                            key = str(each_u) + "_" + coin_name + "_" + SERVER_BOT
                                            if key in self.bot.user_balance_cache:
                                                del self.bot.user_balance_cache[key]
                                        except Exception:
                                            pass
                                        # End of del key
                                        msg_sending = f"[Admin/Pool OP] did an airdrop for pool `{pool_name}`. "\
                                            f"You have **{liq_user_percentages[each_u]}** in that pool. "\
                                            f"Airdrop delivered to your balance:"\
                                            f"```{balance_user[str(each_u)]} {coin_name}```Thank you!"
                                        await member.send(msg_sending)
                                        num_notifying += 1
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                msg += " And notified {} user(s).".format(num_notifying)
                msg += "```" + "\n".join(list_receivers_str) + "```"
                await ctx.edit_original_message(content=msg)
                await log_to_channel(
                    "cexswap",
                    f"[AIRDROP LP]: User {ctx.author.mention} did airdrop LP for pools `{pool_name}`. Testing: {testing}!",
                    self.bot.config['discord']['cexswap']
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @cexswap_airdrop.autocomplete("pool_name")
    async def cexswap_airdrop_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.cexswap_pairs if string in name.lower()][:12]

    @cexswap_airdrop.autocomplete("token")
    async def cexswap_airdrop_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

    @cexswap.sub_command(
        name="apikey",
        usage="cexswap apikey [resetkey]", 
        options=[
            Option('resetkey', 'resetkey', OptionType.string, required=False, choices=[
                OptionChoice("YES", "YES"),
                OptionChoice("NO", "NO")
            ])
        ],
        description="Get token key for CEXSwap API call."
    )
    async def cexswap_apikey(
        self,
        ctx,
        resetkey: str=None
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, loading..."
        await ctx.response.send_message(msg, ephemeral=True)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/cexswap apikey", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if self.bot.config['cexswap_api']['api_private_key_enable'] != 1:
            await ctx.edit_original_message(
                content=f"{ctx.author.mention}, private API is currently disable! Check again later!"
            )
            return

        # Check if user not in main guild
        try:
            main_guild = self.bot.get_guild(self.bot.config['cexswap_api']['main_guild_id'])
            if main_guild is not None:
                get_user = main_guild.get_member(ctx.author.id)
                if get_user is None:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, you need to stay in our main Discord guild to get API key!"
                    )
                    return
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            if resetkey is None:
                resetkey = "NO"
            get_user = await find_user_by_id(str(ctx.author.id), SERVER_BOT)
            link_help = self.bot.config['cexswap_api']['link_help']
            if get_user is None:
                random_string = str(uuid.uuid4())
                hash_key = sha256(random_string.encode()).hexdigest()
                insert_key = await bot_user_add(str(ctx.author.id), SERVER_BOT, encrypt_string(random_string), hash_key)
                if insert_key is True:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, your CEXSwap API key:```{random_string}```Keep it in a secret place!{link_help}"
                    )
                    await log_to_channel(
                        "cexswap",
                        f"[API CREATE]: User {ctx.author.mention} / {ctx.author.id} create a new API key!",
                        self.bot.config['discord']['cexswap']
                    )
                else:
                    await ctx.edit_original_message(
                        content=f"Internal error!"
                    )
            else:
                if resetkey == "NO":
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, your CEXSwap API key:```{decrypt_string(get_user['cexswap_api_key'])}```Keep it in a secret place!{link_help}"
                    )
                    await log_to_channel(
                        "cexswap",
                        f"[API SHOW]: User {ctx.author.mention} / {ctx.author.id} asked to show API key!",
                        self.bot.config['discord']['cexswap']
                    )
                else:
                    # he reset
                    random_string = str(uuid.uuid4())
                    hash_key = sha256(random_string.encode()).hexdigest()
                    insert_key = await bot_user_add(str(ctx.author.id), SERVER_BOT, encrypt_string(random_string), hash_key)
                    if insert_key is True:
                        await ctx.edit_original_message(
                            content=f"{ctx.author.mention}, you reset CEXSwap API key to:```{random_string}```Keep it in a secret place!{link_help}"
                        )
                        await log_to_channel(
                            "cexswap",
                            f"[API RESET]: User {ctx.author.mention} / {ctx.author.id} reset a new API key!",
                            self.bot.config['discord']['cexswap']
                        )
                    else:
                        await ctx.edit_original_message(
                            content=f"Internal error!"
                        )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @cexswap.sub_command(
        name="earning",
        usage="cexswap earning",
        options=[
            Option('option', 'option', OptionType.string, required=False, choices=[
                OptionChoice("show public", "public"),
                OptionChoice("show private", "private")
            ]),
            Option("token", "Show only this token/coin name", OptionType.string, required=False),
        ],
        description="Show some earning from cexswap."
    )
    async def cexswap_earning(
        self,
        ctx,
        option: str="private",
        token: str=None
    ):
        eph = True
        if option.lower() == "public":
            eph = False
        if token is not None:
            token = token.upper()

        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /cexswap loading..."
        await ctx.response.send_message(msg, ephemeral=eph)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/cexswap earning", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            testing = self.bot.config['cexswap']['testing_msg']
            embed = disnake.Embed(
                title="Your LP earning from TipBot's CEXSwap",
                description=f"{ctx.author.mention}, {testing}List of distributed earning from Liquidity Pools.",
                timestamp=datetime.now(),
            )
            if token is None:
                # check current LP user has
                get_poolshare = await cexswap_get_poolshare(str(ctx.author.id), SERVER_BOT)
                if len(get_poolshare) > 0:
                    list_coin_lp_user = []
                    for p in get_poolshare:
                        # amount_1 = num_format_coin(p['amount_ticker_1'])
                        amount_1 = human_format(p['amount_ticker_1'])
                        # amount_2 = num_format_coin(p['amount_ticker_2'])
                        amount_2 = human_format(p['amount_ticker_2'])
                        coin_1 = p['ticker_1_name'][:4] + ".." if len(p['ticker_1_name']) > 5 else p['ticker_1_name']
                        coin_2 = p['ticker_2_name'][:4] + ".." if len(p['ticker_2_name']) > 5 else p['ticker_2_name']
                        list_coin_lp_user.append("⚆ {}/{} :\n---{} {}\n---{} {}\n".format(
                            coin_1, coin_2,
                            amount_1, p['ticker_1_name'],
                            amount_2, p['ticker_2_name']
                        ))
                    list_coin_lp_user_chunks = list(chunks(list_coin_lp_user, 4))
                    j = 1
                    extra_text = ""
                    for i in list_coin_lp_user_chunks:
                        if len(list_coin_lp_user_chunks) > 1:
                            extra_text = " [{}/{}]".format(j, len(list_coin_lp_user_chunks))
                        embed.add_field(
                            name="Your LP{}".format(extra_text),
                            value="{}".format("\n".join(i)),
                            inline=True
                        )
                        j += 1
            else:
                # if that coin is enable
                if token not in self.bot.cexswap_coins:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, there is no `{token}` in CEXSwap."
                    await ctx.edit_original_message(content=msg)
                    return
                # check pool share of a coin by user
                find_other_lp = await cexswap_get_all_poolshares(user_id=None, ticker=token)
                # We'll get a list of that
                if len(find_other_lp) == 0:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you currently don't have any pool share with `{token}`."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    user_amount = 0
                    total_pool_coin = 0
                    user_pools = [i for i in find_other_lp if i['user_id']==str(ctx.author.id)]
                    for i in find_other_lp:
                        if i['user_id'] != str(ctx.author.id):
                            if i['ticker_1_name'] == token:
                                total_pool_coin += i['amount_ticker_1']
                            elif i['ticker_2_name'] == token:
                                total_pool_coin += i['amount_ticker_2']
                        else:
                            if i['ticker_1_name'] == token:
                                user_amount += i['amount_ticker_1']
                                total_pool_coin += i['amount_ticker_1']
                            elif i['ticker_2_name'] == token:
                                user_amount += i['amount_ticker_2']
                                total_pool_coin += i['amount_ticker_2']
                    embed.add_field(
                        name="Your have {} LP with {}".format(len(user_pools), token),
                        value="Amount: {} {}\n({:,.2f} {})".format(
                            num_format_coin(user_amount), token, user_amount/total_pool_coin*100,"%"
                        ),
                        inline=False
                    )
                    embed.add_field(
                        name="Your LP with {}".format(token),
                        value="{}".format(", ".join(list(set([i['pairs'] for i in user_pools])))),
                        inline=False
                    )
            # check earning
            get_user_earning = await get_cexswap_earning(user_id=str(ctx.author.id), from_time=None, pool_id=None)
            if len(get_user_earning) == 0 and token is None:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you don't have any earning from LP yet."
                await ctx.edit_original_message(content=msg)
                return
            elif len(get_user_earning) > 0:
                list_earning = []
                for each in get_user_earning:
                    if token is not None and token != each['got_ticker']:
                        continue
                    coin_emoji = ""
                    try:
                        if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                            if ctx.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is True:
                                coin_emoji = getattr(getattr(self.bot.coin_list, each['got_ticker']), "coin_emoji_discord")
                                coin_emoji = coin_emoji + " " if coin_emoji else ""
                        else:
                            coin_emoji = getattr(getattr(self.bot.coin_list, each['got_ticker']), "coin_emoji_discord")
                            coin_emoji = coin_emoji + " " if coin_emoji else ""
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    earning_amount = num_format_coin(
                        each['collected_amount']
                    )
                    list_earning.append("{}{} {} - {:,.0f} trade(s)".format(coin_emoji, earning_amount, each['got_ticker'], each['total_swap']))
                if len(list_earning) > 0:
                    list_earning_split = list(chunks(list_earning, 12))
                    j = 1
                    extra_text = ""
                    for i in list_earning_split:
                        if len(list_earning_split) > 1:
                            extra_text = " [{}/{}]".format(j, len(list_earning_split))
                        embed.add_field(
                            name="Your earning{}".format(extra_text),
                            value="{}".format("\n".join(i)),
                            inline=False
                        )
                        j += 1

            # last emebed to add
            embed.add_field(
                name="NOTE",
                value="You can check your balance by `/balance` or `/balances`. "\
                    "From every trade, you will always receive fee {} x amount liquidated pools.\n\n"\
                    "You can check recent earning also with `/recent cexswaplp <token>`.".format("0.50%"),
                inline=False
            )
            embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
            embed.set_thumbnail(url=ctx.author.display_avatar)
            await ctx.edit_original_message(content=None, embed=embed)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @cexswap_earning.autocomplete("token")
    async def cexswap_earning_token_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.cexswap_coins if string in name.lower()][:10]

    async def webserver(self):
        async def handler_get(request):
            if 'Authorization' in request.headers:
                try:
                    # find user by key
                    key = request.headers['Authorization']
                    hash_key = sha256(key.encode()).hexdigest()
                    find_user = await find_user_by_apikey(hash_key)
                    if find_user is None:
                        result = {
                            "success": False,
                            "error": "Invalid Authorization API Key!",
                            "time": int(time.time())
                        }
                        return web.json_response(result, status=500)
                    else:
                        if str(request.rel_url).startswith("/get_address/"):
                            coin_name = str(request.rel_url).replace("/get_address/", "").replace("/", "").upper().strip()
                            if len(coin_name) == 0:
                                result = {
                                    "success": False,
                                    "error": "Invalid coin name!",
                                    "time": int(time.time())
                                }
                                return web.json_response(result, status=400)
                            if not hasattr(self.bot.coin_list, coin_name):
                                result = {
                                    "success": False,
                                    "error": f"{coin_name} doesn't exist with us!",
                                    "time": int(time.time())
                                }
                                return web.json_response(result, status=400)
                            else:
                                enable_deposit = getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit")
                                if enable_deposit == 0:
                                    result = {
                                        "success": False,
                                        "error": f"{coin_name} deposit is currently disable!",
                                        "time": int(time.time())
                                    }
                                    return web.json_response(result, status=400)

                                user_id = find_user['user_id']
                                user_server = find_user['user_server']
                                net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                                type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                                get_deposit = await self.wallet_api.sql_get_userwallet(
                                    user_id, coin_name, net_name, type_coin, user_server, 0)
                                if get_deposit is None:
                                    get_deposit = await self.wallet_api.sql_register_user(
                                        user_id, coin_name, net_name, type_coin, user_server, 0, 0
                                    )

                                wallet_address = get_deposit['balance_wallet_address']
                                plain_address = wallet_address
                                if type_coin in ["HNT", "XLM", "VITE", "COSMOS"]:
                                    address_memo = wallet_address.split()
                                    plain_address = address_memo[0] + f" MEMO/TAG: {address_memo[2]}"
                                if plain_address is not None:
                                    result = {
                                        "success": True,
                                        "error": None,
                                        "coin_name": coin_name,
                                        "user_id": user_id,
                                        "address": plain_address,
                                        "time": int(time.time())
                                    }
                                    return web.json_response(result, status=200)
                                else:
                                    result = {
                                        "success": False,
                                        "error": f"{coin_name} internal error!",
                                        "time": int(time.time())
                                    }
                                    return web.json_response(result, status=500)
                        elif str(request.rel_url).startswith("/get_balance/"):
                            coin_name = str(request.rel_url).replace("/get_balance/", "").replace("/", "").upper().strip()
                            if len(coin_name) == 0:
                                result = {
                                    "success": False,
                                    "error": "Invalid coin name!",
                                    "time": int(time.time())
                                }
                                return web.json_response(result, status=400)
                            if not hasattr(self.bot.coin_list, coin_name):
                                result = {
                                    "success": False,
                                    "error": f"{coin_name} doesn't exist with us!",
                                    "time": int(time.time())
                                }
                                return web.json_response(result, status=400)
                            else:
                                user_id = find_user['user_id']
                                user_server = find_user['user_server']
                                net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                                type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")

                                get_deposit = await self.wallet_api.sql_get_userwallet(
                                    user_id, coin_name, net_name, type_coin, user_server, 0)
                                if get_deposit is None:
                                    get_deposit = await self.wallet_api.sql_register_user(
                                        user_id, coin_name, net_name, type_coin, user_server, 0, 0
                                    )

                                wallet_address = get_deposit['balance_wallet_address']
                                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                    wallet_address = get_deposit['paymentid']
                                elif type_coin in ["XRP"]:
                                    wallet_address = get_deposit['destination_tag']

                                height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                                userdata_balance = await self.wallet_api.user_balance(
                                    user_id, coin_name, wallet_address, type_coin,
                                    height, deposit_confirm_depth, user_server
                                )
                                total_balance = userdata_balance['adjust']
                                if total_balance == 0:
                                    # Delete if has key
                                    key = user_id + "_" + coin_name + "_" + user_server
                                    try:
                                        if key in self.bot.user_balance_cache:
                                            del self.bot.user_balance_cache[key]
                                    except Exception:
                                        pass
                                    # End of del key
                                result = {
                                    "success": True,
                                    "error": None,
                                    "coin_name": coin_name,
                                    "balance": total_balance,
                                    "time": int(time.time())
                                }
                                return web.json_response(result, status=200)
                        if str(request.rel_url).startswith("/coininfo/"):
                            coin_name = str(request.rel_url).replace("/coininfo/", "").replace("/", "").upper().strip()
                            if len(coin_name) == 0:
                                result = {
                                    "success": False,
                                    "error": "Invalid coin name!",
                                    "time": int(time.time())
                                }
                                return web.json_response(result, status=400)
                            if not hasattr(self.bot.coin_list, coin_name):
                                result = {
                                    "success": False,
                                    "error": f"{coin_name} doesn't exist with us!",
                                    "time": int(time.time())
                                }
                                return web.json_response(result, status=400)
                            else:
                                min_swap = str(truncate(getattr(getattr(self.bot.coin_list, coin_name), "cexswap_min"), 8))
                                cexswap_enable = getattr(getattr(self.bot.coin_list, coin_name), "cexswap_enable")
                                result = {
                                    "success": True,
                                    "data": {
                                        "cexswap_enable": True if cexswap_enable==1 else False,
                                        "minimum_swap": min_swap,
                                    },
                                    "error": None,
                                    "time": int(time.time())
                                }
                                return web.json_response(result, status=200)
                        else:
                            result = {
                                "success": False,
                                "error": "Invalid call",
                                "time": int(time.time())
                            }
                            return web.json_response(result, status=404)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            else:
                result = {
                    "success": False,
                    "error": "Missing Authorization API key!",
                    "time": int(time.time())
                }
                return web.json_response(result, status=404)
            return web.Response(text="Hello, world")

        async def handler_post(request):
            try:
                if request.body_exists:
                    # check if api is ready only
                    api_readonly = self.bot.config['cexswap_api']['api_readonly']
                    if api_readonly == 1:
                        result = {
                            "success": False,
                            "error": "API is currently read-only mode!",
                            "time": int(time.time())
                        }
                        return web.json_response(result, status=400)

                    payload = await request.read()
                    headers = request.headers
                    full_payload = json.loads(payload)
                    if 'method' not in full_payload:
                        result = {
                            "success": False,
                            "error": "Unknown method!",
                            "time": int(time.time())
                        }
                        return web.json_response(result, status=404)
                    if 'params' not in full_payload:
                        result = {
                            "success": False,
                            "error": "Missing params!",
                            "time": int(time.time())
                        }
                        return web.json_response(result, status=400)
                    method = full_payload['method']
                    params = full_payload['params']
                    id_call = 0
                    if 'id' in full_payload:
                        id_call = full_payload['id']

                    if 'Authorization' in request.headers:
                        # find user by key
                        key = request.headers['Authorization']
                        hash_key = sha256(key.encode()).hexdigest()
                        find_user = await find_user_by_apikey(hash_key)
                        if find_user is None:
                            result = {
                                "success": False,
                                "error": "Invalid Authorization API Key!",
                                "time": int(time.time())
                            }
                            return web.json_response(result, status=500)
                        else:
                            # Check if user not in main guild
                            try:
                                main_guild = self.bot.get_guild(self.bot.config['cexswap_api']['main_guild_id'])
                                if main_guild is not None and find_user['user_server'] == SERVER_BOT:
                                    get_user = main_guild.get_member(int(find_user['user_id']))
                                    if get_user is None:
                                        result = {
                                            "success": False,
                                            "data": None,
                                            "error": "Your Discord Account needs to be in our main Discord Guild to execute this!",
                                            "id": id_call,
                                            "time": int(time.time())
                                        }
                                        await log_to_channel(
                                            "cexswap",
                                            f"[API REJECT]: User <@{find_user['user_id']}> / {find_user['user_id']} not in our Discord Guild!",
                                            self.bot.config['discord']['cexswap']
                                        )
                                        return web.json_response(result, status=200)
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            # Update API calls
                            try:
                                await call_cexswap_api(find_user['user_id'], find_user['user_server'], method, json.dumps(full_payload))
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            if method == "sell":
                                # stop it first here.
                                if find_user['user_id'] in self.bot.tipping_in_progress and \
                                    int(time.time()) - self.bot.tipping_in_progress[find_user['user_id']] < 30:
                                    result = {
                                        "success": False,
                                        "error": "You have another transaction in progress!",
                                        "time": int(time.time())
                                    }

                                if len(params) > 1:
                                    result = {
                                        "success": False,
                                        "data": None,
                                        "error": "Currently, only one trade is allow!",
                                        "id": id_call,
                                        "time": int(time.time())
                                    }
                                    return web.json_response(result, status=200)
                                elif len(params) == 1:
                                    sell_param = params[0]
                                    if 'amount' not in sell_param or 'sell_token' not in sell_param or 'for_token' not in sell_param:
                                        result = {
                                            "success": False,
                                            "data": None,
                                            "error": "Missing or wrong parameters!",
                                            "id": id_call,
                                            "time": int(time.time())
                                        }
                                        return web.json_response(result, status=500)

                                    sell_param['sell_token'] = sell_param['sell_token'].upper()
                                    sell_param['for_token'] = sell_param['for_token'].upper()
                                    amount = sell_param['amount'].replace(",", "")
                                    amount = text_to_num(amount)
                                    if amount is None or amount == 0:
                                        result = {
                                            "success": False,
                                            "data": None,
                                            "error": "Invalid given amount!",
                                            "id": id_call,
                                            "time": int(time.time())
                                        }
                                        return web.json_response(result, status=500)
                                    if sell_param['sell_token'] not in self.bot.cexswap_coins or \
                                        sell_param['for_token'] not in self.bot.cexswap_coins:
                                        result = {
                                            "success": False,
                                            "data": None,
                                            "error": "Invalid given coin/token or they are not in CEXSwap!",
                                            "id": id_call,
                                            "time": int(time.time())
                                        }
                                        return web.json_response(result, status=500)
                                    ref_log = ''.join(random.choice(ascii_uppercase) for i in range(16))
                                    net_name = getattr(getattr(self.bot.coin_list, sell_param['sell_token']), "net_name")
                                    type_coin = getattr(getattr(self.bot.coin_list, sell_param['sell_token']), "type")
                                    height = await self.wallet_api.get_block_height(type_coin, sell_param['sell_token'], net_name)
                                    deposit_confirm_depth = getattr(getattr(self.bot.coin_list, sell_param['sell_token']), "deposit_confirm_depth")
                                    get_deposit = await self.wallet_api.sql_get_userwallet(
                                        find_user['user_id'], sell_param['sell_token'], net_name, type_coin, find_user['user_server'], 0
                                    )
                                    if get_deposit is None:
                                        get_deposit = await self.wallet_api.sql_register_user(
                                            find_user['user_id'], sell_param['sell_token'], net_name, type_coin, find_user['user_server'], 0, 0
                                        )

                                    wallet_address = get_deposit['balance_wallet_address']
                                    if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                        wallet_address = get_deposit['paymentid']
                                    elif type_coin in ["XRP"]:
                                        wallet_address = get_deposit['destination_tag']

                                    userdata_balance = await self.wallet_api.user_balance(
                                        find_user['user_id'], sell_param['sell_token'], wallet_address, 
                                        type_coin, height, deposit_confirm_depth, find_user['user_server']
                                    )
                                    actual_balance = float(userdata_balance['adjust'])
                                    if actual_balance < 0 or truncate(actual_balance, 8) < truncate(amount, 8):
                                        result = {
                                            "success": False,
                                            "error": "Not sufficient balance!",
                                            "time": int(time.time())
                                        }
                                        return web.json_response(result, status=500)
                                    if amount < 0:
                                        result = {
                                            "success": False,
                                            "error": "Invalid given amount!",
                                            "time": int(time.time())
                                        }
                                        return web.json_response(result, status=500)

                                    if find_user['user_id'] in self.bot.tipping_in_progress and \
                                        int(time.time()) - self.bot.tipping_in_progress[find_user['user_id']] < 30:
                                        result = {
                                            "success": False,
                                            "error": "You have another transaction in progress!",
                                            "time": int(time.time())
                                        }
                                    else:
                                        self.bot.tipping_in_progress[find_user['user_id']] = int(time.time())

                                    selling = await cexswap_sold_by_api(
                                        ref_log, amount, sell_param['sell_token'], sell_param['for_token'],
                                        find_user['user_id'], find_user['user_server'],
                                        self.bot.coin_list, self.bot.config
                                    )
                                    if selling['success'] is True:
                                        result = {
                                            "success": True,
                                            "sell": selling['sell'],
                                            "sell_token": selling['sell_token'],
                                            "get": selling['get'],
                                            "for_token": selling['for_token'],
                                            "price_impact_percent": selling['price_impact_percent'],
                                            "message": selling['message'],
                                            "error": None,
                                            "time": int(time.time())
                                        }
                                        if len(selling['delete_cache_balance']) > 0:
                                            for i in selling['delete_cache_balance']:
                                                try:
                                                    if i in self.bot.user_balance_cache:
                                                        del self.bot.user_balance_cache[i]
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                        await log_to_channel(
                                            "cexswap",
                                            f"[API SOLD]: User <@{find_user['user_id']}> / {find_user['user_id']} Sold: " \
                                            f"{selling['sell']} {selling['sell_token']} Get: {selling['get']} {selling['for_token']}. Ref: {selling['ref']}",
                                            self.bot.config['discord']['cexswap']
                                        )
                                        try:
                                            del self.bot.tipping_in_progress[find_user['user_id']]
                                        except Exception:
                                            pass
                                        try:
                                            get_user = self.bot.get_user(int(find_user['user_id']))
                                            if get_user is not None:
                                                msg = f"Sold {selling['sell']} {selling['sell_token']}\nGet: {selling['get']} {selling['for_token']}\nRef: {selling['ref']}"
                                                await get_user.send(
                                                    f"You executed CEXSwap API sold: ```{msg}```" \
                                                    "If you haven't done so, please contact our support and change API key immediately!"
                                                )
                                        except Exception:
                                            pass
                                        return web.json_response(result, status=200)
                                    else:
                                        result = {
                                            "success": False,
                                            "error": selling['error'],
                                            "time": int(time.time())
                                        }
                                        return web.json_response(result, status=500)
                            else:
                                result = {
                                    "success": False,
                                    "error": "Unknown method!",
                                    "time": int(time.time())
                                }
                                return web.json_response(result, status=404)
                    else:
                        result = {
                            "success": False,
                            "error": "Missing Authorization API key!",
                            "time": int(time.time())
                        }
                        return web.json_response(result, status=404)
                else:
                    result = {
                        "success": False,
                        "error": "Invalid call",
                        "time": int(time.time())
                    }
                    return web.json_response(result, status=404)
            except Exception:
                traceback.print_exc(file=sys.stdout)

        app = web.Application()
        app.router.add_get('/{tail:.*}', handler_get)
        app.router.add_post('/{tail:.*}', handler_post)
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(
            runner,
            self.bot.config['cexswap_api']['binding_ip'],
            self.bot.config['cexswap_api']['api_port_private']
        )
        await self.bot.wait_until_ready()
        await self.site.start()

    @tasks.loop(seconds=60.0)
    async def api_trade_announce(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "api_trade_announce"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            lap = int(time.time()) - 600 # not later than 10mn
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `cexswap_sell_logs` 
                        WHERE `api`=1 AND `is_api_announced`=0 AND `time`>%s
                        """
                    await cur.execute(sql, lap)
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        get_guilds = await self.utils.get_trade_channel_list()
                        if len(get_guilds) > 0 and self.bot.config['cexswap']['disable'] == 0 and \
                            self.bot.config['cexswap_api']['api_trade_announcement'] == 1:
                            # too many announcement, skip. Take 10 first
                            result = result[:10]
                            for each_ann in result:
                                try:
                                    list_guild_ids = [i.id for i in self.bot.guilds]
                                    for item in get_guilds:
                                        if int(item['serverid']) not in list_guild_ids:
                                            continue
                                        try:
                                            get_guild = self.bot.get_guild(int(item['serverid']))
                                            if get_guild:
                                                channel = get_guild.get_channel(int(item['trade_channel']))
                                                if channel is None:
                                                    continue
                                                else:
                                                    await channel.send(each_ann['api_messsage'])
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                    # Update announcement
                                    try:
                                        sql = """ UPDATE `cexswap_sell_logs` 
                                            SET `is_api_announced`=1
                                            WHERE `log_id`=%s LIMIT 1;
                                            """
                                        await cur.execute(sql, each_ann['log_id'])
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @commands.Cog.listener()
    async def on_ready(self):
        if len(self.bot.cexswap_coins) == 0:
            await self.cexswap_get_list_enable_pairs()
        if not self.api_trade_announce.is_running():
            self.api_trade_announce.start()

    async def cog_load(self):
        if len(self.bot.cexswap_coins) == 0:
            await self.cexswap_get_list_enable_pairs()
        await self.bot.wait_until_ready()
        if not self.api_trade_announce.is_running():
            self.api_trade_announce.start()

    def cog_unload(self):
        asyncio.ensure_future(self.site.stop())
        self.api_trade_announce.cancel()

def setup(bot):
    cex = Cexswap(bot)
    bot.add_cog(cex)
    bot.loop.create_task(cex.webserver())
