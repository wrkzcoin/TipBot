# For eval
import contextlib
import functools
import io
import json
import random
import sys
import time
import traceback
from datetime import datetime
from decimal import Decimal
from io import BytesIO
import os
from bip_utils import Bip39SeedGenerator, Bip44Coins, Bip44
import uuid
import threading

import aiohttp
import aiomysql
import disnake
from disnake.app_commands import Option
from disnake.enums import OptionType

import store
from Bot import SERVER_BOT, logchanbot, encrypt_string, decrypt_string, \
    RowButtonRowCloseAnyMessage, EMOJI_INFORMATION, EMOJI_RED_NO, truncate
from aiomysql.cursors import DictCursor
from attrdict import AttrDict
from cogs.wallet import WalletAPI
from disnake.ext import commands, tasks
from eth_account import Account
from httpx import AsyncClient, Timeout, Limits
from mnemonic import Mnemonic
from pywallet import wallet as ethwallet
from tronpy import AsyncTron
from tronpy.providers.async_http import AsyncHTTPProvider

from mnemonic import Mnemonic
from pytezos.crypto.key import Key as XtzKey

from thor_requests.wallet import Wallet as thor_wallet

import json
import near_api

from cogs.utils import MenuPage
from cogs.utils import Utils, num_format_coin
from cogs.wallet import sql_check_minimum_deposit_erc20

