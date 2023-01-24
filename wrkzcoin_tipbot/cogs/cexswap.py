import sys, traceback

import disnake
from disnake.ext import commands
from typing import Optional
from disnake import TextInputStyle
from decimal import Decimal
from datetime import datetime
import time
import itertools
from string import ascii_uppercase
import random
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

import store
from Bot import get_token_list, num_format_coin, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, \
    EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, RowButtonCloseMessage, RowButtonRowCloseAnyMessage, human_format, \
    text_to_num, truncate, seconds_str, EMOJI_HOURGLASS_NOT_DONE, EMOJI_INFORMATION, log_to_channel

from cogs.wallet import WalletAPI
from cogs.utils import Utils

# https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

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
                sql = """ SELECT * 
                FROM `cexswap_pools_share` 
                WHERE `user_id`=%s AND `user_server`=%s """
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
                    WHERE `time`>%s
                    """
                elif from_time is not None:
                    extra_sql = """
                    AND `time`>%s
                    """
                if pool_id is not None:
                    if len(extra_sql) == "":
                        pool_sql = """
                        WHERE `pool_id`=%s
                        """
                    else:
                        pool_sql = """
                        AND `pool_id`=%s
                        """
                
                if user_id is not None:
                    sql = """
                    SELECT SUM(`total_sold_amount`) AS sold, SUM(`total_sold_amount_usd`) AS sold_usd,
                    SUM(`got_total_amount`) AS got, SUM(`got_total_amount_usd`) AS got_usd,
                    `sold_ticker`, `got_ticker`,
                    COUNT(*) AS total_swap
                    FROM `cexswap_sell_logs`
                    GROUP BY `sold_ticker`, `got_ticker`
                    WHERE `sell_user_id`=%s """ + extra_sql + """ """ + pool_sql + """
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
                    SELECT SUM(`total_sold_amount`) AS sold, SUM(`total_sold_amount_usd`) AS sold_usd,
                    SUM(`got_total_amount`) AS got, SUM(`got_total_amount_usd`) AS got_usd,
                    `sold_ticker`, `got_ticker`,
                    COUNT(*) AS total_swap
                    FROM `cexswap_sell_logs`
                     """ + extra_sql + """ """ + pool_sql + """
                    GROUP BY `sold_ticker`, `got_ticker`
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
                `sold_ticker`, `got_ticker`,
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

