import random
import re
import sys
import time
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Dict
import asyncio
from unittest.util import strclass
from cachetools import TTLCache

import disnake
import store
from Bot import num_format_coin, logchanbot, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_INFORMATION, SERVER_BOT, text_to_num, \
    truncate, seconds_str_days
from cogs.wallet import WalletAPI
from disnake.app_commands import Option
from disnake.enums import ButtonStyle
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

from disnake.ext import commands, tasks

from cogs.utils import Utils

class TalkDropButton(disnake.ui.View):
    message: disnake.Message
    channel_interact: disnake.TextChannel
    coin_list: Dict

    def __init__(self, ctx, timeout: float, coin_list, bot, channel_interact):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.coin_list = coin_list
        self.ctx = ctx
        self.channel_interact = channel_interact

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True

        ## Update content
        try:
            channel = self.bot.get_channel(self.channel_interact)
            _msg: disnake.Message = await channel.fetch_message(self.message.id)
            await _msg.edit(content=None, view=None)
        except Exception:
            traceback.print_exc(file=sys.stdout)


    @disnake.ui.button(label="Collect", style=ButtonStyle.green, custom_id="talkdrop_tipbot")
    async def join_talkdrop(
            self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        pass


class TalkDrop(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.max_ongoing_by_user = 3
        self.max_ongoing_by_guild = 5
        self.max_messagge_cap = 100
        self.talkdrop_cache = TTLCache(maxsize=2000, ttl=60.0) # if previous value and new value the same, no need to edit
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)


    @tasks.loop(seconds=30.0)
    async def talkdrop_check(self):
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "talkdrop_check"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 10: # not running if less than 10s
            return
        try:
            get_list_talkdrop = await store.get_all_talkdrop("ONGOING")
            if len(get_list_talkdrop) > 0:
                for each_talkdrop in get_list_talkdrop:
                    await self.bot.wait_until_ready()
                    # print("Checkping talkdrop: {}".format(each_talkdrop['message_id']))
                    try:
                        attend_list = await store.get_talkdrop_collectors(each_talkdrop['message_id'])
                        # Update view
                        owner_displayname = each_talkdrop['from_ownername']
                        equivalent_usd = each_talkdrop['real_amount_usd_text']

                        coin_name = each_talkdrop['token_name']
                        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                        time_passed = int(time.time()) - each_talkdrop['talked_from_when']
                        # If talkdrop ends
                        if each_talkdrop['talkdrop_time'] < int(time.time()):
                            embed = disnake.Embed(
                                title="✍️ Talk Drop Ends! ✍️",
                                description="You can collect only if you have chatted in channel <#{}> from {} ago.".format(each_talkdrop['talked_in_channel'], seconds_str_days(time_passed)),
                                timestamp=datetime.fromtimestamp(each_talkdrop['talkdrop_time']))
                            embed.set_footer(text=f"Contributed by {owner_displayname} | /talkdrop | Ended")
                            all_name_list = []
                            if len(attend_list) > 0:
                                name_list = []
                                for each_att in attend_list:
                                    name_list.append("<@{}>".format(each_att['collector_id']))
                                    all_name_list.append(each_att['collector_id'])
                                    if len(name_list) > 0 and len(name_list) % 40 == 0:
                                        embed.add_field(name='Collectors', value=", ".join(name_list), inline=False)
                                        name_list = []
                                if len(name_list) > 0:
                                    embed.add_field(name='Collectors', value=", ".join(name_list), inline=False)
                            indiv_amount = each_talkdrop['real_amount'] / len(all_name_list) if len(all_name_list) > 0 else each_talkdrop['real_amount']
                            amount_in_usd = indiv_amount * each_talkdrop['unit_price_usd'] if each_talkdrop['unit_price_usd'] and each_talkdrop['unit_price_usd'] > 0.0 else 0.0
                            indiv_amount_str = num_format_coin(indiv_amount, coin_name, coin_decimal, False)
                            embed.add_field(
                                name='Each Member Receives:',
                                value=f"{indiv_amount_str} {token_display}",
                                inline=True
                            )
                            embed.add_field(
                                name='Total Amount', 
                                value=num_format_coin(each_talkdrop['real_amount'], coin_name, coin_decimal, False) + " " + coin_name,
                                inline=True
                            )
                            embed.add_field(
                                name='Minimum Messages',
                                value=each_talkdrop['minimum_message'],
                                inline=True
                            )
                            try:
                                channel = self.bot.get_channel(int(each_talkdrop['channel_id']))
                                if channel:
                                    try:
                                        _msg: disnake.Message = await channel.fetch_message(int(each_talkdrop['message_id']))
                                        await _msg.edit(content=None, embed=embed, view=None)
                                        # Update balance
                                        if len(all_name_list) > 0:
                                            try:
                                                key_coin = each_talkdrop['from_userid'] + "_" + coin_name + "_" + SERVER_BOT
                                                if key_coin in self.bot.user_balance_cache:
                                                    del self.bot.user_balance_cache[key_coin]

                                                for each in all_name_list:
                                                    key_coin = each + "_" + coin_name + "_" + SERVER_BOT
                                                    if key_coin in self.bot.user_balance_cache:
                                                        del self.bot.user_balance_cache[key_coin]
                                            except Exception:
                                                pass
                                            talkdrop = await store.sql_user_balance_mv_multiple(each_talkdrop['from_userid'], all_name_list, each_talkdrop['guild_id'], each_talkdrop['channel_id'], indiv_amount, coin_name, "TALKDROP", coin_decimal, SERVER_BOT, each_talkdrop['contract'], float(amount_in_usd), None)
                                        await store.update_talkdrop_id(each_talkdrop['message_id'], "COMPLETED" if len(all_name_list) > 0 else "NOCOLLECT")
                                    except disnake.errors.NotFound:
                                        await logchanbot("talkdrop_check: can not find message ID: {} in channel {}.".format(each_talkdrop['message_id'], each_talkdrop['channel_id']))
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                else:
                                    await logchanbot("talkdrop_check: can not find channel {} for message ID: {}".format(each_talkdrop['channel_id'], each_talkdrop['message_id']))
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                        else:
                            embed = disnake.Embed(
                                title="✍️ Talk Drop ✍️",
                                description="You can collect only if you have chatted in channel <#{}> from {} ago.".format(each_talkdrop['talked_in_channel'], seconds_str_days(time_passed)),
                                timestamp=datetime.fromtimestamp(each_talkdrop['talkdrop_time']))

                            time_left = seconds_str_days(each_talkdrop['talkdrop_time'] - int(time.time())) if int(time.time()) < each_talkdrop['talkdrop_time'] else "00:00:00"
                            lap_div = int((each_talkdrop['talkdrop_time'] - int(time.time()))/30)
                            embed.set_footer(text=f"Contributed by {owner_displayname} | /talkdrop | Time left: {time_left}")
                            name_list = []
                            user_tos = []
                            if len(attend_list) > 0:
                                for each_att in attend_list:
                                    name_list.append("<@{}>".format(each_att['collector_id']))
                                    user_tos.append(each_att['collector_id'])
                                    if len(name_list) > 0 and len(name_list) % 40 == 0:
                                        embed.add_field(name='Collectors', value=", ".join(name_list), inline=False)
                                        name_list = []
                                if len(name_list) > 0:
                                    embed.add_field(name='Collectors', value=", ".join(name_list), inline=False)
                                user_tos = list(set(user_tos))
                            indiv_amount = each_talkdrop['real_amount'] / len(user_tos) if len(user_tos) > 0 else each_talkdrop['real_amount']
                            try:
                                key = each_talkdrop['message_id']
                                if self.talkdrop_cache[key] == "{}_{}_{}".format(len(user_tos), each_talkdrop['real_amount'], lap_div):
                                    continue # to next, no need to edit
                                else:
                                    self.talkdrop_cache[key] = "{}_{}_{}".format(len(user_tos), each_talkdrop['real_amount'], lap_div)
                            except Exception:
                                pass
                            indiv_amount_str = num_format_coin(indiv_amount, coin_name, coin_decimal, False)
                            embed.add_field(
                                name='Each Member Receives:',
                                value=f"{indiv_amount_str} {token_display}",
                                inline=True
                            )
                            embed.add_field(
                                name='Total Amount', 
                                value=num_format_coin(each_talkdrop['real_amount'], coin_name, coin_decimal, False) + " " + coin_name,
                                inline=True
                            )
                            embed.add_field(
                                name='Minimum Messages',
                                value=each_talkdrop['minimum_message'],
                                inline=True
                            )
                            try:
                                channel = self.bot.get_channel(int(each_talkdrop['channel_id']))
                                if channel is None:
                                    await logchanbot("talkdrop_check: can not find channel ID: {}".format(each_talkdrop['channel_id']))
                                    await asyncio.sleep(2.0)
                                else:
                                    try:
                                        _msg: disnake.Message = await channel.fetch_message(int(each_talkdrop['message_id']))
                                        await _msg.edit(content=None, embed=embed)
                                    except disnake.errors.NotFound:
                                        # add fail check
                                        turn_off = False
                                        if each_talkdrop['failed_check'] > 3:
                                            turn_off = True
                                        await store.update_talkdrop_failed(each_talkdrop['message_id'], turn_off)
                                        await logchanbot("talkdrop_check: can not find message ID: {} in channel: {}".format(each_talkdrop['message_id'], each_talkdrop['channel_id']))
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                await asyncio.sleep(2.0)
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("talkdrop_check " +str(traceback.format_exc()))
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))

    async def async_talkdrop(self, ctx, amount: str, token: str, channel: disnake.TextChannel, 
                             from_when: str, end: str, minimum_message: int):
        coin_name = token.upper()
        await ctx.response.send_message(f"{ctx.author.mention}, /talkdrop preparation... ")

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/talkdrop", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # Token name check
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.edit_original_message(content=msg)
            return
        # End token name check

        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo['tiponly'] and serverinfo['tiponly'] != "ALLCOIN" and coin_name not in serverinfo[
            'tiponly'].split(","):
            allowed_coins = serverinfo['tiponly']
            msg = f'{ctx.author.mention}, **{coin_name}** is not allowed here. Currently, allowed `{allowed_coins}`. You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`'
            await ctx.edit_original_message(content=msg)
            return

        # check minimum_message
        if minimum_message < 1 or minimum_message > self.max_messagge_cap:
            msg = f'{ctx.author.mention}, `minimum_message` shall be between 1 to {str(self.max_messagge_cap)}.'
            await ctx.edit_original_message(content=msg)
            return

        # if coin is allowed for talkdrop
        if getattr(getattr(self.bot.coin_list, coin_name), "enable_talkdrop") != 1:
            msg = f'{ctx.author.mention}, **{coin_name}** not enable with `/talkdrop`'
            await ctx.edit_original_message(content=msg)
            return

        # Check if there is many airdrop/mathtip/triviatip/partydrop/talkdrop
        try:
            count_ongoing = await store.discord_freetip_ongoing(str(ctx.author.id), "ONGOING")
            if count_ongoing >= self.max_ongoing_by_user and ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, you still have some ongoing tips. Please wait for them to complete first!'
                await ctx.edit_original_message(content=msg)
                return
            count_ongoing = await store.discord_freetip_ongoing_guild(str(ctx.guild.id), "ONGOING")
            # Check max if set in guild
            if serverinfo and count_ongoing >= serverinfo['max_ongoing_drop'] and ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, there are still some ongoing drops or tips in this guild. Please wait for them to complete first!'
                await ctx.edit_original_message(content=msg)
                return
            elif serverinfo is None and count_ongoing >= self.max_ongoing_by_guild and ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, there are still some ongoing drops or tips in this guild. Please wait for them to complete first!'
                await ctx.edit_original_message(content=msg)
                await logchanbot(f"[TALKDROP] server {str(ctx.guild.id)} has no data in discord_server.")
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # End of ongoing check

        try:
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")

            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")

            min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
            max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")
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

        except Exception:
            traceback.print_exc(file=sys.stdout)
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, some internal error. Please try again."
            await ctx.edit_original_message(content=msg)
            return

        height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        
        # Check amount
        if not amount.isdigit() and amount.upper() == "ALL":
            userdata_balance = await store.sql_user_balance_single(
                str(ctx.author.id), coin_name, wallet_address, type_coin, 
                height, deposit_confirm_depth, SERVER_BOT
            )
            amount = float(userdata_balance['adjust'])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]:  # last is $
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
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method.'
                    await ctx.edit_original_message(content=msg)
                    return
        else:
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                await ctx.edit_original_message(content=msg)
                return
        # end of check if amount is all

        # Check if tx in progress
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return

        try:
            amount = float(amount)
        except ValueError:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid amount.'
            await ctx.edit_original_message(content=msg)
            return

        userdata_balance = await store.sql_user_balance_single(
            str(ctx.author.id), coin_name, wallet_address, type_coin,
            height, deposit_confirm_depth, SERVER_BOT
        )
        actual_balance = float(userdata_balance['adjust'])

        if amount <= 0 or actual_balance <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
            await ctx.edit_original_message(content=msg)
            return

        if amount > max_tip or amount < min_tip:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, amount cannot be bigger than **{num_format_coin(max_tip, coin_name, coin_decimal, False)} {token_display}** or smaller than **{num_format_coin(min_tip, coin_name, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to do a drop of **{num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return

        # Check if channel is text channel
        if type(channel) is not disnake.TextChannel:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, that\'s not a text channel. Try a different channel!'
            await ctx.edit_original_message(content=msg)
            return

        # Check if there is enough talk in that channel
        message_talker = await store.sql_get_messages(
            str(ctx.guild.id), str(channel.id),int(from_when), None
        )
        if ctx.author.id in message_talker:
            message_talker.remove(ctx.author.id)
        if len(message_talker) <= 1:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there are not not enough active text in that channel {channel.mention}. Try again later!'
            await ctx.edit_original_message(content=msg)
            return

        if ctx.author.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.author.id)

        equivalent_usd = ""
        total_in_usd = 0.0
        per_unit = None
        if usd_equivalent_enable == 1:
            native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
            coin_name_for_price = coin_name
            if native_token_name:
                coin_name_for_price = native_token_name
            if coin_name_for_price in self.bot.token_hints:
                id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
            else:
                per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
            if per_unit and per_unit > 0:
                total_in_usd = float(Decimal(amount) * Decimal(per_unit))
                if total_in_usd >= 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(total_in_usd)

        duration_s = int(end)
        talkdrop_end = int(time.time()) + duration_s
        talked_from_when = int(time.time()) - int(from_when)
        owner_displayname = "{}#{}".format(ctx.author.name, ctx.author.discriminator)
        embed = disnake.Embed(
            title="✍️ Talk Drop ✍️",
            description="You can collect only if you have chatted in channel {} from {} ago.".format(channel.mention, seconds_str_days(int(from_when))),
            timestamp=datetime.fromtimestamp(talkdrop_end))
        embed.add_field(
            name='Total Amount',
            value=num_format_coin(amount, coin_name, coin_decimal, False) + " " + coin_name,
            inline=True
        )
        time_left = seconds_str_days(duration_s)
        embed.add_field(
            name='Minimum Messages',
            value=minimum_message,
            inline=True
        )
        embed.set_footer(text=f"Contributed by {owner_displayname} | /talkdrop | Time left: {time_left}")
        try:
            view = TalkDropButton(ctx, duration_s, self.bot.coin_list, self.bot, ctx.channel.id) 
            msg = await ctx.channel.send(content=None, embed=embed, view=view)
            view.message = msg
            view.channel_interact = ctx.channel.id
            await store.insert_talkdrop_create(
                coin_name, contract, str(ctx.author.id),
                owner_displayname, str(view.message.id),
                str(ctx.guild.id), str(ctx.channel.id), 
                str(channel.id), talked_from_when, minimum_message, 
                amount, total_in_usd, equivalent_usd,
                per_unit, coin_decimal, 
                talkdrop_end, "ONGOING"
            )
            await ctx.edit_original_message(content="/talkdrop created 👇")
        except Exception:
            traceback.print_exc(file=sys.stdout)
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.remove(ctx.author.id)

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        usage='talkdrop <amount> <token> <channel> <from when> <end>',
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option('channel', 'channel', OptionType.channel, required=True),
            Option('from_when', 'from_when', OptionType.string, required=True, choices=[
                OptionChoice("last 4h", "14400"),
                OptionChoice("last 8h", "28800"),
                OptionChoice("last 24h", "86400"),
                OptionChoice("last 2d", "172800"),
                OptionChoice("last 7d", "604800"),
                OptionChoice("last 30d", "2592000")
            ]),
            Option('end', 'end', OptionType.string, required=True, choices=[
                OptionChoice("in 1h", "3600"),
                OptionChoice("in 2h", "7200"),
                OptionChoice("in 4h", "14400"),
                OptionChoice("in 8h", "28800"),
                OptionChoice("in 24h", "86400"),
                OptionChoice("in 2d", "172800")
            ]),
            Option('minimum_message', 'minimum_message', OptionType.integer, required=True)
        ],
        description="Create tip talk drop for who actively chat in a channel to collect."
    )
    async def talkdrop(
        self,
        ctx,
        amount: str,
        token: str,
        channel: disnake.TextChannel,
        from_when: str,
        end: str,
        minimum_message: int
    ):
        await self.async_talkdrop(ctx, amount, token, channel, from_when, end, minimum_message)

    @commands.Cog.listener()
    async def on_ready(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.talkdrop_check.is_running():
                self.talkdrop_check.start()

    async def cog_load(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.talkdrop_check.is_running():
                self.talkdrop_check.start()

    def cog_unload(self):
        # Ensure the task is stopped when the cog is unloaded.
        self.talkdrop_check.cancel()
        

def setup(bot):
    bot.add_cog(TalkDrop(bot))