Account.enable_unaudited_hdwallet_features()


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.local_db_extra = None
        self.pool_local_db_extra = None
        self.old_message_data_age = 60 * 24 * 3600  # max. 2 month

    async def openConnection_extra(self):
        if self.local_db_extra is None:
            await self.get_local_db_extra_auth()
        if self.local_db_extra is not None:
            try:
                if self.pool_local_db_extra is None:
                    self.pool_local_db_extra = await aiomysql.create_pool(
                        host=self.local_db_extra['dbhost'], port=3306,
                        minsize=1, maxsize=2,
                        user=self.local_db_extra['dbuser'],
                        password=self.local_db_extra['dbpass'],
                        db=self.local_db_extra['dbname'],
                        cursorclass=DictCursor, autocommit=True
                    )
            except Exception:
                traceback.print_exc(file=sys.stdout)

    async def get_local_db_extra_auth(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `bot_settings` WHERE `name`=%s LIMIT 1
                    """
                    await cur.execute(sql, ('local_db_extra'))
                    result = await cur.fetchone()
                    if result:
                        self.local_db_extra = json.loads(decrypt_string(result['value']))
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("admin " +str(traceback.format_exc()))
        return None

    async def purge_msg(self, number_msg: int = 1000):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_messages` ORDER BY `id` ASC LIMIT %s
                    """
                    await cur.execute(sql, number_msg)
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        # Insert to extra DB and delete
                        data_rows = []
                        delete_ids = []
                        for each in result:
                            if each['message_time'] < int(time.time()) - self.old_message_data_age:
                                data_rows.append((
                                    each['id'], each['serverid'], each['server_name'], each['channel_id'],
                                    each['channel_name'], each['user_id'], each['message_author'],
                                    each['message_id'], each['message_time']
                                ))
                                delete_ids.append(each['id'])
                        if len(data_rows) > 50:
                            await self.openConnection_extra()
                            async with self.pool_local_db_extra.acquire() as conn_extra:
                                async with conn_extra.cursor() as cur_extra:
                                    sql = """
                                    INSERT INTO `discord_messages` (`id`, `serverid`, `server_name`, `channel_id`, 
                                    `channel_name`, `user_id`, `message_author`, `message_id`, `message_time`) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) 
                                    ON DUPLICATE KEY UPDATE 
                                    `message_time`=VALUES(`message_time`)
                                    """
                                    await cur_extra.executemany(sql, data_rows)
                                    await conn_extra.commit()
                                    inserted = cur_extra.rowcount
                                    if inserted > 0:
                                        # Delete from message
                                        await store.openConnection()
                                        async with store.pool.acquire() as conn:
                                            async with conn.cursor() as cur:
                                                sql = " DELETE FROM `discord_messages` WHERE `id` IN (%s)" % ",".join(
                                                    ["%s"] * len(delete_ids))
                                                await cur.execute(sql, tuple(delete_ids))
                                                await conn.commit()
                                                deleted = cur.rowcount
                                                return deleted
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("admin " +str(traceback.format_exc()))
        return 0

    async def get_coin_list_name(self, including_disable: bool = False):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    coin_list_name = []
                    sql = """
                    SELECT `coin_name` FROM `coin_settings` WHERE `enable`=1
                    """
                    if including_disable is True:
                        sql = """
                        SELECT `coin_name` FROM `coin_settings`
                        """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each in result:
                            coin_list_name.append(each['coin_name'])
                        return coin_list_name
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("admin " +str(traceback.format_exc()))
        return None

    async def user_balance_multi(
        self, user_id: str, user_server: str, coinlist: list
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    user_balance_coin = {}
                    sql = """
                    SELECT (`balance`-`withdrew`+`deposited`) AS balance, `token_name` 
                    FROM `user_balance_mv_data` 
                    WHERE `user_id`=%s AND `user_server`=%s
                    """
                    await cur.execute(sql, (user_id, user_server))
                    result_balance = await cur.fetchall()
                    if result_balance:
                        for i in result_balance:
                            if i['token_name'] not in user_balance_coin:
                                user_balance_coin[i['token_name']] = i['balance']

                        sql = """
                        SELECT SUM(`real_amount`) AS airdrop , `token_name`
                        FROM `discord_airdrop_tmp` 
                        WHERE `from_userid`=%s AND `status`=%s
                        GROUP BY `token_name`
                        """
                        await cur.execute(sql, (user_id, "ONGOING"))
                        result_airdrop = await cur.fetchall()
                        if result_airdrop:
                            for i in result_airdrop:
                                if i['token_name'] not in user_balance_coin:
                                    user_balance_coin[i['token_name']] = 0
                                user_balance_coin[i['token_name']] -= Decimal(i['airdrop'])

                        sql = """
                        SELECT SUM(`real_amount`) AS math, `token_name`
                        FROM `discord_mathtip_tmp` 
                        WHERE `from_userid`=%s AND `status`=%s
                        GROUP BY `token_name`
                        """
                        await cur.execute(sql, (user_id, "ONGOING"))
                        result_math = await cur.fetchall()
                        if result_math:
                            for i in result_math:
                                if i['token_name'] not in user_balance_coin:
                                    user_balance_coin[i['token_name']] = 0
                                user_balance_coin[i['token_name']] -= Decimal(i['math'])

                        sql = """
                        SELECT SUM(`real_amount`) AS trivia, `token_name`
                        FROM `discord_triviatip_tmp` 
                        WHERE `from_userid`=%s AND `status`=%s
                        GROUP BY `token_name`
                        """
                        await cur.execute(sql, (user_id, "ONGOING"))
                        result_trivia = await cur.fetchall()
                        if result_trivia:
                            for i in result_trivia:
                                if i['token_name'] not in user_balance_coin:
                                    user_balance_coin[i['token_name']] = 0
                                user_balance_coin[i['token_name']] -= Decimal(i['trivia'])

                        sql = """
                        SELECT SUM(`amount_sell`) AS trade, `coin_sell`
                        FROM `open_order` 
                        WHERE `userid_sell`=%s AND `status`=%s
                        GROUP BY `coin_sell`
                        """
                        await cur.execute(sql, (user_id, "OPEN"))
                        result_trade = await cur.fetchall()
                        if result_trade:
                            for i in result_trade:
                                if i['coin_sell'] not in user_balance_coin:
                                    user_balance_coin[i['coin_sell']] = 0
                                user_balance_coin[i['coin_sell']] -= Decimal(i['trade'])

                        sql = """
                        SELECT SUM(`amount`) AS raffle, `coin_name`
                        FROM `guild_raffle_entries` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `status`=%s
                        GROUP BY `coin_name`
                        """
                        await cur.execute(sql, (user_id, user_server, "REGISTERED"))
                        result_raffle = await cur.fetchall()
                        if result_raffle:
                            for i in result_raffle:
                                if i['coin_name'] not in user_balance_coin:
                                    user_balance_coin[i['coin_name']] = 0
                                user_balance_coin[i['coin_name']] -= Decimal(i['raffle'])

                        sql = """
                        SELECT SUM(`init_amount`) AS party_init, `token_name`
                        FROM `discord_partydrop_tmp` 
                        WHERE `from_userid`=%s  AND `status`=%s
                        GROUP BY `token_name`
                        """
                        await cur.execute(sql, (user_id, "ONGOING"))
                        result_party_init = await cur.fetchall()
                        if result_party_init:
                            for i in result_party_init:
                                if i['token_name'] not in user_balance_coin:
                                    user_balance_coin[i['token_name']] = 0
                                user_balance_coin[i['token_name']] -= Decimal(i['party_init'])

                        sql = """
                        SELECT SUM(`joined_amount`) AS party_join, `token_name`
                        FROM `discord_partydrop_join` 
                        WHERE `attendant_id`=%s AND `status`=%s
                        GROUP BY `token_name`
                        """
                        await cur.execute(sql, (user_id, "ONGOING"))
                        result_party_join = await cur.fetchall()
                        if result_party_join:
                            for i in result_party_join:
                                if i['token_name'] not in user_balance_coin:
                                    user_balance_coin[i['token_name']] = 0
                                user_balance_coin[i['token_name']] -= Decimal(i['party_join'])

                        sql = """
                        SELECT SUM(`real_amount`) AS quick, `token_name`
                        FROM `discord_quickdrop` 
                        WHERE `from_userid`=%s AND `status`=%s
                        GROUP BY `token_name`
                        """
                        await cur.execute(sql, (user_id, "ONGOING"))
                        result_quick = await cur.fetchall()
                        if result_quick:
                            for i in result_quick:
                                if i['token_name'] not in user_balance_coin:
                                    user_balance_coin[i['token_name']] = 0
                                user_balance_coin[i['token_name']] -= Decimal(i['quick'])

                        sql = """
                        SELECT SUM(`real_amount`) AS talk, `token_name`
                        FROM `discord_talkdrop_tmp` 
                        WHERE `from_userid`=%s AND `status`=%s
                        GROUP BY `token_name`
                        """
                        await cur.execute(sql, (user_id, "ONGOING"))
                        result_talk = await cur.fetchall()
                        if result_talk:
                            for i in result_talk:
                                if i['token_name'] not in user_balance_coin:
                                    user_balance_coin[i['token_name']] = 0
                                user_balance_coin[i['token_name']] -= Decimal(i['talk'])
                    for i in coinlist:
                        if i not in user_balance_coin.keys():
                            user_balance_coin[i] = 0
                    return user_balance_coin
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("admin " +str(traceback.format_exc()))
        return None

    async def user_balance(
        self, user_id: str, coin: str, address: str, coin_family: str, top_block: int,
        confirmed_depth: int = 0, user_server: str = 'DISCORD'
    ):
        # address: TRTL/BCN/XMR = paymentId
        token_name = coin.upper()
        user_server = user_server.upper()
        if confirmed_depth == 0 or top_block is None:
            # If we can not get top block, confirm after 20mn. This is second not number of block
            nos_block = 20 * 60
        else:
            nos_block = top_block - confirmed_depth
        confirmed_inserted = 30  # 30s for nano
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # moving tip + / -
                    sql = """
                            SELECT 
                            (SELECT IFNULL((SELECT (`balance`-`withdrew`+`deposited`)  
                            FROM `user_balance_mv_data` 
                            WHERE `user_id`=%s AND `token_name`=%s AND `user_server`=%s LIMIT 1), 0))

                            - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                            FROM `discord_airdrop_tmp` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                            FROM `discord_mathtip_tmp` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                            FROM `discord_triviatip_tmp` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`amount_sell`)  
                            FROM `open_order` 
                            WHERE `coin_sell`=%s AND `userid_sell`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`amount`)  
                            FROM `guild_raffle_entries` 
                            WHERE `coin_name`=%s AND `user_id`=%s AND `user_server`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`init_amount`)  
                            FROM `discord_partydrop_tmp` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`joined_amount`)  
                            FROM `discord_partydrop_join` 
                            WHERE `attendant_id`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                            FROM `discord_quickdrop` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                            FROM `discord_talkdrop_tmp` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))
                          """
                    query_param = [user_id, token_name, user_server,
                                   user_id, token_name, "ONGOING",
                                   user_id, token_name, "ONGOING",
                                   user_id, token_name, "ONGOING",
                                   token_name, user_id, "OPEN",
                                   token_name, user_id, user_server, "REGISTERED",
                                   user_id, token_name, "ONGOING",
                                   user_id, token_name, "ONGOING",
                                   user_id, token_name, "ONGOING",
                                   user_id, token_name, "ONGOING"]
                    sql += """ AS mv_balance"""
                    await cur.execute(sql, tuple(query_param))
                    result = await cur.fetchone()
                    if result:
                        mv_balance = result['mv_balance']
                    else:
                        mv_balance = 0
                balance = {}
                try:
                    balance['adjust'] = 0
                    balance['mv_balance'] = float("%.12f" % mv_balance) if mv_balance else 0
                    balance['adjust'] = float("%.12f" % balance['mv_balance'])
                except Exception:
                    print("issue user_balance coin name: {}".format(token_name))
                    traceback.print_exc(file=sys.stdout)
                # Negative check
                try:
                    if balance['adjust'] < 0:
                        msg_negative = 'Negative balance detected:\nServer:' + user_server + '\nUser: ' + user_id + '\nToken: ' + token_name + '\nBalance: ' + str(
                            balance['adjust'])
                        await logchanbot(msg_negative)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                return balance
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("admin " +str(traceback.format_exc()))

    async def audit_update_poolshare(self, diff_1, diff_2, pool_id):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    UPDATE `cexswap_pools`
                    SET `amount_ticker_1`=`amount_ticker_1`+%s, `amount_ticker_2`=`amount_ticker_2`+%s
                    WHERE `pool_id`=%s LIMIT 1; 
                    """
                    await cur.execute(sql, (diff_1, diff_2, pool_id))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def audit_lp_share(self):
        pool_and_share = {"share": [], "pools": []}
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT SUM(`amount_ticker_1`) as amount_ticker_1, 
                    SUM(`amount_ticker_2`) AS amount_ticker_2, `ticker_1_name`, `ticker_2_name`, `pairs`
                    FROM `cexswap_pools_share`
                    GROUP BY  `ticker_1_name`, `ticker_2_name`
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        pool_and_share['shares'] = result
                    sql = """
                    SELECT *
                    FROM `cexswap_pools`
                    WHERE `enable`=1
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        pool_and_share['pools'] = result

                    sql = """
                    SELECT *
                    FROM `a_cexswap_pools`
                    WHERE `enable`=1
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        pool_and_share['a_pools'] = result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return pool_and_share

    async def audit_lp_db(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    pool = {}
                    # cexswap_pools
                    sql = """
                    SELECT SUM(`amount_ticker_1`) as amount_ticker_1, 
                    SUM(`amount_ticker_2`) AS amount_ticker_2, `ticker_1_name`, `ticker_2_name`
                    FROM `cexswap_pools`
                    GROUP BY `ticker_1_name`, `ticker_2_name`
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        pool['cexswap_pools'] = result

                    # cexswap_pools_share
                    sql = """
                    SELECT SUM(`amount_ticker_1`) as amount_ticker_1, 
                    SUM(`amount_ticker_2`) AS amount_ticker_2, `ticker_1_name`, `ticker_2_name`, `pairs`
                    FROM `cexswap_pools_share`
                    GROUP BY  `ticker_1_name`, `ticker_2_name`
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        pool['cexswap_pools_share'] = result

                    # cexswap_add_remove_logs
                    sql = """
                    SELECT SUM(`amount`) AS amount, `token_name`, `action`
                    FROM `cexswap_add_remove_logs`
                    GROUP BY `token_name`, `action`;
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        pool['cexswap_add_remove_logs'] = result

                    # cexswap_sell_logs
                    sql = """
                    SELECT SUM(`got_total_amount`) AS amount, `got_ticker`
                    FROM `cexswap_sell_logs`
                    GROUP BY `got_ticker`;
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        pool['cexswap_sell_logs'] = result

                    # cexswap_distributing_fee
                    sql = """
                    SELECT SUM(`distributed_amount`) AS amount, `got_ticker`
                    FROM `cexswap_distributing_fee`
                    GROUP BY `got_ticker`;
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        pool['cexswap_distributing_fee'] = result

                    # user_balance_mv cexswaplp
                    sql = """
                    SELECT SUM(`real_amount`) AS amount, `token_name`
                    FROM `user_balance_mv`
                    WHERE `type`=%s AND `from_userid`=%s
                    GROUP BY `token_name`;
                    """
                    await cur.execute(sql, ("CEXSWAPLP", "SYSTEM"))
                    result = await cur.fetchall()
                    if result:
                        pool['cexswaplp'] = result
                    return pool
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("admin " +str(traceback.format_exc()))
        return None

    async def cog_check(self, ctx):
        return commands.is_owner()

    async def get_coin_setting(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    coin_list = {}
                    sql = """
                    SELECT * FROM `coin_settings` WHERE `enable`=1
                    """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each in result:
                            coin_list[each['coin_name']] = each
                        return AttrDict(coin_list)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("admin " +str(traceback.format_exc()))
        return None

    async def sql_get_all_userid_by_coin(self, coin: str):
        coin_name = coin.upper()
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    if type_coin.upper() == "CHIA":
                        sql = """
                        SELECT * FROM `xch_user` 
                        WHERE `coin_name`=%s
                        """
                        await cur.execute(sql, (coin_name))
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql = """
                        SELECT * FROM `cn_user_paymentid` 
                        WHERE `coin_name`=%s
                        """
                        await cur.execute(sql, (coin_name))
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "BTC":
                        sql = """
                        SELECT * FROM `doge_user` 
                        WHERE `coin_name`=%s
                        """
                        await cur.execute(sql, (coin_name))
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "NANO":
                        sql = """
                        SELECT * FROM `nano_user` 
                        WHERE `coin_name`=%s
                        """
                        await cur.execute(sql, (coin_name))
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "ERC-20":
                        sql = """
                        SELECT * FROM `erc20_user`
                        """
                        await cur.execute(sql, )
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "TRC-20":
                        sql = """
                        SELECT * FROM `trc20_user`
                        """
                        await cur.execute(sql, )
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "HNT":
                        sql = """
                        SELECT * FROM `hnt_user` 
                        WHERE `coin_name`=%s
                        """
                        await cur.execute(sql, (coin_name))
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "ADA":
                        sql = """
                        SELECT * FROM `ada_user`
                        """
                        await cur.execute(sql, )
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "XLM":
                        sql = """
                        SELECT * FROM `xlm_user`
                        """
                        await cur.execute(sql, )
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "XRP":
                        sql = """ SELECT * FROM `xrp_user` """
                        await cur.execute(sql, )
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "COSMOS":
                        sql = """
                        SELECT * FROM `cosmos_user`
                        GROUP by `user_id`
                        """
                        await cur.execute(sql, )
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "VITE":
                        sql = """
                        SELECT * FROM `vite_user`
                        GROUP by `user_id`
                        """
                        await cur.execute(sql, )
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "XTZ":
                        sql = """
                        SELECT * FROM `tezos_user`
                        GROUP by `user_id`
                        """
                        await cur.execute(sql, )
                        result = await cur.fetchall()
                        if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("admin " +str(traceback.format_exc()))
        return []

    async def enable_disable_coin(self, coin: str, what: str, toggle: int):
        coin_name = coin.upper()
        what = what.lower()
        if what not in ["withdraw", "deposit", "tip", "partydrop", "quickdrop", "talkdrop", "enable"]:
            return 0
        if what == "withdraw":
            what = "enable_withdraw"
        elif what == "deposit":
            what = "enable_deposit"
        elif what == "tip":
            what = "enable_tip"
        elif what == "partydrop":
            what = "enable_partydrop"
        elif what == "quickdrop":
            what = "enable_quickdrop"
        elif what == "talkdrop":
            what = "enable_talkdrop"
        elif what == "enable":
            what = "enable"
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE coin_settings SET `""" + what + """`=%s 
                    WHERE `coin_name`=%s AND `""" + what + """`<>%s LIMIT 1 """
                    await cur.execute(sql, (toggle, coin_name, toggle))
                    await conn.commit()
                    return cur.rowcount
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def create_address_eth(self):
        def create_eth_wallet():
            seed = ethwallet.generate_mnemonic()
            w = ethwallet.create_wallet(network="ETH", seed=seed, children=1)
            return w

        wallet_eth = functools.partial(create_eth_wallet)
        create_wallet = await self.bot.loop.run_in_executor(None, wallet_eth)
        return create_wallet

    async def create_address_trx(self):
        try:
            _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                       timeout=Timeout(timeout=10, connect=5, read=5))
            TronClient = AsyncTron(provider=AsyncHTTPProvider(self.bot.erc_node_list['TRX'], client=_http_client))
            create_wallet = TronClient.generate_address()
            await TronClient.close()
            return create_wallet
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.guild_only()
    @commands.slash_command(
        usage='say',
        options=[
            Option('text', 'text', OptionType.string, required=True)
        ],
        description="Let bot say something in text channel (Owner only)"
    )
    async def say(
        self,
        ctx,
        text: str
    ):
        try:
            if ctx.author.id != self.bot.config['discord']['owner']:
                await ctx.response.send_message(f"You have no permission!", ephemeral=True)
            else:
                # let bot post some message (testing) etc.
                await logchanbot(f"[TIPBOT SAY] {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator} asked to say:\n{text}")
                await ctx.channel.send("{} asked:\{}".format(ctx.author.mention, text))
                await ctx.response.send_message(f"Message sent!", ephemeral=True)
        except disnake.errors.Forbidden:
            await ctx.response.send_message(f"I have no permission to send text!", ephemeral=True)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @commands.dm_only()
    @commands.group(
        usage="admin <subcommand>",
        hidden=True,
        description="Various admin commands."
    )
    async def admin(self, ctx):
        if ctx.invoked_subcommand is None: await ctx.reply(f"{ctx.author.mention}, invalid admin command")
        if ctx.author.id != self.bot.config['discord']['owner_id']:
            await ctx.reply(f"{ctx.author.mention}, permission denied!")
        return

    @commands.is_owner()
    @admin.command(hidden=True, usage='admin dumpthread', description="Dump all threads")
    async def dumpthread(self, ctx):
        try:
            all_threads = threading.enumerate()
            thread_list = []
            for i in all_threads:
                thread_list.append(str(i))
            joi_thread_list = "\n".join(thread_list)
            data_file = disnake.File(BytesIO(joi_thread_list.encode()),
                                    filename=f"list_thread_{str(int(time.time()))}.txt")
            await ctx.reply(file=data_file)
            return
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(hidden=True, usage='admin enableuser <user id> <user_server>', description="Disable a user from using command.")
    async def enableuser(self, ctx, user_id: str, user_server: str="DISCORD"):
        try:
            if user_server.upper() not in ["DISCORD", "TELEGRAM"]:
                msg = f"{ctx.author.mention}, invalid user_server `{user_server}`."
                await ctx.reply(msg)
                return

            if user_server.upper() == "DISCORD":
                member = self.bot.get_user(int(user_id))
                if member is None:
                    msg = f"{ctx.author.mention}, can't find user with ID `{user_id}@{user_server}`."
                    await ctx.reply(msg)
                    return

            # Check in table
            get_member = await self.utils.async_get_cache_kv(
                "user_disable",
                f"{user_id}_{user_server}"
            )
            if get_member is not None:
                # exist, then remove
                self.utils.del_cache_kv(
                    "user_disable",
                    f"{user_id}_{user_server}"
                )
                msg = f"{ctx.author.mention}, ✅ user `{user_id}@{user_server}` removed from lock!"
                await ctx.reply(msg)
                return
            else:
                msg = f"{ctx.author.mention}, 🔴 user `{user_id}@{user_server}` is not locked."
                await ctx.reply(msg)
                return

        except ValueError:
            msg = f"{ctx.author.mention}, invalid given user ID."
            await ctx.reply(msg)
            return
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="admin disableuser <user id> <user_server> <reasons>",
        description="Disable a user from using command."
    )
    async def disableuser(
        self, ctx, user_id: str, user_server: str="DISCORD", *, reasons: str=None
    ):
        try:
            if reasons is None:
                msg = f"{ctx.author.mention}, please have reasons!"
                await ctx.reply(msg)
                return
            if user_server.upper() not in ["DISCORD", "TELEGRAM"]:
                msg = f"{ctx.author.mention}, invalid user_server `{user_server}`."
                await ctx.reply(msg)
                return

            if user_server.upper() == "DISCORD":
                member = self.bot.get_user(int(user_id))
                if member is None:
                    msg = f"{ctx.author.mention}, can't find user with ID `{user_id}@{user_server}`."
                    await ctx.reply(msg)
                    return

            # Check in table
            get_member = await self.utils.async_get_cache_kv(
                "user_disable",
                f"{user_id}_{user_server}"
            )
            if get_member is not None:
                # exist, then tell.
                reason = get_member['reason']
                locked_time = get_member['time']
                msg = f"{ctx.author.mention}, ✅ user `{user_id}@{user_server}` already locked on <t:{locked_time}:f> reasons ```{reason}```"
                await ctx.reply(msg)
                return
            else:
                await self.utils.async_set_cache_kv(
                    "user_disable",
                    f"{user_id}_{user_server}",
                    {'time': int(time.time()), 'reason': reasons if reasons else "N/A"}
                )
                msg = f"{ctx.author.mention}, ✅ successfully locked `{user_id}@{user_server}` with reasons ```{reasons if reasons else 'N/A'}```"
                await ctx.reply(msg)
                return

        except ValueError:
            msg = f"{ctx.author.mention}, invalid given user ID."
            await ctx.reply(msg)
            return
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="admin updatebalance <coin>",
        description="Force update a balance of a coin/token"
    )
    async def updatebalance(self, ctx, coin: str):
        coin_name = coin.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
            await ctx.reply(msg)
            return
        else:
            msg = await ctx.reply(f"{ctx.author.mention}, loading check for **{coin_name}**..")
            try:
                real_min_deposit = getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit")
                real_deposit_fee = getattr(getattr(self.bot.coin_list, coin_name), "real_deposit_fee")
                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                min_move_deposit = getattr(getattr(self.bot.coin_list, coin_name), "min_move_deposit")
                min_gas_tx = getattr(getattr(self.bot.coin_list, coin_name), "min_gas_tx")
                gas_ticker = getattr(getattr(self.bot.coin_list, coin_name), "gas_ticker")
                move_gas_amount = getattr(getattr(self.bot.coin_list, coin_name), "move_gas_amount")
                erc20_approve_spend = getattr(getattr(self.bot.coin_list, coin_name), "erc20_approve_spend")
                chain_id = getattr(getattr(self.bot.coin_list, coin_name), "chain_id")
                start_time = time.time()
                if type_coin == "ERC-20":
                    check_min_deposit = functools.partial(
                        sql_check_minimum_deposit_erc20,
                        self.bot.erc_node_list[net_name],
                        net_name, coin_name,
                        contract, coin_decimal,
                        min_move_deposit, min_gas_tx,
                        gas_ticker, move_gas_amount,
                        chain_id, real_deposit_fee,
                        erc20_approve_spend, 7200
                    )
                    await self.bot.loop.run_in_executor(None, check_min_deposit)
                    await ctx.reply("{}, processing {} update. Time token {}s".format(ctx.author.mention, coin_name, time.time()-start_time))
                else:
                    await ctx.reply("{}, not support yet for this method for {}.".format(ctx.author.mention, coin_name))
                await msg.delete()
            except Exception:
                traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="admin status <text>",
        description="set bot\'s status."
    )
    async def status(self, ctx, *, msg: str):
        await self.bot.wait_until_ready()
        game = disnake.Game(name=msg)
        await self.bot.change_presence(status=disnake.Status.online, activity=game)
        msg = f"{ctx.author.mention}, changed status to: {msg}"
        await ctx.reply(msg)
        return

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="admin ada <action> [param]",
        description="ADA\'s action"
    )
    async def ada(self, ctx, action: str, param: str = None):
        action = action.upper()
        if action == "CREATE":
            async def call_ada_wallet(url: str, wallet_name: str, seeds: str, number: int, timeout=60):
                try:
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    data_json = {"mnemonic_sentence": seeds, "passphrase": self.bot.config['ada']['default_passphrase'],
                                 "name": wallet_name, "address_pool_gap": number}
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, headers=headers, json=data_json, timeout=timeout) as response:
                            if response.status == 200 or response.status == 201:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                return decoded_data
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                return None

            if param is None:
                msg = f"{ctx.author.mention}, this action requires <param> (number)!"
                await ctx.reply(msg)
                return
            else:
                try:
                    wallet_name = param.split(".")[0]
                    number = int(param.split(".")[1])
                    # Check if wallet_name exist
                    try:
                        await store.openConnection()
                        async with store.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ SELECT * FROM `ada_wallets` WHERE `wallet_name`=%s LIMIT 1 """
                                await cur.execute(sql, (wallet_name))
                                result = await cur.fetchone()
                                if result:
                                    msg = f"{ctx.author.mention}, wallet `{wallet_name}` already exist!"
                                    await ctx.reply(msg)
                                    return
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        return

                    # param "wallet_name.number"
                    mnemo = Mnemonic("english")
                    words = str(mnemo.generate(strength=256))
                    seeds = words.split()
                    create = await call_ada_wallet(self.bot.config['ada']['default_wallet_url'] + "v2/wallets", wallet_name, seeds,
                                                   number, 300)
                    if create:
                        try:
                            await store.openConnection()
                            async with store.pool.acquire() as conn:
                                async with conn.cursor() as cur:
                                    wallet_d = create['id']
                                    sql = """ INSERT INTO `ada_wallets` (`wallet_rpc`, `passphrase`, `wallet_name`, `wallet_id`, `seed`) 
                                    VALUES (%s, %s, %s, %s, %s) """
                                    await cur.execute(sql, (
                                        self.bot.config['ada']['default_wallet_url'], encrypt_string(self.bot.config['ada']['default_passphrase']),
                                        wallet_name, wallet_d, encrypt_string(words)))
                                    await conn.commit()
                                    msg = f"{ctx.author.mention}, wallet `{wallet_name}` created with number `{number}` and wallet ID: `{wallet_d}`."
                                    await ctx.reply(msg)
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    msg = f"{ctx.author.mention}, invalid <param> (wallet_name.number)!"
                    await ctx.reply(msg)
                    return
        elif action == "MOVE" or action == "MV":  # no param, move from all deposit balance to withdraw
            async def fetch_wallet_status(url, timeout):
                try:
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=headers, timeout=timeout) as response:
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                return decoded_data
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                return None

            async def estimate_fee_with_asset(url: str, to_address: str, assets, amount_atomic: int, timeout: int = 90):
                # assets: list of asset
                try:
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    data_json = {"payments": [
                        {"address": to_address, "amount": {"quantity": 0, "unit": "lovelace"}, "assets": assets}],
                        "withdrawal": "self"}
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, headers=headers, json=data_json, timeout=timeout) as response:
                            if response.status == 202:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                return decoded_data
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                return None

            async def send_tx(url: str, to_address: str, ada_atomic_amount: int, assets, passphrase: str,
                              timeout: int = 90):
                try:
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    data_json = {"passphrase": decrypt_string(passphrase), "payments": [
                        {"address": to_address, "amount": {"quantity": ada_atomic_amount, "unit": "lovelace"},
                         "assets": assets}], "withdrawal": "self"}
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, headers=headers, json=data_json, timeout=timeout) as response:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            return decoded_data
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                return None

            try:
                await store.openConnection()
                async with store.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM `ada_wallets` """
                        await cur.execute(sql, )
                        result = await cur.fetchall()
                        if result and len(result) > 0:
                            withdraw_address = None
                            has_deposit = False
                            for each_w in result:
                                if each_w['wallet_name'] == "withdraw_ada" and each_w['is_for_withdraw'] == 1:
                                    addresses = each_w['addresses'].split("\n")
                                    random.shuffle(addresses)
                                    withdraw_address = addresses[0]
                            for each_w in result:
                                if each_w['is_for_withdraw'] != 1 and each_w[
                                    'used_address'] > 0 and withdraw_address is not None:
                                    # fetch wallet_id only those being used.
                                    try:
                                        fetch_wallet = await fetch_wallet_status(
                                            each_w['wallet_rpc'] + "v2/wallets/" + each_w['wallet_id'], 60)
                                        if fetch_wallet and fetch_wallet['state']['status'] == "ready":
                                            # we will move only those synced
                                            # minimum ADA: 20
                                            min_balance = 20 * 10 ** 6
                                            reserved_balance = 1 * 10 ** 6
                                            amount = fetch_wallet['balance']['available']['quantity']
                                            if amount < min_balance:
                                                continue
                                            else:
                                                assets = []
                                                if 'available' in fetch_wallet['assets'] and len(
                                                        fetch_wallet['assets']['available']) > 0:
                                                    for each_asset in fetch_wallet['assets']['available']:
                                                        # Check if they are in TipBot
                                                        for each_coin in self.bot.coin_name_list:
                                                            if getattr(getattr(self.bot.coin_list, each_coin),
                                                                       "type") == "ADA" and getattr(
                                                                getattr(self.bot.coin_list, each_coin), "header") == \
                                                                    each_asset['asset_name']:
                                                                # We have it
                                                                policy_id = getattr(
                                                                    getattr(self.bot.coin_list, each_coin), "contract")
                                                                assets.append({"policy_id": policy_id,
                                                                               "asset_name": each_asset['asset_name'],
                                                                               "quantity": each_asset['quantity']})
                                                # async def estimate_fee_with_asset(url: str, to_address: str, assets, amount_atomic: int, timeout: int=90):
                                                estimate_tx = await estimate_fee_with_asset(
                                                    each_w['wallet_rpc'] + "v2/wallets/" + each_w['wallet_id'] \
                                                        + "/payment-fees", withdraw_address, assets, amount, 10)
                                                if estimate_tx and "minimum_coins" in estimate_tx and "estimated_min" in estimate_tx:
                                                    sending_tx = await send_tx(
                                                        each_w['wallet_rpc'] + "v2/wallets/" + each_w[
                                                            'wallet_id'] + "/transactions", withdraw_address,
                                                        amount - estimate_tx['estimated_min'][
                                                            'quantity'] - reserved_balance, assets,
                                                        each_w['passphrase'], 30)
                                                    if "code" in sending_tx and "message" in sending_tx:
                                                        # send error
                                                        wallet_id = each_w['wallet_id']
                                                        msg = f"{ctx.author.mention}, error with `{wallet_id}`\n````{str(sending_tx)}``"
                                                        await ctx.reply(msg)
                                                        print(msg)
                                                    elif "status" in sending_tx and sending_tx['status'] == "pending":
                                                        has_deposit = True
                                                        # success
                                                        wallet_id = each_w['wallet_id']
                                                        tx_hash = sending_tx['id']
                                                        msg = f"{ctx.author.mention}, successfully transfer `{wallet_id}` to `{withdraw_address}` via `{tx_hash}`."
                                                        await ctx.reply(msg)
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                            if has_deposit is False:
                                msg = f"{ctx.author.mention}, there is no any wallet with balance sufficient to transfer.!"
                                await ctx.reply(msg)
                                return
                        else:
                            msg = f"{ctx.author.mention}, doesnot have any wallet in DB!"
                            await ctx.reply(msg)
                            return
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif action == "DELETE" or action == "DEL":  # param is name only
            if param is None:
                msg = f"{ctx.author.mention}, required param `wallet_name`!"
                await ctx.reply(msg)
                return

            async def call_ada_delete_wallet(url_wallet_id: str, timeout=60):
                try:
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.delete(url_wallet_id, headers=headers, timeout=timeout) as response:
                            if response.status == 204:
                                return True
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                return None

            wallet_name = param.strip()
            wallet_id = None
            # Check if wallet_name exist
            try:
                await store.openConnection()
                async with store.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM `ada_wallets` WHERE `wallet_name`=%s LIMIT 1 """
                        await cur.execute(sql, (wallet_name))
                        result = await cur.fetchone()
                        if result:
                            wallet_id = result['wallet_id']
                            delete = await call_ada_delete_wallet(
                                self.bot.config['ada']['default_wallet_url'] + "v2/wallets/" + wallet_id, 300)
                            if delete is True:
                                try:
                                    await store.openConnection()
                                    async with store.pool.acquire() as conn:
                                        async with conn.cursor() as cur:
                                            sql = """ INSERT INTO `ada_wallets_archive` 
                                                      SELECT * FROM `ada_wallets` 
                                                      WHERE `wallet_id`=%s;
                                                      DELETE FROM `ada_wallets` WHERE `wallet_id`=%s LIMIT 1 """
                                            await cur.execute(sql, (wallet_id, wallet_id))
                                            await conn.commit()
                                            msg = f"{ctx.author.mention}, sucessfully delete wallet `{wallet_name}` | `{wallet_id}`."
                                            await ctx.reply(msg)
                                            return
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            else:
                                msg = f"{ctx.author.mention}, failed to delete `{wallet_name}` | `{wallet_id}` from wallet server!"
                                await ctx.reply(msg)
                                return
                        else:
                            msg = f"{ctx.author.mention}, wallet `{wallet_name}` not exist in database!"
                            await ctx.reply(msg)
                            return
            except Exception:
                traceback.print_exc(file=sys.stdout)
                return
        elif action == "LIST":  # no params
            # List all in DB
            try:
                await store.openConnection()
                async with store.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM `ada_wallets` """
                        await cur.execute(sql, )
                        result = await cur.fetchall()
                        if result and len(result) > 0:
                            list_wallets = []
                            for each_w in result:
                                list_wallets.append(
                                    "Name: {}, ID: {}".format(each_w['wallet_name'], each_w['wallet_id']))
                            list_wallets_j = "\n".join(list_wallets)
                            data_file = disnake.File(BytesIO(list_wallets_j.encode()),
                                                     filename=f"list_ada_wallets_{str(int(time.time()))}.csv")
                            await ctx.author.send(file=data_file)
                            return
                        else:
                            msg = f"{ctx.author.mention}, nothing in DB!"
                            await ctx.reply(msg)
                            return
            except Exception:
                traceback.print_exc(file=sys.stdout)
                return
        else:
            msg = f"{ctx.author.mention}, action not exist!"
            await ctx.reply(msg)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="admin guildlist",
        description="Dump guild list, name, number of users."
    )
    async def guildlist(self, ctx):
        try:
            list_g = []
            for g in self.bot.guilds:
                list_g.append("{}, {}, {}".format(str(g.id), len(g.members), g.name))
            list_g_str = "ID, Numbers, Name\n" + "\n".join(list_g)
            data_file = disnake.File(BytesIO(list_g_str.encode()),
                                     filename=f"list_bot_guilds_{str(int(time.time()))}.csv")
            await ctx.author.send(file=data_file)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="admin clearbutton <channel id> <msg id>",
        description="Clear all buttons of a message ID."
    )
    async def clearbutton(self, ctx, channel_id: str, msg_id: str):
        try:
            _channel: disnake.TextChannel = await self.bot.fetch_channel(int(channel_id))
            _msg: disnake.Message = await _channel.fetch_message(int(msg_id))
            if _msg is not None:
                if _msg.author != self.bot.user:
                    msg = f"{ctx.author.mention}, that message `{msg_id}` was not belong to me."
                    await ctx.reply(msg)
                else:
                    await _msg.edit(view=None)
                    msg = f"{ctx.author.mention}, removed all view from `{msg_id}`."
                    await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, I can not find message `{msg_id}`."
                await ctx.reply(msg)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="admin leave <guild id>",
        description="Bot to leave a server by ID."
    )
    async def leave(self, ctx, guild_id: str):
        try:
            guild = self.bot.get_guild(int(guild_id))
            if guild is not None:
                await logchanbot(
                    f"[LEAVING] {ctx.author.name}#{ctx.author.discriminator} / {str(ctx.author.id)} commanding to leave guild `{guild.name} / {guild_id}`.")
                msg = f"{ctx.author.mention}, OK leaving guild `{guild.name} / {guild_id}`."
                await ctx.reply(msg)
                await guild.leave()
            else:
                msg = f"{ctx.author.mention}, I can not find guild id `{guild_id}`."
                await ctx.reply(msg)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="checkshare",
        description="run check pool share of CEXSwap"
    )
    async def checkshare(self, ctx):
        if ctx.author.id != self.bot.config['discord']['owner_id']:
            await logchanbot("⚠️⚠️⚠️⚠️ {}#{} / {} is trying checkshare!".format(
                ctx.author.name, ctx.author.discriminator, ctx.author.mention)
            )
            return
        try:
            pools = {}
            get_poolshares = await self.audit_lp_share()
            if len(get_poolshares['shares']) > 0 and len(get_poolshares['pools']) > 0:
                for sh in get_poolshares['shares']:
                    # sum all share of each coins
                    if sh['pairs'] not in pools:
                        pools[sh['pairs']] = {sh['ticker_1_name']: Decimal(0), sh['ticker_2_name']: Decimal(0)}
                    pools[sh['pairs']][sh['ticker_1_name']] += sh['amount_ticker_1']
                    pools[sh['pairs']][sh['ticker_2_name']] += sh['amount_ticker_2']
                # check with pool
                checked_lines = []
                response = "Updating: \n"
                updating = False
                for p in get_poolshares['pools']:
                    if p['pairs'] not in pools:
                        checked_lines.append("!{} /pool_id: {} in pools but not in share!".format(p['pairs'], p['pool_id']))
                    else:
                        diff_1 = pools[p['pairs']][p['ticker_1_name']] - p['amount_ticker_1']
                        diff_2 = pools[p['pairs']][p['ticker_2_name']] - p['amount_ticker_2']
                        if truncate(abs(diff_1), 6) != Decimal(0) or truncate(abs(diff_2), 6) != Decimal(0):
                            # check amount
                            checked_lines.append("⚆ {} /pool_id: {} has {} {}/{} {} in pool vs {} {} / {} {} in pool shares!".format(
                                p['pairs'], p['pool_id'],
                                num_format_coin(p['amount_ticker_1']), p['ticker_1_name'],
                                num_format_coin(p['amount_ticker_2']), p['ticker_2_name'],
                                num_format_coin(pools[p['pairs']][p['ticker_1_name']]), p['ticker_1_name'],
                                num_format_coin(pools[p['pairs']][p['ticker_2_name']]), p['ticker_2_name']
                            ))
                        if truncate(abs(diff_1), 6) != Decimal(0):
                            checked_lines.append("    diff ({})[share - pool] = {} {}".format(p['pairs'], num_format_coin(diff_1), p['ticker_1_name']))
                        if truncate(abs(diff_2), 6) != Decimal(0):
                            checked_lines.append("    diff ({})[share - pool] = {} {}".format(p['pairs'], num_format_coin(diff_2), p['ticker_2_name']))
                        if truncate(abs(diff_1), 6) != Decimal(0) or truncate(abs(diff_2), 6) != Decimal(0):
                            updating = await self.audit_update_poolshare(diff_1, diff_2, p['pool_id'])
                            if updating is True:
                                checked_lines.append("    Fixed amount pool: {} {} / {} {} for pool_id: {}".format(
                                    diff_1, p['ticker_1_name'], diff_2, p['ticker_2_name'], p['pool_id']))
                                break
                reply_msg = await ctx.reply(response + "```{}```".format("\n".join(checked_lines)))
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="auditshare",
        description="Audit share of CEXSwap"
    )
    async def auditshare(self, ctx):
        if ctx.author.id != self.bot.config['discord']['owner_id']:
            await logchanbot("⚠️⚠️⚠️⚠️ {}#{} / {} is trying auditshare!".format(
                ctx.author.name, ctx.author.discriminator, ctx.author.mention)
            )
            return
        try:
            pools = {}
            get_poolshares = await self.audit_lp_share()
            if len(get_poolshares['shares']) > 0 and len(get_poolshares['pools']) > 0:
                for sh in get_poolshares['shares']:
                    # sum all share of each coins
                    if sh['pairs'] not in pools:
                        pools[sh['pairs']] = {sh['ticker_1_name']: Decimal(0), sh['ticker_2_name']: Decimal(0)}
                    pools[sh['pairs']][sh['ticker_1_name']] += sh['amount_ticker_1']
                    pools[sh['pairs']][sh['ticker_2_name']] += sh['amount_ticker_2']
                # check with pool
                checked_lines = []
                for p in get_poolshares['pools']:
                    if p['pairs'] not in pools:
                        checked_lines.append("!{} /pool_id: {} in pools but not in share!".format(p['pairs'], p['pool_id']))
                    else:
                        diff_1 = pools[p['pairs']][p['ticker_1_name']] - p['amount_ticker_1']
                        diff_2 = pools[p['pairs']][p['ticker_2_name']] - p['amount_ticker_2']
                        if truncate(abs(diff_1), 6) != Decimal(0) or truncate(abs(diff_2), 6) != Decimal(0):
                            # check amount
                            checked_lines.append("⚆ {} /pool_id: {} has {} {}/{} {} in pool vs {} {} / {} {} in pool shares!".format(
                                p['pairs'], p['pool_id'],
                                num_format_coin(p['amount_ticker_1']), p['ticker_1_name'],
                                num_format_coin(p['amount_ticker_2']), p['ticker_2_name'],
                                num_format_coin(pools[p['pairs']][p['ticker_1_name']]), p['ticker_1_name'],
                                num_format_coin(pools[p['pairs']][p['ticker_2_name']]), p['ticker_2_name']
                            ))
                        if truncate(abs(diff_1), 6) != Decimal(0):
                            checked_lines.append("    diff ({})[share - pool] = {} {}".format(p['pairs'], num_format_coin(diff_1), p['ticker_1_name']))
                        if truncate(abs(diff_2), 6) != Decimal(0):
                            checked_lines.append("    diff ({})[share - pool] = {} {}".format(p['pairs'], num_format_coin(diff_2), p['ticker_2_name']))
                # a pools
                a_checked_lines = []
                for p in get_poolshares['a_pools']:
                    if p['pairs'] not in pools:
                        a_checked_lines.append("!{} /pool_id: {} in pools but not in share!".format(p['pairs'], p['pool_id']))
                    else:
                        diff_1 = pools[p['pairs']][p['ticker_1_name']] - p['amount_ticker_1']
                        diff_2 = pools[p['pairs']][p['ticker_2_name']] - p['amount_ticker_2']
                        if truncate(abs(diff_1), 6) != Decimal(0) or truncate(abs(diff_2), 6) != Decimal(0):
                            # check amount
                            a_checked_lines.append("⚆ {} /pool_id: {} has {} {}/{} {} in pool vs {} {} / {} {} in pool shares!".format(
                                p['pairs'], p['pool_id'],
                                num_format_coin(p['amount_ticker_1']), p['ticker_1_name'],
                                num_format_coin(p['amount_ticker_2']), p['ticker_2_name'],
                                num_format_coin(pools[p['pairs']][p['ticker_1_name']]), p['ticker_1_name'],
                                num_format_coin(pools[p['pairs']][p['ticker_2_name']]), p['ticker_2_name']
                            ))
                        if truncate(abs(diff_1), 6) != Decimal(0):
                            a_checked_lines.append("    diff ({})[share - pool] = {} {}".format(p['pairs'], num_format_coin(diff_1), p['ticker_1_name']))
                        if truncate(abs(diff_2), 6) != Decimal(0):
                            a_checked_lines.append("    diff ({})[share - pool] = {} {}".format(p['pairs'], num_format_coin(diff_2), p['ticker_2_name']))
                # send result
                msg = "1) Using pools:" + "\n".join(checked_lines)
                if len(msg) >= 2000:
                    data_file = disnake.File(
                        BytesIO(msg.encode()),
                        filename=f"auditshare_{str(int(time.time()))}.txt"
                    )
                    await ctx.reply(file=data_file)
                else:
                    await ctx.reply(msg)

                msg = "2) Using a_pools:" + "\n".join(a_checked_lines)
                if len(msg) >= 2000:
                    data_file = disnake.File(
                        BytesIO(msg.encode()),
                        filename=f"a_auditshare_{str(int(time.time()))}.txt"
                    )
                    await ctx.reply(file=data_file)
                else:
                    await ctx.reply(msg)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="auditlp",
        description="Audit LP of CEXSwap"
    )
    async def auditlp(self, ctx):
        if ctx.author.id != self.bot.config['discord']['owner_id']:
            await logchanbot("⚠️⚠️⚠️⚠️ {}#{} / {} is trying auditlp!".format(
                ctx.author.name, ctx.author.discriminator, ctx.author.mention)
            )
            return
        try:
            get_lp = await self.audit_lp_db()
            cexswap_pools = {}
            cexswap_pools_share = {}
            cexswap_add = {}
            cexswap_remove = {}
            cexswap_sell_logs = {}
            cexswap_distributing_fee = {}
            cexswaplp = {}
            final_amount = {}
            coin_list = []
            if get_lp is not None:
                # cexswap_pools
                if len(get_lp['cexswap_pools']) > 0:
                    for each in get_lp['cexswap_pools']:
                        if each['ticker_1_name'] not in coin_list:
                            coin_list.append(each['ticker_1_name'])
                        if each['ticker_2_name'] not in coin_list:
                            coin_list.append(each['ticker_2_name'])
                        # ticker_1
                        if each['ticker_1_name'] not in cexswap_pools:
                            cexswap_pools[each['ticker_1_name']] = each['amount_ticker_1']
                        else:
                            cexswap_pools[each['ticker_1_name']] += each['amount_ticker_1']
                        # ticker_2
                        if each['ticker_2_name'] not in cexswap_pools:
                            cexswap_pools[each['ticker_2_name']] = each['amount_ticker_2']
                        else:
                            cexswap_pools[each['ticker_2_name']] += each['amount_ticker_2']

                # cexswap_pools_share
                if len(get_lp['cexswap_pools_share']) > 0:
                    for each in get_lp['cexswap_pools_share']:
                        if each['ticker_1_name'] not in coin_list:
                            coin_list.append(each['ticker_1_name'])
                        if each['ticker_2_name'] not in coin_list:
                            coin_list.append(each['ticker_2_name'])
                        # ticker_1
                        if each['ticker_1_name'] not in cexswap_pools_share:
                            cexswap_pools_share[each['ticker_1_name']] = each['amount_ticker_1']
                        else:
                            cexswap_pools_share[each['ticker_1_name']] += each['amount_ticker_1']
                        # ticker_2
                        if each['ticker_2_name'] not in cexswap_pools_share:
                            cexswap_pools_share[each['ticker_2_name']] = each['amount_ticker_2']
                        else:
                            cexswap_pools_share[each['ticker_2_name']] += each['amount_ticker_2']

                # cexswap_add_remove_logs
                if len(get_lp['cexswap_add_remove_logs']) > 0:
                    for each in get_lp['cexswap_add_remove_logs']:
                        if each['token_name'] not in coin_list:
                            coin_list.append(each['token_name'])

                        if each['action'] == "add":
                            if each['token_name'] not in cexswap_add:
                                cexswap_add[each['token_name']] = each['amount']
                            else:
                                cexswap_add[each['token_name']] += each['amount']
                        else:
                            if each['token_name'] not in cexswap_remove:
                                cexswap_remove[each['token_name']] = each['amount']
                            else:
                                cexswap_remove[each['token_name']] += each['amount']

                # cexswap_sell_logs
                if len(get_lp['cexswap_sell_logs']) > 0:
                    for each in get_lp['cexswap_sell_logs']:
                        if each['got_ticker'] not in coin_list:
                            coin_list.append(each['got_ticker'])

                        if each['got_ticker'] not in cexswap_sell_logs:
                            cexswap_sell_logs[each['got_ticker']] = each['amount']
                        else:
                            cexswap_sell_logs[each['got_ticker']] += each['amount']

                # cexswap_distributing_fee
                if len(get_lp['cexswap_distributing_fee']) > 0:
                    for each in get_lp['cexswap_distributing_fee']:
                        if each['got_ticker'] not in coin_list:
                            coin_list.append(each['got_ticker'])

                        if each['got_ticker'] not in cexswap_distributing_fee:
                            cexswap_distributing_fee[each['got_ticker']] = each['amount']
                        else:
                            cexswap_distributing_fee[each['got_ticker']] += each['amount']
                
                # cexswaplp
                if len(get_lp['cexswaplp']) > 0:
                    for each in get_lp['cexswaplp']:
                        if each['token_name'] not in coin_list:
                            coin_list.append(each['token_name'])

                        if each['token_name'] not in cexswaplp:
                            cexswaplp[each['token_name']] = each['amount']
                        else:
                            cexswaplp[each['token_name']] += each['amount']

                # Final pool vs share
                msg = ""
                result = []
                for each in coin_list:
                    if each in cexswap_pools:
                        final_amount[each] = 0.0
                        if each in cexswap_pools:
                            final_amount[each] += float(cexswap_pools[each])
                        if each in cexswap_pools_share:
                            final_amount[each] -= float(cexswap_pools_share[each])
                        result.append("\nPOOL vs SHARE FOR {}\n   {} - {} = {} {}".format(
                            each, float(truncate(cexswap_pools[each], 4)),
                            float(truncate(cexswap_pools_share[each], 4)),
                            "✅" if truncate(final_amount[each], 8) == 0 else "🔴",
                            truncate(final_amount[each], 6)
                        ))
                msg += "\n".join(result)
                msg += "\n\n"
                result = []
                for each in coin_list:
                    add_remove = 0.0
                    pool_amount = 0.0
                    if cexswap_pools.get(each):
                        pool_amount += float(cexswap_pools.get(each))

                    if cexswap_add.get(each):
                        add_remove += float(cexswap_add.get(each))
                    if cexswap_remove.get(each):
                        add_remove -= float(cexswap_remove.get(each))
                    if cexswap_sell_logs.get(each):
                        add_remove -= float(cexswap_sell_logs.get(each))
                    if cexswap_distributing_fee.get(each):
                        add_remove -= float(cexswap_distributing_fee.get(each))
                    if cexswaplp.get(each):
                        add_remove -= float(cexswaplp.get(each))
                    if cexswap_pools.get(each) is not None:
                        result.append("DETAIL {}:\n   POOL: {}\n   -(ADD: {} - REMOVE: {} - SOLD {} - FEE {} - FEE LP {})\n   = {} ({:,.2f}{}) GOT: {} {}\n".format(
                            each, pool_amount, 
                            truncate(float(cexswap_add.get(each)), 5) if cexswap_add.get(each) else 0, 
                            truncate(float(cexswap_remove.get(each)), 5) if cexswap_remove.get(each) else 0,
                            truncate(float(cexswap_sell_logs.get(each)), 5) if cexswap_sell_logs.get(each) else 0,
                            truncate(float(cexswap_distributing_fee.get(each)), 4) if cexswap_distributing_fee.get(each) else 0,
                            truncate(float(cexswaplp.get(each)), 5) if cexswaplp.get(each) else 0,
                            truncate(add_remove, 4), add_remove/float(cexswap_pools.get(each))*100, "%",
                            truncate(float(cexswap_pools.get(each)) - add_remove, 5),
                            "✅" if truncate(float(cexswap_pools.get(each)) - add_remove, 5) >= 0 else "🔴"
                        ))
                msg += "\n".join(result)
                msg = f"```{msg}```"
                if len(msg) >= 2000:
                    data_file = disnake.File(
                        BytesIO(msg.encode()),
                        filename=f"auditLP_{str(int(time.time()))}.txt"
                    )
                    reply_msg = await ctx.reply(file=data_file)
                await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, I can not get result."
                await ctx.reply(msg)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="auditcoin <coin name>",
        description="Audit coin\'s balance"
    )
    async def auditcoin(self, ctx, coin: str):
        if ctx.author.id != self.bot.config['discord']['owner_id']:
            await logchanbot("⚠️⚠️⚠️⚠️ {}#{} / {} is trying auditcoin!".format(
                ctx.author.name, ctx.author.discriminator, ctx.author.mention)
            )
            return
        coin_name = coin.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
            await ctx.reply(msg)
            return
        else:
            list_user_balances = []
            try:
                type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                deposit_confirm_depth = 0 # including all pending
                # getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                all_user_id = await self.sql_get_all_userid_by_coin(coin_name)
                time_start = int(time.time())
                list_users = [m.id for m in self.bot.get_all_members()]
                list_guilds = [g.id for g in self.bot.guilds]
                already_checked = []
                if len(all_user_id) > 0:
                    msg = f"{ctx.author.mention}, {EMOJI_INFORMATION} **{coin_name}** there are "\
                        f"total {str(len(all_user_id))} user records. Wait a big while..."
                    await ctx.reply(msg)
                    sum_balance = 0.0
                    sum_user = 0
                    sum_unfound_balance = 0.0
                    sum_unfound_user = 0
                    negative_users = []
                    for each_user_id in all_user_id:
                        if each_user_id['user_id'] in already_checked:
                            continue
                        else:
                            already_checked.append(each_user_id['user_id'])
                        get_deposit = await self.wallet_api.sql_get_userwallet(
                            each_user_id['user_id'], coin_name, net_name, type_coin,
                            each_user_id['user_server'], 
                            each_user_id['chat_id'] if each_user_id['chat_id'] else 0
                        )
                        if get_deposit is None:
                            continue
                        wallet_address = get_deposit['balance_wallet_address']
                        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                            wallet_address = get_deposit['paymentid']
                        elif type_coin in ["XRP"]:
                            wallet_address = get_deposit['destination_tag']
                        userdata_balance = await self.user_balance(
                            each_user_id['user_id'], coin_name, wallet_address,
                            type_coin, height, deposit_confirm_depth,
                            each_user_id['user_server']
                        )
                        total_balance = userdata_balance['adjust']
                        member_name = "N/A"
                        if each_user_id['user_id'].isdigit():
                            member = self.bot.get_user(int(each_user_id['user_id']))
                            if member is not None:
                                member_name = "{}#{}".format(member.name, member.discriminator)
                        if total_balance > 0:
                            list_user_balances.append({
                                'user_id': each_user_id['user_id'],
                                'member_name': member_name,
                                'user_server': each_user_id['user_server'],
                                'balance': total_balance,
                                'coin_name': coin_name
                            })
                        elif total_balance < 0:
                            negative_users.append(each_user_id['user_id'])
                        sum_balance += total_balance
                        sum_user += 1
                        try:
                            if each_user_id['user_id'].isdigit() and each_user_id['user_server'] == SERVER_BOT and \
                                    each_user_id['is_discord_guild'] == 0:
                                if int(each_user_id['user_server']) not in list_users:
                                    sum_unfound_user += 1
                                    sum_unfound_balance += total_balance
                            elif each_user_id['user_id'].isdigit() and each_user_id['user_server'] == SERVER_BOT and \
                                    each_user_id['is_discord_guild'] == 1:
                                if int(each_user_id['user_server']) not in list_guilds:
                                    sum_unfound_user += 1
                                    sum_unfound_balance += total_balance
                        except Exception:
                            pass

                    duration = int(time.time()) - time_start
                    msg_checkcoin = f"{ctx.author.mention}, COIN **{coin_name}**\n"
                    msg_checkcoin += "```"
                    wallet_stat_str = ""
                    if type_coin == "ADA":
                        try:
                            await store.openConnection()
                            async with store.pool.acquire() as conn:
                                async with conn.cursor() as cur:
                                    sql = """ SELECT * FROM `ada_wallets` """
                                    await cur.execute(sql, )
                                    result = await cur.fetchall()
                                    if result and len(result) > 0:
                                        wallet_stat = []
                                        for each_w in result:
                                            wallet_stat.append(
                                                "name: {}, syncing: {}, height: {}, addr. used {:,.2f}{}".format(
                                                    each_w['wallet_name'], each_w['syncing'], each_w['height'],
                                                    each_w['used_address'] / each_w['address_pool_gap'] * 100, "%"
                                                )
                                            )
                                        wallet_stat_str = "\n".join(wallet_stat)
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    msg_checkcoin += wallet_stat_str + "\n"
                    msg_checkcoin += "Total record id in DB: " + str(sum_user) + "\n"
                    msg_checkcoin += "Total balance: " + num_format_coin(sum_balance) + " " + coin_name + "\n"
                    msg_checkcoin += "Total user/guild not found (discord): " + str(sum_unfound_user) + "\n"
                    msg_checkcoin += "Total balance not found (discord): " + num_format_coin(
                        sum_unfound_balance) + " " + coin_name + "\n"
                    if len(negative_users) > 0:
                        msg_checkcoin += "Negative balance: " + str(len(negative_users)) + "\n"
                        msg_checkcoin += "Negative users: " + ", ".join(negative_users)
                    msg_checkcoin += "Time token: {}s".format(duration)
                    msg_checkcoin += "```"
                    # List balance sheet
                    # list_user_balances.append("user id, server, balance, coin name")
                    # sort by balance
                    list_user_balances = sorted(list_user_balances, key=lambda d: d['balance'], reverse=True)
                    new_list = []
                    new_list.append("user id, member_name, server, balance, coin name")
                    for v in list_user_balances:
                        new_list.append("{}, {}, {}, {}".format(
                            v['user_id'], v['member_name'], v['user_server'], v['balance'], v['coin_name']
                        ))

                    balance_sheet_file = disnake.File(
                        BytesIO(("\n".join(new_list)).encode()),
                        filename=f"balance_sheet_{coin_name}_{str(int(time.time()))}.csv"
                    )
                    if len(msg_checkcoin) > 1000:
                        data_file = disnake.File(
                            BytesIO(msg_checkcoin.encode()),
                            filename=f"auditcoin_{coin_name}_{str(int(time.time()))}.txt"
                        )
                        reply_msg = await ctx.reply(file=data_file)
                        await reply_msg.reply(file=balance_sheet_file)
                    else:
                        reply_msg = await ctx.reply(msg_checkcoin)
                        await reply_msg.reply(file=balance_sheet_file)
                else:
                    msg = f"{ctx.author.mention}, {coin_name}: there is no users for this."
                    await ctx.reply(msg)
            except Exception:
                traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="printbal <user> <coin>",
        description="print user\'s balance."
    )
    async def printbal(self, ctx, member_id: str, coin: str, user_server: str = "DISCORD"):
        coin_name = coin.upper()
        if member_id.upper() == "SWAP":
            member_id = member_id.upper()
            user_server = "SYSTEM"
        else:
            user_server = user_server.upper()
        try:
            if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                coin_name = self.bot.coin_alias_names[coin_name]
            if not hasattr(self.bot.coin_list, coin_name):
                await ctx.reply(f"{ctx.author.mention}, **{coin_name}** does not exist with us.")
                return
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            deposit_confirm_depth = 0
            # deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            get_deposit = await self.wallet_api.sql_get_userwallet(
                member_id, coin_name, net_name, type_coin, user_server, 0
            )
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(
                    member_id, coin_name, net_name, type_coin, user_server, 0, 0
                )
            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
            try:
                # Add update for future call
                try:
                    await self.utils.update_user_balance_call(member_id, type_coin)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                userdata_balance = await self.user_balance(
                    member_id, coin_name, wallet_address, type_coin, height, deposit_confirm_depth, user_server
                )
                total_balance = userdata_balance['adjust']
                balance_str = "UserId: {}\n{}{} Details:\n{}".format(
                    member_id, total_balance, coin_name, json.dumps(userdata_balance)
                )
                await ctx.reply(balance_str)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="creditlist <message>",
        description="Credit a list of users"
    )
    async def creditlist(self, ctx, *, credit_msg: str=None):
        if ctx.author.id != self.bot.config['discord']['owner_id']:
            await logchanbot("⚠️⚠️⚠️⚠️ {}#{} / {} is trying creditlist!".format(
                ctx.author.name, ctx.author.discriminator, ctx.author.mention)
            )
            return
        if self.bot.config['discord']['enable_creditlist'] != 1:
            msg = f"{ctx.author.mention}, this is disable."
            await ctx.reply(msg)
            return            
        if len(ctx.message.attachments) == 0:
            msg = f"{ctx.author.mention}, missing attachment."
            await ctx.reply(msg)
            return
        else:
            # check attachment
            creditor = "SYSTEM"
            try:
                total_user_credit = 0
                async with aiohttp.ClientSession() as session:
                    async with session.get(str(ctx.message.attachments[0]), timeout=32) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            user_list = res_data.splitlines()
                            user_list_msg = {}
                            for i in user_list:
                                credit_list = i.split(",")
                                if len(credit_list) == 3 and credit_list[2].isdigit():
                                    try:
                                        user_to = credit_list[2]
                                        amount = float(credit_list[0])
                                        coin_name =  credit_list[1]
                                        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                        await store.sql_user_balance_mv_single(
                                            creditor, user_to, "CREDIT+", "CREDIT+", amount,
                                            coin_name, "CREDIT", coin_decimal, SERVER_BOT,
                                            contract, 0.0, credit_msg
                                        )
                                        if user_to not in user_list_msg:
                                            user_list_msg[user_to] = []
                                        user_list_msg[user_to].append("{} {}".format(
                                            num_format_coin(amount), coin_name
                                        ))
                                        total_user_credit += 1
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                            for k, v in user_list_msg.items():
                                try:
                                    if k.isdigit():
                                        member = self.bot.get_user(int(k))
                                        if member is not None:
                                            await member.send("You received tip(s)```{}```from TipBot Admin/OP. Extra message: {}".format(
                                                "\n".join(v), credit_msg)
                                            )
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            msg = f"{ctx.author.mention}, there are {str(total_user_credit)} user to credit. Uniq users: {str(len(user_list_msg.keys()))}."
                            await ctx.reply(msg)
                            return
            except Exception:
                traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="credit <user> <amount> <coin> <server>",
        description="Credit a user with amount of a coin/token"
    )
    async def credit(self, ctx, member_id: str, amount: str, coin: str, user_server: str = "DISCORD"):
        user_server = user_server.upper()
        if ctx.author.id != self.bot.config['discord']['owner_id']:
            await logchanbot("⚠️⚠️⚠️⚠️ {}#{} / {} is trying credit!".format(
                ctx.author.name, ctx.author.discriminator, ctx.author.mention)
            )
            return
        if self.bot.config['discord']['enable_credit'] != 1:
            msg = f"{ctx.author.mention}, this is disable."
            await ctx.reply(msg)
            return  
        if user_server not in ["DISCORD", "TWITTER", "TELEGRAM", "REDDIT"]:
            await ctx.reply(f"{ctx.author.mention}, invalid server.")
            return
        creditor = "CREDITOR"
        amount = amount.replace(",", "")
        try:
            amount = float(amount)
        except ValueError:
            await ctx.reply(f"{ctx.author.mention}, invalid amount.")
            return
        coin_name = coin.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
            await ctx.reply(msg)
            return

        try:
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
            max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")

            if amount > max_tip or amount < min_tip:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, credit cannot be bigger than **"\
                    f"{num_format_coin(max_tip)} {token_display}**"\
                    f" or smaller than **{num_format_coin(min_tip)} {token_display}**."
                await ctx.reply(msg)
                return

            get_deposit = await self.wallet_api.sql_get_userwallet(
                member_id, coin_name, net_name, type_coin, user_server, 0
            )
            if get_deposit is None:
                msg = f"{ctx.author.mention}, {member_id} not exist with server `{user_server}` in our DB."
                await ctx.reply(msg)
                return
            else:
                # let's credit
                try:
                    # No need amount_in_usd, keep it 0.0
                    tip = await store.sql_user_balance_mv_single(
                        creditor, member_id, "CREDIT+", "CREDIT+", amount,
                        coin_name, "CREDIT", coin_decimal, user_server,
                        contract, 0.0, None
                    )
                    if tip:
                        msg = f"[CREDITING] to user {member_id} server {user_server} with amount "\
                            f": {num_format_coin(amount)} {coin_name}"
                        await ctx.reply(msg)
                        await logchanbot(
                            f"[CREDITING] {ctx.author.name}#{ctx.author.discriminator} / {str(ctx.author.id)} "\
                            f"credit to user {member_id} server {user_server} with amount : "\
                            f"{num_format_coin(amount)} {coin_name}"
                        )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("admin " +str(traceback.format_exc()))
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @tasks.loop(seconds=60.0)
    async def auto_purge_old_message(self):
        # Check if task recently run @bot_task_logs
        task_name = "admin_auto_purge_old_message"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        numbers = 1000
        try:
            purged_items = await self.purge_msg(numbers)
            if purged_items > 50:
                print(f"{datetime.now():%Y-%m-%d-%H-%M-%S} auto_purge_old_message: {str(purged_items)}")
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="baluser <user>",
        description="Check a user's balances"
    )
    async def baluser(self, ctx, member_id: str, user_server: str = "DISCORD"):
        if member_id.upper() == "SWAP":
            member_id = member_id.upper()
            user_server = "SYSTEM"
        else:
            user_server = user_server.upper()
        try:
            zero_tokens = []
            has_none_balance = True
            mytokens = await store.get_coin_settings(coin_type=None)
            total_all_balance_usd = 0.0
            all_pages = []
            all_names = [each['coin_name'] for each in mytokens]
            total_coins = len(mytokens)
            page = disnake.Embed(
                title=f"[ BALANCE LIST {member_id} ]",
                timestamp=datetime.now(),
            )
            page.add_field(
                name="Coin/Tokens: [{}]".format(len(all_names)),
                value=", ".join(all_names),
                inline=False
            )
            page.set_thumbnail(url=ctx.author.display_avatar)
            page.set_footer(text="Use the reactions to flip pages.")
            all_pages.append(page)
            num_coins = 0
            per_page = 20
            # check mutual guild for is_on_mobile
            try:
                if isinstance(ctx.channel, disnake.DMChannel):
                    one_guild = [each for each in ctx.author.mutual_guilds][0]
                else:
                    one_guild = ctx.guild
                member = one_guild.get_member(ctx.author.id)
                if member.is_on_mobile() is True:
                    per_page = 10
            except Exception:
                pass
            tmp_msg = await ctx.reply(f"{ctx.author.mention} balance loading...")
            start = int(time.time())
            userdata_balances = await self.user_balance_multi(member_id, user_server, all_names)
            print("Finish balance: {}".format(int(time.time()) - start))
            if userdata_balances is None:
                await tmp_msg.edit("internal error.")
                return

            prices = {}
            for i in all_names:
                price_with = getattr(getattr(self.bot.coin_list, i), "price_with")
                if price_with:
                    per_unit = await self.utils.get_coin_price(i, price_with)
                    if per_unit and per_unit['price'] and per_unit['price'] > 0:
                        prices[i] = per_unit['price']
                if i not in prices:
                    prices[i] = 0
            print("Finish price: {}".format(int(time.time()) - start))

            original_em = disnake.Embed(
                title=f"[ BALANCE LIST {member_id} ]",
                description="Thank you for using TipBot!",
                timestamp=datetime.now()
            )
            original_em.set_thumbnail(url=ctx.author.display_avatar)
            original_em.set_footer(text="Use the reactions to flip pages.")

            for each_token in mytokens:
                coin_name = each_token['coin_name']
                type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                if num_coins == 0 or num_coins % per_page == 0:
                    page = original_em.copy()
                total_balance = float("%.8f" % userdata_balances[coin_name])
                if total_balance == 0:
                    zero_tokens.append(coin_name)
                    continue
                elif total_balance > 0:
                    has_none_balance = False
                equivalent_usd = ""
                if price_with:
                    per_unit = await self.utils.get_coin_price(coin_name, price_with)
                    if per_unit and per_unit['price'] and per_unit['price'] > 0:
                        per_unit = per_unit['price']
                        total_in_usd = float(Decimal(total_balance) * Decimal(per_unit))
                        total_all_balance_usd += total_in_usd
                        if total_in_usd >= 0.01:
                            equivalent_usd = " ~ {:,.2f}$".format(total_in_usd)
                        elif total_in_usd >= 0.0001:
                            equivalent_usd = " ~ {:,.4f}$".format(total_in_usd)

                page.add_field(
                    name="{}{}".format(token_display, equivalent_usd),
                    value=num_format_coin(total_balance),
                    inline=True
                )
                num_coins += 1
                if num_coins > 0 and num_coins % per_page == 0:
                    all_pages.append(page)
                    if num_coins < total_coins - len(zero_tokens):
                        page = original_em.copy()
                    else:
                        all_pages.append(page)
                        break
            # Check if there is remaining
            if (total_coins - len(zero_tokens)) % per_page > 0:
                all_pages.append(page)
            # Replace first page
            if total_all_balance_usd > 0.01:
                total_all_balance_usd = "Having ~ {:,.2f}$".format(total_all_balance_usd)
            elif total_all_balance_usd > 0.0001:
                total_all_balance_usd = "Having ~ {:,.4f}$".format(total_all_balance_usd)
            else:
                total_all_balance_usd = "Thank you for using TipBot!"

            page = original_em.copy()
            # Remove zero from all_names
            if has_none_balance is True:
                msg = f"{member_id} does not have any balance."
                await ctx.reply(msg)
                return
            else:
                all_names = [each for each in all_names if each not in zero_tokens]
                page.add_field(
                    name="Coin/Tokens: [{}]".format(len(all_names)),
                    value=", ".join(all_names),
                    inline=False
                )
                if len(zero_tokens) > 0:
                    zero_tokens = list(set(zero_tokens))
                    page.add_field(
                        name="Zero Balances: [{}]".format(len(zero_tokens)),
                        value=", ".join(zero_tokens),
                        inline=False
                    )
                all_pages[0] = page
                print("Finish menu: {}".format(int(time.time()) - start))

                view = MenuPage(ctx, all_pages, timeout=120, disable_remove=False)
                await tmp_msg.delete()
                view.message = await ctx.reply(content=None, embed=all_pages[0], view=view)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="pending",
        description="Check pending things"
    )
    async def pending(self, ctx):
        ts = datetime.utcnow()
        embed = disnake.Embed(title='Pending Actions', timestamp=ts)
        embed.add_field(name="Pending Tx", value=str(len(self.bot.tipping_in_progress)), inline=True)
        if len(self.bot.tipping_in_progress) > 0:
            string_ints = [str(num) for num in self.bot.tipping_in_progress]
            list_pending = '{' + ', '.join(string_ints) + '}'
            embed.add_field(name="List Pending By", value=list_pending, inline=True)

        embed.set_footer(text=f"Pending requested by {ctx.author.name}#{ctx.author.discriminator}")
        try:
            await ctx.reply(embed=embed)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="withdraw <coin/token>",
        description="Enable/Disable withdraw for a coin/token"
    )
    async def withdraw(self, ctx, coin: str):
        coin_name = coin.upper()
        command = "withdraw"
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
            await ctx.reply(msg)
            return
        else:
            enable_withdraw = getattr(getattr(self.bot.coin_list, coin_name), "enable_withdraw")
            new_value = 1
            new_text = "enable"
            if enable_withdraw == 1:
                new_value = 0
                new_text = "disable"
            toggle = await self.enable_disable_coin(coin_name, command, new_value)
            if toggle > 0:
                msg = f"{ctx.author.mention}, **{coin_name}** `{command}` is `{new_text}` now."
                await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, **{coin_name}** `{command}` is `{new_text}` failed to update."
                await ctx.reply(msg)
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
            coin_list_name = await self.get_coin_list_name()
            if coin_list_name:
                self.bot.coin_name_list = coin_list_name

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="tip <coin/token>",
        description="Enable/Disable tip for a coin/token"
    )
    async def tip(self, ctx, coin: str):
        coin_name = coin.upper()
        command = "tip"
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
            await ctx.reply(msg)
            return
        else:
            enable_tip = getattr(getattr(self.bot.coin_list, coin_name), "enable_tip")
            new_value = 1
            new_text = "enable"
            if enable_tip == 1:
                new_value = 0
                new_text = "disable"
            toggle = await self.enable_disable_coin(coin_name, command, new_value)
            if toggle > 0:
                msg = f"{ctx.author.mention}, **{coin_name}** `{command}` is `{new_text}` now."
                await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, **{coin_name}** `{command}` is `{new_text}` failed to update."
                await ctx.reply(msg)
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
            coin_list_name = await self.get_coin_list_name()
            if coin_list_name:
                self.bot.coin_name_list = coin_list_name

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="partydrop <coin/token>",
        description="Enable/Disable /partydrop for a coin/token"
    )
    async def partydrop(self, ctx, coin: str):
        coin_name = coin.upper()
        command = "partydrop"
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
            await ctx.reply(msg)
            return
        else:
            enable_partydrop = getattr(getattr(self.bot.coin_list, coin_name), "enable_partydrop")
            new_value = 1
            new_text = "enable"
            if enable_partydrop == 1:
                new_value = 0
                new_text = "disable"
            toggle = await self.enable_disable_coin(coin_name, command, new_value)
            if toggle > 0:
                msg = f"{ctx.author.mention}, **{coin_name}** `/{command}` is `{new_text}` now."
                await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, **{coin_name}** `/{command}` is `{new_text}` failed to update."
                await ctx.reply(msg)
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
            coin_list_name = await self.get_coin_list_name()
            if coin_list_name:
                self.bot.coin_name_list = coin_list_name

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="quickdrop <coin/token>",
        description="Enable/Disable /quickdrop for a coin/token"
    )
    async def quickdrop(self, ctx, coin: str):
        coin_name = coin.upper()
        command = "quickdrop"
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
            await ctx.reply(msg)
            return
        else:
            enable_quickdrop = getattr(getattr(self.bot.coin_list, coin_name), "enable_quickdrop")
            new_value = 1
            new_text = "enable"
            if enable_quickdrop == 1:
                new_value = 0
                new_text = "disable"
            toggle = await self.enable_disable_coin(coin_name, command, new_value)
            if toggle > 0:
                msg = f"{ctx.author.mention}, **{coin_name}** `/{command}` is `{new_text}` now."
                await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, **{coin_name}** `/{command}` is `{new_text}` failed to update."
                await ctx.reply(msg)
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
            coin_list_name = await self.get_coin_list_name()
            if coin_list_name:
                self.bot.coin_name_list = coin_list_name

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="talkdrop <coin/token>",
        description="Enable/Disable /talkdrop for a coin/token"
    )
    async def talkdrop(self, ctx, coin: str):
        coin_name = coin.upper()
        command = "talkdrop"
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
            await ctx.reply(msg)
            return
        else:
            enable_talkdrop = getattr(getattr(self.bot.coin_list, coin_name), "enable_talkdrop")
            new_value = 1
            new_text = "enable"
            if enable_talkdrop == 1:
                new_value = 0
                new_text = "disable"
            toggle = await self.enable_disable_coin(coin_name, command, new_value)
            if toggle > 0:
                msg = f"{ctx.author.mention}, **{coin_name}** `/{command}` is `{new_text}` now."
                await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, **{coin_name}** `/{command}` is `{new_text}` failed to update."
                await ctx.reply(msg)
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
            coin_list_name = await self.get_coin_list_name()
            if coin_list_name:
                self.bot.coin_name_list = coin_list_name

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="enablecoin <coin/token>",
        description="Enable/Disable a coin/token"
    )
    async def enablecoin(self, ctx, coin: str):
        coin_name = coin.upper()
        command = "enable"
        if hasattr(self.bot.coin_list, coin_name):
            is_enable = getattr(getattr(self.bot.coin_list, coin_name), "enable")
            new_value = 1
            new_text = "enable"
            if is_enable == 1:
                new_value = 0
                new_text = "disable"
            toggle = await self.enable_disable_coin(coin_name, command, new_value)
            if toggle > 0:
                msg = f"{ctx.author.mention}, **{coin_name}** `{command}` is `{new_text}` now."
                await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, **{coin_name}** `{command}` is `{new_text}` failed to update."
                await ctx.reply(msg)
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
            coin_list_name = await self.get_coin_list_name()
            if coin_list_name:
                self.bot.coin_name_list = coin_list_name
        else:
            try:
                coin_list = await self.get_coin_list_name(True)
                if coin_name not in coin_list:
                    msg = f"{ctx.author.mention}, **{coin_name}** not exist in our setting DB."
                    await ctx.reply(msg)
                    return
                else:
                    new_value = 1
                    toggle = await self.enable_disable_coin(coin_name, command, new_value)
                    if toggle > 0:
                        msg = f"{ctx.author.mention}, **{coin_name}** `{command}` is enable now."
                        await ctx.reply(msg)
                        # Update
                        coin_list = await self.get_coin_setting()
                        if coin_list:
                            self.bot.coin_list = coin_list
                        coin_list_name = await self.get_coin_list_name()
                        if coin_list_name:
                            self.bot.coin_name_list = coin_list_name
                    else:
                        msg = f"{ctx.author.mention}, **{coin_name}** `{command}` is `{new_value}` failed to update."
                        await ctx.reply(msg)
            except Exception:
                traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="deposit <coin/token>",
        description="Enable/Disable deposit for a coin/token"
    )
    async def deposit(self, ctx, coin: str):
        coin_name = coin.upper()
        command = "deposit"
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
            await ctx.reply(msg)
            return
        else:
            enable_deposit = getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit")
            new_value = 1
            new_text = "enable"
            if enable_deposit == 1:
                new_value = 0
                new_text = "disable"
            toggle = await self.enable_disable_coin(coin_name, command, new_value)
            if toggle > 0:
                msg = f"{ctx.author.mention}, **{coin_name}** `{command}` is `{new_text}` now."
                await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, **{coin_name}** `{command}` is `{new_text}` failed to update."
                await ctx.reply(msg)
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
            coin_list_name = await self.get_coin_list_name()
            if coin_list_name:
                self.bot.coin_name_list = coin_list_name

    @commands.is_owner()
    @admin.command(
        usage="eval <expression>",
        description="Do some eval."
    )
    async def eval(
        self,
        ctx,
        *,
        code
    ):
        if self.bot.config['discord']['enable_eval'] != 1:
            return

        if ctx.author.id != self.bot.config['discord']['owner_id']:
            await logchanbot("⚠️⚠️⚠️⚠️ {}#{} / {} is trying eval! ```{}```".format(
                ctx.author.name, ctx.author.discriminator, ctx.author.mention, code)
            )
            return

        str_obj = io.StringIO()  # Retrieves a stream of data
        try:
            with contextlib.redirect_stdout(str_obj):
                exec(code)
        except Exception as e:
            return await ctx.reply(f"```{e.__class__.__name__}: {e}```")
        await ctx.reply(f"```{str_obj.getvalue()}```")

    @commands.is_owner()
    @admin.command(
        hidden=True,
        usage="create [option]",
        description="Create an address erc-20, trc-20, xtz, near, vet, uuid"
    )
    async def create(self, ctx, token: str):
        if token.upper() not in ["ERC-20", "TRC-20", "XTZ", "NEAR", "VET", "UUID"]:
            await ctx.reply(f"{ctx.author.mention}, only with ERC-20 and TRC-20.")
        elif token.upper() == "ERC-20":
            try:
                w = await self.create_address_eth()
                await ctx.reply(f"{ctx.author.mention}, ```{str(w)}```", view=RowButtonRowCloseAnyMessage())
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif token.upper() == "TRC-20":
            try:
                w = await self.create_address_trx()
                await ctx.reply(f"{ctx.author.mention}, ```{str(w)}```", view=RowButtonRowCloseAnyMessage())
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif token.upper() == "XTZ":
            try:
                mnemo = Mnemonic("english")
                words = str(mnemo.generate(strength=128))
                key = XtzKey.from_mnemonic(mnemonic=words, passphrase="", email="")
                await ctx.reply(f"{ctx.author.mention}, ```Pub: {key.public_key_hash()}\nSeed: {words}\nKey: {key.secret_key()}```", view=RowButtonRowCloseAnyMessage())
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif token.upper() == "NEAR":
            try:
                mnemo = Mnemonic("english")
                words = str(mnemo.generate(strength=128))
                seed = [words]

                seed_bytes = Bip39SeedGenerator(words).Generate("")
                bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.NEAR_PROTOCOL)
                key_byte = bip44_mst_ctx.PrivateKey().Raw().ToHex()
                address = bip44_mst_ctx.PublicKey().ToAddress()

                sender_key_pair = near_api.signer.KeyPair(bytes.fromhex(key_byte))
                sender_signer = near_api.signer.Signer(address, sender_key_pair)
                new_addr = sender_signer.public_key.hex()
                if new_addr == address:
                    await ctx.reply(
                        f"{ctx.author.mention}, {address}:```Seed:{words}\nKey: {key_byte}```",
                        view=RowButtonRowCloseAnyMessage()
                    )
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif token.upper() == "VET":
            wallet = thor_wallet.newWallet()
            await ctx.reply(
                f"{ctx.author.mention}, {wallet.address}:```key:{wallet.priv.hex()}```",
                view=RowButtonRowCloseAnyMessage()
            )
        elif token.upper() == "UUID":
            await ctx.reply(
                f"{ctx.author.mention}, uuid:```{str(uuid.uuid4())}```",
                view=RowButtonRowCloseAnyMessage()
            )

    @commands.is_owner()
    @admin.command(
        usage="encrypt <expression>",
        description="Encrypt text."
    )
    async def encrypt(
        self,
        ctx,
        *,
        text
    ):
        encrypt = encrypt_string(text)
        if encrypt: return await ctx.reply(f"```{encrypt}```", view=RowButtonRowCloseAnyMessage())

    @commands.is_owner()
    @admin.command(
        usage="decrypt <expression>",
        description="Decrypt text."
    )
    async def decrypt(
        self,
        ctx,
        *,
        text
    ):
        decrypt = decrypt_string(text)
        if decrypt: return await ctx.reply(f"```{decrypt}```", view=RowButtonRowCloseAnyMessage())

    @commands.Cog.listener()
    async def on_ready(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.auto_purge_old_message.is_running():
                self.auto_purge_old_message.start()

    async def cog_load(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.auto_purge_old_message.is_running():
                self.auto_purge_old_message.start()

    def cog_unload(self):
        # Ensure the task is stopped when the cog is unloaded.
        self.auto_purge_old_message.cancel()

def setup(bot):
    bot.add_cog(Admin(bot))