async def get_cexswap_earning(user_id: str=None, from_time: int=None, pool_id: int=None):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                extra_sql = ""
                pool_sql = ""
                if user_id is None and from_time is not None:
                    extra_sql = """
                    WHERE `date`>%s
                    """
                elif from_time is not None:
                    extra_sql = """
                    AND `date`>%s
                    """
                if pool_id is not None:
                    if len(extra_sql) == "":
                        pool_sql = """
                        WHERE `pool_id`=%s
                        """
                    else:
                        pool_sql = """
                        AND `pool_id`=%s
                        """
                
                if user_id is not None:
                    sql = """
                    SELECT `got_ticker`, `distributed_user_id`, `distributed_user_server`, 
                        SUM(`distributed_amount`) AS collected_amount, SUM(`got_total_amount`) AS got_total_amount,
                        COUNT(*) as total_swap
                    FROM `cexswap_distributing_fee`
                    WHERE `distributed_user_id`=%s """ + extra_sql + """ """ + pool_sql + """
                    GROUP BY `got_ticker`
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

async def cexswap_airdrop_lp_detail(
    list_balance_updates, list_lp_receivers
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
                                        print("PROFIT=>{}".format(msg))
                                        possible_profits.append("  ⚆ {}=>{}, {}=>{}".format(
                                            from_coin, middle_coin, middle_coin, to_coin
                                        ))
                                    else:
                                        print("NO PROFIT=>{}".format(msg))
                    return possible_profits
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return possible_profits
    
async def cexswap_sold(
    ref_log: str, pool_id: int, amount_sell: float, sell_ticker: str,
    amount_get: float, got_ticker: str,
    user_id: str, user_server: str,
    guild_id: str,
    got_fee_dev: float, got_fee_liquidators: float,
    got_fee_guild: float, liquidators, contract: str, coin_decimal: int,
    channel_id: str, per_unit_sell: float, per_unit_get: float,
    pool_amount_sell: float, pool_amount_get: float
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
                `sell_user_id`, `user_server`, `time`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                data_rows += [
                    pool_id, "{}->{}".format(sell_ticker, got_ticker), ref_log, sell_ticker, float(amount_sell),
                    float(amount_sell)*float(per_unit_sell), guild_id, float(amount_get),float(amount_get)*float(per_unit_get),
                    float(got_fee_dev), float(got_fee_liquidators), float(got_fee_guild), got_ticker, user_id,
                    user_server, int(time.time())
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

                # add to mv_data
                sql = """
                    INSERT INTO `user_balance_mv`
                    (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`,
                    `real_amount`, `real_amount_usd`, `token_decimal`, `type`, `date`, `user_server`, `extra_message`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                liq_rows = []
                for each in liquidators:
                    liq_rows.append((
                        got_ticker, contract, "SYSTEM", each[1], guild_id, channel_id,
                        each[0], each[0]*float(per_unit_get), coin_decimal, "CEXSWAPLP", int(time.time()), each[2],
                        ref_log
                    ))
                if guild_id != "DM":
                    liq_rows.append((
                        got_ticker, contract, "SYSTEM", guild_id, guild_id, channel_id,
                        float(got_fee_guild), float(got_fee_guild)*float(per_unit_get), coin_decimal, "CEXSWAPLP", int(time.time()), each[2],
                        ref_log
                    ))
                await cur.executemany(sql, liq_rows)
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
                    for i in self.lp_sorted_key[:8]:
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
                        coin_decimal = getattr(getattr(self.bot.coin_list, k), "decimal")
                        amount_str = num_format_coin(v, k, coin_decimal, False)
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
    def __init__(self, ctx, bot, list_coins, active_coin):
        self.ctx = ctx
        self.bot = bot
        self.list_coins = list_coins
        self.active_coin = active_coin
        self.utils = Utils(self.bot)

        options = [
            disnake.SelectOption(
                label=each,
                description="Select {}".format(each),
                emoji=getattr(getattr(self.bot.coin_list, each), "coin_emoji_discord")
            ) for each in self.list_coins
        ]

        super().__init__(
            placeholder="Choose coin/token..." if self.active_coin is None else "You selected {}".format(self.active_coin),
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
                    coin_decimal_1 = getattr(getattr(self.bot.coin_list, each_p['ticker_1_name']), "decimal")
                    coin_decimal_2 = getattr(getattr(self.bot.coin_list, each_p['ticker_2_name']), "decimal")

                    rate_1 = num_format_coin(
                        each_p['amount_ticker_2']/each_p['amount_ticker_1'],
                        each_p['ticker_2_name'], coin_decimal_2, False
                    )
                    rate_2 = num_format_coin(
                        each_p['amount_ticker_1']/each_p['amount_ticker_2'],
                        each_p['ticker_1_name'], coin_decimal_1, False
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
                            num_format_coin(each_p['amount_ticker_1'], each_p['ticker_1_name'], coin_decimal_1, False), each_p['ticker_1_name'],
                            num_format_coin(each_p['amount_ticker_2'], each_p['ticker_2_name'], coin_decimal_2, False), each_p['ticker_2_name'],
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
        super().__init__(timeout=120.0)
        self.ctx = ctx
        self.bot = bot
        self.list_coins = list_coins
        self.active_coin = active_coin

        self.add_item(DropdownLP(self.ctx, self.bot, self.list_coins, self.active_coin))

    async def on_timeout(self):
        original_message = await self.ctx.original_message()
        await original_message.edit(view=None)
# End of DropdownLP Viewer

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

            coin_decimal_1 = getattr(getattr(self.bot.coin_list, self.ticker_1), "decimal")
            coin_decimal_2 = getattr(getattr(self.bot.coin_list, self.ticker_2), "decimal")

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
                height = self.wallet_api.get_block_height(type_coin, self.ticker_1, net_name)
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

                height = self.wallet_api.get_block_height(type_coin, self.ticker_1, net_name)
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
                height = self.wallet_api.get_block_height(type_coin, self.ticker_2, net_name)
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

                height = self.wallet_api.get_block_height(type_coin, self.ticker_2, net_name)
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
                        liq_pair['pool']['amount_ticker_2']/liq_pair['pool']['amount_ticker_1'],
                        self.ticker_2, coin_decimal_2, False
                    )
                    rate_2 = num_format_coin(
                        liq_pair['pool']['amount_ticker_1']/liq_pair['pool']['amount_ticker_2'],
                        self.ticker_1, coin_decimal_1, False
                    )
                    rate_coin_12 = "{} {} = {} {}\n{} {} = {} {}".format(
                        1, self.ticker_1, rate_1, self.ticker_2, 1, self.ticker_2, rate_2, self.ticker_1
                    )
                    embed.add_field(
                        name="Total liquidity",
                        value="{} {}\n{} {}".format(
                            num_format_coin(liq_pair['pool']['amount_ticker_1'], liq_pair['pool']['ticker_1_name'], coin_decimal_1, False), liq_pair['pool']['ticker_1_name'],
                            num_format_coin(liq_pair['pool']['amount_ticker_2'], liq_pair['pool']['ticker_2_name'], coin_decimal_2, False), liq_pair['pool']['ticker_2_name']
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
                                num_format_coin(liq_pair['pool_share']['amount_ticker_1'], liq_pair['pool_share']['ticker_1_name'], coin_decimal_1, False), liq_pair['pool_share']['ticker_1_name'], percent_1, 
                                num_format_coin(liq_pair['pool_share']['amount_ticker_2'], liq_pair['pool_share']['ticker_2_name'], coin_decimal_1, False), liq_pair['pool_share']['ticker_2_name'], percent_2
                            ),
                            inline=False
                        )
                if accepted is True:
                    embed.add_field(
                        name="Adding Ticker {}".format(self.ticker_1),
                        value="Amount: {} {}{}".format(num_format_coin(amount_1, self.ticker_1, coin_decimal_1, False), self.ticker_1, text_adjust_1),
                        inline=False
                    )
                    embed.add_field(
                        name="Adding Ticker {}".format(self.ticker_2),
                        value="Amount: {} {}{}".format(num_format_coin(amount_2, self.ticker_1, coin_decimal_1, False), self.ticker_2, text_adjust_2),
                        inline=False
                    )
                else:
                    if liq_pair is not None:
                        cexswap_min_add_liq_1 = getattr(getattr(self.bot.coin_list, self.ticker_1), "cexswap_min_initialized_liq")
                        cexswap_min_add_liq_2 = getattr(getattr(self.bot.coin_list, self.ticker_2), "cexswap_min_initialized_liq")

                    init_liq_text = "{} {}\n{} {}".format(
                        num_format_coin(cexswap_min_add_liq_1, self.ticker_1, coin_decimal_1, False), self.ticker_1,
                        num_format_coin(cexswap_min_add_liq_2, self.ticker_2, coin_decimal_2, False), self.ticker_2
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

            await interaction.edit_original_message(f"{interaction.author.mention}, Update! Please accept or cancel.")
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
            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)

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
            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)

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
                coin_decimal_1 = getattr(getattr(self.bot.coin_list, ticker[0]), "decimal")
                coin_decimal_2 = getattr(getattr(self.bot.coin_list, ticker[1]), "decimal")
                add_msg = "{} {} and {} {}".format(
                    num_format_coin(self.amount_1, ticker[0], coin_decimal_1, False), ticker[0],
                    num_format_coin(self.amount_2, ticker[1], coin_decimal_2, False), ticker[1]
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
                                if hasattr(inter, "guild") and hasattr(inter.guild, "id") and channel.id != inter.channel.id:
                                    continue
                                else:
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
                    coin_decimal_1 = getattr(getattr(self.bot.coin_list, each_lp['ticker_1_name']), "decimal")
                    coin_decimal_2 = getattr(getattr(self.bot.coin_list, each_lp['ticker_2_name']), "decimal")
                    lp_in_usd[each_lp['pairs']] = {
                        'ticker_1_name': each_lp['ticker_1_name'],
                        'amount_ticker_1': num_format_coin(each_lp['amount_ticker_1'], each_lp['ticker_1_name'], coin_decimal_1, False),
                        'ticker_2_name': each_lp['ticker_2_name'],
                        'amount_ticker_2': num_format_coin(each_lp['amount_ticker_2'], each_lp['ticker_2_name'], coin_decimal_2, False),
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
                        coin_decimal = getattr(getattr(self.bot.coin_list, i), "decimal")
                        earning_amount = num_format_coin(
                            list_earning_dict[i], i, coin_decimal, False
                        )
                        traded_amount = num_format_coin(
                            list_volume_dict[i], i, coin_decimal, False
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
                    coin_decimal_1 = getattr(getattr(self.bot.coin_list, each_p['ticker_1_name']), "decimal")
                    coin_decimal_2 = getattr(getattr(self.bot.coin_list, each_p['ticker_2_name']), "decimal")

                    rate_1 = num_format_coin(
                        each_p['amount_ticker_2']/each_p['amount_ticker_1'],
                        each_p['ticker_2_name'], coin_decimal_2, False
                    )
                    rate_2 = num_format_coin(
                        each_p['amount_ticker_1']/each_p['amount_ticker_2'],
                        each_p['ticker_1_name'], coin_decimal_1, False
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
                            num_format_coin(each_p['amount_ticker_1'], each_p['ticker_1_name'], coin_decimal_1, False), each_p['ticker_1_name'],
                            num_format_coin(each_p['amount_ticker_2'], each_p['ticker_2_name'], coin_decimal_2, False), each_p['ticker_2_name'],
                            rate_coin_12
                        ),
                        inline=False
                    )

                # filter uniq tokens
                list_coins = list(set([i['ticker_1_name'] for i in get_pools] + [i['ticker_2_name'] for i in get_pools]))[:25]

                # Create the view containing our dropdown
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
            await ctx.response.send_message(msg)
            return

        sell_token = sell_token.upper()
        for_token = for_token.upper()

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
                coin_decimal = getattr(getattr(self.bot.coin_list, sell_token), "decimal")
                usd_equivalent_enable = getattr(getattr(self.bot.coin_list, sell_token), "usd_equivalent_enable")
                cexswap_max_swap_percent_sell = getattr(getattr(self.bot.coin_list, sell_token), "cexswap_max_swap_percent")
                max_swap_sell_cap = cexswap_max_swap_percent_sell * float(amount_liq_sell)

                net_name = getattr(getattr(self.bot.coin_list, sell_token), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, sell_token), "type")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, sell_token), "deposit_confirm_depth")
                contract = getattr(getattr(self.bot.coin_list, sell_token), "contract")

                if "$" in amount[-1] or "$" in amount[0]:  # last is $
                    # Check if conversion is allowed for this coin.
                    amount = amount.replace(",", "").replace("$", "")
                    if usd_equivalent_enable == 0:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{sell_token}`."
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        native_token_name = getattr(getattr(self.bot.coin_list, sell_token), "native_token_name")
                        coin_name_for_price = sell_token
                        if native_token_name:
                            coin_name_for_price = native_token_name
                        per_unit = None
                        if coin_name_for_price in self.bot.token_hints:
                            id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                            per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                        else:
                            per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
                        if per_unit and per_unit > 0:
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

                height = self.wallet_api.get_block_height(type_coin, sell_token, net_name)
                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(ctx.author.id), sell_token, net_name, type_coin, SERVER_BOT, 0
                )
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(ctx.author.id), sell_token, net_name, type_coin, SERVER_BOT, 0, 0
                    )

                height = self.wallet_api.get_block_height(type_coin, sell_token, net_name)
                userdata_balance = await self.wallet_api.user_balance(
                    str(ctx.author.id), sell_token, wallet_address, 
                    type_coin, height, deposit_confirm_depth, SERVER_BOT
                )
                actual_balance = float(userdata_balance['adjust'])

                # Check if amount is more than liquidity
                if truncate(float(amount), 8) > truncate(float(max_swap_sell_cap), 8):
                    coin_decimal_1 = getattr(getattr(self.bot.coin_list, liq_pair['pool']['ticker_1_name']), "decimal")
                    coin_decimal_2 = getattr(getattr(self.bot.coin_list, liq_pair['pool']['ticker_2_name']), "decimal")
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, the given amount `{sell_amount_old}`"\
                        f" is more than allowable 10% of liquidity `{num_format_coin(max_swap_sell_cap, sell_token, coin_decimal, False)} {token_display}`." \
                        f"```Current LP: {num_format_coin(liq_pair['pool']['amount_ticker_1'], liq_pair['pool']['ticker_1_name'], coin_decimal_1, False)} "\
                        f"{liq_pair['pool']['ticker_1_name']} and "\
                        f"{num_format_coin(liq_pair['pool']['amount_ticker_2'], liq_pair['pool']['ticker_2_name'], coin_decimal_2, False)} "\
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

                if sell_token == liq_pair['pool']['ticker_2_name']:
                    amount_get = amount * float(liq_pair['pool']['amount_ticker_1'] / liq_pair['pool']['amount_ticker_2'])
                    slippage = 1.0 - amount / float(liq_pair['pool']['amount_ticker_2']) - self.bot.config['cexswap_slipage']['reserve']
                # adjust slippage
                amount_get = slippage * amount_get
                if slippage > 1 or slippage < 0.88:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, internal error with slippage. Try again later!"
                    await ctx.edit_original_message(content=msg)
                    return
                
                # If the amount get is too small.
                if amount_get < self.bot.config['cexswap']['minimum_receive_or_reject']:
                    coin_decimal_get = getattr(getattr(self.bot.coin_list, for_token), "decimal")
                    num_receive = num_format_coin(amount_get, for_token, coin_decimal_get, False)
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, the received amount is too small "\
                        f"{num_receive} {for_token}. Please increase your sell amount!"
                    await ctx.edit_original_message(content=msg)
                    return

                if amount <= 0 or actual_balance <= 0:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}."
                    await ctx.edit_original_message(content=msg)
                    return
                elif truncate(amount, 8) < truncate(cexswap_min, 8):
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, the given amount `{sell_amount_old}`"\
                        f" is below minimum `{num_format_coin(cexswap_min, sell_token, coin_decimal, False)} {token_display}`."
                    await ctx.edit_original_message(content=msg)
                    return

                elif truncate(actual_balance, 8) < truncate(amount, 8):
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, ⚠️ Please re-check balance {token_display}."
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
                    coin_decimal = getattr(getattr(self.bot.coin_list, for_token), "decimal")
                    channel_id = "DM" if guild_id == "DM" else str(ctx.channel.id)
                    # get price per unit
                    per_unit_sell = 0.0
                    if getattr(getattr(self.bot.coin_list, sell_token), "usd_equivalent_enable") == 1:
                        native_token_name = getattr(getattr(self.bot.coin_list, sell_token), "native_token_name")
                        coin_name_for_price = sell_token
                        if native_token_name:
                            coin_name_for_price = native_token_name
                        if coin_name_for_price in self.bot.token_hints:
                            id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                            per_unit_sell = self.bot.coin_paprika_id_list[id]['price_usd']
                        else:
                            per_unit_sell = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
                        if per_unit_sell and per_unit_sell < 0.0000000001:
                            per_unit_sell = 0.0

                    per_unit_get = 0.0
                    if getattr(getattr(self.bot.coin_list, for_token), "usd_equivalent_enable") == 1:
                        native_token_name = getattr(getattr(self.bot.coin_list, for_token), "native_token_name")
                        coin_name_for_price = for_token
                        if native_token_name:
                            coin_name_for_price = native_token_name
                        if coin_name_for_price in self.bot.token_hints:
                            id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                            per_unit_get = self.bot.coin_paprika_id_list[id]['price_usd']
                        else:
                            per_unit_get = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
                        if per_unit_get and per_unit_get < 0.0000000001:
                            per_unit_get = 0.0

                    fee = truncate(got_fee_dev, 12) + truncate(got_fee_liquidators, 12) + truncate(got_fee_guild, 12)
                    coin_decimal_get = getattr(getattr(self.bot.coin_list, for_token), "decimal")
                    coin_decimal_sell = getattr(getattr(self.bot.coin_list, sell_token), "decimal")
                    user_amount_get = num_format_coin(truncate(amount_get - float(fee), 12), for_token, coin_decimal_get, False)
                    user_amount_sell = num_format_coin(amount, sell_token, coin_decimal_sell, False)

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
                        f"From selling {user_amount_sell} {sell_token}```Ref: `{ref_log}`{suggestion_msg}"

                    # If there is progress
                    if str(ctx.author.id) in self.bot.tipping_in_progress and \
                        int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 30:
                        msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
                        await ctx.response.send_message(content=msg, ephemeral=True)
                        return

                    view = ConfirmSell(self.bot, ctx.author.id)
                    await ctx.edit_original_message(content=msg, view=view)

                    await cexswap_find_possible_trade(
                        sell_token, for_token, amount * slippage, amount_get
                    )

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
                        height = self.wallet_api.get_block_height(type_coin, sell_token, net_name)
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
                        selling = await cexswap_sold(
                            ref_log, liq_pair['pool']['pool_id'], truncate(amount, 12), sell_token, 
                            truncate(amount_get, 12), for_token, str(ctx.author.id), SERVER_BOT,
                            guild_id,
                            truncate(got_fee_dev, 12), truncate(got_fee_liquidators, 12), truncate(got_fee_guild, 12),
                            liq_users, contract, coin_decimal, channel_id, per_unit_sell, per_unit_get,
                            pool_amount_sell, pool_amount_get
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
                                        key = u[1] + "_" + sell_token + "_" + SERVER_BOT
                                        if key in self.bot.user_balance_cache:
                                            del self.bot.user_balance_cache[key]
                                        key = u[1] + "_" + for_token + "_" + SERVER_BOT
                                        if key in self.bot.user_balance_cache:
                                            del self.bot.user_balance_cache[key]
                                if guild_id != "DM":
                                    key = guild_id + "_" + for_token + "_" + SERVER_BOT
                                    if key in self.bot.user_balance_cache:
                                        del self.bot.user_balance_cache[key]
                            except Exception:
                                pass
                            # End of del key
                            # fee_str = num_format_coin(fee, for_token, coin_decimal_get, False)
                            # . Fee {fee_str} {for_token}\n
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, successfully traded!\n"\
                                f"```Get {user_amount_get} {for_token}\n"\
                                f"From selling {user_amount_sell} {sell_token}```✅ Ref: `{ref_log}`{suggestion_msg}"
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
                                    try:
                                        get_guild = self.bot.get_guild(int(item['serverid']))
                                        if get_guild:
                                            channel = get_guild.get_channel(int(item['trade_channel']))
                                            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") and channel.id != ctx.channel.id:
                                                continue
                                            else:
                                                await channel.send(f"[CEXSWAP]: A user sold {user_amount_sell} {sell_token} for "\
                                                    f"{user_amount_get} {for_token}."
                                                )
                                    except disnake.errors.Forbidden:
                                        await self.botLogChan.send(
                                            f"[CEXSwap] failed to message to guild {get_guild.name} / {get_guild.id}."
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
                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
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
                        elif coin_name == i['ticker_2_name']:
                            total_liq += i['amount_ticker_2']                            
                        target_coin = i['ticker_1_name']
                        rate_1 = i['amount_ticker_1'] / i['amount_ticker_2']
                        if coin_name == target_coin:
                            target_coin = i['ticker_2_name']
                            rate_1 = i['amount_ticker_2'] / i['amount_ticker_1']
                        coin_decimal_target = getattr(getattr(self.bot.coin_list, target_coin), "decimal")
                        coin_emoji_target = getattr(getattr(self.bot.coin_list, target_coin), "coin_emoji_discord")
                        if truncate(rate_1, 10) > 0:
                            rate_list.append("{} {} {}".format(
                                coin_emoji_target,
                                num_format_coin(
                                    rate_1, target_coin, coin_decimal_target, False
                                ), target_coin
                            ))
                    if len(rate_list) > 0:
                        rate_list_chunks = list(chunks(rate_list, 12))
                        j = 1
                        for i in rate_list_chunks:
                            embed.add_field(
                                name="RATE LIST {} (Active LP / [{}/{}])".format(coin_name, j, len(rate_list_chunks)),
                                value="{}".format("\n".join(i)),
                                inline=False
                            )
                            j += 1
                    embed.add_field(
                        name="All liquidity {}".format(coin_name),
                        value=num_format_coin(total_liq, coin_name, coin_decimal, False),
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
                                            num_format_coin(sum_amount, coin_name, coin_decimal, False), equi_usd
                                        ),
                                        inline=True
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
                await ctx.edit_original_message(
                    content=None,
                    embed=embed
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
                coin_decimal_1 = getattr(getattr(self.bot.coin_list, tickers[0]), "decimal")
                coin_decimal_2 = getattr(getattr(self.bot.coin_list, tickers[1]), "decimal")

                testing = self.bot.config['cexswap']['testing_msg']
                embed = disnake.Embed(
                    title="LP Pool {} - {}/{} TipBot's CEXSwap".format(pool_name, coin_emoji_1, coin_emoji_2),
                    description=f"{ctx.author.mention}, {testing}Summary.",
                    timestamp=datetime.now(),
                )
                init_liq_text = "{} {}\n{} {}".format(
                    num_format_coin(min_initialized_liq_1, tickers[0], coin_decimal_1, False), tickers[0],
                    num_format_coin(min_initialized_liq_2, tickers[1], coin_decimal_2, False), tickers[1]
                )
                min_liq_1 = getattr(getattr(self.bot.coin_list, tickers[0]), "cexswap_min_add_liq")
                min_liq_2 = getattr(getattr(self.bot.coin_list, tickers[1]), "cexswap_min_add_liq")
                add_liq_text = "{} {}\n{} {}".format(
                    num_format_coin(min_liq_1, tickers[0], coin_decimal_1, False), tickers[0],
                    num_format_coin(min_liq_2, tickers[1], coin_decimal_2, False), tickers[1]
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
                        liq_pair['pool']['amount_ticker_2']/liq_pair['pool']['amount_ticker_1'],
                        tickers[1], coin_decimal_2, False
                    )
                    rate_2 = num_format_coin(
                        liq_pair['pool']['amount_ticker_1']/liq_pair['pool']['amount_ticker_2'],
                        tickers[0], coin_decimal_1, False
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
                            num_format_coin(liq_pair['pool']['amount_ticker_1'], liq_pair['pool']['ticker_1_name'], coin_decimal_1, False), liq_pair['pool']['ticker_1_name'],
                            num_format_coin(liq_pair['pool']['amount_ticker_2'], liq_pair['pool']['ticker_2_name'], coin_decimal_2, False), liq_pair['pool']['ticker_2_name'],
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
                            coin_decimal = getattr(getattr(self.bot.coin_list, each['sold_ticker']), "decimal")
                            sold_amount = num_format_coin(
                                each['sold'], each['sold_ticker'], coin_decimal, False
                            )
                            list_volume.append("{}{} {}".format(coin_emoji, sold_amount, each['sold_ticker']))

                            # trade with
                            coin_emoji = ""
                            try:
                                coin_emoji = getattr(getattr(self.bot.coin_list, each['got_ticker']), "coin_emoji_discord")
                                coin_emoji = coin_emoji + " " if coin_emoji else ""
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            coin_decimal = getattr(getattr(self.bot.coin_list, each['got_ticker']), "decimal")
                            traded_amount = num_format_coin(
                                each['got'], each['got_ticker'], coin_decimal, False
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
                        value="This pool LP doesn't exist yet!",
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
            coin_decimal_1 = getattr(getattr(self.bot.coin_list, tickers[0]), "decimal")
            coin_decimal_2 = getattr(getattr(self.bot.coin_list, tickers[1]), "decimal")

            init_liq_text = "{} {} and {} {}".format(
                num_format_coin(min_initialized_liq_1, tickers[0], coin_decimal_1, False), tickers[0],
                num_format_coin(min_initialized_liq_2, tickers[1], coin_decimal_2, False), tickers[1]
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
                    liq_pair['pool']['amount_ticker_2']/liq_pair['pool']['amount_ticker_1'],
                    tickers[1], coin_decimal_2, False
                )
                rate_2 = num_format_coin(
                    liq_pair['pool']['amount_ticker_1']/liq_pair['pool']['amount_ticker_2'],
                    tickers[0], coin_decimal_1, False
                )
                rate_coin_12 = "{} {} = {} {}\n{} {} = {} {}".format(
                    1, tickers[0], rate_1, tickers[1], 1, tickers[1], rate_2, tickers[0]
                )
                
                # show total liq
                embed.add_field(
                    name="Total liquidity",
                    value="{} {}\n{} {}".format(
                        num_format_coin(liq_pair['pool']['amount_ticker_1'], liq_pair['pool']['ticker_1_name'], coin_decimal_1, False), liq_pair['pool']['ticker_1_name'],
                        num_format_coin(liq_pair['pool']['amount_ticker_2'], liq_pair['pool']['ticker_2_name'], coin_decimal_2, False), liq_pair['pool']['ticker_2_name']
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
                            num_format_coin(liq_pair['pool_share']['amount_ticker_1'], liq_pair['pool_share']['ticker_1_name'], coin_decimal_1, False), liq_pair['pool_share']['ticker_1_name'], percent_1, 
                            num_format_coin(liq_pair['pool_share']['amount_ticker_2'], liq_pair['pool_share']['ticker_2_name'], coin_decimal_1, False), liq_pair['pool_share']['ticker_2_name'], percent_2
                        ),
                        inline=False
                    )

                min_liq_1 = getattr(getattr(self.bot.coin_list, tickers[0]), "cexswap_min_add_liq")
                min_liq_2 = getattr(getattr(self.bot.coin_list, tickers[1]), "cexswap_min_add_liq")
                init_liq_text = "{} {}\n{} {}".format(
                    num_format_coin(min_liq_1, tickers[0], coin_decimal_1, False), tickers[0],
                    num_format_coin(min_liq_2, tickers[1], coin_decimal_2, False), tickers[1]
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
                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
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

                height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
                )
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                    )

                height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
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
                    num_format_coin(float(userdata_balance['adjust']), coin_name, coin_decimal, False)
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
                    coin_decimal_1 = getattr(getattr(self.bot.coin_list, liq_pair['pool']['ticker_1_name']), "decimal")
                    coin_decimal_2 = getattr(getattr(self.bot.coin_list, liq_pair['pool']['ticker_2_name']), "decimal")

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
                            amount_1_str = num_format_coin(each_s['amount_ticker_1'], each_s['ticker_1_name'], coin_decimal_1, False)
                            amount_2_str = num_format_coin(each_s['amount_ticker_2'], each_s['ticker_2_name'], coin_decimal_2, False)
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
                    coin_decimal_1 = getattr(getattr(self.bot.coin_list, ticker_1), "decimal")
                    coin_decimal_2 = getattr(getattr(self.bot.coin_list, ticker_2), "decimal")
                    amount_1_str = num_format_coin(amount_remove_1, ticker_1, coin_decimal_1, False)
                    amount_2_str = num_format_coin(amount_remove_2, ticker_2, coin_decimal_2, False)

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
        ],
        description="Admin to airdrop to all liquidators."
    )
    async def cexswap_airdrop(
        self,
        ctx,
        pool_name: str,
        amount: str,
        token: str,
        max_alert: int
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /cexswap loading aidrop..."
        await ctx.response.send_message(msg, ephemeral=True)

        if ctx.author.id != self.bot.config['discord']['owner']:
            await ctx.edit_original_message(content=f"{ctx.auhtor.mention}, you don't have permission!")
            await log_to_channel(
                "cexswap",
                f"[AIRDROP]: User {ctx.author.mention} tried /cexswap airdrop. Permission denied!",
                self.bot.config['discord']['cexswap']
            )
            return
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

            if max_alert <= 0:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, `max_alert` must be bigger than 0."
                await ctx.edit_original_message(content=msg)
                return
            elif max_alert > self.bot.config['cexswap']['max_airdrop_lp']:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, `max_alert` must be smaller than "\
                    f"{self.bot.config['cexswap']['max_airdrop_lp']}."
                await ctx.edit_original_message(content=msg)
                return

            tickers = pool_name.split("/")
            liq_pair = await cexswap_get_pool_details(tickers[0], tickers[1], None)
            if liq_pair is None:
                msg = f"{EMOJI_ERROR}, {ctx.author.mention}, there is no liquidity of `{pool_name}` yet."
                await ctx.edit_original_message(content=msg)
                return

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

            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
            max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")

            if "$" in amount[-1] or "$" in amount[0]:  # last is $
                # Check if conversion is allowed for this coin.
                amount = amount.replace(",", "").replace("$", "")
                if usd_equivalent_enable == 0:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{coin_name}`."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
                    coin_name_for_price = coin_name
                    if native_token_name:
                        coin_name_for_price = native_token_name
                    per_unit = None
                    if coin_name_for_price in self.bot.token_hints:
                        id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                    else:
                        per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
                    if per_unit and per_unit > 0:
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

            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
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
                    f"**{num_format_coin(max_tip, coin_name, coin_decimal, False)} {token_display}** or smaller than "\
                    f"**{num_format_coin(min_tip, coin_name, coin_decimal, False)} {token_display}**."
                await ctx.edit_original_message(content=msg)
                return
            elif amount > actual_balance:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to do a airdrop LP of "\
                    f"**{num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}**."
                await ctx.edit_original_message(content=msg)
                return

            liq_users = []
            liq_user_percentages = {}
            if len(liq_pair['pool_share']) > 0:
                for each_s in liq_pair['pool_share']:
                    distributed_amount = truncate(
                            float(each_s['amount_ticker_1']) / float(liq_pair['pool']['amount_ticker_1']) * \
                            float(truncate(amount, 12)), 8
                    )
                    if distributed_amount > 0:
                        liq_users.append([float(distributed_amount), each_s['user_id'], each_s['user_server']])
                        if float(each_s['amount_ticker_1']) / float(liq_pair['pool']['amount_ticker_1']) > 0.0001:
                            liq_user_percentages[each_s['user_id']] = "{:,.2f} {}".format(
                                float(each_s['amount_ticker_1']) / float(liq_pair['pool']['amount_ticker_1'])*100, "%"
                            )
            if len(liq_users) == 0:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention} internal error, found 0 liquidator."
                await ctx.edit_original_message(content=msg)
                return
            else:
                balance_rows = []
                lp_details = []
                lp_discord_users = []
                # owner
                balance_rows.append((
                    str(ctx.author.id), coin_name, SERVER_BOT, -float(truncate(amount, 8)), int(time.time())
                ))
                # lp users
                balance_user = {}
                for i in liq_users:
                    try:
                        if float(truncate(amount, 8)) > 0.0:
                            balance_rows.append((
                                i[1], coin_name, SERVER_BOT, float(truncate(i[0], 8)), int(time.time())
                            ))
                            lp_details.append((
                                liq_pair['pool']['pool_id'], pool_name, str(ctx.author.id), i[1], coin_name,
                                float(truncate(amount, 8)), float(truncate(i[0], 8)),
                                float(truncate(i[0], 8)) / float(truncate(amount, 8)) * 100,
                                int(time.time())
                            ))
                            if i[2] == SERVER_BOT:
                                lp_discord_users.append(i[1])
                                balance_user[str(i[1])] = num_format_coin(i[0], coin_name, coin_decimal, False)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                airdroping = await cexswap_airdrop_lp_detail(
                    balance_rows, lp_details
                )
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
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, successfully airdrop for pool: `{pool_name}`."
                    for each_u in lp_discord_users:
                        list_receivers_str.append("UserID {}: {} {}".format(each_u, balance_user[str(each_u)], coin_name))
                        try:
                            member = self.bot.get_user(int(each_u))
                            if member is not None:
                                try:
                                    # Delete if has key
                                    try:
                                        key = str(each_u) + "_" + coin_name + "_" + SERVER_BOT
                                        if key in self.bot.user_balance_cache:
                                            del self.bot.user_balance_cache[key]
                                    except Exception:
                                        pass
                                    # End of del key
                                    msg_sending = f"Admin did an airdrop for pool `{pool_name}`. "\
                                        f"You have **{liq_user_percentages[each_u]}** in that pool. "\
                                        f"Airdrop shared delivers to your balance:"\
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
                    f"[AIRDROP LP]: User {ctx.author.mention} did airdrop LP for pools `{pool_name}`!",
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
        name="earning",
        usage="cexswap earning",
        options=[
            Option('option', 'option', OptionType.string, required=False, choices=[
                OptionChoice("show public", "public"),
                OptionChoice("show private", "private")
            ])
        ],
        description="Show some earning from cexswap."
    )
    async def cexswap_earning(
        self,
        ctx,
        option: str="private"
    ):
        eph = True
        if option.lower() == "public":
            eph = False
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
            # check current LP user has
            get_poolshare = await cexswap_get_poolshare(str(ctx.author.id), SERVER_BOT)
            if len(get_poolshare) > 0:
                list_coin_lp_user = []
                for p in get_poolshare:
                    # coin_decimal = getattr(getattr(self.bot.coin_list, p['ticker_1_name']), "decimal")
                    # amount_1 = num_format_coin(p['amount_ticker_1'], p['ticker_1_name'], coin_decimal, False)
                    amount_1 = human_format(p['amount_ticker_1'])
                    # coin_decimal = getattr(getattr(self.bot.coin_list, p['ticker_2_name']), "decimal")
                    # amount_2 = num_format_coin(p['amount_ticker_2'], p['ticker_2_name'], coin_decimal, False)
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

            # check earning
            get_user_earning = await get_cexswap_earning(user_id=str(ctx.author.id), from_time=None, pool_id=None)
            if len(get_user_earning) == 0:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you don't have any earning from LP yet."
                await ctx.edit_original_message(content=msg)
                return
            else:
                embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
                embed.set_thumbnail(url=ctx.author.display_avatar)
                list_earning = []
                for each in get_user_earning:
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
                    coin_decimal = getattr(getattr(self.bot.coin_list, each['got_ticker']), "decimal")
                    earning_amount = num_format_coin(
                        each['collected_amount'], each['got_ticker'], coin_decimal, False
                    )
                    list_earning.append("{}{} {} - {:,.0f} trade(s)".format(coin_emoji, earning_amount, each['got_ticker'], each['total_swap']))

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
                embed.add_field(
                    name="NOTE",
                    value="You can check your balance by `/balance` or `/balances`. "\
                        "From every trade, you will always receive fee {} x amount liquidated pools.".format("0.50%"),
                    inline=False
                )
                await ctx.edit_original_message(content=None, embed=embed)
        except Exception:
            traceback.print_exc(file=sys.stdout)


    @commands.Cog.listener()
    async def on_ready(self):
        if len(self.bot.cexswap_coins) == 0:
            await self.cexswap_get_list_enable_pairs()

    async def cog_load(self):
        if len(self.bot.cexswap_coins) == 0:
            await self.cexswap_get_list_enable_pairs()

    def cog_unload(self):
        pass

def setup(bot):
    bot.add_cog(Cexswap(bot))
