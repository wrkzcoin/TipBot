import aiohttp
import sys
import time
import traceback
from datetime import datetime
import random
from decimal import Decimal
import uuid
# For hash file in case already have
import hashlib
import magic
from io import BytesIO

import disnake
from disnake.ext import commands, tasks
from disnake import TextInputStyle

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
from disnake import ActionRow, Button, ButtonStyle
import json
import asyncio
import store

from cogs.utils import MenuPage
from cogs.utils import Utils, num_format_coin

from Bot import logchanbot, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_INFORMATION, seconds_str, \
    RowButtonRowCloseAnyMessage, SERVER_BOT, EMOJI_HOURGLASS_NOT_DONE, DEFAULT_TICKER, text_to_num, log_to_channel
from cogs.wallet import WalletAPI


class TaskGuild(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.uploaded_accept = self.bot.config['reward_task']['screenshot_allowed']
        self.uploaded_storage = self.bot.config['reward_task']['path_screenshot']
        self.url_screenshot = self.bot.config['reward_task']['url_screenshot']

    async def insert_joining(
        self, task_id: int, guild_id: str, user_id: str, desc: str, screenshot: str
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `discord_guild_task_completed`
                    (`task_id`, `guild_id`, `user_id`, `description`, `screenshot`, `time`)
                    VALUES
                    (%s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (
                        task_id, guild_id, user_id, desc, screenshot, int(time.time())
                    ))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def rejected_task(
        self, task_id: int, guild_id: str, user_id: str, desc: str, screenshot: str,
        insert_time: int, status: str, by_uid: str
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `discord_guild_task_rejected`
                    (`task_id`, `guild_id`, `user_id`, `description`, `screenshot`, `time`, `status`, `rejected_date`, `rejected_by_uid`)
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s);

                    DELETE FROM `discord_guild_task_completed`
                    WHERE `task_id`=%s AND `guild_id`=%s AND `user_id`=%s;
                    """
                    await cur.execute(sql, (
                        task_id, guild_id, user_id, desc, screenshot, insert_time, status, int(time.time()), by_uid,
                        task_id, guild_id, user_id
                    ))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def pay_task_all(
        self, guild_id: str, amount: float, coin_name: str, coin_decimal: int,
        list_user_ids, contract: str, channel_id: str, user_server: str, task_id: int
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
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

                    INSERT INTO `user_balance_mv`
                    (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`,
                    `real_amount`, `real_amount_usd`, `token_decimal`, `type`, `date`, `user_server`, `extra_message`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);

                    UPDATE `discord_guild_task_completed`
                    SET `status`=%s, `paid_time`=%s WHERE `task_id`=%s AND `user_id`=%s;

                    UPDATE `discord_guild_tasks`
                    SET `num_paid`=`num_paid`+1
                    WHERE `id`=%s;
                    """
                    paid = 0
                    for user_id in list_user_ids:
                        data_list = [
                            guild_id, coin_name, user_server, -amount, int(time.time()),
                            user_id, coin_name, user_server, amount, int(time.time()),
                            coin_name, contract, guild_id, user_id, guild_id, channel_id,
                            amount, 0, coin_decimal, "TIP", int(time.time()), user_server, "Reward Task",
                            "PAID", int(time.time()), task_id, user_id,
                            task_id
                        ]
                        await cur.execute(sql, tuple(data_list))
                        await conn.commit()
                        paid += 1
                    return paid
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def pay_task(
        self, guild_id: str, amount: float, coin_name: str, coin_decimal: int,
        user_id: str, contract: str, channel_id: str, user_server: str, task_id: int
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
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

                    INSERT INTO `user_balance_mv`
                    (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`,
                    `real_amount`, `real_amount_usd`, `token_decimal`, `type`, `date`, `user_server`, `extra_message`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);

                    UPDATE `discord_guild_task_completed`
                    SET `status`=%s, `paid_time`=%s WHERE `task_id`=%s AND `user_id`=%s LIMIT 1;

                    UPDATE `discord_guild_tasks`
                    SET `num_paid`=`num_paid`+1
                    WHERE `id`=%s;
                    """
                    # minus from guild
                    data_rows = [
                        guild_id, coin_name, user_server, -amount, int(time.time())
                    ]
                    # plus to user
                    data_rows += [
                        user_id, coin_name, user_server, amount, int(time.time())
                    ]
                    # record
                    data_rows += [
                        coin_name, contract, guild_id, user_id, guild_id, channel_id,
                        amount, 0, coin_decimal, "TIP", int(time.time()), user_server, "Reward Task"
                    ]
                    # update status
                    data_rows += [
                        "PAID", int(time.time()), task_id, user_id
                    ]
                    # increase number paid
                    data_rows += [
                        task_id
                    ]
                    await cur.execute(sql, tuple(data_rows))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def create_task(
        self, guild_id: str, guild_name: str, user_id: str, title: str, number: int, duration: int,
        start_time: int, end_time: int, amount: float, coin_name: str, channel_id: str,
        cost_amount: float, cost_coin: str, status: str, user_server: str, fee_to: str
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `discord_guild_tasks`
                    (`guild_id`, `guild_name`, `created_by_uid`, `title`, `number`, `duration`, `start_time`, `end_time`, 
                    `amount`, `coin_name`, `channel_id`, `cost_amount`, `cost_coin`, `status`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    data_rows = [
                        guild_id, guild_name, user_id, title, number, duration, start_time, end_time,
                        amount, coin_name, channel_id, cost_amount, cost_coin, status
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
                    # minus from guild
                    data_rows += [
                        guild_id, cost_coin, user_server, -cost_amount, int(time.time())
                    ]
                    # plus to dev
                    data_rows += [
                        fee_to, cost_coin, user_server, cost_amount, int(time.time())
                    ]
                    await cur.execute(sql, tuple(data_rows))
                    await conn.commit()
                    return cur.rowcount
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def close_task(
        self, guild_id: str, task_id: int
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    UPDATE `discord_guild_tasks`
                    SET `status`=%s
                    WHERE `guild_id`=%s AND `id`=%s AND `status`=%s;

                    UPDATE `discord_guild_task_completed`
                    SET `status`=%s
                    WHERE `status`=%s AND `task_id`=%s;
                    """
                    await cur.execute(sql, (
                        "COMPLETED", guild_id, task_id, "ONGOING",
                        "CLOSED", "PENDING", task_id
                    ))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def get_list_tasks(
        self, status: str="ONGOING"
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_guild_tasks`
                    WHERE `status`=%s
                    """
                    await cur.execute(sql, (
                        status
                    ))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def change_task_status(
        self, task_id: int
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    UPDATE `discord_guild_tasks`
                    SET `status`=%s
                    WHERE `id`=%s AND `status`=%s
                    """
                    await cur.execute(sql, (
                        "COMPLETED", task_id, "ONGOING"
                    ))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def list_tasks(
        self, guild_id: str, status: str
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_guild_tasks`
                    WHERE `guild_id`=%s AND `status`=%s
                    """
                    await cur.execute(sql, (
                        guild_id, status
                    ))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_a_task(
        self, guild_id: str, id_task: int
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_guild_tasks`
                    WHERE `guild_id`=%s AND `id`=%s
                    LIMIT 1;
                    """
                    await cur.execute(sql, (
                        guild_id, id_task
                    ))
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def get_a_task_completing(
        self, id_task: int
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT COUNT(*) AS number FROM `discord_guild_task_completed`
                    WHERE `task_id`=%s
                    """
                    await cur.execute(sql, (
                        id_task
                    ))
                    result = await cur.fetchone()
                    if result:
                        return result['number']
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def get_a_task_completing_user(
        self, id_task: int, user_id: str
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT a.*, b.`amount`, b.`coin_name`, b.`created_by_uid`, 
                    b.`number`, b.`start_time`, b.`end_time`, b.`title`, `b`.`channel_id`
                        FROM `discord_guild_task_completed` a
                    INNER JOIN `discord_guild_tasks` b
                        ON a.task_id= b.id
                    WHERE a.`task_id`=%s AND a.`user_id`=%s LIMIT 1
                    """
                    await cur.execute(sql, (
                        id_task, user_id
                    ))
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def get_non_paid_task_users(
        self, id_task: int
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT a.*, b.`amount`, b.`coin_name`, b.`created_by_uid`, 
                    b.`number`, b.`start_time`, b.`end_time`
                        FROM `discord_guild_task_completed` a
                    INNER JOIN `discord_guild_tasks` b
                        ON a.task_id= b.id
                    WHERE a.`task_id`=%s AND a.`status`=%s
                    """
                    await cur.execute(sql, (
                        id_task, "PENDING"
                    ))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_a_task_users(
        self, id_task: int
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT a.*, b.`amount`, b.`coin_name`, b.`created_by_uid`, 
                    b.`number`, b.`start_time`, b.`end_time`
                        FROM `discord_guild_task_completed` a
                    INNER JOIN `discord_guild_tasks` b
                        ON a.task_id= b.id
                    WHERE a.`task_id`=%s
                    """
                    await cur.execute(sql, (
                        id_task
                    ))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    @commands.guild_only()
    @commands.slash_command(
        name="task",
        dm_permission=False,
        description="Manage Guild's reward task(s) and complete task by user(s)."
    )
    async def guild_task(self, ctx):
        if self.bot.config['reward_task']['is_private'] == 1 and ctx.author.id not in self.bot.config['reward_task']['testers']:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, this command is not public yet. "\
                "Please try again later!"
            await ctx.response.send_message(msg)
            return

    @commands.has_permissions(manage_channels=True)
    @guild_task.sub_command(
        name="logchan",
        usage="task logchan <channel>",
        options=[
            Option('channel', 'channel', OptionType.channel, required=True),
        ],
        description="Set log channel of task reward."
    )
    async def task_set_logchannel(
        self,
        ctx,
        channel: disnake.TextChannel
    ):
        await ctx.response.send_message(f"{ctx.author.mention}, loading a new task ...", ephemeral=True)
        if type(channel) is not disnake.TextChannel:
            await ctx.edit_original_message(
                content=f"{ctx.author.mention}, that\'s not a text channel. Try a different channel!")
            return

        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo['reward_task_channel']:
            try: 
                if channel.id == int(serverinfo['reward_task_channel']):
                    await ctx.edit_original_message(
                        content=f"{EMOJI_INFORMATION} {channel.mention} is already the reward log channel!")
                    return
                else:
                    # test sending embed
                    try:
                        embed = disnake.Embed(
                            title="Reward Message",
                            description=f"{ctx.author.mention}, reward log will be here!",
                            timestamp=datetime.now(),
                        )
                        embed.set_footer(text="Reward task channel set by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
                        embed.set_thumbnail(url=self.bot.user.display_avatar)
                        await channel.send(content=None, embed=embed)
                    except disnake.errors.Forbidden:
                        await ctx.edit_original_message(
                            content=f"{EMOJI_INFORMATION} {ctx.author.mention}, I have no permission to send embed in that channel {channel.mention}!")
                        return
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await ctx.edit_original_message(
                            content=f"{EMOJI_INFORMATION} {ctx.author.mention}, internal error. Please report!")
                        return
                    # change channel info
                    update = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'reward_task_channel', str(channel.id))
                    await ctx.edit_original_message(
                        content=f"Reward task log channel of guild {ctx.guild.name} has set to {channel.mention}.")
                    await log_to_channel(
                        "reward",
                        f"[REWARD TASK] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                        f"set reward task channel to #{ctx.channel.name}.",
                        self.bot.config['discord']['reward_webhook']
                    )
                    if update is True:
                        # kv trade guild channel
                        try:
                            await self.utils.async_set_cache_kv(
                                "reward_task_guild",
                                str(ctx.guild.id),
                                ctx.channel.id
                            )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("guild " +str(traceback.format_exc()))
        else:
            # test sending embed
            try:
                embed = disnake.Embed(
                    title="Reward Message",
                    description=f"{ctx.author.mention}, reward log will be here!",
                    timestamp=datetime.now(),
                )
                embed.set_footer(text="Reward task channel set by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
                embed.set_thumbnail(url=self.bot.user.display_avatar)
                await channel.send(content=None, embed=embed)
            except disnake.errors.Forbidden:
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, I have no permission to send embed in that channel {channel.mention}!")
                return
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, internal error. Please report!")
                return
            # change channel info
            update = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'reward_task_channel', str(channel.id))
            if update is True:
                # kv trade guild channel
                try:
                    await self.utils.async_set_cache_kv(
                        "reward_task_guild",
                        str(ctx.guild.id),
                        ctx.channel.id
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            await ctx.edit_original_message(
                content=f"Reward task channel of guild {ctx.guild.name} has set to {channel.mention}.")
            await log_to_channel(
                "reward",
                f"[REWARD TASK] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                f"changed reward task channel to #{ctx.channel.name}.",
                self.bot.config['discord']['reward_webhook']
            )

    @commands.has_permissions(manage_channels=True)
    @guild_task.sub_command(
        name="add",
        usage="task add <title> <number> <duration> <amount> <coin/token> <channel>",
        options=[
            Option('title', 'title', OptionType.string, required=True),
            Option('number', 'number', OptionType.number, required=True),
            Option('duration', 'duration', OptionType.number, required=True, choices=[
                OptionChoice("12h", 43200),
                OptionChoice("1d", 86400),
                OptionChoice("2d", 172800),
                OptionChoice("3d", 259200),
                OptionChoice("7d", 604800),
                OptionChoice("14d", 1209600),
                OptionChoice("30d", 2592000)
            ]),
            Option('amount', 'amount', OptionType.string, required=True),
            Option('coin_name', 'coin_name', OptionType.string, required=True),
            Option('channel', 'channel', OptionType.channel, required=True),
        ],
        description="Create a new reward task."
    )
    async def task_add(
        self,
        ctx,
        title: str,
        number: int,
        duration: int,
        amount: str,
        coin_name: str,
        channel: disnake.TextChannel
    ):
        await ctx.response.send_message(f"{ctx.author.mention}, loading a new task ...", ephemeral=True)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/task add", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo is None:
                # Let's add some info if server return None
                await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo['reward_task_channel'] is None:
                await ctx.edit_original_message(
                    content=f"{EMOJI_ERROR} {ctx.author.mention}, please ask Guild Owner to set `/task logchan` first!"
                )
                return
            elif serverinfo['reward_task_channel']:
                log_channel = self.bot.get_channel(int(serverinfo['reward_task_channel']))
                if log_channel is None:
                    await ctx.edit_original_message(
                        content=f"{EMOJI_ERROR} {ctx.author.mention}, I could not find log channel for reward task. Please set it again!"
                    )
                    return
            title = title.strip()
            if len(title) > 128:
                await ctx.edit_original_message(
                    content=f"{EMOJI_ERROR} {ctx.author.mention}, title is too long. Reduce it to less than 128 chars!"
                )
                return
            elif len(title) < 8:
                await ctx.edit_original_message(
                    content=f"{EMOJI_ERROR} {ctx.author.mention}, title is too short. At least 8 chars!"
                )
                return
            number = int(number)
            # count ongoing task by guild
            # check if guild's balance by charged coin/token
            # check if guild has sufficient balance for reward task
            # charge and create a task
            get_all_tasks = await self.list_tasks(str(ctx.guild.id), "ONGOING")
            if len(get_all_tasks) >= self.bot.config['reward_task']['max_per_guild']:
                await ctx.edit_original_message(
                    content=f"{EMOJI_ERROR} {ctx.author.mention}, this Guild {ctx.guild.name} "\
                    f"already reached max. ongoing tasks!")
                await log_to_channel(
                    "reward",
                    f"[REWARD TASK] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                    f"tried to created a new reward task. Guild {ctx.guild.id} reached maximum number!",
                    self.bot.config['discord']['reward_webhook']
                )
                return
            
            if number < 0:
                await ctx.edit_original_message(content=f"{EMOJI_ERROR} {ctx.author.mention}, number can't be negative!")
                return
            elif number > self.bot.config['reward_task']['max_number']:
                await ctx.edit_original_message(content=f"{EMOJI_ERROR} {ctx.author.mention}, set number to 0 if you want unlimited!")
                return

            coin_name =  coin_name.upper()
            if not hasattr(self.bot.coin_list, coin_name):
                await ctx.edit_original_message(content=f'{ctx.author.mention}, **{coin_name}** does not exist with us.')
                return

            # fee
            charged_amount = self.bot.config['reward_task']['charged_amount']
            charged_coin = self.bot.config['reward_task']['charged_coin']
            net_name = getattr(getattr(self.bot.coin_list, charged_coin), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, charged_coin), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, charged_coin), "deposit_confirm_depth")
            get_deposit = await self.wallet_api.sql_get_userwallet(
                str(ctx.guild.id), charged_coin, net_name, type_coin, SERVER_BOT, 0
            )
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(
                    str(ctx.guild.id), charged_coin, net_name, type_coin, SERVER_BOT, 0, 1
                )

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

            height = await self.wallet_api.get_block_height(type_coin, charged_coin, net_name)
            userdata_balance = await self.wallet_api.user_balance(
                str(ctx.guild.id), charged_coin, wallet_address, 
                type_coin, height, deposit_confirm_depth, SERVER_BOT)
            actual_balance = float(userdata_balance['adjust'])
            if actual_balance < charged_amount:
                await ctx.edit_original_message(
                    content=f"{EMOJI_ERROR} {ctx.author.mention}, your Guild doesn't have sufficient "\
                        f"{charged_coin}. **{num_format_coin(charged_amount)} {charged_coin}** is required to create a reward task. "\
                        "Please deposit with `/guild deposit`"
                )
                await log_to_channel(
                    "reward",
                    f"[REWARD TASK] Rejected user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                    f"who tried to created a new task reward with {coin_name} at guild {ctx.guild.id} / {ctx.guild.name}!"\
                    f" Insufficient {charged_coin} balance!",
                    self.bot.config['discord']['reward_webhook']
                )
                return
            # end of fee

            enabe_reward_task = getattr(getattr(self.bot.coin_list, coin_name), "enabe_reward_task")
            if enabe_reward_task != 1:
                await ctx.edit_original_message(
                    content=f"{EMOJI_ERROR} {ctx.author.mention}, {coin_name} is not enabled for reward task!")
                await log_to_channel(
                    "reward",
                    f"[REWARD TASK] Rejected user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                    f"who tried to created a new task reward with {coin_name} at guild {ctx.guild.id} / {ctx.guild.name}!"\
                    f" Coin/token {coin_name} is not enable for task reward!",
                    self.bot.config['discord']['reward_webhook']
                )
                return

            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
            max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
            get_deposit = await self.wallet_api.sql_get_userwallet(
                str(ctx.guild.id), coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(
                    str(ctx.guild.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 1
                )

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
            userdata_balance = await self.wallet_api.user_balance(
                str(ctx.guild.id), coin_name, wallet_address, 
                type_coin, height, deposit_confirm_depth, SERVER_BOT)
            actual_balance = float(userdata_balance['adjust'])

            # Check if channel is text channel
            if type(channel) is not disnake.TextChannel:
                msg = f"{ctx.author.mention}, that\'s not a text channel. Try a different channel!"
                await ctx.edit_original_message(content=msg)
                return
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount."
                await ctx.edit_original_message(content=msg)
                return
            # We assume max reward by max_tip / 10
            elif amount < min_tip or amount > max_tip / 10:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, reward task cannot be smaller than "\
                    f"{num_format_coin(min_tip)} {token_display} "\
                    f"or bigger than {num_format_coin(max_tip / 10)} {token_display}."
                await ctx.edit_original_message(content=msg)
                return
            # We assume at least guild need to have 100x of reward or depends on guild's population
            elif amount*100 > actual_balance:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, your guild needs to have at least 100x "\
                    f"reward task's amount. 100x rewards = {num_format_coin(amount*100)} "\
                    f"{token_display}. Check with `/guild balance`."
                await ctx.edit_original_message(content=msg)
                return
            else:
                # Check channel
                get_channel = self.bot.get_channel(int(channel.id))
                channel_str = str(channel.id)
                # Test message
                task_detail = f"🆕 Reward task created:\n"\
                    f"Title: {title}\n"\
                    f"Reward: {num_format_coin(amount)} {coin_name}\n"\
                    f"Ends: <t:{str(int(time.time() + duration))}:f>"
                try:
                    await get_channel.send(task_detail)
                except Exception:
                    msg = f"{ctx.author.mention}, failed to message channel {channel.mention}. Set reward task denied!"
                    await ctx.edit_original_message(content=msg)
                    traceback.print_exc(file=sys.stdout)
                    return
                try:
                    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                    if serverinfo is None:
                        # Let's add some info if server return None
                        await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
                except Exception:
                    await ctx.edit_original_message(content=f"{ctx.author.mention}, internal error. Please report.")
                    traceback.print_exc(file=sys.stdout)

                create_task = await self.create_task(
                    str(ctx.guild.id), ctx.guild.name, str(ctx.author.id), title, number, duration,
                    int(time.time()), int(time.time() + duration), amount, coin_name, channel_str,
                    charged_amount, charged_coin, "ONGOING", SERVER_BOT, self.bot.config['reward_task']['fee_to']
                )
                if create_task is not None:
                    task_detail = f"🆕 Reward task created:\n"\
                        f"Title: {title}\n"\
                        f"Reward: {num_format_coin(amount)} {coin_name}\n"\
                        f"Ends: <t:{str(int(time.time() + duration))}:f>"
                    await ctx.edit_original_message(
                        content=f"New task created in {channel.mention}!"
                    )
                    await log_to_channel(
                        "reward",
                        f"[REWARD TASK] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                        f"successfully created a new task reward with {coin_name} at guild {ctx.guild.id} / {ctx.guild.name}!\n\n{task_detail}",
                        self.bot.config['discord']['reward_webhook']
                    )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.has_permissions(manage_channels=True)
    @guild_task.sub_command(
        name="close",
        usage="task close <ref id>",
        options=[
            Option('ref_id', 'ref_id', OptionType.number, required=True)
        ],
        description="Close an ongoing task."
    )
    async def task_close(
        self,
        ctx,
        ref_id: int
    ):
        await ctx.response.send_message(f"{ctx.author.mention}, loading task ...", ephemeral=True)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/task close", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            # check if task exist
            # check status if still ongoing
            ref_id = int(ref_id)
            get_task = await self.get_a_task(str(ctx.guild.id), ref_id)
            if get_task is None:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, there's no such task ID **{str(ref_id)}** for this guild!"\
                        " Please check with `/task list`")
                await log_to_channel(
                    "reward",
                    f"[REWARD TASK] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                    f"tried to close a task reward {str(ref_id)} at guild {ctx.guild.id} / {ctx.guild.name} which not exist!",
                    self.bot.config['discord']['reward_webhook']
                )
                return
            else:
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                log_channel = self.bot.get_channel(int(serverinfo['reward_task_channel']))
                closing_task = await self.close_task(str(ctx.guild.id), ref_id)
                if closing_task is True:
                    await ctx.edit_original_message(content=f"{ctx.author.mention}, successfully closed task {str(ref_id)} - {get_task['title']}!")
                    await log_to_channel(
                        "reward",
                        f"[REWARD TASK] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                        f"successfully closed a new task reward {str(ref_id)} at guild {ctx.guild.id} / {ctx.guild.name}!",
                        self.bot.config['discord']['reward_webhook']
                    )
                    if serverinfo['reward_task_channel'] and log_channel is not None:
                        await log_channel.send(f"{ctx.author.mention} successfully closed task {str(ref_id)} - {get_task['title']}!")
                    return
                else:
                    await ctx.edit_original_message(content=f"{ctx.author.mention}, internal error during closing task!")
                    return
        except ValueError:
            await ctx.edit_original_message(content=f"{ctx.author.mention}, invalid given ref ID {ref_id}!")
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @guild_task.sub_command(
        name="list",
        usage="task list",
        description="View all ongoing tasks."
    )
    async def task_list(
        self,
        ctx
    ):
        # Everyone can see this list.
        await ctx.response.send_message(f"{ctx.author.mention}, loading task ...")
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/task list", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            # show all ongoing tasks
            get_all_tasks = await self.list_tasks(str(ctx.guild.id), "ONGOING")
            if len(get_all_tasks) == 0:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, this guild has no ongoing reward task!")
                return
            else:
                list_tasks = []
                for c, i in enumerate(get_all_tasks, start=1):
                    list_tasks.append("{}) {} - {} {}. ⏱️ <t:{}:f>\n".format(
                        i['id'], i['title'][0:256], num_format_coin(i['amount']), i['coin_name'], i['end_time']
                    ))
                await ctx.edit_original_message(
                    content="{}, list of ongoing reward task(s) in {}:\n\n{}".format(
                        ctx.author.mention, ctx.guild.name, "\n".join(list_tasks)
                    )
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @guild_task.sub_command(
        name="id",
        usage="task id <ref id>",
        options=[
            Option('ref_id', 'ref_id', OptionType.number, required=True),
            Option('user', 'user', OptionType.user, required=False),
        ],
        description="Check a task ID."
    )
    async def task_id(
        self,
        ctx,
        ref_id: int,
        user: disnake.Member=None
    ):
        if user is None:
            await ctx.response.send_message(f"{ctx.author.mention}, loading task ...")
        else:
            await ctx.response.send_message(f"{ctx.author.mention}, loading task ...", ephemeral=True)
            if ctx.author.id != user.id:
                get_user = ctx.guild.get_member(ctx.author.id)
                if get_user.guild_permissions.manage_channels is False:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, permission denied! You can only check yours!")
                    return
            
        # anyone can check
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/task id", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            ref_id = int(ref_id)
            a_task = await self.get_a_task(str(ctx.guild.id), ref_id)
            if a_task is None:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, there's no such task ID **{str(ref_id)}** for this guild!"\
                        " Please check with `/task list`")
                return
            else:
                get_tasks = await self.get_a_task_users(ref_id)
                if user is None:
                    msg = "Task ID: **{}** ({}) ⏱️ <t:{}:f>\n⚆ Title: {}\n⚆ Reward: {} {}".format(
                        str(ref_id), a_task['status'], a_task['end_time'], a_task['title'], 
                        num_format_coin(a_task['amount']), a_task['coin_name']
                    )
                    if len(get_tasks) > 0:
                        pending = []
                        paid = []
                        pending_no_mention = []
                        paid_no_mention = []
                        for i in get_tasks:
                            if i['status'] == "PENDING":
                                pending.append("<@{}>".format(i['user_id']))
                                get_u = self.bot.get_user(int(i['user_id']))
                                if get_u is not None:
                                    pending_no_mention.append("{}#{}".format(get_u.name, get_u.discriminator))
                                else:
                                    pending_no_mention.append("<@{}>".format(i['user_id']))
                            elif i['status'] == "PAID":
                                paid.append("<@{}>".format(i['user_id']))
                                get_u = self.bot.get_user(int(i['user_id']))
                                if get_u is not None:
                                    paid_no_mention.append("{}#{}".format(get_u.name, get_u.discriminator))
                                else:
                                    paid_no_mention.append("<@{}>".format(i['user_id']))
                        if len(pending) > 0:
                            msg += "\n⚆ Pending: {} user(s).".format(len(pending))
                        if len(paid) > 0:
                            msg += "\n⚆ Paid: {} user(s).".format(len(paid))
                        if len(pending) > 0:
                            msg += "\n⚆ Pending payment user(s): {}".format(
                                ", ".join(pending_no_mention)
                            )
                        if len(paid) > 0:
                            msg += "\n⚆ Paid user(s): {}".format(
                                ", ".join(paid_no_mention)
                            )
                    await ctx.edit_original_message(
                        content=msg)
                else:
                    check_task = await self.get_a_task_completing_user(ref_id, str(user.id))
                    if check_task is None:
                        await ctx.edit_original_message(
                            content=f"{ctx.author.mention}, that user hasn't completed the task yet. Ask them to `/task complete`")
                        return
                    else:
                        embed = disnake.Embed(
                            title="Reward task submission",
                            description=f"Proof submission by {user.mention}",
                            timestamp=datetime.fromtimestamp(check_task['time']),
                        )
                        embed.add_field(
                            name="Task #{}".format(ref_id),
                            value=check_task['title'],
                            inline=False
                        )
                        embed.add_field(
                            name="Total paid",
                            value=a_task['num_paid'],
                            inline=True
                        )
                        embed.set_footer(text="Status: {}".format(
                            check_task['status']
                        ))
                        embed.set_image(url=self.bot.config['reward_task']['url_screenshot'] + check_task['screenshot'])
                        await ctx.edit_original_message(
                            content=None, embed=embed)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.has_permissions(manage_channels=True)
    @guild_task.sub_command(
        name="payall",
        usage="task pay <ref id>",
        options=[
            Option('ref_id', 'ref_id', OptionType.number, required=True)
        ],
        description="Pay all pending users with ref id."
    )
    async def task_pay_all(
        self,
        ctx,
        ref_id: int
    ):
        await ctx.response.send_message(f"{ctx.author.mention}, loading task payment ...")
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/task payall", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo is None:
                # Let's add some info if server return None
                await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo['reward_task_channel'] is None:
                await ctx.edit_original_message(
                    content=f"{EMOJI_ERROR} {ctx.author.mention}, please set `/task logchan` first!"
                )
                return
            elif serverinfo['reward_task_channel']:
                log_channel = self.bot.get_channel(int(serverinfo['reward_task_channel']))
                if log_channel is None:
                    await ctx.edit_original_message(
                        content=f"{EMOJI_ERROR} {ctx.author.mention}, I could not find log channel for reward task. Please set it again!"
                    )
                    return

            ref_id = int(ref_id)
            get_task = await self.get_a_task(str(ctx.guild.id), ref_id)
            if get_task is None:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, there's no such task ID **{str(ref_id)}** for this guild!"\
                        " Please check with `/task list`")
                return
            else:
                amount = get_task['amount']
                coin_name = get_task['coin_name']
                # check balance
                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(ctx.guild.id), coin_name, net_name, type_coin, SERVER_BOT, 0
                )
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(ctx.guild.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 1
                    )

                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                elif type_coin in ["XRP"]:
                    wallet_address = get_deposit['destination_tag']

                height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                userdata_balance = await self.wallet_api.user_balance(
                    str(ctx.guild.id), coin_name, wallet_address, 
                    type_coin, height, deposit_confirm_depth, SERVER_BOT)
                actual_balance = float(userdata_balance['adjust'])

                get_tasks = await self.get_a_task_users(ref_id)
                list_pending = []
                list_mentioned = []
                if len(get_tasks) > 0:
                    for i in get_tasks:
                        if i['status'] == "PENDING":
                            list_pending.append(i['user_id'])
                            list_mentioned.append("<@{}>".format(i['user_id']))
                if len(list_pending) == 0:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, there's no such pending payment for Task ID: **{str(ref_id)}** for this guild!")
                    return
                else:
                    if actual_balance < len(list_pending) * amount:
                        await ctx.edit_original_message(
                            content=f"{ctx.author.mention}, your Guild {ctx.guild.name} doesn't have sufficient balance of "\
                                f"{coin_name} to pay all Task ID: **{str(ref_id)}**!")
                        await log_to_channel(
                            "reward",
                            f"[REWARD TASK] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                            f"would like to pay all {str(len(list_pending))} pending user(s) but not sufficient balance for Task ID"\
                            f": **{str(ref_id)}** at guild {ctx.guild.id} / {ctx.guild.name}!",
                            self.bot.config['discord']['reward_webhook']
                        )
                        return
                    else:
                        # pay them all and mark as paid
                        paying = await self.pay_task_all(
                            str(ctx.guild.id), amount, coin_name, coin_decimal,
                            list_pending, contract, str(ctx.channel.id), SERVER_BOT, ref_id
                        )
                        if paying > 0:
                            mention_list = ", ".join(list_mentioned)
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, successfully paid to {str(len(list_pending))} user(s)"\
                                    f" for task ID: **{str(ref_id)}**!")
                            try:
                                get_reward_chan = self.bot.get_channel(int(get_task['channel_id']))
                                await get_reward_chan.send(
                                    f"{EMOJI_INFORMATION} {ctx.author.mention} successfully "\
                                    f"paid a reward task ID **{str(ref_id)}** to {mention_list} with "\
                                    f"amount {num_format_coin(amount)} {coin_name} each.")
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                await log_to_channel(
                                    "reward",
                                    f"[REWARD TASK] can't find or no permission to send log message in guild {ctx.guild.id} / {ctx.guild.name}!",
                                    self.bot.config['discord']['reward_webhook']
                                )
                            # DM user
                            try:
                                for i in list_pending:
                                    user = self.bot.get_user(int(i))
                                    if user is not None:
                                        await user.send(
                                            f"You got a reward task of {num_format_coin(amount)} {coin_name} in Guild {ctx.guild.name} "\
                                            f"for task ID: {str(ref_id)} executed by {ctx.author.mention}!"
                                        )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            if log_channel is not None:
                                await log_channel.send(f"User {ctx.author.mention} execute to pay all pending for task ID: **{str(ref_id)}** to {mention_list} with "\
                                    f"amount {num_format_coin(amount)} {coin_name} each.!")
                        else:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, internal error. Please report!")
                        return
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @guild_task.sub_command(
        name="reject",
        usage="task reject <ref id> <user>",
        options=[
            Option('ref_id', 'ref_id', OptionType.number, required=True),
            Option('user', 'user', OptionType.user, required=True),
        ],
        description="Reject a user/or yourself from a Task ID."
    )
    async def task_reject(
        self,
        ctx,
        ref_id: int,
        user: disnake.Member
    ):
        await ctx.response.send_message(f"{ctx.author.mention}, loading task rejection ...", ephemeral=True)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/task reject", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo is None:
                # Let's add some info if server return None
                await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo['reward_task_channel'] is None:
                await ctx.edit_original_message(
                    content=f"{EMOJI_ERROR} {ctx.author.mention}, please set `/task logchan` first!"
                )
                return
            elif serverinfo['reward_task_channel']:
                channel = self.bot.get_channel(int(serverinfo['reward_task_channel']))
                if channel is None:
                    await ctx.edit_original_message(
                        content=f"{EMOJI_ERROR} {ctx.author.mention}, I could not find log channel for reward task. Please set it again!"
                    )
                    return
            ref_id = int(ref_id)
            # Check if user has access. If not check if he wants to reject his own
            permission_granted = False
            if ctx.author.id == user.id:
                permission_granted = True

            if permission_granted is False:
                get_user = ctx.guild.get_member(ctx.author.id)
                if get_user.guild_permissions.manage_channels is True:
                    permission_granted = True
            if permission_granted is False:
                await ctx.edit_original_message(
                    content=f"{EMOJI_ERROR} {ctx.author.mention}, permission denied or you should reject only on your own one!"
                )
                await channel.send(f"{ctx.author.mention} tried to reject Task ID: **{str(ref_id)}** submitted by user {user.mention}. Permission denied!")
                return

            get_task = await self.get_a_task(str(ctx.guild.id), ref_id)
            if get_task is None:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, there's no such task ID **{str(ref_id)}** for this guild!"\
                        " Please check with `/task list`")
                return

            check_task = await self.get_a_task_completing_user(ref_id, str(user.id))
            if check_task is None:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, that specific task hasn't completed the task yet. Ask them to `/task complete`")
                return
            else:
                # check if they get paid?
                if check_task['status'] == "PAID":
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, the user was already paid. Rejection denied!")
                    return
                elif check_task['status'] == "CLOSED":
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, can not reject a closed task!")
                    return
                else:
                    # pending
                    # Check if wrong guild?
                    if int(check_task['guild_id']) != ctx.guild.id:
                        await ctx.edit_original_message(
                            content=f"{ctx.author.mention}, the task ref **{str(ref_id)}** is not belong to this Guild!")
                        return
                    rejecting = await self.rejected_task(
                        ref_id, str(ctx.guild.id), str(user.id), check_task['description'], check_task['screenshot'],
                        check_task['time'], check_task['status'], str(ctx.author.id)
                    )
                    if rejecting is True:
                        await ctx.edit_original_message(
                            content=f"{ctx.author.mention}, successfully deleted a task by {user.mention} for Task ID: **{str(ref_id)}**.")   
                        try:
                            get_user = self.bot.get_user(user.id)
                            if get_user is not None and get_user.id != user.id:
                                await get_user.send(
                                    f"Your submitted Task ID: **{str(ref_id)}** - [{check_task['title']}] in Guild {ctx.guild.name} was rejected. You can re-submit.")
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        # message assigned channel
                        try:
                            task_channel = self.bot.get_channel(int(check_task['channel_id']))
                            if task_channel is not None:
                                await task_channel.send(f"{ctx.author.mention} rejected Task ID: **{str(ref_id)}** - [{check_task['title']}] "\
                                                        f"submitted by {user.mention} <t:{check_task['time']}:f>. {user.mention} can still re-submit.")
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        await channel.send(f"{ctx.author.mention} rejected Task ID: **{str(ref_id)}** - [{check_task['title']}] submitted by {user.mention}.")
                    else:
                        await ctx.edit_original_message(
                            content=f"{ctx.author.mention}, internal error during deleting task **{str(ref_id)}** for {user.mention}.")
                    return
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.has_permissions(manage_channels=True)
    @guild_task.sub_command(
        name="pay",
        usage="task pay <ref id> <user>",
        options=[
            Option('ref_id', 'ref_id', OptionType.number, required=True),
            Option('user', 'user', OptionType.user, required=True),
        ],
        description="Pay a user for a completed task."
    )
    async def task_pay(
        self,
        ctx,
        ref_id: int,
        user: disnake.Member
    ):
        await ctx.response.send_message(f"{ctx.author.mention}, loading task payment ...")
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/task pay", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo is None:
                # Let's add some info if server return None
                await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo['reward_task_channel'] is None:
                await ctx.edit_original_message(
                    content=f"{EMOJI_ERROR} {ctx.author.mention}, please set `/task logchan` first!"
                )
                return
            elif serverinfo['reward_task_channel']:
                channel = self.bot.get_channel(int(serverinfo['reward_task_channel']))
                if channel is None:
                    await ctx.edit_original_message(
                        content=f"{EMOJI_ERROR} {ctx.author.mention}, I could not find log channel for reward task. Please set it again!"
                    )
                    return
            # check if user already completed with /task complete
            # show proof, => confirm payment (check guild's balance as well)
            # notify user about reward task by DM, post to the assigned channel.
            ref_id = int(ref_id)
            get_task = await self.get_a_task(str(ctx.guild.id), ref_id)
            if get_task is None:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, there's no such task ID **{str(ref_id)}** for this guild!"\
                        " Please check with `/task list`")
                return

            check_task = await self.get_a_task_completing_user(ref_id, str(user.id))
            if check_task is None:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, that user hasn't completed the task yet. Ask them to `/task complete`")
                return
            else:
                # check if they get paid?
                if check_task['status'] != "PENDING":
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, user {user.mention} already got paid for task ID: "\
                            f"{str(ref_id)} OR the task was already closed!")
                    return
                else:
                    # Check if wrong guild?
                    if int(check_task['guild_id']) != ctx.guild.id:
                        await ctx.edit_original_message(
                            content=f"{ctx.author.mention}, the task ref {str(ref_id)} is not belong to this Guild!")
                        return
                    amount = check_task['amount']
                    coin_name = check_task['coin_name']
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                    net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                    type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                    deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                    token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                    get_deposit = await self.wallet_api.sql_get_userwallet(
                        str(ctx.guild.id), coin_name, net_name, type_coin, SERVER_BOT, 0
                    )
                    if get_deposit is None:
                        get_deposit = await self.wallet_api.sql_register_user(
                            str(ctx.guild.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 1
                        )

                    wallet_address = get_deposit['balance_wallet_address']
                    if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        wallet_address = get_deposit['paymentid']
                    elif type_coin in ["XRP"]:
                        wallet_address = get_deposit['destination_tag']

                    height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                    userdata_balance = await self.wallet_api.user_balance(
                        str(ctx.guild.id), coin_name, wallet_address, 
                        type_coin, height, deposit_confirm_depth, SERVER_BOT)
                    actual_balance = float(userdata_balance['adjust'])
                    if actual_balance < amount:
                        await ctx.edit_original_message(
                            content=f"{EMOJI_ERROR} {ctx.author.mention}, your guild doesn't have sufficient "\
                                f"{coin_name}. Required: **{num_format_coin(amount)} {coin_name}**! Please deposit with `/guild deposit`."
                        )
                        await log_to_channel(
                            "reward",
                            f"[REWARD TASK] Rejected payment of {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                            f"for a task reward with {coin_name} at guild {ctx.guild.id} / {ctx.guild.name}!"\
                            f" Guild has insufficient {coin_name} balance!",
                            self.bot.config['discord']['reward_webhook']
                        )
                        return
                    else:
                        paying = await self.pay_task(
                            str(ctx.guild.id), amount, coin_name, coin_decimal,
                            str(user.id), contract, str(ctx.channel.id), SERVER_BOT, ref_id
                        )
                        if paying is True:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, successfully paid to {user.mention} for task ID: {str(ref_id)}!")
                            try:
                                await channel.send(
                                    f"{EMOJI_INFORMATION} {ctx.author.mention} successfully "\
                                    f"paid a reward task ID {str(ref_id)} to user {user.mention} with "\
                                    f"amount {num_format_coin(amount)} {coin_name}.")
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                await log_to_channel(
                                    "reward",
                                    f"[REWARD TASK] can't find or no permission to send log message in guild {ctx.guild.id} / {ctx.guild.name}!",
                                    self.bot.config['discord']['reward_webhook']
                                )
                            # DM user
                            try:
                                await user.send(
                                    f"You got a reward task of {num_format_coin(amount)} {coin_name} in Guild {ctx.guild.name} "\
                                    f"for task ID: {str(ref_id)} executed by {ctx.author.mention}!"
                                )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            # reward channel
                            get_reward_chan = self.bot.get_channel(int(get_task['channel_id']))
                            if get_reward_chan is not None:
                                await get_reward_chan.send(f"User {user.mention} successfully get paid {num_format_coin(amount)} {coin_name} for task ID: {str(ref_id)}!")
                        else:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, internal error. Please report!")
                        return
        except ValueError:
            await ctx.edit_original_message(content=f"{ctx.author.mention}, invalid given ref ID **{ref_id}**!")
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @guild_task.sub_command(
        name="complete",
        usage="task complete <ref> <description> <attachment>",
        options=[
            Option('ref_id', 'ref_id', OptionType.number, required=True),
            Option('description', 'description', OptionType.string, required=True),
            Option('image', 'image', OptionType.attachment, required=True)
        ],
        description="Submit your complete task."
    )
    async def task_complete(
        self,
        ctx,
        ref_id: int,
        description: str,
        image: disnake.Attachment
    ):
        await ctx.response.send_message(f"{ctx.author.mention}, loading task ...")
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/task complete", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo is None:
                # Let's add some info if server return None
                await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo['reward_task_channel'] is None:
                await ctx.edit_original_message(
                    content=f"{EMOJI_ERROR} {ctx.author.mention}, please ask Guild Owner to set `/task logchan` first!"
                )
                return
            elif serverinfo['reward_task_channel']:
                channel = self.bot.get_channel(int(serverinfo['reward_task_channel']))
                if channel is None:
                    await ctx.edit_original_message(
                        content=f"{EMOJI_ERROR} {ctx.author.mention}, I could not find log channel for reward task. "\
                            "Please ask admin set it again!"
                    )
                    await log_to_channel(
                        "reward",
                        f"[REWARD TASK] Failed to find log message in guild {ctx.guild.id} / {ctx.guild.name} "\
                        f"during `/task complete` by {ctx.author.mention}!",
                        self.bot.config['discord']['reward_webhook']
                    )
                    return
            # if user already submited
            # if a guild has such task id ongoing or already reached maximum number
            # stored record and save proof,
            # post in assigned channel.
            ref_id = int(ref_id)
            get_task = await self.get_a_task(str(ctx.guild.id), ref_id)
            if get_task is None:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, there's no such task ID **{str(ref_id)}** for this guild!"\
                        " Please check with `/task list`")
                await log_to_channel(
                    "reward",
                    f"[REWARD TASK] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                    f"tried to complete a task reward {str(ref_id)} at guild {ctx.guild.id} / {ctx.guild.name} which not exist!",
                    self.bot.config['discord']['reward_webhook']
                )
                await channel.send(content=f"{ctx.author.mention} tried to complete task ID **{str(ref_id)}** which doesn't exist!")
                return
            else:
                # if he's the owner of task
                if int(get_task['created_by_uid']) == ctx.author.id:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, that's your own task reward in this Guild!")
                    return
                # Check if wrong guild?
                if int(get_task['guild_id']) != ctx.guild.id:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, the task ref {str(ref_id)} is not belong to this Guild!")
                    return

                check_task = await self.get_a_task_completing_user(ref_id, str(ctx.author.id))
                if check_task is not None:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, you already submitted this task completion **{str(ref_id)}** in this Guild!")
                    return

                # if already expired
                if get_task['end_time'] < int(time.time()):
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, task ID **{ref_id}** is already expired!")
                    await channel.send(content=f"{ctx.author.mention} tried to complete task ID **{str(ref_id)}** which was already expired!")
                    return

                # count
                count = await self.get_a_task_completing(ref_id)
                if get_task['number'] != 0 and count >= get_task['number']:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, task **{str(ref_id)}** already reached number of collecting!")
                    return
                # else add
                else:
                    res_data = None
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(str(image), timeout=32) as response:
                                if response.status == 200:
                                    res_data = await response.read()
                                    hash_object = hashlib.sha256(res_data)
                                    hex_dig = str(hash_object.hexdigest())
                                    mime_type = magic.from_buffer(res_data, mime=True)
                                    if mime_type not in self.uploaded_accept:
                                        await ctx.edit_original_message(
                                            content=f"{ctx.author.mention}, the uploaded image is not a supported file.")
                                        return
                                    else:
                                        random_string = str(uuid.uuid4())
                                        saved_name = hex_dig + "_" + random_string + "." + mime_type.split("/")[1]
                                        with open(self.uploaded_storage + saved_name, "wb") as f:
                                            f.write(BytesIO(res_data).getbuffer())
                                        saving = await self.insert_joining(
                                            ref_id, str(ctx.guild.id), str(ctx.author.id), description, saved_name
                                        )
                                        if saving is True:
                                            try:
                                                embed = disnake.Embed(
                                                    title="Reward task submission",
                                                    description=f"{ctx.author.mention} submitted a reward task proof!",
                                                    timestamp=datetime.now(),
                                                )
                                                embed.add_field(
                                                    name="Task #{}".format(ref_id),
                                                    value=get_task['title'],
                                                    inline=False
                                                )
                                                embed.add_field(
                                                    name="Count",
                                                    value=count+1,
                                                    inline=True
                                                )
                                                embed.add_field(
                                                    name="Description",
                                                    value=description[0:800],
                                                    inline=False
                                                )
                                                embed.set_footer(text="By: {}#{} / Guild: {}".format(
                                                    ctx.author.name, ctx.author.discriminator, ctx.guild.name
                                                ))
                                                embed.set_image(url=self.bot.config['reward_task']['url_screenshot'] + saved_name)
                                                await channel.send(content=None, embed=embed)
                                                # DM owner
                                                user = self.bot.get_user(int(get_task['created_by_uid']))
                                                if user is not None:
                                                    link = "https://discord.com/channels/{}/{}".format(
                                                        ctx.guild.id, ctx.channel.id
                                                    )
                                                    try:
                                                        await user.send(content=link, embed=embed)
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                                # Post to channel
                                                await ctx.edit_original_message(
                                                    content=f"{ctx.author.mention}, successfully submitted a task **{str(ref_id)}** in Guild {ctx.guild.name}!")
                                            except disnake.errors.Forbidden:
                                                await ctx.edit_original_message(
                                                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, I have no permission to send embed guild's "\
                                                        "log channel. Please report to this Guild Owner!")
                                                await log_to_channel(
                                                    "reward",
                                                    f"[REWARD TASK] Failed to send log message in guild {ctx.guild.id} / {ctx.guild.name}! Submitted by {ctx.author.mention}.",
                                                    self.bot.config['discord']['reward_webhook']
                                                )
                                                return
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                                await ctx.edit_original_message(
                                                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, internal error. Please report!")
                                                return
                                        else:
                                            await ctx.edit_original_message(
                                                content=f"{ctx.author.mention}, internal error during joining a task **{str(ref_id)}**!")
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except ValueError:
            await ctx.edit_original_message(content=f"{ctx.author.mention}, invalid given ref ID **{ref_id}**!")
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @tasks.loop(seconds=20.0)
    async def check_guild_reward_tasks(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "check_guild_reward_tasks"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        try:
            list_tasks = await self.get_list_tasks("ONGOING")
            if len(list_tasks) > 0:
                # if already expired
                for i in list_tasks:
                    if i['end_time'] < int(time.time()):
                        try:
                            update_status = await self.change_task_status(i['id'])
                            get_unpaid_list = await self.get_non_paid_task_users(i['id'])
                            user_paying = ""
                            if len(get_unpaid_list) > 1:
                                user_paying = f" There are {str(len(get_unpaid_list))} pending users to pay for task ID: **{str(i['id'])}**."
                            elif len(get_unpaid_list) == 1:
                                user_paying = f" There is {str(len(get_unpaid_list))} pending user to pay for task ID: **{str(i['id'])}**."
                            if update_status is True:
                                channel = self.bot.get_channel(int(i['channel_id']))
                                if channel is not None:
                                    try:
                                        await channel.send(f"Task ID: **{str(i['id'])}** - [{i['title']}] expired!{user_paying}")
                                        serverinfo = await store.sql_info_by_server(i['guild_id'])
                                        if serverinfo['reward_task_channel']:
                                            get_log_chan = self.bot.get_channel(int(serverinfo['reward_task_channel']))
                                            if get_log_chan is not None:
                                                await get_log_chan.send(f"Task ID: {str(i['id'])} expired! Currently paid {str(i['num_paid'])} user(s)!{user_paying}")
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_guild_reward_tasks.is_running():
            self.check_guild_reward_tasks.start()

    async def cog_load(self):
        if not self.check_guild_reward_tasks.is_running():
            self.check_guild_reward_tasks.start()

    def cog_unload(self):
        self.check_guild_reward_tasks.cancel()

def setup(bot):
    bot.add_cog(TaskGuild(bot))
