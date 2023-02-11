import sys, traceback

import disnake
from disnake.ext import commands, tasks
from decimal import Decimal
from datetime import datetime
import time
import json
import asyncio
from typing import List

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
import store
from Bot import get_token_list, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, \
    EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, RowButtonCloseMessage, RowButtonRowCloseAnyMessage, human_format, \
    text_to_num, truncate, seconds_str, EMOJI_HOURGLASS_NOT_DONE, EMOJI_INFORMATION, seconds_str_days

from cogs.wallet import WalletAPI
from cogs.utils import Utils, num_format_coin


async def external_get_guild_role_shop_items(guild_id: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_guild_role_shop` 
                WHERE `guild_id`=%s AND `max_slot`>`already_ordered` 
                ORDER BY `created_date` DESC
                """
                await cur.execute(sql, guild_id)
                result = await cur.fetchall()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("gshop " +str(traceback.format_exc()))
    return []

class GShop(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.max_default_guild_item = 5 # max active items to list
        self.max_duration = 180*24*3600 # ~ 6 months
        self.max_ordered_min = 1
        self.max_ordered_max = 1000
        self.botLogChan = None


    async def autocomplete_item_idx(ctx, string: str) -> List[str]:
        if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
            get_guild_items = await external_get_guild_role_shop_items(str(ctx.guild.id))
            if len(get_guild_items) > 0:
                return [each['item_id'] for each in get_guild_items if string.lower() in each['item_id'].lower()]
            else:
                return ["There's no items..."]
        return ["N/A in Direct Message!"]


    @tasks.loop(seconds=30.0)
    async def role_ordered_check(self):
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "role_ordered_check"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return

        try:
            get_active_orders = await self.get_guild_role_ordered_list(0)
            if len(get_active_orders) > 0:
                for each_order in get_active_orders:
                    await self.bot.wait_until_ready() # add one more check..
                    try:
                        guild = self.bot.get_guild(int(each_order['guild_id']))
                        if guild is None:
                            await logchanbot(f"[GSHOP] can not find Guild {str(each_order['guild_id'])}.")
                            continue
                        # re-check if TipBot has manage_roles permission
                        bot_user = guild.get_member(int(self.bot.user.id))
                        if bot_user is None:
                            await logchanbot(f"[GSHOP] can not fetch TipBot's user in Guild {str(each_order['guild_id'])}.")
                            await asyncio.sleep(1.0)
                            continue
                        bot_role_dict = dict(bot_user.guild_permissions)
                        if bot_role_dict['manage_roles'] is False:
                            await logchanbot(f"[GSHOP] TipBot doesn\'t has permission `manage_roles` in Guild `{str(each_order['guild_id'])}`.")
                            continue
                        role = disnake.utils.get(guild.roles, id=int(each_order['role_id']))
                        if role is None:
                            await logchanbot(f"[GSHOP] can not find role id {str(each_order['role_id'])} in Guild {str(each_order['guild_id'])}.")
                            continue
                        member = guild.get_member(int(each_order['ordered_by_uid']))
                        if member is None:
                            await logchanbot(f"[GSHOP] can not find member id {str(each_order['ordered_by_uid'])} in Guild {str(each_order['guild_id'])}.")
                            continue
                        # We found guild and we found role and we found user
                        # Check if expired
                        if int(each_order['expired_date']) < int(time.time()):
                            # Turn expired on
                            # Message User, Message Owner
                            if not role.is_assignable():
                                await logchanbot(f"[GSHOP] TipBot has no permission to assign role `{role.name}` for order `{each_order['item_id']}` in Guild `{each_order['guild_id']}`.")
                                continue
                            if member.roles and role in member.roles:
                                try:
                                    await member.remove_roles(role)
                                    expiring = await self.set_expired_role_item(each_order['id'])
                                    if expiring is True:
                                        try:
                                            await member.send("Your role purchased item_id: `{}` in Guild `{}` is expired.".format(each_order['item_id'], guild.name))
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        try:
                                            await guild.owner.send("User `{}#{}` s' purchased role item_id: `{}` in Guild `{}` is expired.".format(member.name, member.discriminator, each_order['item_id'], guild.name))
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            if member.roles and role not in member.roles:
                                # just set expire if he doesn't have that role
                                try:
                                    expiring = await self.set_expired_role_item(each_order['id'])
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            else:
                                await logchanbot(f"[GSHOP] ERROR to turn expired on for id {str(each_order['id'])}.")
                                continue
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
            else:
                await asyncio.sleep(10.0)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))


    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    async def set_expired_role_item(self, idx: int):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `discord_guild_role_ordered` 
                    SET `is_expired`=1 
                    WHERE `id`=%s 
                    LIMIT 1
                    """
                    await cur.execute(sql, idx)
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("gshop " +str(traceback.format_exc()))
        return False

    async def get_guild_role_shop_items(self, guild_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `discord_guild_role_shop` 
                    WHERE `guild_id`=%s AND `max_slot`>`already_ordered` 
                    ORDER BY `created_date` DESC
                    """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("gshop " +str(traceback.format_exc()))
        return []

    async def get_guild_role_shop_by_item_id(self, item_id: str, guild_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `discord_guild_role_shop` 
                    WHERE `item_id`=%s AND `guild_id`=%s AND `max_slot`>`already_ordered` 
                    LIMIT 1
                    """
                    await cur.execute(sql, (item_id, guild_id))
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("gshop " +str(traceback.format_exc()))
        return None

    async def add_guild_role_shop(
        self, item_id: str, guild_id: str, role_id: str, role_name: str,
        duration: int, token_name: str, token_decimal: int, real_amount: float,
        max_slot: int, already_ordered: int, created_date: int, created_by_uid: str,
        created_by_uname: str
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                        sql = """ INSERT INTO `discord_guild_role_shop` (`item_id`, `guild_id`, 
                        `role_id`, `role_name`, `duration`, `token_name`, `token_decimal`, `real_amount`,
                        `max_slot`, `already_ordered`, `created_date`, `created_by_uid`, `created_by_uname`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """
                        add_arg = [item_id, guild_id, role_id, role_name, 
                                   duration, token_name, token_decimal,
                                   real_amount, max_slot, already_ordered,
                                   created_date, created_by_uid, created_by_uname]
                        await cur.execute(sql, tuple(add_arg))
                        await conn.commit()
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("gshop " +str(traceback.format_exc()))
        return False

    async def delete_guild_role_shop(
        self, item_id: str, guild_id: str, deleted_by_uid: str
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `discord_guild_role_shop` 
                              WHERE `item_id`=%s AND `guild_id`=%s
                              LIMIT 1 """
                    await cur.execute(sql, (item_id, guild_id))
                    result = await cur.fetchone()
                    if result:
                        sql = """ INSERT INTO `discord_guild_role_shop_deleted` (`item_id`, `guild_id`, 
                        `role_id`, `role_name`, `duration`, `token_name`, `token_decimal`, 
                        `real_amount`, `max_slot`, `already_ordered`, `created_date`, 
                        `created_by_uid`, `created_by_uname`, `deleted_date`, `deleted_by_uid`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """
                        delete_arg = [item_id, guild_id, result['role_id'], result['role_name'], 
                                      result['duration'], result['token_name'], result['token_decimal'],
                                      result['real_amount'], result['max_slot'], result['already_ordered'],
                                      result['created_date'], result['created_by_uid'], result['created_by_uname'],
                                      int(time.time()), deleted_by_uid]
                        sql += """ DELETE FROM `discord_guild_role_shop` 
                        WHERE `item_id`=%s LIMIT 1;
                        """
                        delete_arg += [item_id]
                        await cur.execute(sql, tuple(delete_arg))
                        await conn.commit()
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("gshop " +str(traceback.format_exc()))
        return False

    async def get_guild_role_ordered_list(self, is_expired: int):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `discord_guild_role_ordered` 
                              WHERE `is_expired`=%s 
                              ORDER BY `ordered_date` DESC """
                    await cur.execute(sql, is_expired)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("gshop " +str(traceback.format_exc()))
        return []

    async def check_exist_role_ordered(
        self, item_id, guild_id, ordered_by_uid, is_expired
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `discord_guild_role_ordered` 
                              WHERE `item_id`=%s AND `guild_id`=%s AND `ordered_by_uid`=%s AND `is_expired`=%s 
                              LIMIT 1 """
                    await cur.execute(sql, (item_id, guild_id, ordered_by_uid, is_expired))
                    result = await cur.fetchone()
                    if result:
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("gshop " +str(traceback.format_exc()))
        return False

    async def check_exist_role_item_id(self, item_id, guild_id):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `discord_guild_role_shop` 
                    WHERE `item_id`=%s AND `guild_id`=%s 
                    LIMIT 1
                    """
                    await cur.execute(sql, (item_id, guild_id))
                    result = await cur.fetchone()
                    if result:
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("gshop " +str(traceback.format_exc()))
        return False

    async def guild_role_ordered(
        self, role_shop_id: int, role_shop_json: str, item_id: str, guild_id: str, role_id: str,
        acc_real_amount: float, token_name: str, token_decimal: int,
        ordered_by_uid: str, ordered_by_uname: str, renewed_date: int,
        expired_date: int, is_expired: int
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `discord_guild_role_ordered` (`role_shop_id`, `role_shop_json`, `item_id`, 
                    `guild_id`, `role_id`, `acc_real_amount`, `token_name`, `token_decimal`, `ordered_by_uid`, 
                    `ordered_by_uname`, `ordered_date`, `renewed_date`, `expired_date`, `is_expired`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (
                        role_shop_id, role_shop_json, item_id, guild_id, role_id, 
                        acc_real_amount, token_name, token_decimal,
                        ordered_by_uid, ordered_by_uname, int(time.time()),
                        renewed_date, expired_date, is_expired)
                    )
                    sql_2 = """
                    UPDATE `discord_guild_role_shop` 
                    SET `already_ordered`=`already_ordered`+1 
                    WHERE `id`=%s 
                    LIMIT 1
                    """
                    await cur.execute(sql_2, role_shop_id)
                    await conn.commit()
                    return True	
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("gshop " +str(traceback.format_exc()))
        return False

    @commands.guild_only()
    @commands.slash_command(
        dm_permission=False,
        name="gshop",
        description="Guild shop's commands."
    )
    async def gshop(self, ctx):
        await self.bot_log()

    @commands.bot_has_permissions(send_messages=True)
    @commands.has_permissions(manage_channels=True)
    @gshop.sub_command(
        name="delete",
        usage="gshop delete <item id>",
        description="Delete an item from Guild's shop.")
    async def slash_delete(
        self,
        ctx,
        item_id: str = commands.Param(autocomplete=autocomplete_item_idx)
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /gshop loading..."
        await ctx.response.send_message(msg)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/gshop delete", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        try:
            # if enable_role_shop is on/off
            if serverinfo and serverinfo['enable_role_shop'] == 0:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, role shop is disable in this Guild. "\
                    f"Contact TipBot\'s dev."
                await ctx.edit_original_message(content=msg)
                await logchanbot(
                    f"[GSHOP] User `{str(ctx.author.id)}` in Guild `{str(ctx.guild.id)}` tried with /gshop which disable in their Guild."
                )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)

        item_info = await self.get_guild_role_shop_by_item_id(item_id, str(ctx.guild.id))
        if item_info is None:
            msg = f"{ctx.author.mention}, item_id `{item_id}` not exist!"
            await ctx.edit_original_message(content=msg)
        else:
            delete_item = await self.delete_guild_role_shop(item_id, str(ctx.guild.id), str(ctx.author.id))
            if delete_item is True:
                msg = f"{ctx.author.mention}, successfully removed listing `{item_id}` from this guild!"
                await ctx.edit_original_message(content=msg)
                await logchanbot(
                    f"[GSHOP] server {str(ctx.guild.id)}, user `{str(ctx.author.id)}` removed item `{item_id}`."
                )
                if ctx.author.id != ctx.guild.owner.id:
                    await ctx.guild.owner.send(
                        f"User `{str(ctx.author.id)}` just removed listing item `{item_id}` "\
                        f"from Guild `{str(ctx.guild.id)} / {ctx.guild.name}`."
                    )
            else:
                msg = f"{ctx.author.mention}, internal error when deleting! Please report!"
                await ctx.edit_original_message(content=msg)
                await logchanbot(f"[GSHOP] server {str(ctx.guild.id)}, user `{str(ctx.author.id)}` failed to remove item `{item_id}`.")

    @commands.bot_has_permissions(send_messages=True)
    @gshop.sub_command(
        name="buyrole",
        usage="gshop buyrole <item id>",
        description="Buy a role using your wallet balance."
    )
    async def slash_buyrole(
        self,
        ctx,
        item_id: str = commands.Param(autocomplete=autocomplete_item_idx)
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /gshop loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/gshop buyrole", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        try:
            # if enable_role_shop is on/off
            if serverinfo and serverinfo['enable_role_shop'] == 0:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, role shop is disable in this Guild. "\
                    "Contact TipBot's dev."
                await ctx.edit_original_message(content=msg)
                await logchanbot(
                    f"[GSHOP] User `{str(ctx.author.id)}` in Guild `{str(ctx.guild.id)}` tried with /gshop which disable in their Guild."
                )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            # get item_id
            item_id = item_id.lower()
            item_info = await self.get_guild_role_shop_by_item_id(item_id, str(ctx.guild.id))
            if item_info is None:
                msg = f"{ctx.author.mention}, item_id `{item_id}` not exist!"
                await ctx.edit_original_message(content=msg)
            else:
                # Check if out of stock
                if item_info['already_ordered'] >= item_info['max_slot']:
                    msg = f"{ctx.author.mention}, item_id `{item_id}` is out of stock already!"
                    await ctx.edit_original_message(content=msg)
                    return
                # check if user has that role already
                role_name = item_info['role_name']
                coin_name = item_info['token_name']
                coin_decimal = item_info['token_decimal']
                net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")
                token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                amount = item_info['real_amount']

                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
                )
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
                    )

                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                elif type_coin in ["XRP"]:
                    wallet_address = get_deposit['destination_tag']

                height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                member = ctx.guild.get_member(int(ctx.author.id))
                try:
                    role = disnake.utils.get(ctx.guild.roles, id=int(item_info['role_id']))
                    if role is None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I can not find role `{role_name}`, "\
                            f"please try again later or report to Guild owner!"
                        await ctx.edit_original_message(content=msg)
                        await logchanbot(
                            f"[GSHOP] server {str(ctx.guild.id)}, can not find role `{role_name}`."
                        )
                        return
                    elif role and not role.is_assignable():
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, role `{role.name}` is no assignable "\
                            "by TipBot or TipBot has no permission to do! Please report to Guild owner!"
                        await ctx.edit_original_message(content=msg)
                        return
                    elif role and role in member.roles:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have role `{role.name}` already. "\
                            f"Purchase item_id `{item_id}` denied!"
                        await ctx.edit_original_message(content=msg)
                        await logchanbot(
                            f"[GSHOP] denied purchasing `{role.name}` in Guild `{str(ctx.guild.id)} / "\
                            f"{ctx.guild.name}` by user `{str(ctx.author.id)}` (He/she has it already)."
                        )
                        return
                    # re-check if role can kick/ban
                    role_dict = dict(role.permissions)
                    if role_dict['kick_members'] is True or role_dict['ban_members'] is True or role_dict['manage_channels'] is True:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you cannot purchase role which can kick/ban users!"
                        await ctx.edit_original_message(content=msg)
                        await logchanbot(
                            f"[GSHOP] denied purchasing `{role.name}` which can kick/ban users "\
                            f"in Guild `{str(ctx.guild.id)} / {ctx.guild.name}`."
                        )
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, internal error!"
                    await ctx.edit_original_message(content=msg)
                    return
                # Check if user's having that item and still not expired yet.
                check_item = await self.check_exist_role_ordered(item_id, str(ctx.guild.id), str(ctx.author.id), 0)
                if check_item is True:
                    # check if user role removed for some reason.
                    if role in member.roles:
                        msg = f"{ctx.author.mention}, you still have item_id `{item_id}` and not expired yet!"
                        await ctx.edit_original_message(content=msg)
                    else:
                        await member.add_roles(role)
                        msg = f"{ctx.author.mention}, you still have item_id `{item_id}` and not expired yet "\
                            f"but role is not with you. We added `{role.name}` back to you."
                        await ctx.edit_original_message(content=msg)
                        await logchanbot(
                            f"[GSHOP] added role `{role.name}` back to User `{str(ctx.author.id)}` "\
                            f"Guild `{str(ctx.guild.id)} / {ctx.guild.name}`. Item `{item_id}` not expired yet."
                        )
                    return

                # Check if stocks already
                if item_info and item_info['max_slot'] <= item_info['already_ordered']:
                    msg = f"{ctx.author.mention}, item_id `{item_id}` is out of stock already!"
                    await ctx.edit_original_message(content=msg)
                else:
                    # still have stock
                    # check balance
                    userdata_balance = await store.sql_user_balance_single(
                        str(ctx.author.id), coin_name, wallet_address, type_coin,
                        height, deposit_confirm_depth, SERVER_BOT
                    )
                    actual_balance = float(userdata_balance['adjust'])
                if amount > actual_balance:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to do purchase "\
                        f"`{role.name}` which cost **{num_format_coin(amount)} "\
                        f"{token_display}**."
                    await ctx.edit_original_message(content=msg)
                else:
                    # purchase and add to database
                    renewed_date = int(time.time()) + item_info['duration']
                    expired_date = renewed_date
                    purchase = await self.guild_role_ordered(
                        item_info['id'], json.dumps(item_info), item_info['item_id'], str(ctx.guild.id),
                        item_info['role_id'], amount, coin_name, coin_decimal,
                        str(ctx.author.id), "{}#{}".format(ctx.author.name, ctx.author.discriminator),
                        renewed_date, expired_date, 0
                    )
                    if purchase is True:
                        # 1) Deduct balance
                        # 2) Assign Role
                        # 3) Log?
                        real_amount_usd = 0
                        if usd_equivalent_enable == 1:
                            try:
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
                                    real_amount_usd = float(Decimal(amount) * Decimal(per_unit))
                            except Exception:
                                traceback.print_exc(file=sys.stdout)

                        try:
                            key_coin = str(ctx.guild.id) + "_" + coin_name + "_" + SERVER_BOT
                            if key_coin in self.bot.user_balance_cache:
                                del self.bot.user_balance_cache[key_coin]

                            key_coin = str(ctx.author.id) + "_" + coin_name + "_" + SERVER_BOT
                            if key_coin in self.bot.user_balance_cache:
                                del self.bot.user_balance_cache[key_coin]
                        except Exception:
                            pass
                        move_balance = await store.sql_user_balance_mv_single(
                            str(ctx.author.id), str(ctx.guild.id), str(ctx.guild.id),
                            str(ctx.channel.id), amount, coin_name, "GSHOP",
                            coin_decimal, SERVER_BOT, contract, real_amount_usd, None
                        )
                        if move_balance is True:
                            # Assign role
                            await member.add_roles(role)
                            duration = seconds_str_days(item_info['duration'])
                            cost = "{} {}".format(num_format_coin(amount), coin_name)
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, successfully purchased item "\
                                f"`{item_id}` for `{cost}` with role `{role.name}` for period {duration}!"
                            await ctx.edit_original_message(content=msg)
                            # Try DM guild owner
                            await logchanbot(
                                f"[GSHOP] user `{str(ctx.author.id)}` has successfully purchased `{item_id}` in "\
                                f"Guild `{str(ctx.guild.id)} / {ctx.guild.name}`. Guild's credit added: `{cost}`."
                            )
                            try:
                                await ctx.guild.owner.send(
                                    f"User `{str(ctx.author.id)}` just purchased role item `{item_id}` in "\
                                    f"Guild `{str(ctx.guild.id)} / {ctx.guild.name}` with amount `{amount} {coin_name}` "\
                                    f"credit to Guild's wallet."
                                )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                        else:
                            await logchanbot(
                                f"[GSHOP] failed to move balance of purchase role `{item_id}` in "\
                                f"Guild `{str(ctx.guild.id)} / {ctx.guild.name}` by user `{str(ctx.author.id)}`."
                            )
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, internal error. Please report!"
                            await ctx.edit_original_message(content=msg)
                    else:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, internal error. Please report!"
                        await ctx.edit_original_message(content=msg)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.bot_has_permissions(send_messages=True)
    @commands.has_permissions(manage_channels=True)
    @gshop.sub_command(
        name="addrole",
        usage="gshop addrole <role_name> <amount> <token> <duration>",
        options=[
            Option('role_name', 'Role to give', OptionType.role, required=True),
            Option('stocks', 'Available for orders', OptionType.number, required=True),
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token or coin name', OptionType.string, required=True),
            Option('duration', 'duration', OptionType.string, required=True, choices=[
                OptionChoice("3d", "3d"),
                OptionChoice("7d", "7d"),
                OptionChoice("30d", "30d")
            ]),
        ],
        description="Add a role to Guild Shop for anyone to purchase."
    )
    async def slash_addrole(
        self,
        ctx,
        role_name: disnake.Role,
        stocks: int,
        amount: str,
        token: str,
        duration: str
    ):
        coin_name = token.upper()
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /gshop loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/gshop addrole", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # Token name check
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
            await ctx.edit_original_message(content=msg)
            return
        # End token name check

        # Check if Bot has managed_role permission
        bot_user = ctx.guild.get_member(int(self.bot.user.id))
        bot_role_dict = dict(bot_user.guild_permissions)
        if bot_role_dict['manage_roles'] is False:
            msg = f"{ctx.author.mention}, TipBot doesn't has permission `manage_roles`! "\
                "Please adjust permission and try again!"
            await ctx.edit_original_message(content=msg)
            await logchanbot(
                f"[GSHOP] User `{str(ctx.author.id)}` tried to add sell role in `{str(ctx.guild.id)}` "\
                "but TipBot has no `manage_roles` permission!"
            )
            return

        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")
        min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
        max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")

        # If $ is in amount, let's convert to coin/token
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
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount."
                await ctx.edit_original_message(content=msg)
                return

        if amount <= 0:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, please put amount correctly!"
            await ctx.edit_original_message(content=msg)
            return

        if amount > max_tip or amount < min_tip:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention} amount cannot be bigger than "\
                f"**{num_format_coin(max_tip)} {token_display}** "\
                f"or smaller than **{num_format_coin(min_tip)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return

        stocks = int(stocks)
        if stocks < self.max_ordered_min or stocks > self.max_ordered_max:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, `stocks` must be between "\
                f"{str(self.max_ordered_min)} and {str(self.max_ordered_max)}!"
            await ctx.edit_original_message(content=msg)
            return

        # Check if role is assignable by bot
        try:
            role = disnake.utils.get(ctx.guild.roles, name=role_name.name)
            if not role.is_assignable():
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, role `{role_name.name}` is no assignable "\
                    "by TipBot or TipBot has no permission to do!"
                await ctx.edit_original_message(content=msg)
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, internal error!"
            await ctx.edit_original_message(content=msg)
            return

        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        get_guild_items = await self.get_guild_role_shop_items(str(ctx.guild.id))
        try:
            # if enable_role_shop is on/off
            if serverinfo and serverinfo['enable_role_shop'] == 0:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, role shop is disable in this Guild. "\
                    f"Contact TipBot's dev."
                await ctx.edit_original_message(content=msg)
                await logchanbot(
                    f"[GSHOP] User `{str(ctx.author.id)}` in Guild `{str(ctx.guild.id)}` "\
                    f"tried with /gshop which disable in their Guild."
                )
                return
            # Check max if set in guild
            if serverinfo and len(get_guild_items) >= serverinfo['max_role_shop_items'] and \
                ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, there are maximum number of "\
                    "role items listed already!"
                await ctx.edit_original_message(content=msg)
                return
            elif serverinfo is None and len(get_guild_items) >= self.max_default_guild_item and \
                ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, there are maximum number of role "\
                    "items listed already!"
                await ctx.edit_original_message(content=msg)
                await logchanbot(f"[GSHOP] server {str(ctx.guild.id)} has no data in discord_server.")
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        item_id = role_name.name + "/" + token + "/" + duration + "/" + str(amount) + "-" + coin_name
        item_id = item_id.lower()
        check_exist = await self.check_exist_role_item_id(item_id, str(ctx.guild.id))
        if check_exist is True:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, duplicated data `{item_id}`. "\
                f"Try with a different token or different `stocks` OR delete item_id `{item_id}`!"
            await ctx.edit_original_message(content=msg)
            return

        duration = int(duration.replace("d", "")) * 86400
        if duration < 86400 or duration > self.max_duration:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, internal error!"
            await ctx.edit_original_message(content=msg)
            return

        # Check if role can kick/ban. Avoid that
        try:
            role_dict = dict(role.permissions)
            if role_dict['kick_members'] is True or role_dict['ban_members'] is True or role_dict['manage_channels'] is True:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you cannot sell role which can kick/ban users!"
                await ctx.edit_original_message(content=msg)
                await logchanbot(
                    f"[GSHOP] wanted to list role `{role.name}` which can kick/ban "\
                    "users in Guild `{str(ctx.guild.id)} / {ctx.guild.name}`."
                )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)

        add_listing = await self.add_guild_role_shop(
            item_id, str(ctx.guild.id), role_name.id, 
            role_name.name, duration, coin_name,
            coin_decimal, amount, stocks, 0, int(time.time()),
            str(ctx.author.id), "{}#{}".format(ctx.author.name, ctx.author.discriminator)
        )
        if add_listing is True:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, new item listed item_id: `{item_id}`."
            await ctx.edit_original_message(content=msg)
            await logchanbot(f"[GSHOP] new item added `{item_id}` in Guild `{str(ctx.guild.id)} / {ctx.guild.name}`.")
            if ctx.author.id != ctx.guild.owner.id:
                await ctx.guild.owner.send(
                    f"User `{str(ctx.author.id)}` just add a listing item `{item_id}` to sell in "\
                    f"Guild `{str(ctx.guild.id)} / {ctx.guild.name}` for role `{role.name}`."
                )
        else:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, internal error!"
            await ctx.edit_original_message(content=msg)
            await logchanbot(
                f"[GSHOP] item added failed `{item_id}` in Guild `{str(ctx.guild.id)} / {ctx.guild.name}`."
            )

    @slash_addrole.autocomplete("token")
    async def quickdrop_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

    @commands.bot_has_permissions(send_messages=True)
    @gshop.sub_command(
        name="rolelist",
        usage="gshop rolelist",
        description="List all available roles on Guild's store."
    )
    async def slash_rolelist(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /gshop loading..."
        await ctx.response.send_message(msg)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/gshop rolelist", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        try:
            # if enable_role_shop is on/off
            if serverinfo and serverinfo['enable_role_shop'] == 0:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, role shop is disable in this Guild. "\
                    "Contact TipBot\'s dev."
                await ctx.edit_original_message(content=msg)
                await logchanbot(
                    f"[GSHOP] User `{str(ctx.author.id)}` in Guild `{str(ctx.guild.id)}` tried with "\
                    f"/gshop which disable in their Guild."
                )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)

        get_guild_items = await self.get_guild_role_shop_items(str(ctx.guild.id))
        if len(get_guild_items) == 0:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, there is no role to buy yet! "\
                f"Check again later or request Guild\'s admin."
            await ctx.edit_original_message(content=msg)
        else:
            embed = disnake.Embed(
                title=f"Role Shop List in {ctx.guild.name}",
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator} | /gshop")
            for each in get_guild_items:
                duration = int(each['duration']/3600/24)
                coin_emoji = ""
                try:
                    if ctx.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is True:
                        coin_emoji = getattr(getattr(self.bot.coin_list, each['token_name']), "coin_emoji_discord")
                        coin_emoji = coin_emoji + " " if coin_emoji else ""
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                embed.add_field(
                    name="{}".format(each['item_id']),
                    value="Role: {}\nCost: {}{} {}\nAvailable/Total: {}/{}".format(
                        each['role_name'], coin_emoji, num_format_coin(each['real_amount']), each['token_name'],
                        each['max_slot'] - each['already_ordered'], each['max_slot']),
                    inline=False
                )
            await ctx.edit_original_message(content=None, embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.role_ordered_check.is_running():
                self.role_ordered_check.start()

    async def cog_load(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.role_ordered_check.is_running():
                self.role_ordered_check.start()

    def cog_unload(self):
        # Ensure the task is stopped when the cog is unloaded.
        self.role_ordered_check.cancel()


def setup(bot):
    bot.add_cog(GShop(bot))
