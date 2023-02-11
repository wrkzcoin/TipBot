import random
import re
import sys
import time
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Dict
import asyncio
from cachetools import TTLCache

import disnake
import store
from Bot import logchanbot, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_INFORMATION, SERVER_BOT, text_to_num, \
    truncate, seconds_str_days
from cogs.wallet import WalletAPI
from disnake.app_commands import Option
from disnake.enums import ButtonStyle
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

from disnake.ext import commands, tasks
from cogs.utils import Utils, num_format_coin


class PartyButton(disnake.ui.View):
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


    @disnake.ui.button(label="Join (x1)", style=ButtonStyle.primary, custom_id="partydrop_tipbot")
    async def join_party(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        pass

    @disnake.ui.button(label="🎉 Join (x10)", style=ButtonStyle.green, custom_id="partydrop_tipbot_10x")
    async def join_party_10x(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        pass

    @disnake.ui.button(label="🎉🎉 Join (x40) 🎉🎉", style=ButtonStyle.danger, custom_id="partydrop_tipbot_40x")
    async def join_party_40x(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        pass


class PartyDrop(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.max_ongoing_by_user = 3
        self.max_ongoing_by_guild = 5
        self.party_cache = TTLCache(maxsize=2000, ttl=60.0) # if previous value and new value the same, no need to edit
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)


    @tasks.loop(seconds=30.0)
    async def party_check(self):
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "party_check"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 5: # not running if less than 15s
            return
        try:
            get_list_parties = await store.get_all_party("ONGOING")
            if len(get_list_parties) > 0:
                for each_party in get_list_parties:
                    await self.bot.wait_until_ready()
                    # print("Checkping party: {}".format(each_party['message_id']))
                    try:
                        get_message = await store.get_party_id(each_party['message_id'])
                        attend_list = await store.get_party_attendant(each_party['message_id'])
                        # Update view
                        owner_displayname = get_message['from_ownername']
                        sponsor_amount = get_message['init_amount']
                        equivalent_usd = get_message['real_init_amount_usd_text']
                        coin_name = get_message['token_name']
                        coin_emoji = ""
                        try:
                            channel = self.bot.get_channel(int(get_message['channel_id']))
                            if channel and channel.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is True:
                                coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                                coin_emoji = coin_emoji + " " if coin_emoji else ""
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                        total_amount = get_message['init_amount']
                        # If party ends
                        if each_party['partydrop_time'] < int(time.time()):
                            embed = disnake.Embed(
                                title=f"🎉 Party Drop Ends! 🎉",
                                description="Each click will deduct from your TipBot's balance. Minimum entrance cost: {}`{} {}`. "\
                                    "Party Pot will be distributed equally to all attendees after "\
                                    "completion.".format(
                                        coin_emoji,
                                        num_format_coin(get_message['minimum_amount']),
                                        coin_name
                                ),
                                timestamp=datetime.fromtimestamp(get_message['partydrop_time']))
                            embed.set_footer(text=f"Initiated by {owner_displayname} | /partydrop | Ended")
                            if len(coin_emoji) > 0:
                                extension = ".png"
                                if coin_emoji.startswith("<a:"):
                                    extension = ".gif"
                                split_id = coin_emoji.split(":")[2]
                                link = 'https://cdn.discordapp.com/emojis/' + str(split_id.replace(">", "")).strip() + extension
                                embed.set_thumbnail(url=link)
                            user_tos = []
                            user_tos.append({'from_user': get_message['from_userid'], 'to_user': str(self.bot.user.id), 'guild_id': get_message['guild_id'], 'channel_id': get_message['channel_id'], 'amount': get_message['init_amount'], 'coin': get_message['token_name'], 'decimal': get_message['token_decimal'], 'contract': get_message['contract'], 'real_amount_usd': get_message['real_init_amount_usd'], 'extra_message': None})
                            all_name_list = []
                            all_name_list.append(get_message['from_userid'])
                            if len(attend_list) > 0:
                                name_list = []
                                name_list.append("<@{}> : {} {}".format(get_message['from_userid'], num_format_coin(get_message['init_amount']), token_display))
                                for each_att in attend_list:
                                    name_list.append("<@{}> : {} {}".format(each_att['attendant_id'], num_format_coin(each_att['joined_amount']), token_display))
                                    total_amount += each_att['joined_amount']
                                    user_tos.append({'from_user': each_att['attendant_id'], 'to_user': str(self.bot.user.id), 'guild_id': get_message['guild_id'], 'channel_id': get_message['channel_id'], 'amount': each_att['joined_amount'], 'coin': get_message['token_name'], 'decimal': get_message['token_decimal'], 'contract': get_message['contract'], 'real_amount_usd': get_message['unit_price_usd']*each_att['joined_amount'] if get_message['unit_price_usd'] and get_message['unit_price_usd'] > 0 else 0.0, 'extra_message': None})
                                    
                                    all_name_list.append(each_att['attendant_id'])
                                    if len(name_list) > 0 and len(name_list) % 15 == 0:
                                        embed.add_field(name='Attendant', value="\n".join(name_list), inline=False)
                                        name_list = []
                                if len(name_list) > 0:
                                    embed.add_field(name='Attendant', value="\n".join(name_list), inline=False)
                            indiv_amount = total_amount / len(all_name_list) # including initiator
                            amount_in_usd = indiv_amount * get_message['unit_price_usd'] if get_message['unit_price_usd'] and get_message['unit_price_usd'] > 0.0 else 0.0
                            indiv_amount_str = num_format_coin(indiv_amount)
                            embed.add_field(
                                name='Each Member Receives:',
                                value=f"{coin_emoji}{indiv_amount_str} {token_display}",
                                inline=True
                            )
                            embed.add_field(
                                name='Started amount', 
                                value=coin_emoji + num_format_coin(get_message['init_amount']) + " " + coin_name,
                                inline=True
                            )
                            embed.add_field(
                                name='Party Pot', 
                                value=coin_emoji + num_format_coin(total_amount) + " " + coin_name,
                                inline=True
                            )
                            try:
                                channel = self.bot.get_channel(int(get_message['channel_id']))
                                if channel is None:
                                    await logchanbot("party_check: can not find channel ID: {}".format(each_party['channel_id']))
                                    await asyncio.sleep(2.0)
                                    continue
                                _msg: disnake.Message = await channel.fetch_message(int(each_party['message_id']))
                                await _msg.edit(content=None, embed=embed, view=None)
                                # Update balance
                                mv_partydrop = await store.sql_user_balance_mv_multple_amount(user_tos, "PARTYDROP", SERVER_BOT)
                                if mv_partydrop is True:
                                    try:
                                        key_coin = str(self.bot.user.id) + "_" + coin_name + "_" + SERVER_BOT
                                        if key_coin in self.bot.user_balance_cache:
                                            del self.bot.user_balance_cache[key_coin]

                                        for each in all_name_list:
                                            key_coin = each + "_" + coin_name + "_" + SERVER_BOT
                                            if key_coin in self.bot.user_balance_cache:
                                                del self.bot.user_balance_cache[key_coin]
                                    except Exception:
                                        pass
                                    party = await store.sql_user_balance_mv_multiple(str(self.bot.user.id), all_name_list, get_message['guild_id'], get_message['channel_id'], indiv_amount, coin_name, "PARTYDROP", coin_decimal, SERVER_BOT, get_message['contract'], float(amount_in_usd), None)
                                    if party is True:
                                        await store.update_party_id(each_party['message_id'], "COMPLETED" if len(attend_list) > 0 else "NOCOLLECT")
                            except disnake.errors.NotFound:
                                    await logchanbot("[PARTYDROP]: can not find message ID: {} of channel {} in guild: {}. Set that to FAILED.".format(
                                        each_party['message_id'], each_party['channel_id'], each_party['guild_id']
                                    ))
                                    await store.update_party_failed(each_party['message_id'], True)
                                    await asyncio.sleep(1.0)
                            except disnake.errors.DiscordServerError:
                                    await logchanbot("[PARTYDROP]: DiscordServerError message ID: {} of channel {} in guild: {}.".format(
                                        each_party['message_id'], each_party['channel_id'], each_party['guild_id']
                                    ))
                                    await asyncio.sleep(1.0)
                                    continue
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                        else:
                            embed = disnake.Embed(
                                title=f"🎉 Party Drop 🎉",
                                description="Each click will deduct from your TipBot's balance. Minimum entrance cost: {}`{} {}`. "\
                                    "Party Pot will be distributed equally to all attendees after "\
                                    "completion.".format(
                                        coin_emoji, num_format_coin(get_message['minimum_amount']),
                                        coin_name
                                ),
                                timestamp=datetime.fromtimestamp(get_message['partydrop_time']))
                            if len(coin_emoji) > 0:
                                extension = ".png"
                                if coin_emoji.startswith("<a:"):
                                    extension = ".gif"
                                split_id = coin_emoji.split(":")[2]
                                link = 'https://cdn.discordapp.com/emojis/' + str(split_id.replace(">", "")).strip() + extension
                                embed.set_thumbnail(url=link)
                            time_left = seconds_str_days(get_message['partydrop_time'] - int(time.time())) if int(time.time()) < get_message['partydrop_time'] else "00:00:00"
                            lap_div = int((get_message['partydrop_time'] - int(time.time()))/30)
                            embed.set_footer(text=f"Initiated by {owner_displayname} | /partydrop | Time left: {time_left}")
                            name_list = []
                            user_tos = []
                            user_tos.append(get_message['from_userid'])
                            if len(attend_list) > 0:
                                name_list.append("<@{}> : {} {}".format(get_message['from_userid'], num_format_coin(get_message['init_amount']), token_display))
                                for each_att in attend_list:
                                    name_list.append("<@{}> : {} {}".format(each_att['attendant_id'], num_format_coin(each_att['joined_amount']), token_display))
                                    total_amount += each_att['joined_amount']
                                    user_tos.append(each_att['attendant_id'])
                                    if len(name_list) > 0 and len(name_list) % 15 == 0:
                                        embed.add_field(name='Attendant', value="\n".join(name_list), inline=False)
                                        name_list = []
                                if len(name_list) > 0:
                                    embed.add_field(name='Attendant', value="\n".join(name_list), inline=False)
                                user_tos = list(set(user_tos))
                            indiv_amount = total_amount / len(user_tos) # including initiator
                            try:
                                key = each_party['message_id']
                                if self.party_cache[key] == "{}_{}_{}".format(len(user_tos), total_amount, lap_div):
                                    continue # to next, no need to edit
                                else:
                                    self.party_cache[key] = "{}_{}_{}".format(len(user_tos), total_amount, lap_div)
                            except Exception:
                                pass
                            amount_in_usd = indiv_amount * get_message['unit_price_usd'] if get_message['unit_price_usd'] and get_message['unit_price_usd'] > 0.0 else 0.0
                            indiv_amount_str = num_format_coin(indiv_amount)
                            embed.add_field(
                                name='Each Member Receives:',
                                value=f"{coin_emoji}{indiv_amount_str} {token_display}",
                                inline=True
                            )
                            embed.add_field(
                                name='Started amount', 
                                value=coin_emoji + num_format_coin(get_message['init_amount']) + " " + coin_name,
                                inline=True
                            )
                            embed.add_field(
                                name='Party Pot', 
                                value=coin_emoji + num_format_coin(total_amount) + " " + coin_name,
                                inline=True
                            )
                            try:
                                channel = self.bot.get_channel(int(get_message['channel_id']))
                                if channel is None:
                                    await logchanbot("party_check: can not find channel ID: {}".format(each_party['channel_id']))
                                    await asyncio.sleep(2.0)
                                else:
                                    try:
                                        _msg: disnake.Message = await channel.fetch_message(int(each_party['message_id']))
                                        if _msg is not None and _msg.edited_at and int(time.time()) - int(_msg.edited_at.timestamp()) > 60:
                                            await _msg.edit(content=None, embed=embed)
                                    except disnake.errors.NotFound:
                                        # add fail check
                                        turn_off = False
                                        if each_party['failed_check'] > 3:
                                            turn_off = True
                                        await store.update_party_failed(each_party['message_id'], turn_off)
                                        await logchanbot("party_check: can not find message ID: {} in channel: {}".format(each_party['message_id'], each_party['channel_id']))
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                await asyncio.sleep(2.0)
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("party_check " +str(traceback.format_exc()))
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))

    async def async_partydrop(self, ctx, min_amount: str, sponsor_amount: str, token: str, duration: str):
        coin_name = token.upper()
        await ctx.response.send_message(f"{ctx.author.mention}, /partydrop preparation... ")

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/partydrop", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # check lock
        try:
            is_user_locked = self.utils.is_locked_user(str(ctx.author.id), SERVER_BOT)
            if is_user_locked is True:
                await ctx.edit_original_message(
                    content = f"{EMOJI_RED_NO} {ctx.author.mention}, your account is locked for using the Bot. "\
                    "Please contact bot dev by /about link."
                )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # end check lock

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

        # if coin is allowed for partydrop
        if getattr(getattr(self.bot.coin_list, coin_name), "enable_partydrop") != 1:
            msg = f'{ctx.author.mention}, **{coin_name}** not enable with `/partydrop`'
            await ctx.edit_original_message(content=msg)
            return

        # Check if there is many airdrop/mathtip/triviatip/partydrop
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
                await logchanbot(f"[PARTYDROP] server {str(ctx.guild.id)} has no data in discord_server.")
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # End of ongoing check

        try:
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            coin_emoji = ""
            try:
                if ctx.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is True:
                    coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                    coin_emoji = coin_emoji + " " if coin_emoji else ""
            except Exception:
                traceback.print_exc(file=sys.stdout)
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

        height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        
        # Check min_amount
        if not min_amount.isdigit() and min_amount.upper() == "ALL":
            userdata_balance = await store.sql_user_balance_single(
                str(ctx.author.id), coin_name, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT
            )
            min_amount = float(userdata_balance['adjust'])
        # If $ is in min_amount, let's convert to coin/token
        elif "$" in min_amount[-1] or "$" in min_amount[0]:  # last is $
            # Check if conversion is allowed for this coin.
            min_amount = min_amount.replace(",", "").replace("$", "")
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
                    min_amount = float(Decimal(min_amount) / Decimal(per_unit))
                else:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method.'
                    await ctx.edit_original_message(content=msg)
                    return
        else:
            min_amount = min_amount.replace(",", "")
            min_amount = text_to_num(min_amount)
            if min_amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given minimum amount.'
                await ctx.edit_original_message(content=msg)
                return
        # end of check if min_amount is all

        # Check sponsor_amount
        if not sponsor_amount.isdigit() and sponsor_amount.upper() == "ALL":
            userdata_balance = await store.sql_user_balance_single(
                str(ctx.author.id), coin_name, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT
            )
            sponsor_amount = float(userdata_balance['adjust'])
        # If $ is in sponsor_amount, let's convert to coin/token
        elif "$" in sponsor_amount[-1] or "$" in sponsor_amount[0]:  # last is $
            # Check if conversion is allowed for this coin.
            sponsor_amount = sponsor_amount.replace(",", "").replace("$", "")
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
                    sponsor_amount = float(Decimal(sponsor_amount) / Decimal(per_unit))
                else:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method.'
                    await ctx.edit_original_message(content=msg)
                    return
        else:
            sponsor_amount = sponsor_amount.replace(",", "")
            sponsor_amount = text_to_num(sponsor_amount)
            if sponsor_amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given sponsored amount.'
                await ctx.edit_original_message(content=msg)
                return
        # end of check if sponsor_amount is all

        # Check if tx in progress
        if str(ctx.author.id) in self.bot.tipping_in_progress and \
            int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 150:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
            await ctx.edit_original_message(content=msg)
            return

        try:
            min_amount = float(min_amount)
        except ValueError:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid minimum amount.'
            await ctx.edit_original_message(content=msg)
            return

        try:
            sponsor_amount = float(sponsor_amount)
        except ValueError:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid sponsored amount.'
            await ctx.edit_original_message(content=msg)
            return

        default_duration = 60
        duration_s = 0
        try:
            duration_s = int(duration)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid duration.'
            await ctx.edit_original_message(content=msg)
            return

        userdata_balance = await store.sql_user_balance_single(
            str(ctx.author.id), coin_name, wallet_address, type_coin,
            height, deposit_confirm_depth, SERVER_BOT
        )
        actual_balance = float(userdata_balance['adjust'])

        if min_amount <= 0 or sponsor_amount <= 0 or actual_balance <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
            await ctx.edit_original_message(content=msg)
            return

        if min_amount > max_tip or min_amount < min_tip:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, minimum amount cannot be bigger than "\
                f"**{num_format_coin(max_tip)} {token_display}** "\
                f"or smaller than **{num_format_coin(min_tip)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return
        elif sponsor_amount > 5*max_tip or sponsor_amount < min_tip:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, sponored amount cannot be bigger than "\
                f"**{num_format_coin(5*max_tip)} {token_display}** "\
                f"or smaller than **{num_format_coin(min_tip)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return
        elif min_amount > sponsor_amount/5:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, sponsored amount must be at least 5x of minimum amount."
            await ctx.edit_original_message(content=msg)
            return
        elif sponsor_amount > actual_balance:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to sponsor "\
                f"**{num_format_coin(sponsor_amount)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return

        if str(ctx.author.id) not in self.bot.tipping_in_progress:
            self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())

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
                total_in_usd = float(Decimal(sponsor_amount) * Decimal(per_unit))
                if total_in_usd >= 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(total_in_usd)

        # Delete if has key
        key = str(ctx.author.id) + "_" + coin_name + "_" + SERVER_BOT
        try:
            if key in self.bot.user_balance_cache:
                del self.bot.user_balance_cache[key]
        except Exception:
            pass
        # End of del key

        party_end = int(time.time()) + duration_s
        owner_displayname = "{}#{}".format(ctx.author.name, ctx.author.discriminator)
        embed = disnake.Embed(
            title=f"🎉 Party Drop 🎉",
            description="Each click will deduct from your TipBot's balance. Minimum entrance cost: {}`{} {}`. "\
                "Party Pot will be distributed equally to all attendees after "\
                "completion.".format(
                    coin_emoji,
                    num_format_coin(min_amount),
                    coin_name
            ),
            timestamp=datetime.fromtimestamp(party_end)
        )
        embed.add_field(
            name='Started amount',
            value=coin_emoji + num_format_coin(sponsor_amount) + " " + coin_name,
            inline=True
        )
        embed.add_field(
            name='Party Pot',
            value=coin_emoji + num_format_coin(sponsor_amount) + " " + coin_name,
            inline=True
        )
        time_left = seconds_str_days(duration_s)
        embed.set_footer(text=f"Initiated by {owner_displayname} | /partydrop | Time left: {time_left}")
        if len(coin_emoji) > 0:
            extension = ".png"
            if coin_emoji.startswith("<a:"):
                extension = ".gif"
            split_id = coin_emoji.split(":")[2]
            link = 'https://cdn.discordapp.com/emojis/' + str(split_id.replace(">", "")).strip() + extension
            embed.set_thumbnail(url=link)
        try:
            view = PartyButton(ctx, duration_s, self.bot.coin_list, self.bot, ctx.channel.id) 
            msg = await ctx.channel.send(content=None, embed=embed, view=view)
            view.message = msg
            view.channel_interact = ctx.channel.id
            await store.insert_partydrop_create(
                coin_name, contract, str(ctx.author.id),
                owner_displayname, str(view.message.id),
                str(ctx.guild.id), str(ctx.channel.id), 
                min_amount, sponsor_amount, total_in_usd,
                equivalent_usd, per_unit, coin_decimal, 
                party_end, "ONGOING"
            )
            await ctx.edit_original_message(content="/partydrop created 👇")
        except disnake.errors.Forbidden:
            await ctx.edit_original_message(content="Missing permission! Or failed to send embed message.")
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            del self.bot.tipping_in_progress[str(ctx.author.id)]
        except Exception:
            pass

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        dm_permission=False,
        usage='partydrop <amount> <token> <duration>',
        options=[
            Option('min_amount', 'min_amount', OptionType.string, required=True),
            Option('sponsor_amount', 'sponsor_amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option('duration', 'duration', OptionType.string, required=True, choices=[
                OptionChoice("2mn", "120"),
                OptionChoice("5mn", "300"),
                OptionChoice("10mn", "600"),
                OptionChoice("30mn", "1800"),
                OptionChoice("1h", "3600"),
                OptionChoice("2h", "7200"),
                OptionChoice("4h", "14400"),
                OptionChoice("12h", "43200"),
                OptionChoice("1d", "86400"),
                OptionChoice("2d", "172800")
            ]),
        ],
        description="Create party drop and other people join."
    )
    async def partydrop(
        self,
        ctx,
        min_amount: str,
        sponsor_amount: str,
        token: str,
        duration: str
    ):
        await self.async_partydrop(ctx, min_amount, sponsor_amount, token, duration)

    @partydrop.autocomplete("token")
    async def partydrop_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

    @commands.Cog.listener()
    async def on_ready(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.party_check.is_running():
                self.party_check.start()

    async def cog_load(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.party_check.is_running():
                self.party_check.start()

    def cog_unload(self):
        # Ensure the task is stopped when the cog is unloaded.
        self.party_check.cancel()


def setup(bot):
    bot.add_cog(PartyDrop(bot))
