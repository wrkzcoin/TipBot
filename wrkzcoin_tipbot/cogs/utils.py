import sys
import traceback
from typing import List
import time
from cachetools import TTLCache

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
        embed = self.embeds[self.embed_count]

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
        embed = self.embeds[self.embed_count]

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
        embed = self.embeds[self.embed_count]

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
        embed = self.embeds[self.embed_count]

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
                    sql = """ INSERT INTO `bot_commanded` (`guild_id`, `user_id`, `user_server`, `command`, `timestamp`)
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


def setup(bot):
    bot.add_cog(Utils(bot))
