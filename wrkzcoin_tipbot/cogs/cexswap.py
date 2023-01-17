import sys, traceback

import disnake
from disnake.ext import commands
from disnake import TextInputStyle
from decimal import Decimal
from datetime import datetime
import time
import itertools
from string import ascii_uppercase
import random
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

# ascii table
from terminaltables import AsciiTable
import store
from Bot import get_token_list, num_format_coin, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, \
    EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, RowButtonCloseMessage, RowButtonRowCloseAnyMessage, human_format, \
    text_to_num, truncate, seconds_str, EMOJI_HOURGLASS_NOT_DONE, EMOJI_INFORMATION

from cogs.utils import MenuPage
from cogs.wallet import WalletAPI
from cogs.utils import Utils


async def cexswap_get_pool_details(ticker_1: str, ticker_2: str, user_id: str=None):
    try:
        pool_detail = {}
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * 
                FROM `a_test_cexswap_pools` 
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
                            FROM `a_test_cexswap_pools_share` 
                            WHERE `pool_id`=%s """
                            await cur.execute(sql, (result['pool_id']))
                            detail_res = await cur.fetchall()
                            if detail_res is not None:
                                pool_detail['pool_share'] = detail_res
                        else:
                            sql = """ SELECT * 
                            FROM `a_test_cexswap_pools_share` 
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
                FROM `a_test_cexswap_pools_share` 
                WHERE `user_id`=%s AND `user_server`=%s """
                await cur.execute(sql, (user_id, user_server))
                result = await cur.fetchall()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def cexswap_earning(user_id: str=None):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if user_id is not None:
                    sql = """
                    SELECT `got_ticker`, `distributed_user_id`, `distributed_user_server`, 
                        SUM(`distributed_amount`) as collected_amount, COUNT(*) as total_swap
                    FROM `a_test_cexswap_distributing_fee`
                    WHERE `distributed_user_id`=%s
                    GROUP BY `got_ticker`
                    """
                    await cur.execute(sql, user_id)
                    result = await cur.fetchall()
                    if result:
                        return result
                else:
                    sql = """
                    SELECT `got_ticker`, `distributed_user_id`, `distributed_user_server`, 
                        SUM(`distributed_amount`) as collected_amount, COUNT(*) as total_swap
                    FROM `a_test_cexswap_distributing_fee`
                    GROUP BY `got_ticker`
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

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
                DELETE FROM `a_test_cexswap_pools` 
                WHERE `pool_id`=%s LIMIT 1;
                """
                data_rows = [pool_id]

                sql += """
                INSERT INTO `a_test_cexswap_add_remove_logs`
                (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                VALUES (%s, %s, %s, %s, %s, %s, %s);

                INSERT INTO `a_test_cexswap_add_remove_logs`
                (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """
                data_rows += [pool_id, user_id, user_server, "removepool", int(time.time()), amount_1, ticker_1]
                data_rows += [pool_id, user_id, user_server, "removepool", int(time.time()), amount_2, ticker_2]

                sql += """
                DELETE FROM `a_test_cexswap_pools_share` 
                WHERE `pool_id`=%s;
                """
                data_rows += [pool_id]

                if len(liq_users) > 0:
                    add_sql = """
                    UPDATE `a_test_user_balance_mv_data`
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
                    DELETE FROM `a_test_cexswap_pools` 
                    WHERE `pool_id`=%s LIMIT 1;
                    """
                else:
                    extra = """
                    UPDATE `a_test_cexswap_pools`
                        SET `amount_ticker_1`=`amount_ticker_1`-%s,
                            `amount_ticker_2`=`amount_ticker_2`-%s
                        WHERE `pool_id`=%s AND `ticker_1_name`=%s AND `ticker_2_name`=%s;
                    """
                if complete is True:
                    sql = extra + """
                    DELETE FROM `a_test_cexswap_pools_share`
                    WHERE `pool_id`=%s AND `ticker_1_name`=%s AND `ticker_2_name`=%s 
                        AND `user_id`=%s AND `user_server`=%s LIMIT 1;

                    UPDATE `a_test_user_balance_mv_data`
                    SET `balance`=`balance`+%s
                    WHERE `user_id`=%s AND `token_name`=%s LIMIT 1;

                    UPDATE `a_test_user_balance_mv_data`
                    SET `balance`=`balance`+%s
                    WHERE `user_id`=%s AND `token_name`=%s LIMIT 1;

                    INSERT INTO `a_test_cexswap_add_remove_logs`
                    (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);

                    INSERT INTO `a_test_cexswap_add_remove_logs`
                    (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """
                    data_rows = [
                        pool_id, ticker_1, ticker_2, user_id, user_server,
                        amount_1, user_id, ticker_1,
                        amount_2, user_id, ticker_2,
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
                    UPDATE `a_test_cexswap_pools_share`
                        SET `amount_ticker_1`=`amount_ticker_1`-%s, `amount_ticker_2`=`amount_ticker_2`-%s
                    WHERE `pool_id`=%s AND `ticker_1_name`=%s AND `ticker_2_name`=%s AND `user_id`=%s 
                        AND `user_server`=%s LIMIT 1;

                    UPDATE `a_test_user_balance_mv_data`
                    SET `balance`=`balance`+%s
                    WHERE `user_id`=%s AND `token_name`=%s LIMIT 1;

                    UPDATE `a_test_user_balance_mv_data`
                    SET `balance`=`balance`+%s
                    WHERE `user_id`=%s AND `token_name`=%s LIMIT 1;

                    INSERT INTO `a_test_cexswap_add_remove_logs`
                    (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);

                    INSERT INTO `a_test_cexswap_add_remove_logs`
                    (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """
                    data_rows = [
                        amount_1, amount_2, pool_id, ticker_1, ticker_2, user_id, user_server,
                        amount_1, user_id, ticker_1,
                        amount_2, user_id, ticker_2,
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

async def cexswap_sold(
    ref_log: str, pool_id: int, percentage_inc: float, amount_sell: float, sell_ticker: str,
    amount_get: float, got_ticker: str,
    user_id: str, user_server: str,
    guild_id: str,
    got_fee_dev: float, got_fee_liquidators: float,
    got_fee_guild: float, liquidators
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
                UPDATE `a_test_cexswap_pools`
                SET `amount_ticker_1`=`amount_ticker_1`+%s
                WHERE `ticker_1_name`=%s AND `pool_id`=%s;

                UPDATE `a_test_cexswap_pools`
                SET `amount_ticker_2`=`amount_ticker_2`+%s
                WHERE `ticker_2_name`=%s AND `pool_id`=%s;

                UPDATE `a_test_cexswap_pools`
                SET `amount_ticker_1`=`amount_ticker_1`-%s
                WHERE `ticker_1_name`=%s AND `pool_id`=%s;

                UPDATE `a_test_cexswap_pools`
                SET `amount_ticker_2`=`amount_ticker_2`-%s
                WHERE `ticker_2_name`=%s AND `pool_id`=%s;

                UPDATE `a_test_cexswap_pools_share`
                SET `amount_ticker_1`=`amount_ticker_1`*%s
                WHERE `ticker_1_name`=%s AND `pool_id`=%s;

                UPDATE `a_test_cexswap_pools_share`
                SET `amount_ticker_2`=`amount_ticker_2`*%s
                WHERE `ticker_2_name`=%s AND `pool_id`=%s;

                UPDATE `a_test_cexswap_pools_share`
                SET `amount_ticker_1`=`amount_ticker_1`*%s
                WHERE `ticker_1_name`=%s AND `pool_id`=%s;

                UPDATE `a_test_cexswap_pools_share`
                SET `amount_ticker_2`=`amount_ticker_2`*%s
                WHERE `ticker_2_name`=%s AND `pool_id`=%s;

                UPDATE `a_test_user_balance_mv_data`
                SET `balance`=`balance`-%s 
                WHERE `user_id`=%s AND `token_name`=%s LIMIT 1;

                UPDATE `a_test_user_balance_mv_data`
                SET `balance`=`balance`+%s
                WHERE `user_id`=%s AND `token_name`=%s LIMIT 1;

                INSERT INTO `a_test_user_balance_mv_data`
                (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    `balance`=`balance`+VALUES(`balance`),
                    `update_date`=VALUES(`update_date`);

                INSERT INTO `a_test_user_balance_mv_data`
                (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    `balance`=`balance`+VALUES(`balance`),
                    `update_date`=VALUES(`update_date`);

                INSERT INTO `a_test_cexswap_sell_logs`
                (`pool_id`, `pairs`, `ref_log`, `sold_ticker`, `total_sold_amount`,
                `guild_id`, `got_total_amount`,
                `got_fee_dev`, `got_fee_liquidators`, `got_fee_guild`, `got_ticker`,
                `sell_user_id`, `user_server`, `time`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                # TODO; real balance
                data_rows = [
                    float(amount_sell), sell_ticker, pool_id, float(amount_sell), sell_ticker, pool_id, 
                    float(amount_get), got_ticker, pool_id, float(amount_get), got_ticker, pool_id,
                    1+float(percentage_inc), sell_ticker, pool_id,
                    1+float(percentage_inc), sell_ticker, pool_id,
                    1-float(percentage_inc), got_ticker, pool_id,
                    1-float(percentage_inc), got_ticker, pool_id
                ]
    
                data_rows += [
                    float(amount_sell), user_id, sell_ticker,
                    float(amount_get)-float(got_fee_dev)-float(got_fee_liquidators)-float(got_fee_guild), user_id, got_ticker
                ]
                data_rows += [
                    "SYSTEM", got_ticker, SERVER_BOT, float(got_fee_dev), int(time.time()),
                    guild_id, got_ticker, SERVER_BOT, float(got_fee_guild), int(time.time())
                ]

                data_rows += [
                    pool_id, "{}->{}".format(sell_ticker, got_ticker), ref_log, sell_ticker, float(amount_sell),
                    guild_id, float(amount_get),
                    float(got_fee_dev), float(got_fee_liquidators), float(got_fee_guild), got_ticker, user_id, user_server, int(time.time())
                ]
                await cur.execute(sql, tuple(data_rows))
                await conn.commit()

                sql = """ SELECT * 
                    FROM `a_test_cexswap_sell_logs` 
                    WHERE `ref_log`=%s LIMIT 1
                    """
                sell_id = cur.lastrowid
                await cur.execute(sql, ref_log)
                result = await cur.fetchone()
                if result:
                    sell_id = result['log_id']

                # add to distributed fee
                sql = """
                    INSERT INTO `a_test_cexswap_distributing_fee`
                    (`sell_log_id`, `pool_id`, `got_ticker`, `got_total_amount`, 
                    `distributed_amount`, `distributed_user_id`, `distributed_user_server`, `date`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                liq_rows = []
                for each in liquidators:
                    liq_rows.append((
                        sell_id, pool_id, got_ticker, float(amount_get),
                        each[0], each[1], each[2], int(time.time())
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
                    FROM `a_test_cexswap_pools` 
                    WHERE `enable`=1 
                    AND ((`ticker_1_name`=%s AND `ticker_2_name`=%s)
                        OR (`ticker_1_name`=%s AND `ticker_2_name`=%s)) """
                await cur.execute(sql, (ticker_1_name, ticker_2_name, ticker_2_name, ticker_1_name))
                result = await cur.fetchone()
                if result:
                    pool_id = result['pool_id']
                    existing_pool = True
                else:
                    sql = """ INSERT INTO `a_test_cexswap_pools` 
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
                    INSERT INTO `a_test_cexswap_pools_share`
                    (`pool_id`, `pairs`, `amount_ticker_1`, `ticker_1_name`,
                    `amount_ticker_2`, `ticker_2_name`, `user_id`, `user_server`,
                    `updated_date`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY 
                        UPDATE 
                        `amount_ticker_1`=amount_ticker_1+VALUES(`amount_ticker_1`),
                        `amount_ticker_2`=amount_ticker_2+VALUES(`amount_ticker_2`),
                        `updated_date`=VALUES(`updated_date`);
                    
                    INSERT INTO `a_test_cexswap_add_remove_logs`
                    (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);

                    INSERT INTO `a_test_cexswap_add_remove_logs`
                    (`pool_id`, `user_id`, `user_server`, `action`, `date`, `amount`, `token_name`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);

                    UPDATE `a_test_user_balance_mv_data`
                    SET `balance`=`balance`-%s WHERE `user_id`=%s AND `token_name`=%s LIMIT 1;

                    UPDATE `a_test_user_balance_mv_data`
                    SET `balance`=`balance`-%s WHERE `user_id`=%s AND `token_name`=%s LIMIT 1;
                    """
                    # TODO: change to real table data `a_test_user_balance_mv_data`
                    data_row = [pool_id, pairs, amount_ticker_1, ticker_1_name,
                        amount_ticker_2, ticker_2_name, user_id, user_server, int(time.time()),
                        pool_id, user_id, user_server, "add", int(time.time()), amount_ticker_1, ticker_1_name,
                        pool_id, user_id, user_server, "add", int(time.time()), amount_ticker_2, ticker_2_name,
                        amount_ticker_1, user_id, ticker_1_name,
                        amount_ticker_2, user_id, ticker_2_name
                    ]
                    if existing_pool is True:
                        sql += """ UPDATE `a_test_cexswap_pools` 
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

class add_liqudity(disnake.ui.Modal):
    def __init__(self, ctx, bot, ticker_1: str, ticker_2: str, owner_userid: str) -> None:
        self.ctx = ctx
        self.bot = bot
        self.ticker_1 = ticker_1
        self.ticker_2 = ticker_2
        self.wallet_api = WalletAPI(self.bot)
        self.owner_userid = owner_userid

        components = [
            disnake.ui.TextInput(
                label="Amount Coin {}".format(ticker_1),
                placeholder="10000",
                custom_id="cexswap_amount_coin_id_1",
                style=TextInputStyle.short,
                max_length=16
            ),
            disnake.ui.TextInput(
                label="Amount Coin {}".format(ticker_2),
                placeholder="10000",
                custom_id="cexswap_amount_coin_id_2",
                style=TextInputStyle.short,
                max_length=16
            )
        ]
        super().__init__(title="Add a new liqudity", custom_id="modal_add_new_liqudity", components=components)

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        # Check if type of question is bool or multipe
        try:
            # await interaction.response.defer()
            await interaction.response.send_message(content=f"{interaction.author.mention}, checking liquidity...", ephemeral=True)

            liq_pair = await cexswap_get_pool_details(self.ticker_1, self.ticker_2, self.owner_userid)
            testing = self.bot.config['cexswap']['testing_msg']
            embed = disnake.Embed(
                title="Add Liquidity to TipBot's CEXSwap",
                description=f"{interaction.author.mention}, {testing}Please click on add liqudity and confirm later.",
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

            accepted = False
            text_adjust_1 = ""
            text_adjust_2 = ""
            if amount_1 and amount_2:
                accepted = True
                if amount_1 < 0 or amount_2 < 0:
                    accepted = False

                if liq_pair is None:
                    embed.add_field(
                        name="New Pool",
                        value="This is a new pair and a start price will be based on yours.",
                        inline=False
                    )
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
                        value="```{} {}\n{} {}```".format(
                            num_format_coin(liq_pair['pool']['amount_ticker_1'], liq_pair['pool']['ticker_1_name'], coin_decimal_1, False), liq_pair['pool']['ticker_1_name'],
                            num_format_coin(liq_pair['pool']['amount_ticker_2'], liq_pair['pool']['ticker_2_name'], coin_decimal_2, False), liq_pair['pool']['ticker_2_name']
                        ),
                        inline=False
                    )
                    embed.add_field(
                        name="Existing Pool | Rate",
                        value="```{}```".format(rate_coin_12),
                        inline=False
                    )
                    # If a user has already some liq
                    percent_1 = ""
                    percent_2 = ""
                    try:
                        percent_1 = " - {:,.2f} {}".format(liq_pair['pool_share']['amount_ticker_1']/ liq_pair['pool']['amount_ticker_1']*100, "%")
                        percent_2 = " - {:,.2f} {}".format(liq_pair['pool_share']['amount_ticker_1']/ liq_pair['pool']['amount_ticker_1']*100, "%")
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    if liq_pair['pool_share'] is not None:
                        embed.add_field(
                            name="Your existing liquidity",
                            value="```{} {}{}\n{} {}{}```".format(
                                num_format_coin(liq_pair['pool_share']['amount_ticker_1'], liq_pair['pool_share']['ticker_1_name'], coin_decimal_1, False), liq_pair['pool_share']['ticker_1_name'], percent_1, 
                                num_format_coin(liq_pair['pool_share']['amount_ticker_2'], liq_pair['pool_share']['ticker_2_name'], coin_decimal_1, False), liq_pair['pool_share']['ticker_2_name'], percent_2
                            ),
                            inline=False
                        )
                if accepted is True:
                    embed.add_field(
                        name="Adding Ticker {}".format(self.ticker_1),
                        value="```Amount: {} {}{}```".format(num_format_coin(amount_1, self.ticker_1, coin_decimal_1, False), self.ticker_1, text_adjust_1),
                        inline=False
                    )
                    embed.add_field(
                        name="Adding Ticker {}".format(self.ticker_2),
                        value="```Amount: {} {}{}```".format(num_format_coin(amount_2, self.ticker_1, coin_decimal_1, False), self.ticker_2, text_adjust_2),
                        inline=False
                    )
                else:
                    min_initialized_liq_1 = getattr(getattr(self.bot.coin_list, self.ticker_1), "cexswap_min_initialized_liq")
                    min_initialized_liq_2 = getattr(getattr(self.bot.coin_list, self.ticker_2), "cexswap_min_initialized_liq")
                    coin_decimal_1 = getattr(getattr(self.bot.coin_list, self.ticker_1), "decimal")
                    coin_decimal_2 = getattr(getattr(self.bot.coin_list, self.ticker_2), "decimal")

                    init_liq_text = "{} {} and {} {}".format(
                        num_format_coin(min_initialized_liq_1, self.ticker_1, coin_decimal_1, False), self.ticker_1,
                        num_format_coin(min_initialized_liq_2, self.ticker_2, coin_decimal_2, False), self.ticker_2
                    )
                    embed.add_field(
                        name="Minimum adding",
                        value=f"```{init_liq_text}```",
                        inline=False
                    )
                    embed.add_field(
                        name="Error",
                        value=f'{EMOJI_RED_NO} {interaction.author.mention}, invalid given amount.',
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Error",
                    value=f'{EMOJI_RED_NO} {interaction.author.mention}, invalid given amount.',
                    inline=False
                )
    
            await interaction.message.edit(
                content=None,
                embed=embed,
                view=add_liquidity_btn(self.ctx, self.bot, self.owner_userid, "{}/{}".format(self.ticker_1, self.ticker_2), accepted,
                amount_1, amount_2)
            )

            await interaction.edit_original_message("Update! Please accept or cancel.")
        except Exception:
            traceback.print_exc(file=sys.stdout)
            return

# Defines a simple view of row buttons.
class add_liquidity_btn(disnake.ui.View):
    def __init__(
        self, ctx, bot, owner_id: str, pool_name: str, accepted: bool=False,
        amount_1: float=None, amount_2: float=None,
    ):
        super().__init__(timeout=60.0)
        self.ctx = ctx
        self.bot = bot
        self.owner_id = owner_id
        self.pool_name = pool_name
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

    @disnake.ui.button(label="Add", style=disnake.ButtonStyle.red, custom_id="cexswap_addliquidity_btn")
    async def add_click(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        # await inter.response.send_message("This is the first button.")
        # await inter.response.defer()
        if inter.author.id != self.ctx.author.id:
            await inter.response.send_message(f"{inter.author.mention}, that's not your menu!", ephemeral=True)
            return
        ticker = self.pool_name.split("/")
        await inter.response.send_modal(
                modal=add_liqudity(inter, self.bot, ticker[0], ticker[1], self.owner_id))

    @disnake.ui.button(label="Accept", style=disnake.ButtonStyle.green, custom_id="cexswap_acceptliquidity_btn")
    async def accept_click(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.ctx.author.id:
            await inter.response.send_message(f"{inter.author.mention}, that's not your menu!", ephemeral=True)
            return
        else:
            await inter.response.send_message(f"{inter.author.mention}, checking liquidity.")
        # add liquidity
        # TODO: re-check rate. If change. Reject the insert
        ticker = self.pool_name.split("/")
        add_liq = await cexswap_insert_new(
            self.pool_name, self.amount_1, ticker[0], self.amount_2, ticker[1],
            str(inter.author.id), SERVER_BOT
        )
        if add_liq is True:
            msg = f'{EMOJI_INFORMATION} {inter.author.mention}, successfully added.'
            await inter.edit_original_message(content=msg)
        else:
            msg = f'{EMOJI_INFORMATION} {inter.author.mention}, internal error.'
            await inter.edit_original_message(content=msg)
        self.accept_click.disabled = True
        self.add_click.disabled = True
        await inter.message.edit(view=None)

    @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.gray, custom_id="cexswap_cancelliquidity_btn")
    async def cancel_click(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.ctx.author.id:
            await inter.response.send_message(f"{inter.author.mention}, that's not your menu!", ephemeral=True)
            return
        else:
            await inter.message.delete()

class Cexswap(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.cexswap_pairs = []
        self.cexswap_coins = []

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
                    FROM `a_test_user_balance_mv_data` 
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
                        self.cexswap_coins = list_coins
                        for pair in itertools.combinations(list_coins, 2):
                            list_pairs.append("{}/{}".format(pair[0], pair[1]))
                        if len(list_pairs) > 0:
                            self.cexswap_pairs = list_pairs
                            return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def cexswap_get_pools(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                    FROM `a_test_cexswap_pools`
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []
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
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, cexswap/market function is not ENABLE yet in this guild. "\
                        "Please request Guild owner to enable by `/SETTING TRADE`'
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
                name="Coins with CEXSwap",
                value="{}".format(", ".join(self.cexswap_coins)),
                inline=False
            )
            embed.add_field(
                name="Pairs with CEXSwap",
                value="{}".format(", ".join(self.cexswap_pairs)),
                inline=False
            )  
            # LP available
            get_pools = await self.cexswap_get_pools()
            if len(get_pools) > 0:
                list_pairs = [i['pairs'] for i in get_pools]
                embed.add_field(
                    name="Active LP",
                    value="{}".format(", ".join(list_pairs)),
                    inline=False
                )  
            # List distributed fee
            get_user_earning = await cexswap_earning(None)
            if len(get_user_earning) > 0:
                testing = self.bot.config['cexswap']['testing_msg']
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

                embed.add_field(
                    name="Fee to liquidator(s) - {} coin(s)".format(len(get_user_earning)),
                    value="{}".format("\n".join(list_earning)),
                    inline=False
                )
            embed.add_field(
                name="Remark",
                value="Please often check this summary. We will often have some updates.",
                inline=False
            )  
            embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
            embed.set_thumbnail(url=self.bot.user.display_avatar)
            await ctx.edit_original_message(content=None, embed=embed)
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
        get_pools = await self.cexswap_get_pools()
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
            for each_p in get_pools[0:20]:
                coin_decimal_1 = getattr(getattr(self.bot.coin_list, each_p['ticker_1_name']), "decimal")
                coin_decimal_2 = getattr(getattr(self.bot.coin_list, each_p['ticker_2_name']), "decimal")
                embed.add_field(
                    name="Active LP {}".format(each_p['pairs']),
                    value="```{} {}\n{} {}```".format(
                        num_format_coin(each_p['amount_ticker_1'], each_p['ticker_1_name'], coin_decimal_1, False), each_p['ticker_1_name'],
                        num_format_coin(each_p['amount_ticker_2'], each_p['ticker_2_name'], coin_decimal_2, False), each_p['ticker_2_name']
                    ),
                    inline=False
                )
            await ctx.edit_original_message(content=None, embed=embed)

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
            msg = f"{EMOJI_ERROR}, {ctx.author.mention}, there is no liquidity of `{sell_token}/{for_token}` yet."
            await ctx.edit_original_message(content=msg)
            return
        else:
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
                    if amount is None:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                        await ctx.edit_original_message(content=msg)
                        return

                amount_get = amount * liq_pair['pool']['amount_ticker_2'] / liq_pair['pool']['amount_ticker_1']

                if sell_token == liq_pair['pool']['ticker_1_name']:
                    percentage_inc = amount / liq_pair['pool']['amount_ticker_1']
                else:
                    percentage_inc = amount / liq_pair['pool']['amount_ticker_2']

                if sell_token == liq_pair['pool']['ticker_2_name']:
                    amount_get = amount * liq_pair['pool']['amount_ticker_1'] / liq_pair['pool']['amount_ticker_2']

                if amount <= 0: # TODO: or actual_balance <= 0:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}."
                    await ctx.edit_original_message(content=msg)
                    return
                elif amount < cexswap_min:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, the given amount `{sell_amount_old}`"\
                        f" is below minimum `{num_format_coin(cexswap_min, sell_token, coin_decimal, False)} {token_display}`."
                    await ctx.edit_original_message(content=msg)
                    return
                # TODO: compare with actual balance

                # Check if amount is more than liquidity
                elif amount > max_swap_sell_cap:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, the given amount `{sell_amount_old}`"\
                        f" is more than allowable 10% of liquidity `{num_format_coin(max_swap_sell_cap, sell_token, coin_decimal, False)} {token_display}`."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    # OK, sell..
                    got_fee_dev = amount_get * Decimal(self.bot.config['cexswap']['dev_fee'] / 100)
                    got_fee_liquidators = amount_get * Decimal(self.bot.config['cexswap']['liquidator_fee'] / 100)
                    got_fee_guild = 0.0
                    guild_id = "DM"
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                        got_fee_guild = amount_get * Decimal(self.bot.config['cexswap']['guild_fee'] / 100)
                        guild_id = str(ctx.guild.id)
                    else:
                        got_fee_dev += amount_get * Decimal(self.bot.config['cexswap']['guild_fee'] / 100)

                    ref_log = ''.join(random.choice(ascii_uppercase) for i in range(32))

                    if len(liq_pair['pool_share']) > 0:
                        liq_users = []
                        for each_s in liq_pair['pool_share']:
                            distributed_amount = None
                            if for_token == each_s['ticker_1_name']:
                                print("{} / {} = {}".format(each_s['amount_ticker_1'], float(liq_pair['pool']['amount_ticker_1']), float(each_s['amount_ticker_1']) / float(liq_pair['pool']['amount_ticker_1'])))
                                distributed_amount = float(each_s['amount_ticker_1']) / float(liq_pair['pool']['amount_ticker_1']) * float(truncate(got_fee_liquidators, 12))
                            elif for_token == each_s['ticker_2_name']:
                                print("{} / {} = {}".format(each_s['amount_ticker_2'], float(liq_pair['pool']['amount_ticker_2']), float(each_s['amount_ticker_2']) / float(liq_pair['pool']['amount_ticker_2'])))
                                distributed_amount = float(each_s['amount_ticker_2']) / float(liq_pair['pool']['amount_ticker_2']) * float(truncate(got_fee_liquidators, 12))
                            if distributed_amount is not None:
                                liq_users.append([distributed_amount, each_s['user_id'], each_s['user_server']])
                    selling = await cexswap_sold(
                        ref_log, liq_pair['pool']['pool_id'], percentage_inc, Decimal(truncate(amount, 12)), sell_token, 
                        Decimal(truncate(amount_get, 12)), for_token, str(ctx.author.id), SERVER_BOT,
                        guild_id,
                        truncate(got_fee_dev, 12), truncate(got_fee_liquidators, 12), truncate(got_fee_guild, 12),
                        liq_users
                    )
                    if selling is True:
                        fee = Decimal(truncate(got_fee_dev, 12)) + Decimal(truncate(got_fee_liquidators, 12)) + Decimal(truncate(got_fee_guild, 12))
                        coin_decimal_get = getattr(getattr(self.bot.coin_list, for_token), "decimal")
                        coin_decimal_sell = getattr(getattr(self.bot.coin_list, sell_token), "decimal")
                        user_amount_get = num_format_coin(truncate(amount_get - fee, 12), for_token, coin_decimal_get, False)
                        user_amount_sell = num_format_coin(amount, sell_token, coin_decimal_sell, False)
                        # fee_str = num_format_coin(fee, for_token, coin_decimal_get, False)
                        # . Fee {fee_str} {for_token}\n
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, successfully /cexswap!\n"\
                            f"```Get {user_amount_get} {for_token}\n"\
                            f"From selling {user_amount_sell} {sell_token}```Ref: `{ref_log}`"
                        await ctx.edit_original_message(content=msg)
                    else:
                        await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, internal error!")
            except Exception:
                traceback.print_exc(file=sys.stdout)

    @cexswap_sell.autocomplete("sell_token")
    async def cexswap_addliquidity_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.cexswap_coins if string in name.lower()][:12]

    @cexswap_sell.autocomplete("for_token")
    async def cexswap_addliquidity_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.cexswap_coins if string in name.lower()][:12]

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

        try:
            testing = self.bot.config['cexswap']['testing_msg']
            embed = disnake.Embed(
                title="Add Liquidity to TipBot's CEXSwap",
                description=f"{ctx.author.mention}, {testing}Please click on add liqudity and confirm later.",
                timestamp=datetime.now(),
            )
            tickers = pool_name.split("/")
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
                    value="```{} {}\n{} {}```".format(
                        num_format_coin(liq_pair['pool']['amount_ticker_1'], liq_pair['pool']['ticker_1_name'], coin_decimal_1, False), liq_pair['pool']['ticker_1_name'],
                        num_format_coin(liq_pair['pool']['amount_ticker_2'], liq_pair['pool']['ticker_2_name'], coin_decimal_2, False), liq_pair['pool']['ticker_2_name']
                    ),
                    inline=False
                )
                embed.add_field(
                    name="Existing Pool | Rate",
                    value="```{}```".format(rate_coin_12),
                    inline=False
                )
                # If a user has already some liq
                percent_1 = ""
                percent_2 = ""
                try:
                    percent_1 = " - {:,.2f} {}".format(liq_pair['pool_share']['amount_ticker_1']/ liq_pair['pool']['amount_ticker_1']*100, "%")
                    percent_2 = " - {:,.2f} {}".format(liq_pair['pool_share']['amount_ticker_1']/ liq_pair['pool']['amount_ticker_1']*100, "%")
                except Exception:
                    traceback.print_exc(file=sys.stdout)

                if liq_pair['pool_share'] is not None:
                    embed.add_field(
                        name="Your existing liquidity",
                        value="```{} {}{}\n{} {}{}```".format(
                            num_format_coin(liq_pair['pool_share']['amount_ticker_1'], liq_pair['pool_share']['ticker_1_name'], coin_decimal_1, False), liq_pair['pool_share']['ticker_1_name'], percent_1, 
                            num_format_coin(liq_pair['pool_share']['amount_ticker_2'], liq_pair['pool_share']['ticker_2_name'], coin_decimal_1, False), liq_pair['pool_share']['ticker_2_name'], percent_2
                        ),
                        inline=False
                    )

                min_liq_1 = getattr(getattr(self.bot.coin_list, tickers[0]), "cexswap_min_add_liq")
                min_liq_2 = getattr(getattr(self.bot.coin_list, tickers[1]), "cexswap_min_add_liq")
                init_liq_text = "{} {} and {} {}".format(
                    num_format_coin(min_liq_1, tickers[0], coin_decimal_1, False), tickers[0],
                    num_format_coin(min_liq_2, tickers[1], coin_decimal_2, False), tickers[1]
                )
            embed.add_field(
                name="Minimum adding",
                value=f"```{init_liq_text}```",
                inline=False
            )

            embed.add_field(
                name="Adding Ticker {}{}".format(coin_emoji_1, tickers[0]),
                value="```Amount: .. {}```".format(tickers[0]),
                inline=False
            )
            embed.add_field(
                name="Adding Ticker {}{}".format(coin_emoji_2, tickers[1]),
                value="```Amount: .. {}```".format(tickers[1]),
                inline=False
            )

            await ctx.edit_original_message(
                content=None,
                embed=embed,
                view=add_liquidity_btn(ctx, self.bot, str(ctx.author.id), pool_name, accepted=False,
                amount_1=None, amount_2=None)
            )

            # ticker = pool_name.split("/")
            # await ctx.response.send_modal(
            #         modal=add_liqudity(ctx, self.bot, ticker[0], ticker[1], ctx.author.id))
            # await ctx.response.defer()
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @cexswap_addliquidity.autocomplete("pool_name")
    async def cexswap_addliquidity_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.cexswap_pairs if string in name.lower()][:12]

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
            # TODO: logchan
            return

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/cexswap removepools", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            pool_name = pool_name.upper()
            tickers = pool_name.split("/")

            liq_pair = await cexswap_get_pool_details(tickers[0], tickers[1], None)
            if liq_pair is None:
                msg = f"{EMOJI_ERROR}, {ctx.author.mention}, there is no liqudity for that pool `{pool_name}`. "
                await ctx.edit_original_message(content=msg)
                return
            else:
                # TODO: logchan
                if len(liq_pair['pool_share']) > 0:
                    liq_users = []
                    notifying_u = []
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
                                msg_sending = f"Admin removed pool `{pool_name}`. You pool shared return to your balance:"\
                                    f"```{balance_user[str(liq_u)]}```"
                                await member.send(msg_sending)
                                num_notifying += 1
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    msg += "And notified {} user(s).".format(num_notifying)
                    await ctx.edit_original_message(content=msg)
                else:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, internal error."
                    await ctx.edit_original_message(content=msg)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @cexswap_removepools.autocomplete("pool_name")
    async def cexswap_removepools_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.cexswap_pairs if string in name.lower()][:12]

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

        percentage = int(percentage.replace("%", ""))
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/cexswap removeliquidity", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        pool_name = pool_name.upper()
        tickers = pool_name.split("/")
        get_poolshare = await cexswap_get_poolshare(str(ctx.author.id), SERVER_BOT)
        if len(get_poolshare) == 0:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, sorry! You don't have any liquidity in any pools."
            await ctx.edit_original_message(content=msg)
        else:
            try:
                liq_pair = await cexswap_get_pool_details(tickers[0], tickers[1], str(ctx.author.id))
                if liq_pair is None:
                    msg = f"{EMOJI_ERROR}, {ctx.author.mention}, there is no liqudity for that pool `{pool_name}`. "
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
                    # if you own all pair and amout remove is all.
                    if truncate(float(amount_remove_1), 12) == \
                        truncate(float(liq_pair['pool']['amount_ticker_1']), 12):
                        delete_pool = True
                    removing = await cexswap_remove_pool_share(
                        liq_pair['pool']['pool_id'], amount_remove_1, ticker_1, amount_remove_2, ticker_2,
                        str(ctx.author.id), SERVER_BOT, complete_remove, delete_pool
                    )
                    coin_decimal_1 = getattr(getattr(self.bot.coin_list, ticker_1), "decimal")
                    coin_decimal_2 = getattr(getattr(self.bot.coin_list, ticker_2), "decimal")
                    amount_1_str = num_format_coin(amount_remove_1, ticker_1, coin_decimal_1, False)
                    amount_2_str = num_format_coin(amount_remove_2, ticker_2, coin_decimal_2, False)
                    if removing is True:
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, successfully remove liqudity:" \
                            f"```{amount_1_str} {ticker_1}\n{amount_2_str} {ticker_2}```"
                        await ctx.edit_original_message(content=msg)
                    else:
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, internal error."
                        await ctx.edit_original_message(content=msg)
            except Exception:
                traceback.print_exc(file=sys.stdout)

    @cexswap_removeliquidity.autocomplete("pool_name")
    async def cexswap_removeliquidity_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.cexswap_pairs if string in name.lower()][:12]

    @cexswap.sub_command(
        name="earning",
        usage="cexswap earning",
        description="Show some earning from cexswap."
    )
    async def cexswap_earning(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /cexswap loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/cexswap earning", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            get_user_earning = await cexswap_earning(str(ctx.author.id))
            if len(get_user_earning) == 0:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you don't have any earning from LP yet."
                await ctx.edit_original_message(content=msg)
                return
            else:
                testing = self.bot.config['cexswap']['testing_msg']
                embed = disnake.Embed(
                    title="Your LP earning from TipBot's CEXSwap",
                    description=f"{ctx.author.mention}, {testing}List of distributed earning from Liquidity Pools.",
                    timestamp=datetime.now(),
                )
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

                embed.add_field(
                    name="Earning from {} coin(s)".format(len(get_user_earning)),
                    value="{}".format("\n".join(list_earning)),
                    inline=False
                )
                await ctx.edit_original_message(content=None, embed=embed)
        except Exception:
            traceback.print_exc(file=sys.stdout)


    @commands.Cog.listener()
    async def on_ready(self):
        await self.cexswap_get_list_enable_pairs()

    async def cog_load(self):
        await self.cexswap_get_list_enable_pairs()

    def cog_unload(self):
        pass

def setup(bot):
    bot.add_cog(Cexswap(bot))
