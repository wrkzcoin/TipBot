import asyncio

import sys
import time
import traceback
from datetime import datetime
import random
import json

import uuid
from decimal import Decimal
import timeago
import disnake
from disnake.ext import tasks, commands

from cachetools import TTLCache

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
from discord_webhook import AsyncDiscordWebhook

import store
from Bot import get_token_list, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_INFORMATION, \
    EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, RowButtonCloseMessage, \
    RowButtonRowCloseAnyMessage, human_format, text_to_num, truncate, \
    NOTIFICATION_OFF_CMD, DEFAULT_TICKER, seconds_str, seconds_str_days
from cogs.wallet import WalletAPI
from cogs.utils import MenuPage
from cogs.utils import Utils, num_format_coin


class Guild(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.botLogChan = None
        self.enable_logchan = True

        # /featurerole
        self.max_featurerole = 6

        # DB
        self.pool = None
        self.ttlcache = TTLCache(maxsize=4096, ttl=60.0)

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)


    async def get_faucet_claim_user_guild(self, userId: str, guild_id: str, user_server: str="DISCORD"):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `user_balance_mv` 
                              WHERE `from_userid`=%s AND `to_userid`= %s AND `type`=%s AND `user_server`=%s 
                              ORDER BY `date` DESC LIMIT 1 """
                    await cur.execute(sql, ( guild_id, userId, "GUILDFAUCET", user_server))
                    result = await cur.fetchone()
                    if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("guild " +str(traceback.format_exc()))
        return None

    @tasks.loop(seconds=60.0)
    async def check_tiptalker_drop(self):
        time_lap = 10 # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "guild_check_tiptalker_drop"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            # Get list active drop in guilds
            list_activedrop = await self.get_activedrop()
            if len(list_activedrop) > 0:
                for each_drop in list_activedrop:
                    coin_name = each_drop['tiptallk_coin']
                    if not hasattr(self.bot.coin_list, coin_name):
                        continue
                    net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                    type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                    deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                    token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                    price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                    key = "guild_activedrop_{}".format( each_drop['serverid'] )
                    try:
                        if self.ttlcache[key] == key:
                            continue # next
                        else:
                            self.ttlcache[key] = key
                    except Exception:
                        pass
                    lap_str = seconds_str_days( each_drop['tiptalk_duration'] )
                    get_guild = self.bot.get_guild(int(each_drop['serverid']))
                    get_channel = self.bot.get_channel( int(each_drop['tiptalk_channel']) )
                    if get_guild is None:
                        continue
                    if get_channel is None:
                        continue
                    try:
                        get_bot = get_guild.get_member( self.bot.user.id )
                        if not get_bot.guild_permissions.send_messages:
                            await logchanbot(
                                f"[ACTIVEDROP] in guild {get_guild.name} / {str(get_guild.id)} "\
                                "I have no permission to send message. Skipped."
                            )
                            continue
                    except Exception:
                        traceback.print_exc(file=sys.stdout)

                    # check last drop
                    last_drop = await self.get_last_activedrop_guild( each_drop['serverid'] )
                    role = None
                    if last_drop is None or \
                        (last_drop is not None and int(time.time()) - last_drop['spread_time'] >= each_drop['tiptalk_duration']):
                        # let's spread tiptalker
                        additional_time = 0
                        if last_drop is not None and 300 > int(time.time()) - last_drop['spread_time'] - each_drop['tiptalk_duration'] > 0:
                            additional_time = int(time.time()) - last_drop['spread_time'] - each_drop['tiptalk_duration']
                        message_talker = await store.sql_get_messages(
                            each_drop['serverid'], each_drop['tiptalk_channel'],
                            each_drop['tiptalk_duration'] + additional_time, None
                        )
                        msg = ""
                        msg_no_embed = ""
                        list_receivers = []
                        if len(message_talker) == 0:
                            # Tell, there is 0 tip talkers..
                            msg = f"There is 0 active talkers in the last {lap_str}."
                        else:
                            if each_drop['tiptalk_role_id'] is not None:
                                role = disnake.utils.get(get_guild.roles, id=int(each_drop['tiptalk_role_id']))

                            # Check guild's balance
                            get_deposit = await self.wallet_api.sql_get_userwallet(
                                each_drop['serverid'], coin_name, net_name, type_coin, SERVER_BOT, 0
                            )
                            if get_deposit is None:
                                get_deposit = await self.wallet_api.sql_register_user(
                                    each_drop['serverid'], coin_name, net_name, type_coin, SERVER_BOT, 0, 1
                                )

                            wallet_address = get_deposit['balance_wallet_address']
                            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                wallet_address = get_deposit['paymentid']
                            elif type_coin in ["XRP"]:
                                wallet_address = get_deposit['destination_tag']

                            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                            userdata_balance = await self.wallet_api.user_balance(
                                each_drop['serverid'], coin_name, 
                                wallet_address, type_coin, height, 
                                deposit_confirm_depth, SERVER_BOT
                            )
                            actual_balance = float(userdata_balance['adjust'])
                            
                            if actual_balance < float(each_drop['tiptalk_amount']):
                                msg = f"Guild {get_guild.name} runs out of {coin_name}'s balance. "\
                                    f"Please deposit with {self.bot.config['command_list']['guild_deposit']} command."
                                msg_no_embed = msg
                                await logchanbot(
                                    f"[ACTIVEDROP] in guild {get_guild.name} / {get_guild.id} runs out of {coin_name} balance."
                                )
                                # add to DB
                                await self.insert_new_activedrop_guild(
                                    each_drop['serverid'], get_guild.name, 
                                    each_drop['tiptalk_channel'], coin_name, 
                                    coin_decimal, 0.0, 0.0, 0, None, None, int(time.time())
                                )
                            else:
                                list_receiver_names = []
                                for member_id in message_talker:
                                    try:
                                        member = get_guild.get_member( int(member_id) )
                                        if (member and member in get_guild.members and role and hasattr(member, "roles") \
                                            and role in member.roles) or (role is None and member and member in get_guild.members):
                                            user_to = await self.wallet_api.sql_get_userwallet(
                                                str(member_id), coin_name, net_name, type_coin, SERVER_BOT, 0
                                            )
                                            if user_to is None:
                                                user_to = await self.wallet_api.sql_register_user(
                                                    str(member_id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                                                )
                                            try:
                                                list_receivers.append(str(member_id))
                                                list_receiver_names.append("{}#{}".format(member.name, member.discriminator))
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                                await logchanbot("guild " +str(traceback.format_exc()))
                                                print('Failed creating wallet for activedrop for userid: {}'.format(member_id))
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot("guild " +str(traceback.format_exc()))
                                if len(list_receivers) == 0:
                                    msg = f"There is 0 active talkers in the last {lap_str}."
                                    # add to DB
                                    await self.insert_new_activedrop_guild(
                                        each_drop['serverid'], get_guild.name, each_drop['tiptalk_channel'], coin_name,
                                        coin_decimal, each_drop['tiptalk_amount'], each_drop['tiptalk_amount'],
                                        len(list_receivers), None, None, int(time.time())
                                    )
                                    # No need to message, just pass
                                    continue
                                else:
                                    equivalent_usd = ""
                                    amount_in_usd = 0.0
                                    amount = each_drop['tiptalk_amount']/len(list_receivers)
                                    if price_with:
                                        per_unit = await self.utils.get_coin_price(coin_name, price_with)
                                        if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                            per_unit = per_unit['price']
                                            amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                                            if amount_in_usd > 0.0001:
                                                equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
                                    try:
                                        # re-check last drop
                                        last_drop_recheck = await self.get_last_activedrop_guild( each_drop['serverid'] )
                                        if last_drop_recheck is not None and int(time.time()) - last_drop_recheck['spread_time'] < 60:
                                            continue
                                        # add to DB
                                        await self.insert_new_activedrop_guild(
                                            each_drop['serverid'], get_guild.name, each_drop['tiptalk_channel'],
                                            coin_name, coin_decimal, each_drop['tiptalk_amount'],
                                            each_drop['tiptalk_amount']/len(list_receivers), len(list_receivers),
                                            json.dumps(list_receivers), json.dumps(list_receiver_names), int(time.time())
                                        )

                                        tiptalk = await store.sql_user_balance_mv_multiple(
                                            each_drop['serverid'], list_receivers, each_drop['serverid'],
                                            each_drop['tiptalk_channel'], each_drop['tiptalk_amount']/len(list_receivers),
                                            coin_name, "TIPTALK", coin_decimal, SERVER_BOT, contract, float(amount_in_usd), None
                                        )
                                        list_mentioned = [f"<@{each}>" for each in list_receivers]
                                        msg = ", ".join(list_mentioned) + f" active talker(s) in the last {lap_str}."
                                        each_msg = "each"
                                        if len(list_mentioned) == 1:
                                            each_msg = "alone"
                                        msg_no_embed = ", ".join(list_receiver_names) + " got {} {} {}. Next drop in {}.".format(
                                            num_format_coin(
                                                each_drop['tiptalk_amount']/len(list_receivers) if len(list_receivers) > 0 else each_drop['tiptalk_amount']
                                            ),
                                            coin_name,
                                            each_msg,
                                            seconds_str(each_drop['tiptalk_duration'])
                                        )
                                        if len(msg) > 999:
                                            verb = "is"
                                            if len(list_receivers) > 0:
                                                verb = "are"
                                            msg = f"There {verb} {str(len(list_receivers))} active talker(s) in the last {lap_str}."
                                            msg_no_embed = msg + " Each got {} {}. Next drop in {}. "\
                                                "You can disable it by /tiptalker and set amount 0.".format(num_format_coin(
                                                    each_drop['tiptalk_amount']/len(list_receivers) if len(list_receivers) > 0 else each_drop['tiptalk_amount']
                                                ),
                                                coin_name,
                                                seconds_str(each_drop['tiptalk_duration'])
                                            )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot("guild " +str(traceback.format_exc()))
                        if len(msg) > 0:
                            try:
                                coin_emoji = ""
                                if get_guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is True:
                                    coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                                    coin_emoji = coin_emoji + " " if coin_emoji else ""
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            embed = disnake.Embed(
                                title = "ACTIVEDROP/TALKER {}".format( get_guild.name ),
                                description="Keep on chatting in <#{}>".format(each_drop['tiptalk_channel']),
                                timestamp=datetime.now()
                            )
                            embed.add_field(
                                name="RECEIVER(s): {}".format(len(list_receivers)),
                                value=msg,
                                inline=False
                            )
                            embed.add_field(
                                name="TOTAL",
                                value="{}{} {}".format(
                                    coin_emoji, num_format_coin(each_drop['tiptalk_amount']), coin_name
                                ),
                                inline=False
                            )
                            embed.add_field(
                                name="EACH",
                                value="{}{} {}".format(
                                    coin_emoji,
                                    num_format_coin(
                                        each_drop['tiptalk_amount']/len(list_receivers) if len(list_receivers) > 0 else each_drop['tiptalk_amount']
                                    ), 
                                    coin_name
                                ),
                                inline=False
                            )
                            if each_drop['tiptalk_role_id'] and role:
                                embed.add_field(name="ROLE", value=role.name, inline=False)
                            embed.add_field(
                                name="NEXT DROP",
                                value="<t:{}:f>".format(int(time.time()) + each_drop['tiptalk_duration']),
                                inline=False
                            )
                            if len(coin_emoji) > 0:
                                extension = ".png"
                                if coin_emoji.startswith("<a:"):
                                    extension = ".gif"
                                split_id = coin_emoji.split(":")[2]
                                link = 'https://cdn.discordapp.com/emojis/' + str(split_id.replace(">", "")).strip() + extension
                                embed.set_thumbnail(url=link)
                            embed.set_footer(text="You can disable it by /tiptalker and set amount 0.")
                            if get_channel and len(list_receivers) > 0:
                                try:
                                    await get_channel.send(embed=embed)
                                    await logchanbot(
                                        f"[ACTIVEDROP] in guild {get_guild.name} / {get_guild.id} to {str(len(list_receivers))} "\
                                        f"for total of {num_format_coin(each_drop['tiptalk_amount'])} {coin_name}."
                                    )
                                except disnake.errors.Forbidden:
                                    try:
                                        await get_channel.send(content=msg_no_embed)
                                        await logchanbot(
                                            f"[ACTIVEDROP] in guild {get_guild.name} / {get_guild.id} to {str(len(list_receivers))} "\
                                            f"for total of {num_format_coin(each_drop['tiptalk_amount'])} {coin_name}."
                                        )
                                    except disnake.errors.Forbidden:
                                        await logchanbot(
                                            f"🔴 [ACTIVEDROP] in guild {get_guild.name} / {get_guild.id} to {str(len(list_receivers))} "\
                                            f" - No permission to send embed / message. Disable talkdrop."
                                        )
                                        update_tiptalk = await self.update_activedrop(str(get_guild.id), 0.0, None, None, None, None)
                                        await get_guild.owner.send(
                                            "I have no permission to send text/embed in your assigned channel for `talkdrop`. Hence, it's disable now!"
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    # Check if guild has at least 10x amount of reward or disable
    @tasks.loop(seconds=60.0)
    async def monitor_guild_reward_amount(self):
        time_lap = 10 # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "guild_monitor_guild_reward_amount"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_server` WHERE `vote_reward_amount`>0
                    """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each_guild in result:
                            coin_name = each_guild['vote_reward_coin']
                            if not hasattr(self.bot.coin_list, coin_name):
                                # skip
                                continue
                            # Check guild's balance
                            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                            get_deposit = await self.wallet_api.sql_get_userwallet(
                                each_guild['serverid'], coin_name, net_name, type_coin, SERVER_BOT, 0
                            )
                            if get_deposit is None:
                                get_deposit = await self.wallet_api.sql_register_user(
                                    each_guild['serverid'], coin_name, net_name, type_coin, SERVER_BOT, 0, 1
                                )

                            wallet_address = get_deposit['balance_wallet_address']
                            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                wallet_address = get_deposit['paymentid']
                            elif type_coin in ["XRP"]:
                                wallet_address = get_deposit['destination_tag']

                            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                            userdata_balance = await self.wallet_api.user_balance(
                                each_guild['serverid'], coin_name, 
                                wallet_address, type_coin, height, 
                                deposit_confirm_depth, SERVER_BOT
                            )
                            actual_balance = float(userdata_balance['adjust'])
                            if actual_balance < 10*float(each_guild['vote_reward_amount']):
                                amount = 10*float(each_guild['vote_reward_amount'])
                                # Disable it
                                # Process, only guild owner can process
                                update_reward = await self.update_reward(each_guild['serverid'], actual_balance, coin_name, True, None)
                                if update_reward > 0:
                                    try:
                                        guild_found = self.bot.get_guild(int(each_guild['serverid']))
                                        user_found = self.bot.get_user(guild_found.owner.id)
                                        if user_found is not None:
                                            await user_found.send(
                                                f"Currently, your guild's balance of {coin_name} is lower than 10x reward: "\
                                                f"{num_format_coin(amount)} {coin_name}. "\
                                                f"Vote reward is disable."
                                            )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    await self.vote_logchan(f"[{SERVER_BOT}] Disable vote reward for {guild_found.name} / "\
                                        f"{guild_found.id}. Guild\'s balance below 10x: "\
                                        f"{num_format_coin(amount)} {coin_name}."
                                    )
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    async def guild_exist_featurerole(self, guild_id: str, role_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `discord_feature_roles` 
                    WHERE `guild_id`=%s AND `role_id`=%s 
                    LIMIT 1
                    """
                    await cur.execute(sql, (guild_id, role_id))
                    result = await cur.fetchone()
                    if result:
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def guild_delete_featurerole(self, guild_id: str, role_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ DELETE FROM `discord_feature_roles` 
                    WHERE `guild_id`=%s AND `role_id`=%s 
                    LIMIT 1
                    """
                    await cur.execute(sql, (guild_id, role_id))
                    await conn.commit()	
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def guild_update_featurerole(
        self, guild_id: str, role_id: str, faucet_multipled_by: float,
        guild_vote_multiplied_by: float, faucet_cut_time_percent: float,
        updated_by_uid: str, updated_by_uname: str
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `discord_feature_roles` (`guild_id`, `role_id`, 
                    `faucet_multipled_by`, `guild_vote_multiplied_by`, `faucet_cut_time_percent`, 
                    `updated_by_uid`, `updated_by_uname`, `date`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s) 
                    ON DUPLICATE KEY 
                    UPDATE 
                    `faucet_multipled_by`=VALUES(`faucet_multipled_by`),
                    `guild_vote_multiplied_by`=VALUES(`guild_vote_multiplied_by`),
                    `faucet_cut_time_percent`=VALUES(`faucet_cut_time_percent`),
                    `updated_by_uid`=VALUES(`updated_by_uid`),
                    `updated_by_uname`=VALUES(`updated_by_uname`),
                    `date`=VALUES(`date`)
                    """
                    await cur.execute(sql, (
                        guild_id, role_id, faucet_multipled_by, 
                        guild_vote_multiplied_by, faucet_cut_time_percent,
                        updated_by_uid, updated_by_uname, int(time.time())
                    ))
                    await conn.commit()	
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def vote_logchan(self, content: str):
        try:
            webhook = AsyncDiscordWebhook(url=self.bot.config['discord']['vote_webhook'], content=content)
            await webhook.execute()
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def guild_find_by_key(self, guild_id: str, secret: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT `"""+secret+"""` FROM `discord_server` WHERE `serverid`=%s
                    """
                    await cur.execute(sql, ( guild_id ))
                    result = await cur.fetchone()
                    if result: return result[secret]
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def guild_insert_key(self, guild_id: str, key: str, secret: str, update: bool=False):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `discord_server` SET `"""+secret+"""`=%s WHERE `serverid`=%s LIMIT 1
                    """
                    await cur.execute(sql, (key, guild_id))
                    await conn.commit()
                    return cur.rowcount
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def update_reward(
        self, guild_id: str, amount: float, coin_name: str, disable: bool=False, channel: str=None
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if disable is True:
                        sql = """ UPDATE `discord_server` SET `vote_reward_amount`=%s, 
                        `vote_reward_coin`=%s, `vote_reward_channel`=%s WHERE `serverid`=%s LIMIT 1
                        """
                        await cur.execute(sql, ( None, None, guild_id, None ))
                        await conn.commit()
                        return cur.rowcount
                    else:
                        sql = """ UPDATE `discord_server` SET `vote_reward_amount`=%s, 
                        `vote_reward_coin`=%s, `vote_reward_channel`=%s WHERE `serverid`=%s LIMIT 1
                        """
                        await cur.execute(sql, ( amount, coin_name.upper(), channel, guild_id  ))
                        await conn.commit()
                        return cur.rowcount
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def update_faucet(
        self, guild_id: str, amount: float, coin_name: str, duration: int=43200, 
        disable: bool=False, channel: str=None
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if disable is True:
                        sql = """ UPDATE `discord_server` SET `faucet_amount`=%s, 
                        `faucet_coin`=%s, `faucet_channel`=%s, `faucet_duration`=%s 
                        WHERE `serverid`=%s LIMIT 1
                        """
                        await cur.execute(sql, ( None, None, None, None, guild_id ))
                        await conn.commit()
                        return cur.rowcount
                    else:
                        sql = """ UPDATE `discord_server` 
                        SET `faucet_amount`=%s, `faucet_coin`=%s, `faucet_channel`=%s, 
                        `faucet_duration`=%s WHERE `serverid`=%s LIMIT 1
                        """
                        await cur.execute(sql, ( amount, coin_name.upper(), channel, duration, guild_id  ))
                        await conn.commit()
                        return cur.rowcount
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def update_activedrop(
        self, guild_id: str, amount: float=0, coin_name: str=None, duration: int=3600, 
        channel: str=None, role_id: str=None
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `discord_server` SET `tiptalk_amount`=%s, 
                    `tiptallk_coin`=%s, `tiptalk_channel`=%s, `tiptalk_duration`=%s, `tiptalk_role_id`=%s 
                    WHERE `serverid`=%s LIMIT 1
                    """
                    await cur.execute(sql, (
                        amount, coin_name.upper() if coin_name else None, 
                        channel, duration, role_id, guild_id
                    ))
                    await conn.commit()
                    return cur.rowcount
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def get_activedrop(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `discord_server`  
                    WHERE `tiptalk_amount`>0
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result and len(result) > 0: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_last_activedrop_guild(self, guild_id):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `discord_tiptalker`  
                    WHERE `guild_id`=%s ORDER BY `id` DESC LIMIT 1
                    """
                    await cur.execute(sql, ( guild_id ))
                    result = await cur.fetchone()
                    if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def insert_new_activedrop_guild(
        self, guild_id: str, guild_name: str, channel_id: str, token_name: str, 
        token_decimal: int, total_amount: float, each_amount: float, numb_receivers: int, 
        list_receivers_id: str, list_receivers_name: str, spread_time: int
    ):
        try:	
            await store.openConnection()	
            async with store.pool.acquire() as conn:	
                async with conn.cursor() as cur:	
                    sql = """ INSERT INTO `discord_tiptalker` (`guild_id`, `guild_name`, 
                    `channel_id`, `token_name`, `token_decimal`, `total_amount`, `each_amount`, 
                    `numb_receivers`, `list_receivers_id`, `list_receivers_name`, spread_time) 	
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """	
                    await cur.execute(sql, (
                        guild_id, guild_name, channel_id, token_name.upper(), token_decimal, total_amount,
                        each_amount, numb_receivers, list_receivers_id, list_receivers_name, spread_time
                    ))
                    await conn.commit()	
                    return True	
        except Exception:	
            await logchanbot("guild " +str(traceback.format_exc()))	
        return False

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        dm_permission=False,
        description="Various guild's commands."
    )
    async def guild(self, ctx):
        pass

    @guild.sub_command(
        name="balance",
        usage="guild balance", 
        description="Show guild's balance"
    )
    async def balance(
        self,
        ctx
    ):
        await ctx.response.defer(ephemeral=False)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/guild balance", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        has_none_balance = True
        total_all_balance_usd = 0.0
        mytokens = await store.get_coin_settings(coin_type=None)

        coin_balance_list = {}
        coin_balance = {}
        coin_balance_usd = {}
        coin_balance_equivalent_usd = {}
        coin_emojis = {}
        for each_token in mytokens:
            try:
                coin_name = each_token['coin_name']
                type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
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
                # height can be None
                userdata_balance = await self.wallet_api.user_balance(
                    str(ctx.guild.id), coin_name, 
                    wallet_address, type_coin, height, 
                    deposit_confirm_depth, SERVER_BOT
                )
                total_balance = userdata_balance['adjust']
                if total_balance > 0:
                    has_none_balance = False
                    coin_balance_list[coin_name] = "{} {}".format(
                        num_format_coin(total_balance), token_display
                    )
                    coin_balance[coin_name] = total_balance
                    price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                    coin_balance_usd[coin_name] = 0.0
                    coin_balance_equivalent_usd[coin_name] = ""
                    coin_emojis[coin_name] = ""
                    try:
                        if ctx.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is True:
                            coin_emojis[coin_name] = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                            coin_emojis[coin_name] = coin_emojis[coin_name] + " " if coin_emojis[coin_name] else ""
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    if price_with:
                        per_unit = await self.utils.get_coin_price(coin_name, price_with)
                        if per_unit and per_unit['price'] and per_unit['price'] > 0:
                            per_unit = per_unit['price']
                            coin_balance_usd[coin_name] = float(Decimal(total_balance) * Decimal(per_unit))
                            total_all_balance_usd += coin_balance_usd[coin_name]
                            if coin_balance_usd[coin_name] >= 0.01:
                                coin_balance_equivalent_usd[coin_name] = " ~ {:,.2f}$".format(coin_balance_usd[coin_name])
                            elif coin_balance_usd[coin_name] >= 0.0001:
                                coin_balance_equivalent_usd[coin_name] = " ~ {:,.4f}$".format(coin_balance_usd[coin_name])
            except Exception:
                traceback.print_exc(file=sys.stdout)

        if has_none_balance is True:
            msg = f'{ctx.author.mention}, this guild does not have any balance.'
            await ctx.edit_original_message(content=msg)
            return
        else:
            ## add page
            all_pages = []
            num_coins = 0
            per_page = 20
            if total_all_balance_usd >= 0.01:
                total_all_balance_usd = "Having ~ {:,.2f}$".format(total_all_balance_usd)
            elif total_all_balance_usd >= 0.0001:
                total_all_balance_usd = "Having ~ {:,.4f}$".format(total_all_balance_usd)
            else:
                total_all_balance_usd = "Thank you for using TipBot!"
                
            for k, v in coin_balance_list.items():
                if num_coins == 0 or num_coins % per_page == 0:
                    page = disnake.Embed(
                        title=f'[ GUILD **{ctx.guild.name.upper()}** BALANCE LIST ]',
                        description=f"`{total_all_balance_usd}`",
                        color=disnake.Color.red(),
                        timestamp=datetime.fromtimestamp(int(time.time())),
                    )

                    if ctx.guild.icon:
                        page.set_thumbnail(url=str(ctx.guild.icon))
                    page.set_footer(text="Use the reactions to flip pages.")
                page.add_field(name="{}{}{}".format(coin_emojis[k], k, coin_balance_equivalent_usd[k]), value="{}".format(v), inline=True)
                num_coins += 1
                if num_coins > 0 and num_coins % per_page == 0:
                    all_pages.append(page)
                    if num_coins < len(coin_balance_list):
                        page = disnake.Embed(
                            title=f'[ GUILD **{ctx.guild.name.upper()}** BALANCE LIST ]',
                            description=f"`{total_all_balance_usd}`",
                            color=disnake.Color.red(),
                            timestamp=datetime.fromtimestamp(int(time.time())),
                        )
                        if ctx.guild.icon:
                            page.set_thumbnail(url=str(ctx.guild.icon))
                        page.set_footer(text="Use the reactions to flip pages.")
                    else:
                        break
                elif num_coins == len(coin_balance_list):
                    all_pages.append(page)
                    break
                
            if len(all_pages) == 1:
                await ctx.edit_original_message(content=None, embed=all_pages[0], view=RowButtonCloseMessage())
            else:
                view = None
                try:
                    view = MenuPage(ctx, all_pages, timeout=30, disable_remove=True)
                    view.message = await ctx.edit_original_message(content=None, embed=all_pages[0], view=view)
                except Exception:
                    msg = f"{ctx.author.mention}, internal error when checking {self.bot.config['command_list']['guild_balance']}. "\
                        "Try again later.  If problem still persists, contact TipBot dev."
                    await ctx.edit_original_message(content=msg)
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(f"[ERROR] /guild balance with {ctx.guild.name} / {ctx.guild.id}")

    @guild.sub_command(
        usage="guild deposit <amount> <coin/token>", 
        options=[
            Option('amount', 'amount', OptionType.string, required=True), 
            Option('coin', 'coin', OptionType.string, required=True) 
        ],
        description="Deposit from your balance to the said guild"
    )
    async def deposit(
        self,
        ctx,
        amount: str, 
        coin: str
    ):

        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/guild deposit", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # check lock
        try:
            is_user_locked = self.utils.is_locked_user(str(ctx.author.id), SERVER_BOT)
            if is_user_locked is True:
                await ctx.edit_original_message(
                    content = f"{EMOJI_RED_NO} {ctx.author.mention}, your account is locked from using the Bot. "\
                    "Please contact bot dev by /about link."
                )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # end check lock

        coin_name = coin.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            await ctx.edit_original_message(content=f'{ctx.author.mention}, **{coin_name}** does not exist with us.')
            return
        # Do the job
        try:
            try:
                coin_emoji = ""
                if ctx.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is True:
                    coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                    coin_emoji = coin_emoji + " " if coin_emoji else ""
            except Exception:
                traceback.print_exc(file=sys.stdout)
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
            max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
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
            # check if amount is all
            all_amount = False
            if not amount.isdigit() and amount.upper() == "ALL":
                all_amount = True
                userdata_balance = await self.wallet_api.user_balance(
                    str(ctx.author.id), coin_name, wallet_address, 
                    type_coin, height, deposit_confirm_depth, SERVER_BOT
                )
                amount = float(userdata_balance['adjust'])
            # If $ is in amount, let's convert to coin/token
            elif "$" in amount[-1] or "$" in amount[0]: # last is $
                # Check if conversion is allowed for this coin.
                amount = amount.replace(",", "").replace("$", "")
                if price_with is None:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this __{coin_name}__."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    per_unit = await self.utils.get_coin_price(coin_name, price_with)
                    if per_unit and per_unit['price'] and per_unit['price'] > 0:
                        per_unit = per_unit['price']
                        amount = float(Decimal(amount) / Decimal(per_unit))
                    else:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. "\
                            f"Try with different method."
                        await ctx.edit_original_message(content=msg)
                        return
            else:
                amount = amount.replace(",", "")
                amount = text_to_num(amount)
                if amount is None:
                    await ctx.edit_original_message(
                        content=f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                    )
                    return
            # end of check if amount is all
            userdata_balance = await self.wallet_api.user_balance(
                str(ctx.author.id), coin_name, 
                wallet_address, type_coin, height, 
                deposit_confirm_depth, SERVER_BOT
            )
            actual_balance = Decimal(userdata_balance['adjust'])
            amount = Decimal(amount)
            if amount <= 0:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please topup more {coin_name}'
                await ctx.edit_original_message(content=msg)
                return
                
            if amount > actual_balance:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to deposit "\
                    f"{num_format_coin(amount)} {token_display}."
                await ctx.edit_original_message(content=msg)
                return

            elif amount < min_tip or amount > max_tip:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, transaction cannot be smaller than "\
                    f"{num_format_coin(min_tip)} {token_display} "\
                    f"or bigger than {num_format_coin(max_tip)} {token_display}."
                await ctx.edit_original_message(content=msg)
                return

            equivalent_usd = ""
            amount_in_usd = 0.0
            per_unit = None
            if price_with:
                per_unit = await self.utils.get_coin_price(coin_name, price_with)
                if per_unit and per_unit['price'] and per_unit['price'] > 0:
                    per_unit = per_unit['price']
                    amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                    if amount_in_usd > 0.0001:
                        equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)

            # OK, move fund
            if str(ctx.author.id) in self.bot.tipping_in_progress:
                await ctx.edit_original_message(
                    content=f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
                )
                return
            else:
                self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())
                try:
                    tip = await store.sql_user_balance_mv_single(
                        str(ctx.author.id), str(ctx.guild.id), str(ctx.guild.id), str(ctx.channel.id),
                        amount, coin_name, 'GUILDDEPOSIT', coin_decimal, SERVER_BOT, contract, amount_in_usd, None
                    )
                    if tip:
                        try:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention} transferred "\
                                f"{coin_emoji}**{num_format_coin(amount)} {coin_name}**"\
                                f"{equivalent_usd} to {ctx.guild.name}."
                            await ctx.edit_original_message(content=msg)
                        except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
                            pass
                        guild_found = self.bot.get_guild(ctx.guild.id)
                        if guild_found: user_found = self.bot.get_user(guild_found.owner.id)
                        if user_found:
                            notifyList = await store.sql_get_tipnotify()
                            if str(guild_found.owner.id) not in notifyList:
                                try:
                                    await user_found.send(
                                        f"Your guild **{ctx.guild.name}** got a deposit of "\
                                        f"{coin_emoji}**{num_format_coin(amount)} {coin_name}**"\
                                        f"{equivalent_usd} from {ctx.author.name}#{ctx.author.discriminator} in "\
                                        f"`#{ctx.channel.name}`\n{NOTIFICATION_OFF_CMD}"
                                    )
                                except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
                                    pass
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            del self.bot.tipping_in_progress[str(ctx.author.id)]
        except Exception:
            pass

    @deposit.autocomplete("coin")
    async def guilddeposit_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

    # Guild deposit
    async def async_mdeposit(self, ctx, token: str=None, plain: str=None):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/mdeposit", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        coin_name = None
        if token is None:
            await ctx.edit_original_message(content=f'{ctx.author.mention}, token name is missing.')
            return
        else:
            coin_name = token.upper()
            if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                coin_name = self.bot.coin_alias_names[coin_name]
            if not hasattr(self.bot.coin_list, coin_name):
                await ctx.edit_original_message(content=f'{ctx.author.mention}, **{coin_name}** does not exist with us.')
                return
            else:
                if getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                    await ctx.edit_original_message(content=f'{ctx.author.mention}, **{coin_name}** deposit disable.')
                    return
                    
        # Do the job
        try:
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            get_deposit = await self.wallet_api.sql_get_userwallet(
                str(ctx.guild.id), coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(
                    str(ctx.guild.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 1
                )
                
            wallet_address = get_deposit['balance_wallet_address']
            description = ""
            fee_txt = ""
            guild_note = " This is guild's deposit address and NOT YOURS."
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            if getattr(getattr(self.bot.coin_list, coin_name), "deposit_note") and \
                len(getattr(getattr(self.bot.coin_list, coin_name), "deposit_note")) > 0:
                description = getattr(getattr(self.bot.coin_list, coin_name), "deposit_note")
            if getattr(getattr(self.bot.coin_list, coin_name), "real_deposit_fee") and \
                getattr(getattr(self.bot.coin_list, coin_name), "real_deposit_fee") > 0:
                fee_txt = " **{} {}** will be deducted from your deposit when it reaches minimum. ".format(
                    getattr(getattr(self.bot.coin_list, coin_name), "real_deposit_fee"), token_display
                )
            embed = disnake.Embed(
                title=f'Deposit for guild {ctx.guild.name}',
                description=description + fee_txt + guild_note,
                timestamp=datetime.fromtimestamp(int(time.time()))
            )
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            try:
                gen_qr_address = await self.wallet_api.generate_qr_address(wallet_address)
                embed.set_thumbnail(url=self.bot.config['storage']['deposit_url'] + wallet_address + ".png")
            except Exception:
                traceback.print_exc(file=sys.stdout)
            plain_msg = 'Guild {} deposit address: ```{}```'.format(ctx.guild.name, wallet_address)
            embed.add_field(name="Guild {}".format(ctx.guild.name), value="__{}__".format(wallet_address), inline=False)
            if getattr(getattr(self.bot.coin_list, coin_name), "explorer_link") and \
                len(getattr(getattr(self.bot.coin_list, coin_name), "explorer_link")) > 0:
                embed.add_field(
                    name="Other links",
                    value="[{}]({})".format("Explorer", getattr(getattr(self.bot.coin_list, coin_name), "explorer_link")),
                    inline=False
                )
            embed.set_footer(text="Use: deposit plain (for plain text)")
            try:
                if plain and plain.lower() == 'plain' or plain.lower() == 'text':
                    await ctx.edit_original_message(content=plain_msg, view=RowButtonRowCloseAnyMessage())
                else:
                    await ctx.edit_original_message(content=None, embed=embed, view=RowButtonRowCloseAnyMessage())
            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)


    @commands.guild_only()
    @commands.slash_command(
        dm_permission=False,
        usage="mdeposit <coin_name>", 
        options=[
            Option('token', 'token', OptionType.string, required=True),
            Option('plain', 'plain', OptionType.string, required=False)
        ],
        description="Get a deposit address for a guild."
    )
    async def mdeposit(
        self, 
        ctx,
        token: str,
        plain: str = 'embed'
    ):
        await self.async_mdeposit(ctx, token, plain)


    @commands.has_permissions(administrator=True)
    @guild.sub_command(
        usage="guild faucetclaim <amount> <coin/token> <channel>", 
        options=[
            Option('amount', 'amount', OptionType.string, required=True), 
            Option('coin', 'coin', OptionType.string, required=True),
            Option('duration', 'duration', OptionType.string, required=True),
            Option('channel', 'channel', OptionType.channel, required=True)
        ],
        description="Allow your guild's user to claim reward."
    )
    async def faucetclaim(
        self,
        ctx,
        amount: str, 
        coin: str,
        duration: str,
        channel: disnake.TextChannel
    ):

        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/guild faucetclaim", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # Check if channel is text channel
        if type(channel) is not disnake.TextChannel:
            msg = f'{ctx.author.mention}, that\'s not a text channel. Try a different channel!'
            await ctx.edit_original_message(content=msg)
            return

        coin_name = coin.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            await ctx.edit_original_message(content=f'{ctx.author.mention}, **{coin_name}** does not exist with us.')
            return

        duration_s = 12*3600
        duration = duration.upper()
        if duration not in ["4H", "8H", "12H", "24H"]:
            await ctx.edit_original_message(content=f'{ctx.author.mention}, accepted duration 4H, 8H, 12H, 24H.')
            return
        elif duration == "4H":
            duration_s = 4*3600
        elif duration == "8H":
            duration_s = 8*3600
        elif duration == "12H":
            duration_s = 12*3600
        elif duration == "24H":
            duration_s = 24*3600

        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
        min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
        max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
        price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")

        get_deposit = await self.wallet_api.sql_get_userwallet(str(ctx.guild.id), coin_name, net_name, type_coin, SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await self.wallet_api.sql_register_user(str(ctx.guild.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 1)

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

        amount = amount.replace(",", "")
        amount = text_to_num(amount)
        if amount is None:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
            await ctx.edit_original_message(content=msg)
            return
        # We assume max reward by max_tip / 10
        elif amount < min_tip or amount > max_tip / 10:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, faucet cannot be smaller than "\
                f"{num_format_coin(min_tip)} {token_display} "\
                f"or bigger than {num_format_coin(max_tip / 10)} {token_display}."
            await ctx.edit_original_message(content=msg)
            return
        # We assume at least guild need to have 100x of reward or depends on guild's population
        elif amount*100 > actual_balance:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, your guild needs to have at least 100x reward balance. "\
                f"100x rewards = {num_format_coin(amount*100)} {token_display}. Check with {self.bot.config['command_list']['guild_balance']}."
            await ctx.edit_original_message(content=msg)
            return
        elif amount*len(ctx.guild.members) > actual_balance:
            population = len(ctx.guild.members)
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you need to have at least {str(population)}x reward balance. "\
                f"{str(population)}x rewards = {num_format_coin(amount*population)} {token_display}."
            await ctx.edit_original_message(content=msg)
            return
        else:
            # Check channel
            get_channel = self.bot.get_channel(int(channel.id))
            channel_str = str(channel.id)
            # Test message
            msg = f"New guild /faucet set to {num_format_coin(amount)} {token_display} "\
                f"by {ctx.author.name}#{ctx.author.discriminator} and message here."
            try:
                await get_channel.send(msg)
            except Exception:
                msg = f'{ctx.author.mention}, failed to message channel {channel.mention}. Set faucet denied!'
                await ctx.edit_original_message(content=msg)
                traceback.print_exc(file=sys.stdout)
                return
            
            # Process, only guild owner can process
            try:
                serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
                if serverinfo is None:
                    # Let's add some info if server return None
                    await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
                    # re-load guild list
                    await self.utils.bot_reload_guilds()
            except Exception:
                traceback.print_exc(file=sys.stdout)
                msg = f'{ctx.author.mention}, internal error. Please report.'
                await ctx.edit_original_message(content=msg)

            update_faucet = await self.update_faucet(str(ctx.guild.id), float(amount), coin_name, duration_s, False, channel_str)
            if update_faucet > 0:
                msg = f"{ctx.author.mention}, successfully faucet in guild {ctx.guild.name} to "\
                    f"{num_format_coin(amount)} {token_display} for every {duration}."
                await ctx.edit_original_message(content=msg)
                try:
                    await logchanbot(
                        f"[{SERVER_BOT}] A user {ctx.author.name}#{ctx.author.discriminator} set "\
                        f"/faucet in guild {ctx.guild.name} / {ctx.guild.id} to "\
                        f"{num_format_coin(amount)} {token_display} for every {duration}."
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            else:
                msg = f'{ctx.author.mention} internal error or nothing updated.'
                await ctx.edit_original_message(content=msg)
            return

    @faucetclaim.autocomplete("coin")
    async def quickdrop_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

    @commands.has_permissions(administrator=True)
    @guild.sub_command(
        usage="guild activedrop <amount> <coin/token> <duration> <#channel> [@role]", 
        options=[
            Option('amount', 'amount', OptionType.string, required=True), 
            Option('coin', 'coin', OptionType.string, required=True),
            Option('duration', 'duration', OptionType.string, required=True, choices=[
                OptionChoice("30 mn", "0.5H"),
                OptionChoice("1 Hour", "1H"),
                OptionChoice("2 Hours", "2H"),
                OptionChoice("3 Hours", "3H"),
                OptionChoice("4 Hours", "4H"),
                OptionChoice("5 Hours", "5H"),
                OptionChoice("6 Hours", "6H"),
                OptionChoice("12 Hours", "12H"),
                OptionChoice("24 Hours", "24H")
            ]),
            Option('channel', 'channel', OptionType.channel, required=True),
            Option('role', 'role', OptionType.role, required=False)
        ],
        description="Let bot rains every interval to active chatter in a channel."
    )
    async def activedrop(
        self,
        ctx,
        amount: str, 
        coin: str,
        duration: str,
        channel: disnake.TextChannel,
        role: disnake.Role=None
    ):
        await self.async_activedrop( ctx, amount, coin, duration, channel, role )

    @activedrop.autocomplete("coin")
    async def activedrop_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @commands.slash_command(
        dm_permission=False,
        usage="tiptalker <amount> <coin/token> <duration> <#channel> [@role]", 
        options=[
            Option('amount', 'amount', OptionType.string, required=True), 
            Option('coin', 'coin', OptionType.string, required=True),
            Option('duration', 'duration', OptionType.string, required=True, choices=[
                OptionChoice("30 mn", "0.5H"),
                OptionChoice("1 Hour", "1H"),
                OptionChoice("2 Hours", "2H"),
                OptionChoice("3 Hours", "3H"),
                OptionChoice("4 Hours", "4H"),
                OptionChoice("5 Hours", "5H"),
                OptionChoice("6 Hours", "6H"),
                OptionChoice("12 Hours", "12H"),
                OptionChoice("24 Hours", "24H")
            ]),
            Option('channel', 'channel', OptionType.channel, required=True),
            Option('role', 'role', OptionType.role, required=False)
        ],
        description="Let bot rains every interval to active chatter in a channel."
    )
    async def tiptalker(
        self,
        ctx,
        amount: str, 
        coin: str,
        duration: str,
        channel: disnake.TextChannel,
        role: disnake.Role=None
    ):
        await self.async_activedrop( ctx, amount, coin, duration, channel, role )

    @tiptalker.autocomplete("coin")
    async def tiptalker_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

    async def async_activedrop(self, ctx, amount: str, coin: str, duration: str, channel: disnake.TextChannel, role: disnake.Role=None):

        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/guild activedrop", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # Check if channel is text channel
        if type(channel) is not disnake.TextChannel:
            msg = f'{ctx.author.mention}, that\'s not a text channel. Try a different channel!'
            await ctx.edit_original_message(content=msg)
            return

        original_duration = duration
        coin_name = coin.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            await ctx.edit_original_message(content=f'{ctx.author.mention}, **{coin_name}** does not exist with us.')
            return

        duration = duration.upper()
        if duration not in ["0.5H", "1H", "2H", "3H", "4H", "5H", "6H", "12H", "24H"]:
            await ctx.edit_original_message(content=f'{ctx.author.mention}, accepted duration 0.5H to 6H.')
            return
        duration_s = int(float(duration.upper().replace("H", ""))*3600)

        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
        min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
        max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
        price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")

        get_deposit = await self.wallet_api.sql_get_userwallet(str(ctx.guild.id), coin_name, net_name, type_coin, SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await self.wallet_api.sql_register_user(str(ctx.guild.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 1)

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']
        elif type_coin in ["XRP"]:
            wallet_address = get_deposit['destination_tag']

        height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        userdata_balance = await self.wallet_api.user_balance(
            str(ctx.guild.id), coin_name, wallet_address, 
            type_coin, height, deposit_confirm_depth, SERVER_BOT
        )
        actual_balance = float(userdata_balance['adjust'])

        amount = amount.replace(",", "")
        serverinfo = None
        # Process, only guild owner can process
        try:
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
            if serverinfo is None:
                # Let's add some info if server return None
                await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
                # re-load guild list
                await self.utils.bot_reload_guilds()
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        except Exception:
            traceback.print_exc(file=sys.stdout)
            msg = f'{ctx.author.mention}, internal error. Please report.'
            await ctx.edit_original_message(content=msg)
        # if amount <= 0, meaning disable
        if amount.isdigit() and float(amount) <= 0 and serverinfo['tiptalk_amount'] > 0:
            update_tiptalk = await self.update_activedrop(str(ctx.guild.id), 0.0, None, None, None, None)
            msg = f'{ctx.author.mention}, disable activedrop/tiptalker in {ctx.guild.name}.'
            await ctx.edit_original_message(content=msg)
            return
        elif amount.isdigit() and float(amount) <= 0 and serverinfo['tiptalk_amount'] == 0:
            msg = f'{ctx.author.mention}, activedrop/tiptalker in {ctx.guild.name} is currently disable.'
            await ctx.edit_original_message(content=msg)
            return
        amount = text_to_num(amount)
        if amount is None:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
            await ctx.edit_original_message(content=msg)
            return
            
        # We assume max reward by max_tip / 10
        elif amount < min_tip or amount > max_tip / 10:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, activedrop/tiptalker amount cannot be smaller than "\
                f"{num_format_coin(min_tip)} {token_display} or bigger than "\
                f"{num_format_coin(max_tip / 10)} {token_display}."
            await ctx.edit_original_message(content=msg)
            try:
                await logchanbot(
                    f"[{SERVER_BOT}] A user {ctx.author.name}#{ctx.author.discriminator} disable "\
                    f"activedrop/tiptalker in guild {ctx.guild.name} / {ctx.guild.id}."
                )
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return

        # We assume at least guild need to have 100x of reward or depends on guild's population
        elif amount*100 > actual_balance:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, your guild needs to have at least 100x `active drop amount`"\
                f". 100x rewards = {num_format_coin(amount*100)} {token_display}."\
                f" Check with {self.bot.config['command_list']['guild_balance']}."
            await ctx.edit_original_message(content=msg)
            return
        else:
            # Check channel
            get_channel = self.bot.get_channel(int(channel.id))
            channel_str = str(channel.id)
            # Test message
            msg = f"New guild's active drop set to __{num_format_coin(amount)} "\
                f"{token_display}__ by {ctx.author.name}#{ctx.author.discriminator} and always rewards "\
                f"to active users in this channel every __{original_duration}__."
            try:
                await get_channel.send(msg)
            except Exception:
                msg = f"{ctx.author.mention}, failed to message channel {channel.mention}. Set active drop denied!"
                await ctx.edit_original_message(content=msg)
                traceback.print_exc(file=sys.stdout)
                return
            role_id = None
            if role and str(role) not in ["@everyone", "@here"]:
                get_role = disnake.utils.get(ctx.guild.roles, name=role.name)
                if get_role:
                    role_id = str(get_role.id)
            update_tiptalk = await self.update_activedrop(str(ctx.guild.id), float(amount), coin_name, duration_s, channel_str, role_id)
            if update_tiptalk > 0:
                msg = f"{ctx.author.mention}, successfully set activedrop/tiptalker in guild {ctx.guild.name} to"\
                    f" {num_format_coin(amount)} {token_display} for every {duration}."
                try:
                    if serverinfo['tiptalk_channel'] and channel_str != serverinfo['tiptalk_channel']:
                        msg += " You guild's previous /tiptalk set in channel <#{}> is deleted.".format( serverinfo['tiptalk_channel'] )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                await ctx.edit_original_message(content=msg)
                try:
                    await logchanbot(
                        f"[{SERVER_BOT}] A user {ctx.author.name}#{ctx.author.discriminator} set "\
                        f"activedrop/tiptalker in guild {ctx.guild.name} / {ctx.guild.id} to "\
                        f"{num_format_coin(amount)} {token_display} for"\
                        f" every {duration} in channel #{ctx.channel.name}."
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            else:
                msg = f'{ctx.author.mention} internal error or nothing updated.'
                await ctx.edit_original_message(content=msg)

    async def async_guild_info(self, ctx, private: bool):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, loading..."
        await ctx.response.send_message(msg, ephemeral=private)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/guild info", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            # re-load guild list
            await self.utils.bot_reload_guilds()
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))

        embed = disnake.Embed(title = "Guild {} / {}".format(ctx.guild.name, ctx.guild.id), timestamp=datetime.now())
        try:
            owner_id = ctx.guild.owner.id
            total_number = ctx.guild.member_count
            total_roles = len(ctx.guild.roles)
            nos_text_channel = len(ctx.guild.text_channels)
            nos_categories = len(ctx.guild.categories)
            num_online = len([member for member in ctx.guild.members if member.bot == False and member.status != disnake.Status.offline])
            num_bot = len([member for member in ctx.guild.members if member.bot == True])
            m_statistics = "Owner: <@{}>\n```Total Members: {}\nOnline: {}\nBots: {}\nRoles: {}\nCategories: {}\nText Channels: {}```".format(
                owner_id, total_number, num_online, num_bot, total_roles, nos_categories, nos_text_channel
            )
            embed.add_field(name="Statistics", value=m_statistics, inline=False)
            if ctx.guild.icon:
                embed.set_thumbnail(url=str(ctx.guild.icon))
        except Exception:
            traceback.print_exc(file=sys.stdout)
        if serverinfo['tiponly'] is not None:
            embed.add_field(
                name="Allowed Coins (Tip)",
                value="{}".format(serverinfo['tiponly']),
                inline=True
            )
        if serverinfo['enable_faucet'] == "YES" and serverinfo['faucet_channel']:
            embed.add_field(
                name="Faucet {} {}".format(serverinfo['faucet_amount'], serverinfo['faucet_coin']),
                value="<#{}>".format(serverinfo['faucet_channel']),
                inline=True
            )
        if serverinfo['botchan']:
            embed.add_field(
                name="Bot Channel",
                value="<#{}>".format(serverinfo['botchan']),
                inline=True
            )
        if serverinfo['tiptalk_channel'] and serverinfo['tiptalk_amount'] > 0 and serverinfo['tiptallk_coin']:
            embed.add_field(
                name="TipTalk",
                value="`{} {} @ {}`".format(
                    serverinfo['tiptalk_amount'], serverinfo['tiptallk_coin'], seconds_str(serverinfo['tiptalk_duration'])
                ),
                inline=True
            )
        if serverinfo['economy_channel'] and serverinfo['enable_economy'] == "YES":
            embed.add_field(
                name="Economy Channel",
                value="<#{}>".format(serverinfo['economy_channel']),
                inline=True
            )
        if serverinfo['mute_tip']:
            embed.add_field(
                name="Mute Tip",
                value=serverinfo['mute_tip'],
                inline=True
            )
        if private is True:
            # show some permission
            permission_list = []
            bot_user = ctx.guild.get_member(self.bot.user.id)
            if ctx.channel.permissions_for(bot_user).send_messages:
                permission_list.append("✅ send_messages")
            else:
                permission_list.append("❌ send_messages")
            if ctx.channel.permissions_for(bot_user).external_emojis:
                permission_list.append("✅ external_emojis")
            else:
                permission_list.append("❌ external_emojis")
            if ctx.channel.permissions_for(bot_user).embed_links:
                permission_list.append("✅ embed_links")
            else:
                permission_list.append("❌ embed_links")
            if ctx.channel.permissions_for(bot_user).manage_roles:
                permission_list.append("✅ manage_roles")
            else:
                permission_list.append("❌ manage_roles")
            embed.add_field(
                name="Permission TipBot",
                value="```{}```".format("\n".join(permission_list)),
                inline=False
            )
        try:
            if serverinfo['feature_roles'] and len(serverinfo['feature_roles'].keys()) > 0:
                list_featureroles = []
                for k, v in serverinfo['feature_roles'].items():
                    faucet_str = '{:,.2f}'.format(v['faucet_multipled_by'])
                    cut_str = '{:,.0f}{}'.format(v['faucet_cut_time_percent']*100, "%")
                    list_featureroles.append("<@&{}>:\nFaucet (x): {}\nFaucet Reduced Time: {}".format(
                        k, faucet_str, cut_str
                    ))
                embed.add_field(
                    name="Featured Role(s)",
                    value="\n\n".join(list_featureroles),
                    inline=False
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
        await ctx.edit_original_message(content=None, embed=embed)

    @commands.bot_has_permissions(send_messages=True)
    @guild.sub_command(
        usage="guild info", 
        description="Get information about a guild."
    )
    async def info(
        self,
        ctx
    ):
        await self.async_guild_info(ctx, private=False)

    @commands.guild_only()
    @commands.user_command(name="GuildInfo")  # optional
    async def guild_info(self, ctx: disnake.ApplicationCommandInteraction):
        await self.async_guild_info(ctx, private=True)


    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @commands.slash_command(
        dm_permission=False,
        name="featurerole",
        usage="featurerole",
        description="Adjust faucet, vote, claim duration cut by a role.")
    async def featurerole(
        self, 
        ctx
    ):
        pass

    @commands.bot_has_permissions(send_messages=True)
    @featurerole.sub_command(
        name="list",
        usage="featurerole list", 
        description="Show active list of feature roles in the Guild."
    )
    async def slash_featurerole_list(
        self, 
        ctx
    ):
        await self.bot_log()
        msg = f'{ctx.author.mention}, checking your guild\'s info...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/featurerole list", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
            if serverinfo and serverinfo['enable_featurerole'] != 1:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, **featurerole** is not enabled in this Guild."
                await ctx.edit_original_message(content=msg)
                return
            elif serverinfo and serverinfo['feature_roles'] is None:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, there is no role listed in **featurerole**."
                await ctx.edit_original_message(content=msg)
                return
            elif serverinfo and serverinfo['feature_roles'] is not None and len(serverinfo['feature_roles'].keys()) > 0:
                embed = disnake.Embed(
                    title = "Guild {} / {}".format(ctx.guild.name, ctx.guild.id),
                    description = "* List a role for selling in your Guild's shop with `/gshop`\n"\
                                  "* Use `/featurerole add` to a specific role for specail features.\n"\
                                  "* Use `/featurerole delete <role>` to delist the featurerole. (Not deleting role).",
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
                if ctx.guild.icon:
                    embed.set_thumbnail(url=str(ctx.guild.icon))
                list_featureroles = []
                for k, v in serverinfo['feature_roles'].items():
                    faucet_str = '{:,.2f}'.format(v['faucet_multipled_by'])
                    cut_str = '{:,.0f}{}'.format(v['faucet_cut_time_percent']*100, "%")
                    list_featureroles.append("<@&{}>:\nFaucet (x): {}\nFaucet Reduced Time: {}".format(
                        k, faucet_str, cut_str
                    ))
                embed.add_field(name="Featured Role(s)", value="\n\n".join(list_featureroles), inline=False)
                await ctx.edit_original_message(content=None, embed=embed)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(send_messages=True)
    @featurerole.sub_command(
        name="add",
        usage="featurerole add <role> ....", 
        options=[
            Option('role', 'role', OptionType.role, required=True),
            Option('faucet_multiplied', 'Multiplied reward for /faucet', OptionType.string, required=True, choices=[
                OptionChoice("1.0x", "1.0"),
                OptionChoice("2.5x", "2.5"),
                OptionChoice("5.0x", "5.0"),
                OptionChoice("7.5x", "7.5"),
                OptionChoice("10x", "10.0")
            ]),
            Option('guild_vote_multiplied', 'Multiplied reward for each guild vote', OptionType.string, required=True, choices=[
                OptionChoice("1.0x", "1.0"),
                OptionChoice("2.5x", "2.5"),
                OptionChoice("5.0x", "5.0"),
                OptionChoice("7.5x", "7.5"),
                OptionChoice("10x", "10.0")
            ]),
            Option('faucet_cut_time_percent', '/faucet cutting time in percentage', OptionType.string, required=True, choices=[
                OptionChoice("0%", "0"),
                OptionChoice("10%", "0.1"),
                OptionChoice("25%", "0.25"),
                OptionChoice("50%", "0.5"),
                OptionChoice("75%", "0.75")
            ]),
        ],
        description="Adjust faucet, vote, claim duration cut by a role."
    )
    async def slash_featurerole_add(
        self, 
        ctx,
        role: disnake.Role,
        faucet_multiplied: str,
        guild_vote_multiplied: str,
        faucet_cut_time_percent: str
    ):
        await self.bot_log()
        msg = f'{ctx.author.mention}, checking your guild\'s info...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/featurerole add", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            prev_faucet = "1.0"
            prev_vote = "1.0"
            prev_cut = "0%"

            if role.name == "@everyone" or role.name == "@here":
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, can't use this role."
                await ctx.edit_original_message(content=msg)
                await logchanbot(
                    f"/featurerole User `{str(ctx.author.id)}` commanded by Guild `{str(ctx.guild.id)}` tried with role {role.name}."
                )
                return
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
            if serverinfo and serverinfo['feature_roles'] is not None and str(role.id) in serverinfo['feature_roles']:
                prev_faucet = '{:,.2f}'.format(serverinfo['feature_roles'][str(role.id)]['faucet_multipled_by'])
                prev_vote = '{:,.2f}'.format(serverinfo['feature_roles'][str(role.id)]['guild_vote_multiplied_by'])
                prev_cut = '{:,.2f}{}'.format(serverinfo['feature_roles'][str(role.id)]['faucet_cut_time_percent']*100, "%")
            if serverinfo and serverinfo['enable_featurerole'] != 1:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, this command is not available in this Guild."
                await ctx.edit_original_message(content=msg)
                await logchanbot(f"/featurerole User `{str(ctx.author.id)}` commanded by Guild `{str(ctx.guild.id)}` is not enable.")	
                return
            # Check if reach max
            if serverinfo and serverinfo['feature_roles'] and len(serverinfo['feature_roles'].keys()) >= self.max_featurerole:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, reach maximum /featurerole"
                await ctx.edit_original_message(content=msg)
                await logchanbot(
                    f"/featurerole User `{str(ctx.author.id)}` commanded by Guild `{str(ctx.guild.id)}` "\
                    "but reached `max_featurerole`."
                )
                return

            new_faucet = float(faucet_multiplied)
            new_vote = float(guild_vote_multiplied)
            new_cut = float(faucet_cut_time_percent)

            new_faucet_str = '{:,.2f}'.format(new_faucet)
            new_vote_str = '{:,.2f}'.format(new_vote)
            new_cut_str = '{:,.0f}{}'.format(new_cut*100, "%")

            faucet_multiplied = float(faucet_multiplied)
            guild_vote_multiplied = float(guild_vote_multiplied)
            faucet_cut_time_percent = float(faucet_cut_time_percent)
            if faucet_multiplied < 0 or faucet_multiplied > 10:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid value `faucet_multiplied`."
                await ctx.edit_original_message(content=msg)
                return

            if guild_vote_multiplied < 0 or guild_vote_multiplied > 10:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid value `guild_vote_multiplied`."
                await ctx.edit_original_message(content=msg)
                return

            if faucet_cut_time_percent < 0 or faucet_cut_time_percent > 1:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid value `faucet_cut_time_percent`."
                await ctx.edit_original_message(content=msg)
                return

            try:
                adjust_feature_role = await self.guild_update_featurerole(
                    str(ctx.guild.id), str(role.id),
                    faucet_multiplied, guild_vote_multiplied,
                    faucet_cut_time_percent, str(ctx.author.id),
                    "{}#{}".format(ctx.author.name, ctx.author.discriminator)
                )
                if adjust_feature_role is True:
                    msg = f"{ctx.author.mention}, featurerole `{role.name}` updated.\n"\
                    f"**Previous values**:\nFaucet (x): {prev_faucet}\nFaucet cutting time: {prev_cut}\nGuild Vote (x): {prev_vote}\n\n"\
                    f"**New values**:\nFaucet (x): {new_faucet_str}\nFaucet cutting time: {new_cut_str}\nGuild Vote (x): {new_vote_str}"
                    await ctx.edit_original_message(content=msg)
                    await logchanbot(
                        f"[FEATUREROLE] User {str(ctx.author.id)} "
                        f"adjusted role in Guild {ctx.guild.name} / `{str(ctx.guild.id)}`.\n"
                        f"**Previous values**:\nFaucet (x): {prev_faucet}\nFaucet cutting time: {prev_cut}\nGuild Vote (x): {prev_vote}\n\n"
                        f"**New values**:\nFaucet (x): {new_faucet_str}\nFaucet cutting time: {new_cut_str}\nGuild Vote (x): {new_vote_str}"
                    )
                else:
                    msg = f"{ctx.author.mention}, internal error. Please report."
                    await ctx.edit_original_message(content=msg)
                    await logchanbot(
                        f"[FEATUREROLE] Failed to adjust by User {str(ctx.author.id)} "\
                        f"in Guild {ctx.guild.name} / {str(ctx.guild.id)}."
                    )
                # re-load guild list
                await self.utils.bot_reload_guilds()
            except Exception:
                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)


    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(send_messages=True)
    @featurerole.sub_command(
        name="delete",
        usage="featurerole delete <role>", 
        options=[
            Option('role', 'role', OptionType.role, required=True)
        ],
        description="Delete a feature role.. (Not deleting role)"
    )
    async def slash_featurerole_delete(
        self, 
        ctx, 
        role: disnake.Role
    ):
        await self.bot_log()
        msg = f'{ctx.author.mention}, checking your guild\'s info...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/featurerole delete", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            check_exist = await self.guild_exist_featurerole(str(ctx.guild.id), str(role.id))
            if check_exist is True:
                delete_feature = await self.guild_delete_featurerole(str(ctx.guild.id), str(role.id))
                if delete_feature is True:
                    msg = f"{ctx.author.mention}, successfully deleted feature role for `{role.name}`. You can add again later!"
                    await ctx.edit_original_message(content=msg)
                    await logchanbot(
                        f"[FEATUREROLE] User {str(ctx.author.id)} in Guild {ctx.guild.name} / {str(ctx.guild.id)} "\
                        f"deleted feature role {role.name}."
                    )
            else:
                msg = f"{ctx.author.mention}, there's no featurerole set for role __{role.name}__."
                await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @commands.slash_command(
        dm_permission=False,
        usage="faucet",
        description="Claim guild's faucet."
    )
    async def faucet(
        self, 
        ctx
    ):

        try:
            cmd_name = ctx.application_command.qualified_name
            command_mention = f"__/{cmd_name}__"
            if self.bot.config['discord']['enable_command_mention'] == 1:
                cmd = self.bot.get_global_command_named(cmd_name)
                command_mention = f"</{cmd_name}:{cmd.id}>"
        except Exception:
            traceback.print_exc(file=sys.stdout)

        await self.bot_log()
        msg = f'{ctx.author.mention}, checking guild\'s faucet...'
        await ctx.response.send_message(msg)
        if str(ctx.author.id) in self.bot.tipping_in_progress and \
            int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 150:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
            await ctx.edit_original_message(content=msg)
            return

        # check if bot channel is set:
        try: 
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
            if serverinfo and serverinfo['faucet_channel'] and ctx.channel.id != int(serverinfo['faucet_channel']):
                try:
                    channel = self.bot.get_channel(int(serverinfo['faucet_channel']))
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, {channel.mention} is the faucet channel!!!'
                    await ctx.edit_original_message(content=msg)
                    return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            if serverinfo and serverinfo['enable_faucet'] == "NO":
                if self.enable_logchan:
                    await self.botLogChan.send(
                        f"{ctx.author.name} / {ctx.author.id} tried `/faucet` in "\
                        f"{ctx.guild.name} / {ctx.guild.id} which is disable."
                    )
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, {command_mention} in this guild is disable."
                await ctx.edit_original_message(content=msg)
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
            return
        # end of channel check
        try:
            if serverinfo['faucet_coin'] and serverinfo['faucet_amount'] > 0 and serverinfo['faucet_duration'] is not None:
                coin_name = serverinfo['faucet_coin']
                amount = serverinfo['faucet_amount']
                duration = serverinfo['faucet_duration']
                extra_amount = 0.0
                previous_amount = 0.0
                if serverinfo['feature_roles'] is not None:
                    try:
                        member = ctx.guild.get_member(ctx.author.id)
                        if member.roles and len(member.roles) > 0:
                            for r in member.roles:
                                if str(r.id) in serverinfo['feature_roles']:
                                    extra_amount = amount * serverinfo['feature_roles'][str(r.id)]['faucet_multipled_by'] - amount
                                    if extra_amount > previous_amount:
                                        previous_amount = extra_amount
                            extra_amount = previous_amount
                    except Exception:
                        traceback.print_exc(file=sys.stdout)

                cutting_duration = 0
                previous_duration = 0
                if serverinfo['feature_roles'] is not None:
                    try:
                        member = ctx.guild.get_member(ctx.author.id)
                        if member.roles and len(member.roles) > 0:
                            for r in member.roles:
                                if str(r.id) in serverinfo['feature_roles']:
                                    cutting_duration = int(duration * serverinfo['feature_roles'][str(r.id)]['faucet_cut_time_percent'])
                                    if cutting_duration > previous_duration:
                                        previous_duration = cutting_duration
                            cutting_duration = previous_duration
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                    coin_name = self.bot.coin_alias_names[coin_name]
                if not hasattr(self.bot.coin_list, coin_name):
                    msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
                    await ctx.edit_original_message(content=msg)
                    return

                get_last_claim = await self.get_faucet_claim_user_guild(str(ctx.author.id), str(ctx.guild.id), SERVER_BOT)
                extra_msg = ""
                if cutting_duration > 0:
                    extra_msg = " You have active guild's role(s) that cut {}'s waiting time by: **{}**.".format(
                        command_mention, seconds_str_days(cutting_duration)
                    )
                if get_last_claim is not None and int(time.time()) - get_last_claim['date'] < duration - cutting_duration:
                    # last_duration = seconds_str(int(time.time()) - get_last_claim['date'])
                    last_duration = disnake.utils.format_dt(
                        get_last_claim['date'],
                        style='f'
                    )
                    # waiting_time = seconds_str(duration - cutting_duration - int(time.time()) + get_last_claim['date'])
                    waiting_time = disnake.utils.format_dt(
                        duration - cutting_duration + get_last_claim['date'],
                        style='R'
                    )
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you claimed in this guild "\
                        f"__{ctx.guild.name}__ on {last_duration}. Waiting time {waiting_time}."\
                        f"{extra_msg} Other reward command {self.bot.config['command_list']['take']}, "\
                        f"{self.bot.config['command_list']['claim']}, {self.bot.config['command_list']['daily']} "\
                        f"and {self.bot.config['command_list']['hourly']}."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    # OK claim
                    net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                    type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                    deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                    token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                    coin_emoji = ""
                    try:
                        if ctx.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is True:
                            coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                            coin_emoji = coin_emoji + " " if coin_emoji else ""
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
                    max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
                    price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")

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
                    userdata_balance = await store.sql_user_balance_single(
                        str(ctx.guild.id), coin_name, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT
                    )
                    actual_balance = float(userdata_balance['adjust'])
                    # Check if tx in progress
                    if str(ctx.guild.id) in self.bot.tipping_in_progress and \
                        int(time.time()) - self.bot.tipping_in_progress[str(ctx.guild.id)] < 150:
                        msg = f"{EMOJI_ERROR} {ctx.author.mention}, another transaction in progress with this guild."
                        await ctx.edit_original_message(content=msg)
                        return

                    if amount + extra_amount <= 0:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, please topup guild with more **{coin_name}** by {self.bot.config['command_list']['guild_deposit']}"
                        await ctx.edit_original_message(content=msg)
                        return

                    if amount + extra_amount > actual_balance:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, guild has insufficient balance for "\
                            f"{num_format_coin(amount + extra_amount)} {token_display}."
                        await ctx.edit_original_message(content=msg)
                        return
                    elif amount + extra_amount < min_tip or amount + extra_amount > max_tip:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, transaction cannot be smaller than "\
                            f"{num_format_coin(min_tip)} {token_display} or "\
                            f"bigger than {num_format_coin(max_tip)} {token_display}."
                        await ctx.edit_original_message(content=msg)
                        return

                    equivalent_usd = ""
                    amount_in_usd = 0.0
                    if price_with:
                        per_unit = await self.utils.get_coin_price(coin_name, price_with)
                        if per_unit and per_unit['price'] and per_unit['price'] > 0:
                            per_unit = per_unit['price']
                            amount_in_usd = float(Decimal(per_unit) * Decimal(amount + extra_amount))
                            if amount_in_usd > 0.0001:
                                equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
                    if str(ctx.guild.id) not in self.bot.tipping_in_progress:
                        self.bot.tipping_in_progress[str(ctx.guild.id)] = int(time.time())
                        try:
                            tip = await store.sql_user_balance_mv_single(
                                str(ctx.guild.id), str(ctx.author.id), str(ctx.guild.id), str(ctx.channel.id),
                                amount + extra_amount, coin_name, 'GUILDFAUCET', coin_decimal, SERVER_BOT, contract, amount_in_usd, None
                            )
                            if tip:
                                extra_msg = ""
                                if extra_amount > 0:
                                    extra_msg = f" You have a guild's role that give you additional bonus {coin_emoji}**" + \
                                        num_format_coin(extra_amount) + " " + coin_name + "**."
                                msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention} got a faucet of "\
                                    f"{coin_emoji}**{num_format_coin(amount + extra_amount)}"\
                                    f" {coin_name}**{equivalent_usd} from __{ctx.guild.name}__.{extra_msg} "\
                                    f"{self.bot.config['command_list']['take']}, "\
                                    f"{self.bot.config['command_list']['claim']}, {self.bot.config['command_list']['daily']} "\
                                    f"and {self.bot.config['command_list']['hourly']}. Invite me to your guild? "\
                                    f"Click on my name and `Add to Server`."
                                await ctx.edit_original_message(content=msg)
                                await logchanbot(
                                    f"[{SERVER_BOT}] User {ctx.author.name}#{ctx.author.discriminator} "\
                                    f"claimed guild /faucet {num_format_coin(amount + extra_amount)}"\
                                    f" {coin_name} in guild {ctx.guild.name}/{ctx.guild.id}."
                                )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        try:
                            del self.bot.tipping_in_progress[str(ctx.guild.id)]
                        except Exception:
                            pass
            else:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, this guild __{ctx.guild.name}__ has no guild's faucet. "\
                    f"You can ask Guild'owner to deposit to Guild with {self.bot.config['command_list']['guild_deposit']} and "\
                    f"create it with {self.bot.config['command_list']['guild_faucetclaim']}."
                await ctx.edit_original_message(content=msg)
                await logchanbot(
                    f"[{SERVER_BOT}] [ERROR] User {ctx.author.name}#{ctx.author.discriminator} "\
                    f"claimed guild /faucet in guild {ctx.guild.name}/{ctx.guild.id}."
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("guild " +str(traceback.format_exc()))
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error.'
            await ctx.edit_original_message(content=msg)
    # Guild deposit

    # Setting command
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.slash_command(
        dm_permission=False,
        description="Guild setting commands."
    )
    async def setting(
        self, ctx
    ):
        pass

    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting tiponly <coin1, coin2, ....>", 
        options=[
            Option('coin_list', 'coin_list', OptionType.string, required=True)
        ],
        description="Allow only these coins for tipping"
    )
    async def tiponly(self, ctx, coin_list: str):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, setting loading..."
        await ctx.response.send_message(msg)
        await self.bot_log()
        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            # re-load guild list
            await self.utils.bot_reload_guilds()
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))

        coin_list = coin_list.upper()
        if coin_list in ["ALLCOIN", "*", "ALL", "TIPALL", "ANY"]:
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'tiponly', "ALLCOIN")
            if self.enable_logchan:
                await self.botLogChan.send(
                    f"{ctx.author.name} / {ctx.author.id} changed tiponly in {ctx.guild.name} / {ctx.guild.id} to __ALLCOIN__"
                )
            msg = f"{ctx.author.mention}, all coins will be allowed in here."
            await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
        elif " " in coin_list or "," in coin_list:
            # multiple coins
            if " " in coin_list:
                coins = coin_list.split()
            elif "," in coin_list:
                coins = coin_list.split(",")
            contained = []
            if len(coins) > 0:
                for each_coin in coins:
                    if not hasattr(self.bot.coin_list, each_coin.upper()):
                        continue
                    else:
                        contained.append(each_coin.upper())
            if contained and len(contained) >= 2:
                tiponly_value = ','.join(contained)
                if self.enable_logchan:
                    await self.botLogChan.send(
                        f'{ctx.author.name} / {ctx.author.id} changed tiponly in {ctx.guild.name} / {ctx.guild.id} to __{tiponly_value}__'
                    )
                msg = f'{ctx.author.mention} TIPONLY for guild {ctx.guild.name} set to: **{tiponly_value}**.'
                await ctx.edit_original_message(content=msg)
                await store.sql_changeinfo_by_server(str(ctx.guild.id), 'tiponly', tiponly_value.upper())
                # re-load guild list
                await self.utils.bot_reload_guilds()
            else:
                msg = f"{ctx.author.mention} No known coin in **{coin_list}**. TIPONLY is remained unchanged in guild __{ctx.guild.name}__."
                await ctx.edit_original_message(content=msg)
        else:
            # Single coin
            if coin_list not in self.bot.coin_name_list:
                msg = f"{ctx.author.mention} {coin_list} is not in any known coin we set."
                await ctx.edit_original_message(content=msg)
            else:
                # coin_list is single coin set_coin
                await store.sql_changeinfo_by_server(str(ctx.guild.id), 'tiponly', coin_list)
                if self.enable_logchan:
                    await self.botLogChan.send(
                        f"{ctx.author.name} / {ctx.author.id} changed tiponly in {ctx.guild.name} / {ctx.guild.id} to __{coin_list}__"
                    )
                msg = f"{ctx.author.mention} {coin_list} will be the only tip here in guild __{ctx.guild.name}__."
                await ctx.edit_original_message(content=msg)
                # re-load guild list
                await self.utils.bot_reload_guilds()

    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        name="mutetip",
        usage="setting mutetip", 
        description="Toggle ping people ON/OFF in your guild, when people tip"
    )
    async def setting_mutetip(
        self, 
        ctx,
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, setting loading..."
        await ctx.response.send_message(msg)
        await self.bot_log()
        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            # re-load guild list
            await self.utils.bot_reload_guilds()
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
                                                                
        if serverinfo and serverinfo['mute_tip'] == "YES":
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'mute_tip', 'NO')
            if self.enable_logchan:
                await self.botLogChan.send(
                    f"{ctx.author.name} / {ctx.author.id} enable PING (mention) "\
                    f"in their guild {ctx.guild.name} / {ctx.guild.id}"
                )
            msg = f"{ctx.author.mention} enable PING (mention) when user(s) got tipped in their guild {ctx.guild.name}."
            await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
        elif serverinfo and serverinfo['mute_tip'] == "NO":
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'mute_tip', 'YES')
            if self.enable_logchan:
                await self.botLogChan.send(
                    f"{ctx.author.name} / {ctx.author.id} disable PING (no mention) "\
                    f"in their guild {ctx.guild.name} / {ctx.guild.id}"
                )
            msg = f"{ctx.author.mention} disable PING (no mention) when user(s) got tipped in this guild {ctx.guild.name}."
            await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
        else:
            msg = f"{ctx.author.mention}, internal error when calling serverinfo function."
            await ctx.edit_original_message(content=msg)

    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting trade", 
        description="Toggle trade enable ON/OFF in your guild"
    )
    async def trade(
        self, 
        ctx,
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, setting loading..."
        await ctx.response.send_message(msg)
        await self.bot_log()
        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            # re-load guild list
            await self.utils.bot_reload_guilds()
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
                                                                
        if serverinfo and serverinfo['enable_trade'] == "YES":
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_trade', 'NO')
            if self.enable_logchan:
                await self.botLogChan.send(
                    f"{ctx.author.name} / {ctx.author.id} DISABLE trade in their guild {ctx.guild.name} / {ctx.guild.id}"
                )
            msg = f"{ctx.author.mention} DISABLE TRADE feature in this guild {ctx.guild.name}."
            await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
        elif serverinfo and serverinfo['enable_trade'] == "NO":
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_trade', 'YES')
            if self.enable_logchan:
                await self.botLogChan.send(
                    f"{ctx.author.name} / {ctx.author.id} ENABLE trade in their guild {ctx.guild.name} / {ctx.guild.id}"
                )
            msg = f"{ctx.author.mention} ENABLE TRADE feature in this guild {ctx.guild.name}. "\
                "You can assign trade channel by `SETTING TRADECHAN`"
            await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
        else:
            msg = f"{ctx.author.mention}, internal error when calling serverinfo function."
            await ctx.edit_original_message(content=msg)

    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting memepls", 
        description="Toggle memepls enable ON/OFF in your guild"
    )
    async def memepls(
        self, 
        ctx,
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, setting loading..."
        await ctx.response.send_message(msg)
        await self.bot_log()
        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            # re-load guild list
            await self.utils.bot_reload_guilds()
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
                                                                
        if serverinfo and serverinfo['enable_memepls'] == "YES":
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_memepls', 'NO')
            if self.enable_logchan:
                await self.botLogChan.send(
                    f'{ctx.author.name} / {ctx.author.id} DISABLE /memepls in their guild {ctx.guild.name} / {ctx.guild.id}'
                )
            msg = f"{ctx.author.mention} DISABLE /memepls feature in this guild {ctx.guild.name}."
            await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
        elif serverinfo and serverinfo['enable_memepls'] == "NO":
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_memepls', 'YES')
            if self.enable_logchan:
                await self.botLogChan.send(
                    f"{ctx.author.name} / {ctx.author.id} ENABLE /memepls in their guild {ctx.guild.name} / {ctx.guild.id}"
                )
            msg = f"{ctx.author.mention} ENABLE /memepls feature in this guild {ctx.guild.name}."
            await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
        else:
            msg = f"{ctx.author.mention}, internal error when calling serverinfo function."
            await ctx.edit_original_message(content=msg)

    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting nsfw", 
        description="Toggle nsfw ON/OFF in your guild"
    )
    async def nsfw(
        self, 
        ctx,
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, setting loading..."
        await ctx.response.send_message(msg)
        await self.bot_log()
        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            # re-load guild list
            await self.utils.bot_reload_guilds()
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))

        if serverinfo and serverinfo['enable_nsfw'] == "YES":
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_nsfw', 'NO')
            if self.enable_logchan:
                await self.botLogChan.send(
                    f"{ctx.author.name} / {ctx.author.id} DISABLE NSFW in their guild {ctx.guild.name} / {ctx.guild.id}"
                )
            msg = f"{ctx.author.mention} DISABLE NSFW command in this guild {ctx.guild.name}."
            await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
        elif serverinfo and serverinfo['enable_nsfw'] == "NO":
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_nsfw', 'YES')
            if self.enable_logchan:
                await self.botLogChan.send(
                    f"{ctx.author.name} / {ctx.author.id} ENABLE NSFW in their guild {ctx.guild.name} / {ctx.guild.id}"
                )
            msg = f"{ctx.author.mention} ENABLE NSFW command in this guild {ctx.guild.name}."
            await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
        else:
            msg = f"{ctx.author.mention}, internal error when calling serverinfo function."
            await ctx.edit_original_message(content=msg)

    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting game", 
        description="Toggle game ON/OFF in your guild"
    )
    async def game(
        self, 
        ctx,
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, setting loading..."
        await ctx.response.send_message(msg)
        await self.bot_log()
        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            # re-load guild list
            await self.utils.bot_reload_guilds()
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo and serverinfo['enable_game'] == "YES":
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_game', 'NO')
            if self.enable_logchan:
                await self.botLogChan.send(
                    f"{ctx.author.name} / {ctx.author.id} DISABLE game in their guild {ctx.guild.name} / {ctx.guild.id}"
                )
            msg = f"{ctx.author.mention} DISABLE GAME feature in this guild {ctx.guild.name}."
            await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
        elif serverinfo and serverinfo['enable_game'] == "NO":
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_game', 'YES')
            if self.enable_logchan:
                await self.botLogChan.send(
                    f"{ctx.author.name} / {ctx.author.id} ENABLE game in their guild {ctx.guild.name} / {ctx.guild.id}"
                )
            msg = f"{ctx.author.mention} ENABLE GAME feature in this guild {ctx.guild.name}."
            await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
        else:
            msg = f"{ctx.author.mention}, internal error when calling serverinfo function."
            await ctx.edit_original_message(content=msg)

    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting botchan", 
        description="Set bot channel to the commanded channel"
    )
    async def botchan(
        self, 
        ctx,
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, setting loading..."
        await ctx.response.send_message(msg)
        await self.bot_log()
        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            # re-load guild list
            await self.utils.bot_reload_guilds()
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo['botchan']:
            try: 
                if ctx.channel.id == int(serverinfo['botchan']):
                    msg = f"{EMOJI_RED_NO} {ctx.channel.mention} is already the bot channel here!"
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    # change channel info
                    await store.sql_changeinfo_by_server(str(ctx.guild.id), 'botchan', str(ctx.channel.id))
                    msg = f'Bot channel of guild {ctx.guild.name} has set to {ctx.channel.mention}.'
                    await ctx.edit_original_message(content=msg)
                    if self.enable_logchan:
                        await self.botLogChan.send(
                            f"{ctx.author.name} / {ctx.author.id} change bot channel "\
                            f"{ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}."
                        )
                    # re-load guild list
                    await self.utils.bot_reload_guilds()
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("guild " +str(traceback.format_exc()))
        else:
            # change channel info
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'botchan', str(ctx.channel.id))
            msg = f'Bot channel of guild {ctx.guild.name} has set to {ctx.channel.mention}.'
            await ctx.edit_original_message(content=msg)
            if self.enable_logchan:
                await self.botLogChan.send(
                    f"{ctx.author.name} / {ctx.author.id} changed bot channel "\
                    f"{ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}."
                )
            # re-load guild list
            await self.utils.bot_reload_guilds()

    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting economychan", 
        description="Set economy game channel to the commanded channel"
    )
    async def economychan(
        self, 
        ctx,
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, setting loading..."
        await ctx.response.send_message(msg)
        await self.bot_log()
        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            # re-load guild list
            await self.utils.bot_reload_guilds()
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo['economy_channel']:
            try: 
                if ctx.channel.id == int(serverinfo['economy_channel']):
                    msg = f"{EMOJI_RED_NO} {ctx.channel.mention} is already the economy game channel here!"
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    # change channel info
                    await store.sql_changeinfo_by_server(str(ctx.guild.id), 'economy_channel', str(ctx.channel.id))
                    msg = f'Economy game channel of guild {ctx.guild.name} has set to {ctx.channel.mention}.'
                    await ctx.edit_original_message(content=msg)
                    if self.enable_logchan:
                        await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} change economy game channel {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')
                    # re-load guild list
                    await self.utils.bot_reload_guilds()
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("guild " +str(traceback.format_exc()))
        else:
            # change channel info
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'economy_channel', str(ctx.channel.id))
            msg = f'Economy game channel of guild {ctx.guild.name} has set to {ctx.channel.mention}.'
            await ctx.edit_original_message(content=msg)
            if self.enable_logchan:
                await self.botLogChan.send(
                    f"{ctx.author.name} / {ctx.author.id} changed economy game channel "\
                    f"{ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}."
                )
            # re-load guild list
            await self.utils.bot_reload_guilds()

    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        name="tradechan",
        usage="setting tradechan", 
        description="Set trade channel to the commanded channel"
    )
    async def tradechan(
        self, 
        ctx,
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, setting loading..."
        await ctx.response.send_message(msg)
        await self.bot_log()
        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            # re-load guild list
            await self.utils.bot_reload_guilds()
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo['trade_channel']:
            try: 
                if ctx.channel.id == int(serverinfo['trade_channel']):
                    msg = f"{EMOJI_RED_NO} {ctx.channel.mention} is already the trade channel here!"
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    # change channel info
                    update = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'trade_channel', str(ctx.channel.id))
                    msg = f"Trade channel of guild {ctx.guild.name} has set to {ctx.channel.mention}."
                    await ctx.edit_original_message(content=msg)
                    # re-load guild list
                    await self.utils.bot_reload_guilds()
                    if update is True:
                        # kv trade guild channel
                        try:
                            await self.utils.async_set_cache_kv(
                                "market_guild",
                                str(ctx.guild.id),
                                ctx.channel.id
                            )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    if self.enable_logchan:
                        await self.botLogChan.send(
                            f"{ctx.author.name} / {ctx.author.id} change trade channel "\
                            f"{ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}."
                        )
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("guild " +str(traceback.format_exc()))
        else:
            # change channel info
            update = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'trade_channel', str(ctx.channel.id))
            msg = f"Trade channel of guild {ctx.guild.name} has set to {ctx.channel.mention}."
            await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
            if update is True:
                # kv trade guild channel
                try:
                    await self.utils.async_set_cache_kv(
                        "market_guild",
                        str(ctx.guild.id),
                        ctx.channel.id
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            if self.enable_logchan:
                await self.botLogChan.send(
                    f"{ctx.author.name} / {ctx.author.id} changed trade channel "\
                    f"{ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}."
                )

    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting setfaucet", 
        description="Toggle faucet enable ON/OFF in your guild"
    )
    async def setfaucet(
        self, 
        ctx,
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, setting loading..."
        await ctx.response.send_message(msg)
        await self.bot_log()
        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            # re-load guild list
            await self.utils.bot_reload_guilds()
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))

        if serverinfo and serverinfo['enable_faucet'] == "YES":
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_faucet', 'NO')
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} DISABLE faucet (take) command in their guild {ctx.guild.name} / {ctx.guild.id}')
            msg = f"{ctx.author.mention} DISABLE faucet (take/claim) command in this guild {ctx.guild.name}."
            await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
        elif serverinfo and serverinfo['enable_faucet'] == "NO":
            await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_faucet', 'YES')
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} ENABLE faucet (take) command in their guild {ctx.guild.name} / {ctx.guild.id}')
            msg = f"{ctx.author.mention} ENABLE faucet (take/claim) command in this guild {ctx.guild.name}."
            await ctx.edit_original_message(content=msg)
            # re-load guild list
            await self.utils.bot_reload_guilds()
        else:
            msg = f"{ctx.author.mention}, internal error when calling serverinfo function."
            await ctx.edit_original_message(content=msg)

    async def async_set_gamechan(self, ctx, game):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, setting loading..."
        await ctx.response.send_message(msg)
        if game is None:
            msg = f"{EMOJI_RED_NO} {ctx.channel.mention} please mention a game name to set game channel for it. Game list: "\
                f"{', '.join(self.bot.config['game']['game_list'])}."
            await ctx.edit_original_message(content=msg)
            return
        else:
            game = game.lower()
            if game not in self.bot.config['game']['game_list']:
                msg = f"{EMOJI_RED_NO} {ctx.channel.mention} please mention a game name within this list"\
                    f": {', '.join(self.bot.config['game']['game_list'])}."
                await ctx.edit_original_message(content=msg)
                return
            else:
                serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
                index_game = "game_" + game + "_channel"
                if serverinfo is None:
                    # Let's add some info if server return None
                    await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
                    # re-load guild list
                    await self.utils.bot_reload_guilds()
                    serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
                if serverinfo[index_game]:
                    try: 
                        if ctx.channel.id == int(serverinfo[index_game]):
                            msg = f"{EMOJI_RED_NO} {ctx.channel.mention} is already for game **{game}** channel here!"
                            await ctx.edit_original_message(content=msg)
                        else:
                            # change channel info
                            await store.sql_changeinfo_by_server(str(ctx.guild.id), index_game, str(ctx.channel.id))
                            msg = f"{ctx.channel.mention} Game **{game}** channel has set to {ctx.channel.mention}."
                            await ctx.edit_original_message(content=msg)
                            # re-load guild list
                            await self.utils.bot_reload_guilds()
                            if self.enable_logchan:
                                await self.botLogChan.send(
                                    f"{ctx.author.name} / {ctx.author.id} changed game **{game}** in channel"\
                                    f" {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}."
                                )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("guild " +str(traceback.format_exc()))
                else:
                    # change channel info
                    await store.sql_changeinfo_by_server(str(ctx.guild.id), index_game, str(ctx.channel.id))
                    msg = f"{ctx.channel.mention} Game **{game}** channel has set to {ctx.channel.mention}."
                    await ctx.edit_original_message(content=msg)
                    # re-load guild list
                    await self.utils.bot_reload_guilds()
                    if self.enable_logchan:
                        await self.botLogChan.send(
                            f"{ctx.author.name} / {ctx.author.id} set game **{game}** channel "\
                            f"in {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}."
                        )

    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting gamechan <game>", 
        options=[
            Option('game', 'game', OptionType.string, required=True, choices=[
                OptionChoice("2048", "2048"),
                OptionChoice("BLACKJACK", "BLACKJACK"),
                OptionChoice("DICE", "DICE"),
                OptionChoice("MAZE", "MAZE"),
                OptionChoice("SLOT", "SLOT"),
                OptionChoice("SNAIL", "SNAIL"),
                OptionChoice("SOKOBAN", "SOKOBAN")
            ]
            )
        ],
        description="Set guild's specific game channel."
    )
    async def gamechan(
        self, 
        ctx,
        game: str
    ):
        await self.async_set_gamechan(ctx, game)

    # End of setting

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(description="Get role counts in the Guild.")
    async def rolecount(self, ctx):
        color = disnake.Color.gold()
        embed = disnake.Embed(color=color, timestamp=datetime.now())
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator} | /rolecount")
        total_role = 0
        for r in ctx.guild.roles:
            nmembers = len(r.members)
            if len(r.members) > 1:
                total_role += 1
                embed.add_field(name=f"{r.name}", value=f"{nmembers:,}")
        embed.add_field(name="Total Roles", value=str(total_role), inline=False)
        await ctx.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.monitor_guild_reward_amount.is_running():
                self.monitor_guild_reward_amount.start()
            if not self.check_tiptalker_drop.is_running():
                self.check_tiptalker_drop.start()

    async def cog_load(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.monitor_guild_reward_amount.is_running():
                self.monitor_guild_reward_amount.start()
            if not self.check_tiptalker_drop.is_running():
                self.check_tiptalker_drop.start()

    def cog_unload(self):
        # Ensure the task is stopped when the cog is unloaded.
        self.monitor_guild_reward_amount.cancel()
        self.check_tiptalker_drop.cancel()


def setup(bot):
    bot.add_cog(Guild(bot))