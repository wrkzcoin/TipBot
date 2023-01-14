import sys
import traceback
from typing import List
import time
from cachetools import TTLCache
from sqlitedict import SqliteDict

import disnake
from disnake.ext import commands

import store
from Bot import RowButtonRowCloseAnyMessage, logchanbot


# https://stackoverflow.com/questions/287871/how-do-i-print-colored-text-to-the-terminal

def print_color(prt, color: str):
    if color == "red":
        print(f"\033[91m{prt}\033[00m")
    elif color == "green":
        print(f"\033[92m{prt}\033[00m")
    elif color == "yellow":
        print(f"\033[93m{prt}\033[00m")
    elif color == "lightpurple":
        print(f"\033[94m{prt}\033[00m")
    elif color == "purple":
        print(f"\033[95m{prt}\033[00m")
    elif color == "cyan":
        print(f"\033[96m{prt}\033[00m")
    elif color == "lightgray":
        print(f"\033[97m{prt}\033[00m")
    elif color == "black":
        print(f"\033[98m{prt}\033[00m")
    else:
        print(f"\033[0m{prt}\033[00m")

async def get_all_coin_names(
    what: str,
    value: int
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT `coin_name` FROM `coin_settings` 
                      WHERE `"""+what+"""`=%s
                      LIMIT 25
                      """
                await cur.execute(sql, value)
                result = await cur.fetchall()
                if result:
                    coin_list = [each["coin_name"] for each in result]
                    return coin_list
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return ["N/A"]

# Defines a simple paginator of buttons for the embed.
class MenuPage(disnake.ui.View):
    message: disnake.Message

    def __init__(self, inter, embeds: List[disnake.Embed], timeout: float = 60, disable_remove: bool=False):
        super().__init__(timeout=timeout)
        self.inter = inter

        # Sets the embed list variable.
        self.embeds = embeds

        # Current embed number.
        self.embed_count = 0

        # Disables previous page button by default.
        self.prev_page.disabled = True

        self.first_page.disabled = True

        if disable_remove is True:
            self.remove.disabled = True

        # Sets the footer of the embeds with their respective page numbers.
        for i, embed in enumerate(self.embeds):
            embed.set_footer(text=f"Page {i + 1} of {len(self.embeds)}")

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True

        if type(self.inter) == disnake.ApplicationCommandInteraction:
            await self.inter.edit_original_message(view=RowButtonRowCloseAnyMessage())
        else:
            if self.message:
                try:
                    await self.message.edit(view=RowButtonRowCloseAnyMessage())
                except Exception as e:
                    pass

    @disnake.ui.button(label="⏪", style=disnake.ButtonStyle.red)
    async def first_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return

        # Decrements the embed count.
        self.embed_count = 0

        # Gets the embed object.
        try:
            embed = self.embeds[self.embed_count]
        except IndexError:
            return

        self.last_page.disabled = False

        # Enables the next page button and disables the previous page button if we're on the first embed.
        self.next_page.disabled = False
        if self.embed_count == 0:
            self.prev_page.disabled = True
            self.first_page.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    @disnake.ui.button(label="◀️", style=disnake.ButtonStyle.red)
    async def prev_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return

        # Decrements the embed count.
        self.embed_count -= 1

        # Gets the embed object.
        try:
            embed = self.embeds[self.embed_count]
        except IndexError:
            self.embed_count += 1
            return

        self.last_page.disabled = False

        # Enables the next page button and disables the previous page button if we're on the first embed.
        self.next_page.disabled = False
        if self.embed_count == 0:
            self.prev_page.disabled = True
            self.first_page.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    # @disnake.ui.button(label="⏹️", style=disnake.ButtonStyle.red)
    @disnake.ui.button(label="⏹️", style=disnake.ButtonStyle.red)
    async def remove(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return
        # await interaction.response.edit_message(view=None)
        try:
            if type(self.inter) == disnake.ApplicationCommandInteraction:
                await interaction.delete_original_message()
            else:
                await interaction.message.delete()
        except Exception as e:
            pass

    # @disnake.ui.button(label="", emoji="▶️", style=disnake.ButtonStyle.green)
    @disnake.ui.button(label="▶️", style=disnake.ButtonStyle.green)
    async def next_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return
        # Increments the embed count.
        self.embed_count += 1

        # Gets the embed object.
        try:
            embed = self.embeds[self.embed_count]
        except IndexError:
            self.embed_count -= 1
            return

        # Enables the previous page button and disables the next page button if we're on the last embed.
        self.prev_page.disabled = False

        self.first_page.disabled = False

        if self.embed_count == len(self.embeds) - 1:
            self.next_page.disabled = True
            self.last_page.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    @disnake.ui.button(label="⏩", style=disnake.ButtonStyle.green)
    async def last_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return
        # Increments the embed count.
        self.embed_count = len(self.embeds) - 1

        # Gets the embed object.
        try:
            embed = self.embeds[self.embed_count]
        except IndexError:
            self.embed_count = len(self.embeds) + 1
            return

        self.first_page.disabled = False

        # Enables the previous page button and disables the next page button if we're on the last embed.
        self.prev_page.disabled = False
        if self.embed_count == len(self.embeds) - 1:
            self.next_page.disabled = True
            self.last_page.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)


class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.commanding_save = 10
        self.adding_commands = False
        self.cache_kv_db_test = SqliteDict(self.bot.config['cache']['temp_leveldb_gen'], tablename="test", autocommit=True)
        self.cache_kv_db_general = SqliteDict(self.bot.config['cache']['temp_leveldb_gen'], tablename="general", autocommit=True)
        self.cache_kv_db_block = SqliteDict(self.bot.config['cache']['temp_leveldb_gen'], tablename="block", autocommit=True)
        self.cache_kv_db_pools = SqliteDict(self.bot.config['cache']['temp_leveldb_gen'], tablename="pools", autocommit=True)
        self.cache_kv_db_paprika = SqliteDict(self.bot.config['cache']['temp_leveldb_gen'], tablename="paprika", autocommit=True)
        self.cache_kv_db_faucet = SqliteDict(self.bot.config['cache']['temp_leveldb_gen'], tablename="faucet", autocommit=True)
        self.cache_kv_db_market_guild = SqliteDict(self.bot.config['cache']['temp_leveldb_gen'], tablename="market_guild", autocommit=True)

    async def get_bot_settings(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `bot_settings` """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    res = {}
                    for each in result:
                        res[each['name']] = each['value']
                    return res
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None


    async def update_user_balance_call(self, user_id: str, type_coin: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if type_coin.upper() == "ERC-20":
                        sql = """ UPDATE `erc20_user` SET `called_Update`=%s WHERE `user_id`=%s """
                    elif type_coin.upper() == "TRC-10" or type_coin.upper() == "TRC-20":
                        sql = """ UPDATE `trc20_user` SET `called_Update`=%s WHERE `user_id`=%s """
                    elif type_coin.upper() == "SOL" or type_coin.upper() == "SPL":
                        sql = """ UPDATE `sol_user` SET `called_Update`=%s WHERE `user_id`=%s """
                    elif type_coin.upper() == "XTZ":
                        sql = """ UPDATE `tezos_user` SET `called_Update`=%s WHERE `user_id`=%s """
                    elif type_coin.upper() == "NEO":
                        sql = """ UPDATE `neo_user` SET `called_Update`=%s WHERE `user_id`=%s """
                    elif type_coin.upper() == "NEAR":
                        sql = """ UPDATE `near_user` SET `called_Update`=%s WHERE `user_id`=%s """
                    elif type_coin.upper() == "ZIL":
                        sql = """ UPDATE `zil_user` SET `called_Update`=%s WHERE `user_id`=%s """
                    elif type_coin.upper() == "VET":
                        sql = """ UPDATE `vet_user` SET `called_Update`=%s WHERE `user_id`=%s """
                    else:
                        return
                    await cur.execute(sql, (int(time.time()), user_id))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("utils " +str(traceback.format_exc()))
        return None

    async def bot_task_logs_add(self, task_name: str, run_at: int):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `bot_task_logs` (`task_name`, `run_at`)
                              VALUES (%s, %s)
                              ON DUPLICATE KEY 
                              UPDATE 
                              `run_at`=VALUES(`run_at`)
                              """
                    await cur.execute(sql, (task_name, run_at))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def bot_task_logs_check(self, task_name: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `bot_task_logs` 
                              WHERE `task_name`=%s ORDER BY `id` DESC LIMIT 1
                              """
                    await cur.execute(sql, task_name)
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def add_command_calls(self):
        if len(self.bot.commandings) <= self.commanding_save:
            return
        if self.adding_commands is True:
            return
        else:
            self.adding_commands = True
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `bot_commanded` 
                    (`guild_id`, `user_id`, `user_server`, `command`, `timestamp`)
                    VALUES (%s, %s, %s, %s, %s)
                    """
                    await cur.executemany(sql, self.bot.commandings)
                    await conn.commit()
                    if cur.rowcount > 0:
                        self.bot.commandings = []
        except Exception:
            traceback.print_exc(file=sys.stdout)
            # could be some length issue
            for each in self.bot.commandings:
                if len(each) != 5:
                    self.bot.commandings.remove(each)
                    await logchanbot("[bot_commanded] removed: " +str(each))
        self.adding_commands = False

    async def get_trade_channel_list(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `discord_server`
                    WHERE `trade_channel` IS NOT NULL
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    # Recent Activity
    async def recent_tips(
        self, user_id: str, user_server: str, token_name: str, coin_family: str, what: str, limit: int
    ):
        global pool
        coin_name = token_name.upper()
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if what.lower() == "withdraw":
                        if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                            sql = """ SELECT * FROM `cn_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "BTC":
                            sql = """ SELECT * FROM `neo_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "NEO":
                            sql = """ SELECT * FROM `doge_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "NEAR":
                            sql = """ SELECT * FROM `near_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "NANO":
                            sql = """ SELECT * FROM `nano_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "CHIA":
                            sql = """ SELECT * FROM `xch_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "ERC-20":
                            sql = """ SELECT * FROM `erc20_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "XTZ":
                            sql = """ SELECT * FROM `tezos_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "ZIL":
                            sql = """ SELECT * FROM `zil_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "VET":
                            sql = """ SELECT * FROM `vet_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "VITE":
                            sql = """ SELECT * FROM `vite_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "TRC-20":
                            sql = """ SELECT * FROM `trc20_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "HNT":
                            sql = """ SELECT * FROM `hnt_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "XRP":
                            sql = """ SELECT * FROM `xrp_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "XLM":
                            sql = """ SELECT * FROM `xlm_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "COSMOS":
                            sql = """ SELECT * FROM `cosmos_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s AND `is_failed`=0
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "ADA":
                            sql = """ SELECT * FROM `xlm_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "SOL" or coin_family == "SPL":
                            sql = """ SELECT * FROM `sol_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                    elif what.lower() == "deposit":
                        if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                            sql = """
                            SELECT a.*, b.*
                            FROM cn_user_paymentid a
                                INNER JOIN cn_get_transfers b
                                    ON a.paymentid = b.payment_id
                            WHERE a.user_id=%s AND a.user_server=%s and a.coin_name=%s
                            ORDER BY b.time_insert DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "BTC":
                            sql = """
                            SELECT a.*, b.*
                            FROM doge_user a
                                INNER JOIN doge_get_transfers b
                                    ON a.balance_wallet_address = b.address
                            WHERE a.user_id=%s AND a.user_server=%s and a.coin_name=%s
                            ORDER BY b.time_insert DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "NEO":
                            sql = """
                            SELECT a.*, b.*
                            FROM neo_user a
                                INNER JOIN neo_get_transfers b
                                    ON a.balance_wallet_address = b.address
                            WHERE a.user_id=%s AND a.user_server=%s and b.coin_name=%s
                            ORDER BY b.time_insert DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "NEAR":
                            sql = """
                            SELECT * 
                            FROM `near_move_deposit`
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "NANO":
                            sql = """
                            SELECT * 
                            FROM `nano_move_deposit`
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "CHIA":
                            sql = """
                            SELECT a.*, b.*
                            FROM xch_user a
                                INNER JOIN xch_get_transfers b
                                    ON a.balance_wallet_address = b.address
                            WHERE a.user_id=%s AND a.user_server=%s and b.coin_name=%s
                            ORDER BY b.time_insert DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "ERC-20":
                            sql = """
                            SELECT * 
                            FROM `erc20_move_deposit` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "XTZ":
                            sql = """
                            SELECT * 
                            FROM `tezos_move_deposit`
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "ZIL":
                            sql = """
                            SELECT * 
                            FROM `zil_move_deposit` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "VET":
                            sql = """
                            SELECT * 
                            FROM `vet_move_deposit`
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "VITE":
                            sql = """
                            SELECT * 
                            FROM `vite_get_transfers`
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "TRC-20":
                            sql = """
                            SELECT * 
                            FROM `trc20_move_deposit`
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "HNT":
                            sql = """
                            SELECT * 
                            FROM `hnt_get_transfers`
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "XRP":
                            sql = """
                            SELECT * 
                            FROM `xrp_get_transfers` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "XLM":
                            sql = """
                            SELECT * 
                            FROM `xlm_get_transfers` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "COSMOS":
                            sql = """
                            SELECT * 
                            FROM `cosmos_get_transfers` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "ADA":
                            sql = """
                            SELECT * 
                            FROM `ada_get_transfers`
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "SOL" or coin_family == "SPL":
                            sql = """
                            SELECT * 
                            FROM `sol_move_deposit` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                            result = await cur.fetchall()
                            if result:
                                return result
                    elif what.lower() == "receive":
                        sql = """ SELECT * FROM `user_balance_mv` 
                        WHERE `to_userid`=%s AND `user_server`=%s AND `token_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif what.lower() == "expense":
                        sql = """ SELECT * FROM `user_balance_mv` 
                        WHERE `from_userid`=%s AND `user_server`=%s AND `token_name`=%s AND `to_userid`<>%s
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name, "TRADE"))
                        result = await cur.fetchall()
                        if result:
                            return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []
    # End of recent activity

    def set_cache_kv(self, table: str, key: str, value):
        try:
            if table.lower() == "test":
                self.cache_kv_db_test[key.upper()] = value
                return True            
            elif table.lower() == "general":
                self.cache_kv_db_general[key.upper()] = value
                return True
            elif table.lower() == "block":
                self.cache_kv_db_block[key.upper()] = value
                return True
            elif table.lower() == "pools":
                self.cache_kv_db_pools[key.upper()] = value
                return True
            elif table.lower() == "paprika":
                self.cache_kv_db_paprika[key.upper()] = value
                return True
            elif table.lower() == "faucet":
                self.cache_kv_db_faucet[key.upper()] = value
                return True
            elif table.lower() == "market_guild":
                self.cache_kv_db_market_guild[key.upper()] = value
                return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    def get_cache_kv(self, table: str, key: str):
        try:
            if table.lower() == "test":
                return self.cache_kv_db_test[key.upper()]
            elif table.lower() == "general":
                return self.cache_kv_db_general[key.upper()]
            elif table.lower() == "block":
                return self.cache_kv_db_block[key.upper()]
            elif table.lower() == "pools":
                return self.cache_kv_db_pools[key.upper()]
            elif table.lower() == "paprika":
                return self.cache_kv_db_paprika[key.upper()]
            elif table.lower() == "faucet":
                return self.cache_kv_db_faucet[key.upper()]
            elif table.lower() == "market_guild":
                return self.cache_kv_db_market_guild[key.upper()]
        except KeyError:
            pass
        return None

    def del_cache_kv(self, table: str, key: str):
        try:
            if table.lower() == "test":
                del self.cache_kv_db_test[key.upper()]
                return True
            elif table.lower() == "general":
                del self.cache_kv_db_general[key.upper()]
                return True
            elif table.lower() == "block":
                del self.cache_kv_db_block[key.upper()]
                return True
            elif table.lower() == "pools":
                del self.cache_kv_db_pools[key.upper()]
                return True
            elif table.lower() == "paprika":
                del self.cache_kv_db_paprika[key.upper()]
                return True
            elif table.lower() == "faucet":
                del self.cache_kv_db_faucet[key.upper()]
                return True
            elif table.lower() == "market_guild":
                del self.cache_kv_db_market_guild[key.upper()]
                return True
        except KeyError:
            pass
        return False

    def get_cache_kv_list(self, table: str):
        try:
            if table.lower() == "test":
                return self.cache_kv_db_test
            elif table.lower() == "general":
                return self.cache_kv_db_general
            elif table.lower() == "block":
                return self.cache_kv_db_block
            elif table.lower() == "pools":
                return self.cache_kv_db_pools
            elif table.lower() == "paprika":
                return self.cache_kv_db_paprika
            elif table.lower() == "faucet":
                return self.cache_kv_db_faucet
            elif table.lower() == "market_guild":
                return self.cache_kv_db_market_guild
        except KeyError:
            pass
        return None

    async def cog_load(self):
        # for testing table
        if self.cache_kv_db_test is None:
            self.cache_kv_db_test = SqliteDict(self.bot.config['cache']['temp_leveldb_gen'], tablename="test", autocommit=True)
        if self.cache_kv_db_general is None:
            self.cache_kv_db_general = SqliteDict(self.bot.config['cache']['temp_leveldb_gen'], tablename="general", autocommit=True)
        if self.cache_kv_db_block is None:
            self.cache_kv_db_block = SqliteDict(self.bot.config['cache']['temp_leveldb_gen'], tablename="block", autocommit=True)
        if self.cache_kv_db_pools is None:
            self.cache_kv_db_pools = SqliteDict(self.bot.config['cache']['temp_leveldb_gen'], tablename="pools", autocommit=True)
        if self.cache_kv_db_paprika is None:
            self.cache_kv_db_paprika = SqliteDict(self.bot.config['cache']['temp_leveldb_gen'], tablename="paprika", autocommit=True)
        if self.cache_kv_db_faucet is None:
            self.cache_kv_db_faucet = SqliteDict(self.bot.config['cache']['temp_leveldb_gen'], tablename="faucet", autocommit=True)
        if self.cache_kv_db_market_guild is None:
            self.cache_kv_db_market_guild = SqliteDict(self.bot.config['cache']['temp_leveldb_gen'], tablename="market_guild", autocommit=True)

    def cog_unload(self):
        self.cache_kv_db_test.close()
        self.cache_kv_db_general.close()
        self.cache_kv_db_block.close()
        self.cache_kv_db_pools.close()
        self.cache_kv_db_paprika.close()
        self.cache_kv_db_faucet.close()
        self.cache_kv_db_market_guild.close()

def setup(bot):
    bot.add_cog(Utils(bot))
