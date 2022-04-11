import sys
import time
import traceback
from datetime import datetime
import random
import re
from decimal import Decimal

import disnake
from disnake.ext import commands, tasks
from disnake.enums import OptionType
from disnake.app_commands import Option

from disnake import ActionRow, Button
from disnake.enums import ButtonStyle
from cachetools import TTLCache

import store
from Bot import num_format_coin, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, EMOJI_MONEYFACE, NOTIFICATION_OFF_CMD, EMOJI_SPEAK, EMOJI_BELL, EMOJI_BELL_SLASH, EMOJI_HOURGLASS_NOT_DONE, EMOJI_INFORMATION, EMOJI_PARTY, SERVER_BOT, seconds_str, text_to_num, truncate
from config import config
import redis_utils
from cogs.wallet import WalletAPI


# Defines a simple view of row buttons.
class FreeTip_Button(disnake.ui.View):
    message: disnake.Message

    def __init__(self, ctx, bot, timeout: float):
        super().__init__(timeout=timeout)
        self.ttlcache = TTLCache(maxsize=500, ttl=60.0)
        self.bot = bot
        self.ctx = ctx


    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True

        get_freetip = None
        _channel = None
        _msg = None
        try:
            original_message = await self.ctx.original_message()
            get_freetip = await store.get_discord_freetip_by_msgid(str(original_message.id))
            if int(get_freetip['message_time']) + 10*60 < int(time.time()):
                _channel: disnake.TextChannel = await self.bot.fetch_channel(int(get_freetip['channel_id']))
                _msg: disnake.Message = await _channel.fetch_message(int(get_freetip['message_id']))
                if _msg is not None:
                    original_message = _msg
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            return


        if get_freetip is None:
            await logchanbot(f"[ERROR FREETIP] Failed timeout in guild {self.ctx.guild.name} / {self.ctx.guild.id}!")
            return

        ## Update content
        get_freetip = await store.get_discord_freetip_by_msgid(str(self.message.id))
        if get_freetip['status'] == "ONGOING":
            amount = get_freetip['real_amount']
            COIN_NAME = get_freetip['token_name']
            equivalent_usd = get_freetip['real_amount_usd_text']

            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
            token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")

            found_owner = False
            owner_displayname = "N/A"
            get_owner = self.bot.get_user(int(get_freetip['from_userid']))
            if get_owner:
                owner_displayname = "{}#{}".format(get_owner.name, get_owner.discriminator)

            attend_list = []
            attend_list_id = []
            attend_list_names = ""
            collectors = await store.get_freetip_collector_by_id(str(self.message.id), get_freetip['from_userid'])
            if len(collectors) > 0:
                # have some
                attend_list = [i['collector_name'] for i in collectors]
                attend_list_names = " | ".join(attend_list)
                attend_list_id = [int(i['collector_id']) for i in collectors]
            else:
                # No collector
                print("FreeTip msg ID {} timeout..".format(str(self.message.id)))

            if len(attend_list) == 0:
                embed = disnake.Embed(title=f"FreeTip appears {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} {equivalent_usd}", description=f"Already expired", timestamp=datetime.fromtimestamp(get_freetip['airdrop_time']))
                if get_freetip['airdrop_content'] and len(get_freetip['airdrop_content']) > 0:
                    embed.add_field(name="Comment", value=get_freetip['airdrop_content'], inline=False)
                embed.set_footer(text=f"FreeTip by {owner_displayname}, and no one collected!")
                try:
                    await original_message.edit(embed=embed, view=None)
                    # update status
                    change_status = await store.discord_freetip_update(str(self.message.id), "NOCOLLECT")
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                link_to_msg = "https://discord.com/channels/{}/{}/{}".format(get_freetip['guild_id'], get_freetip['channel_id'], str(self.message.id))
                # free tip shall always get DM. Ignore notifyList
                try:
                    if get_owner is not None:
                        await get_owner.send(f'Free tip of {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} {equivalent_usd} expired and no one collected.\n{link_to_msg}')
                except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                    pass
            elif len(attend_list) > 0:
                # re-check balance
                User_WalletAPI = WalletAPI(self.bot)
                get_deposit = await User_WalletAPI.sql_get_userwallet(get_freetip['from_userid'], COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                if get_deposit is None:
                    get_deposit = await User_WalletAPI.sql_register_user(get_freetip['from_userid'], COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']

                height = None
                try:
                    if type_coin in ["ERC-20", "TRC-20"]:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                    else:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)

                userdata_balance = await store.sql_user_balance_single(get_freetip['from_userid'], COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                actual_balance = float(userdata_balance['adjust'])
        
                if actual_balance < 0 and get_owner:
                    await self.message.reply(f'{EMOJI_RED_NO} {get_owner.mention}, insufficient balance to do a free tip of {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}.')
                    change_status = await store.discord_freetip_update(str(self.message.id), "FAILED")
                    # end of re-check balance
                else:
                    # Multiple tip here
                    notifyList = await store.sql_get_tipnotify()
                    amountDiv = truncate(amount / len(attend_list_id), 4)
                    tips = None

                    tipAmount = num_format_coin(amount, COIN_NAME, coin_decimal, False)
                    ActualSpend_str = num_format_coin(amountDiv * len(attend_list_id), COIN_NAME, coin_decimal, False)
                    amountDiv_str = num_format_coin(amountDiv, COIN_NAME, coin_decimal, False)

                    each_equivalent_usd = ""
                    actual_spending_usd = ""
                    amount_in_usd = 0.0
                    per_unit = None
                    if usd_equivalent_enable == 1:
                        per_unit = get_freetip['unit_price_usd']
                        if per_unit and per_unit > 0:
                            amount_in_usd = per_unit * float(amountDiv)
                            if amount_in_usd > 0.0001:
                                each_equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
                                actual_spending_usd = " ~ {:,.4f} USD".format(amount_in_usd * len(attend_list_id))

                    try:
                        tips = await store.sql_user_balance_mv_multiple(get_freetip['from_userid'], attend_list_id, get_freetip['guild_id'], get_freetip['channel_id'], float(amountDiv), COIN_NAME, "FREETIP", coin_decimal, SERVER_BOT, contract, float(amount_in_usd))
                        # If tip, update status
                        change_status = await store.discord_freetip_update(get_freetip['message_id'], "COMPLETED")
                        # Edit embed
                        try:
                            embed = disnake.Embed(title=f"FreeTip appears {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} {equivalent_usd}", description=f"Click to collect", timestamp=datetime.fromtimestamp(get_freetip['airdrop_time']))
                            if get_freetip['airdrop_content'] and len(get_freetip['airdrop_content']) > 0:
                                embed.add_field(name="Comment", value=get_freetip['airdrop_content'], inline=False)
                            if len(attend_list_names) >= 1000: attend_list_names = attend_list_names[:1000]
                            try:
                                if len(attend_list) > 0:
                                    embed.add_field(name='Attendees', value=attend_list_names, inline=False)
                                    embed.add_field(name='Individual Tip amount', value=f"{num_format_coin(truncate(amount / len(attend_list), 4), COIN_NAME, coin_decimal, False)} {token_display}", inline=True)
                                    embed.add_field(name="Num. Attendees", value=f"**{len(attend_list)}** members", inline=True)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            embed.set_footer(text=f"Completed! Collected by {len(attend_list_id)} member(s)")
                            await original_message.edit(embed=embed, view=None)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                    if tips:
                        link_to_msg = "https://discord.com/channels/{}/{}/{}".format(get_freetip['guild_id'], get_freetip['channel_id'], str(self.message.id))
                        # free tip shall always get DM. Ignore notifyList
                        try:
                            guild = self.bot.get_guild(int(get_freetip['guild_id']))
                            if get_owner is not None:
                                await get_owner.send(
                                    f'{EMOJI_ARROW_RIGHTHOOK} Free tip of {tipAmount} {token_display} '
                                    f'was sent to ({len(attend_list_id)}) members in server `{guild.name}`.\n'
                                    f'Each member got: **{amountDiv_str} {token_display}**\n'
                                    f'Actual spending: **{ActualSpend_str} {token_display}**\n{link_to_msg}')
                        except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                            pass
                    else:
                        # If tip, update status
                        change_status = await store.discord_freetip_update(str(self.message.id), "FAILED")
        else:
            await original_message.edit(view=None)


    @disnake.ui.button(label="🎁 Collect", style=ButtonStyle.green, custom_id="collect_freetip")
    async def row_enter_airdrop(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        try:
            msg = "Nothing to do!"
            get_message = None
            try:
                msg_id = interaction.message.id
                get_message = await store.get_discord_freetip_by_msgid(str(msg_id))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                original_message = await interaction.original_message()
                get_message = await store.get_discord_freetip_by_msgid(str(original_message.id))

            if get_message is None:
                await interaction.response.send_message(content="Failed to collect free tip!")
                await logchanbot(f"[ERROR FREETIP] Failed to join a free tip in guild {interaction.guild.name} / {interaction.guild.id} by {interaction.author.name}#{interaction.author.discriminator}!")
                return

            if get_message and int(get_message['from_userid']) == interaction.author.id:
                await interaction.response.send_message(content="You are the owner of airdrop id: {}".format(str(interaction.message.id)), ephemeral=True)
                return
            # Check if user in
            check_if_in = await store.check_if_freetip_collector_in(str(interaction.message.id), get_message['from_userid'], str(interaction.author.id))
            if check_if_in:
                # await interaction.response.send_message(content="You already joined this airdrop id: {}".format(str(interaction.message.id)), ephemeral=True)
                await interaction.response.defer()
                return
            else:
                # If time already pass
                if int(time.time()) > get_message['airdrop_time']:
                    # await interaction.response.send_message(content="Airdrop id: {} passed already!".format(str(interaction.message.id)), ephemeral=True)
                    # await interaction.response.defer()
                    return
                else:
                    key = "freetip_{}_{}".format(str(interaction.message.id), str(interaction.author.id))
                    try:
                        if self.ttlcache[key] == key:
                            return
                        else:
                            self.ttlcache[key] = key
                    except Exception as e:
                        pass
                    insert_airdrop = await store.insert_freetip_collector(str(interaction.message.id), get_message['from_userid'], str(interaction.author.id), "{}#{}".format(interaction.author.name, interaction.author.discriminator))
                    msg = "Sucessfully joined airdrop id: {}".format(str(interaction.message.id))
                    await interaction.response.defer()
                    await interaction.response.send_message(content=msg, ephemeral=True)
                    return
        except (disnake.InteractionResponded, disnake.InteractionTimedOut, disnake.NotFound) as e:
            return await interaction.followup.send(
                msg,
                ephemeral=True,
            )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)



class Tips(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        redis_utils.openRedis()
        self.freetip_duration_min = 5
        self.freetip_duration_max = 24*3600


    # Notifytip
    async def async_notifytip(self, ctx, onoff: str):
        if onoff.upper() not in ["ON", "OFF"]:
            msg = f'{ctx.author.mention} You need to use only `ON` or `OFF`.'
            await ctx.response.send_message(msg)
            return

        onoff = onoff.upper()
        notifyList = await store.sql_get_tipnotify()
        if onoff == "ON":
            if str(ctx.author.id) in notifyList:
                msg = f'{ctx.author.mention} {EMOJI_BELL} OK, you will get all notification when tip.'
                await store.sql_toggle_tipnotify(str(ctx.author.id), "ON")
                await ctx.response.send_message(msg)
            else:
                msg = f'{ctx.author.mention} {EMOJI_BELL} You already have notification ON by default.'
                await ctx.response.send_message(msg)
        elif onoff == "OFF":
            if str(ctx.author.id) in notifyList:
                msg = f'{ctx.author.mention} {EMOJI_BELL_SLASH} You already have notification OFF.'
                await ctx.response.send_message(msg)
            else:
                await store.sql_toggle_tipnotify(str(ctx.author.id), "OFF")
                msg = f'{ctx.author.mention} {EMOJI_BELL_SLASH} OK, you will not get any notification when anyone tips.'
                await ctx.response.send_message(msg)
        return


    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        usage='notifytip <on/off>', 
        options=[
            Option('onoff', 'onoff', OptionType.string, required=True)
        ],
        description="Toggle notify tip notification from bot ON|OFF"
    )
    async def notifytip(
        self, 
        ctx, 
        onoff: str
    ):
        await self.async_notifytip(ctx, onoff)
    # End notifytip


    # RandomTip
    async def async_randtip(self, ctx, amount: str, token: str, rand_option: str = None):
        COIN_NAME = token.upper()
        # Token name check
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            await ctx.response.send_message(msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_tip") != 1:
                msg = f'{ctx.author.mention}, **{COIN_NAME}** tipping is disable.'
                await ctx.response.send_message(msg)
                return
        # End token name check
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo['tiponly'] and serverinfo['tiponly'] != "ALLCOIN" and COIN_NAME not in serverinfo['tiponly'].split(","):
            allowed_coins = serverinfo['tiponly']
            msg = f'{ctx.author.mention}, **{COIN_NAME}** is not allowed here. Currently, allowed `{allowed_coins}`. You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`'
            await ctx.response.send_message(msg)
            return

        try:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing random tip...'
            await ctx.response.send_message(msg)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(f"{EMOJI_INFORMATION} {ctx.author.mention}, failed to execute random tip message...", ephemeral=True)
            return

        net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
        contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
        token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")

        MinTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
        MaxTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")

        User_WalletAPI = WalletAPI(self.bot)

        get_deposit = await User_WalletAPI.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await User_WalletAPI.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']

        # Check if tx in progress
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return

        height = None
        try:
            if type_coin in ["ERC-20", "TRC-20"]:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
            else:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        # check if amount is all
        all_amount = False
        if not amount.isdigit() and amount.upper() == "ALL":
            all_amount = True
            userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
            amount = float(userdata_balance['adjust'])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]: # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            if usd_equivalent_enable == 0:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{COIN_NAME}`."
                await ctx.edit_original_message(content=msg)
                return
            else:
                native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                COIN_NAME_FOR_PRICE = COIN_NAME
                if native_token_name:
                    COIN_NAME_FOR_PRICE = native_token_name
                per_unit = None
                if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                    id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                    per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                else:
                    per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
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
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.'
                await ctx.edit_original_message(content=msg)
                return
        # end of check if amount is all

        # Get a random user in the guild, except bots. At least 3 members for random.
        has_last = False
        message_talker = None
        listMembers = None
        minimum_users = 2
        try:
            # Check random option
            if rand_option is None or rand_option.upper().startswith("ALL"):
                listMembers = [member for member in ctx.guild.members if member.bot is False]
            elif rand_option and rand_option.upper().startswith("ONLINE"):
                listMembers = [member for member in ctx.guild.members if member.bot is False and member.status != disnake.Status.offline]
            elif rand_option and rand_option.upper().strip().startswith("LAST "):
                argument = rand_option.strip().split(" ")
                if len(argument) == 2:
                    # try if the param is 1111u
                    num_user = argument[1].lower()
                    if 'u' in num_user or 'user' in num_user or 'users' in num_user or 'person' in num_user or 'people' in num_user:
                        num_user = num_user.replace("people", "")
                        num_user = num_user.replace("person", "")
                        num_user = num_user.replace("users", "")
                        num_user = num_user.replace("user", "")
                        num_user = num_user.replace("u", "")
                        try:
                            num_user = int(num_user)
                            if num_user < minimum_users:
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, number of random users cannot below **{minimum_users}**.'
                                await ctx.edit_original_message(content=msg)
                                return
                            elif num_user >= minimum_users:
                                message_talker = await store.sql_get_messages(str(ctx.guild.id), str(ctx.channel.id), 0, num_user + 1)
                                if len(message_talker) == 0:
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is not sufficient user to count.'
                                    await ctx.edit_original_message(content=msg)
                                if ctx.author.id in message_talker:
                                    message_talker.remove(ctx.author.id)
                                else:
                                    # remove the last one
                                    message_talker.pop()
                                if len(message_talker) < minimum_users:
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is not sufficient user to count for random tip.'
                                    await ctx.edit_original_message(content=msg)
                                    return
                                elif len(message_talker) < num_user:
                                    try:
                                        msg = f'{EMOJI_INFORMATION} {ctx.author.mention} I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}** and random to one of those **{len(message_talker)}** users.'
                                        await ctx.channel.send(msg)
                                    except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                        # no need tip
                                        return
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                            has_last = True
                        except ValueError:
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid param after **LAST** for random tip. Support only *LAST* **X**u right now.'
                            await ctx.edit_original_message(content=msg)
                            return
                    else:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid param after **LAST** for random tip. Support only *LAST* **X**u right now.'
                        await ctx.edit_original_message(content=msg)
                        return
                else:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid param after **LAST** for random tip. Support only *LAST* **X**u right now.'
                    await ctx.edit_original_message(content=msg)
                    return

            if has_last is False and listMembers and len(listMembers) >= minimum_users:
                rand_user = random.choice(listMembers)
                max_loop = 0
                if rand_user == ctx.author:
                    while True:
                        if rand_user != ctx.author:
                            break
                        else:
                            rand_user = random.choice(listMembers)
                        max_loop += 1
                        if max_loop >= 5:
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention} {token_display}, please try again, maybe guild doesn\'t have so many users.'
                            await ctx.edit_original_message(content=msg)
                            return

            elif has_last is True and message_talker and len(message_talker) >= minimum_users:
                rand_user_id = random.choice(message_talker)
                max_loop = 0
                if rand_user_id == ctx.author.id:
                    while True:
                        rand_user = self.bot.get_user(rand_user_id)
                        if rand_user and rand_user != ctx.author and rand_user in ctx.guild.members:
                            break
                        else:
                            rand_user_id = random.choice(message_talker)
                            rand_user = self.bot.get_user(rand_user_id)
                        max_loop += 1
                        if max_loop >= 10:
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention} {token_display}, please try again, maybe guild doesnot have so many users.'
                            await ctx.edit_original_message(content=msg)
                            break
            else:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} {token_display} not enough member for random tip.'
                await ctx.edit_original_message(content=msg)
                if ctx.author.id in self.bot.TX_IN_PROCESS:
                    self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

        notifyList = await store.sql_get_tipnotify()
        userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])

        if amount > MaxTip or amount < MinTip:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than **{num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}** or smaller than **{num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a random tip of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return

        # add queue also randtip
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention} {EMOJI_HOURGLASS_NOT_DONE}, you have another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return

        equivalent_usd = ""
        total_equivalent_usd = ""
        amount_in_usd = 0.0
        total_amount_in_usd = 0.0

        per_unit = None
        if usd_equivalent_enable == 1:
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            COIN_NAME_FOR_PRICE = COIN_NAME
            if native_token_name:
                COIN_NAME_FOR_PRICE = native_token_name
            if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
            else:
                per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
            if per_unit and per_unit > 0:
                amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                if amount_in_usd > 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)

        tip = None
        if rand_user is not None:
            if ctx.author.id not in self.bot.TX_IN_PROCESS:
                self.bot.TX_IN_PROCESS.append(ctx.author.id)
            Tip_WalletAPI = WalletAPI(self.bot)
            user_to = await User_WalletAPI.sql_get_userwallet(str(rand_user.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
            if user_to is None:
                user_to = await User_WalletAPI.sql_register_user(str(rand_user.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)

            try:
                tip = await store.sql_user_balance_mv_single(str(ctx.author.id), str(rand_user.id), str(ctx.guild.id), str(ctx.channel.id), amount, COIN_NAME, "RANDTIP", coin_decimal, SERVER_BOT, contract, amount_in_usd)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        else:
            # remove queue from randtip
            if ctx.author.id in self.bot.TX_IN_PROCESS:
                self.bot.TX_IN_PROCESS.remove(ctx.author.id)
            await logchanbot(f"{ctx.author.id} randtip got None rand_user.")
            return

        # remove queue from randtip
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.remove(ctx.author.id)

        if tip:
            # tipper shall always get DM. Ignore notifyList
            try:
                msg = f'{EMOJI_ARROW_RIGHTHOOK} {rand_user.name}#{rand_user.discriminator} got your random tip of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}** in server `{ctx.guild.name}`'
                await ctx.followup.send(msg)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            if str(rand_user.id) not in notifyList:
                try:
                    await rand_user.send(
                        f'{EMOJI_MONEYFACE} You got a random tip of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} '
                        f'{token_display}** from {ctx.author.name}#{ctx.author.discriminator} in server `{ctx.guild.name}`\n'
                        f'{NOTIFICATION_OFF_CMD}')
                except Exception as e:
                    pass


    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        usage='randtip', 
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option('rand_option', 'rand_option', OptionType.string, required=False)
        ],
        description="Tip to random user in the guild"
    )
    async def randtip(
        self, 
        ctx,
        amount: str,
        token: str,
        rand_option: str=None
    ):
        try:
            await self.async_randtip(ctx, amount, token, rand_option)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    # End of RandomTip


    # FreeTip
    async def async_freetip(self, ctx, amount: str, token: str, duration: str=None, comment: str = None):
        COIN_NAME = token.upper()
        
        # Token name check
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            await ctx.response.send_message(msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_tip") != 1:
                msg = f'{ctx.author.mention}, **{COIN_NAME}** tipping is disable.'
                await ctx.response.send_message(msg)
                return
        # End token name check
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo['tiponly'] and serverinfo['tiponly'] != "ALLCOIN" and COIN_NAME not in serverinfo['tiponly'].split(","):
            allowed_coins = serverinfo['tiponly']
            msg = f'{ctx.author.mention}, **{COIN_NAME}** is not allowed here. Currently, allowed `{allowed_coins}`. You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`'
            await ctx.response.send_message(msg)
            return

        try:
            await ctx.response.send_message(f"{ctx.author.mention}, freetip preparation... ")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(f"{EMOJI_INFORMATION} {ctx.author.mention}, failed to execute free tip message...", ephemeral=True)
            return

        net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
        MinTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
        MaxTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")

        # token_info = getattr(self.bot.coin_list, COIN_NAME)
        token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
        contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
        User_WalletAPI = WalletAPI(self.bot)
        
        get_deposit = await User_WalletAPI.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await User_WalletAPI.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']

        # Check if tx in progress
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return

        height = None
        try:
            if type_coin in ["ERC-20", "TRC-20"]:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
            else:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        # check if amount is all
        all_amount = False
        if not amount.isdigit() and amount.upper() == "ALL":
            all_amount = True
            userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
            amount = float(userdata_balance['adjust'])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]: # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            if usd_equivalent_enable == 0:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{COIN_NAME}`."
                await ctx.edit_original_message(content=msg)
                return
            else:
                native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                COIN_NAME_FOR_PRICE = COIN_NAME
                if native_token_name:
                    COIN_NAME_FOR_PRICE = native_token_name
                per_unit = None
                if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                    id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                    per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                else:
                    per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
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

        def hms_to_seconds(time_string):
            duration_in_second = 0
            if time_string.isdigit():
                return int(time_string)
            try:
                time_string = time_string.replace("hours", "h")
                time_string = time_string.replace("hour", "h")
                time_string = time_string.replace("hrs", "h")
                time_string = time_string.replace("hr", "h")

                time_string = time_string.replace("minutes", "mn")
                time_string = time_string.replace("mns", "mn")
                time_string = time_string.replace("mins", "mn")
                time_string = time_string.replace("min", "mn")
                mult = {'h': 60*60, 'mn': 60, 's': 1}
                duration_in_second = sum(int(num) * mult.get(val, 1) for num, val in re.findall('(\d+)(\w+)', time_string))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return duration_in_second

        default_duration = 60
        duration_s = 0
        if duration is None:
            duration_s = default_duration # default

        try:
            duration_s = hms_to_seconds(duration)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid duration.'
            await ctx.edit_original_message(content=msg)
            return

        if duration_s == 0:
            duration_s = default_duration
            # Just info, continue
        elif duration_s < self.freetip_duration_min or duration_s > self.freetip_duration_max:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid duration. Please use between {str(self.freetip_duration_min)}s to {str(self.freetip_duration_max)}s.'
            await ctx.edit_original_message(content=msg)
            return

        if amount <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
            await ctx.edit_original_message(content=msg)
            return

        notifyList = await store.sql_get_tipnotify()
        userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])

        if amount > MaxTip or amount < MinTip:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than **{num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}** or smaller than **{num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a free tip of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return

        equivalent_usd = ""
        total_in_usd = 0.0
        per_unit = None
        if usd_equivalent_enable == 1:
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            COIN_NAME_FOR_PRICE = COIN_NAME
            if native_token_name:
                COIN_NAME_FOR_PRICE = native_token_name
            if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
            else:
                per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
            if per_unit and per_unit > 0:
                total_in_usd = float(Decimal(amount) * Decimal(per_unit))
                if total_in_usd >= 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(total_in_usd)

        embed = disnake.Embed(title=f"FreeTip appears {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} {equivalent_usd}", description=f"Click to collect", timestamp=datetime.fromtimestamp(int(time.time())+duration_s))
        try:
            if comment and len(comment) > 0:
                embed.add_field(name="Comment", value=comment, inline=True)
            embed.add_field(name="Attendees", value="React below to join!", inline=False)
            embed.add_field(name="Individual Tip Amount", value=f"{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}", inline=True)
            embed.add_field(name="Num. Attendees", value="**0** members", inline=True)
            embed.set_footer(text=f"FreeTip by {ctx.author.name}#{ctx.author.discriminator}, Time Left: {seconds_str(duration_s)}")
            
            comment_str = ""
            if comment and len(comment) > 0:
                comment_str = comment
            if ctx.author.id not in self.bot.TX_IN_PROCESS:
                self.bot.TX_IN_PROCESS.append(ctx.author.id)
                try:
                    view = FreeTip_Button(ctx, self.bot, duration_s)
                    view.message = await ctx.original_message()
                    insert_freetip = await store.insert_discord_freetip(COIN_NAME, contract, str(ctx.author.id), "{}#{}".format(ctx.author.name, ctx.author.discriminator), str(view.message.id), comment_str, str(ctx.guild.id), str(ctx.channel.id), amount, total_in_usd, equivalent_usd, per_unit, coin_decimal, int(time.time())+duration_s, "ONGOING")
                    await ctx.edit_original_message(content=None, embed=embed, view=view)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.remove(ctx.author.id)


    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        usage='freetip', 
        options=[
            Option('amount', 'amount', OptionType.string, required=True), 
            Option('token', 'token', OptionType.string, required=True), 
            Option('duration', 'duration', OptionType.string, required=True), 
            Option('comment', 'comment', OptionType.string, required=False)
        ],
        description="Spread free tip by user reacting with emoji"
    )
    async def freetip(
        self, 
        ctx,
        amount: str,
        token: str,
        duration: str, 
        comment: str=None
    ):
        try:
            await self.async_freetip(ctx, amount, token, duration, comment)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    # End of FreeTip


    # TipAll
    async def async_tipall(self, ctx, amount: str, token: str, user: str):
        COIN_NAME = token.upper()
        # Token name check
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            await ctx.response.send_message(msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_tip") != 1:
                msg = f'{ctx.author.mention}, **{COIN_NAME}** tipping is disable.'
                await ctx.response.send_message(msg)
                return
        # End token name check
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo['tiponly'] and serverinfo['tiponly'] != "ALLCOIN" and COIN_NAME not in serverinfo['tiponly'].split(","):
            allowed_coins = serverinfo['tiponly']
            msg = f'{ctx.author.mention}, **{COIN_NAME}** is not allowed here. Currently, allowed `{allowed_coins}`. You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`'
            await ctx.response.send_message(msg)
            return

        try:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing tip all...'
            await ctx.response.send_message(msg)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(f"{EMOJI_INFORMATION} {ctx.author.mention}, failed to execute tip all message...", ephemeral=True)

        net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
        MinTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
        MaxTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")

        # token_info = getattr(self.bot.coin_list, COIN_NAME)
        token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
        contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
        User_WalletAPI = WalletAPI(self.bot)
        
        get_deposit = await User_WalletAPI.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await User_WalletAPI.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']

        # Check if tx in progress
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return

        height = None
        try:
            if type_coin in ["ERC-20", "TRC-20"]:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
            else:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        # check if amount is all
        all_amount = False
        if not amount.isdigit() and amount.upper() == "ALL":
            all_amount = True
            userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
            amount = float(userdata_balance['adjust'])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]: # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            if usd_equivalent_enable == 0:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{COIN_NAME}`."
                await ctx.edit_original_message(content=msg)
                return
            else:
                native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                COIN_NAME_FOR_PRICE = COIN_NAME
                if native_token_name:
                    COIN_NAME_FOR_PRICE = native_token_name
                per_unit = None
                if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                    id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                    per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                else:
                    per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
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
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.'
                await ctx.edit_original_message(content=msg)
                return
        # end of check if amount is all

        try:
            amount = float(amount)
        except ValueError:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid amount.'
            await ctx.edit_original_message(content=msg)
            return

        if amount <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
            await ctx.edit_original_message(content=msg)
            return
        
        notifyList = await store.sql_get_tipnotify()
        userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])

        if amount > MaxTip or amount < MinTip:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than **{num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}** or smaller than **{num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to tip of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return


        listMembers = []
        if user.upper() == "ANY" or user.upper() == "ALL":
            listMembers = [member for member in ctx.guild.members]
        else:
            listMembers = [member for member in ctx.guild.members if member.status != disnake.Status.offline and member.bot is False]
        if len(listMembers) == 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is no number of users.'
            await ctx.edit_original_message(content=msg)
            return

        print("Number of tip-all in {}: {}".format(ctx.guild.name, len(listMembers)))
        max_allowed = 400
        if len(listMembers) > max_allowed:
            # Check if premium guild
            if serverinfo and serverinfo['is_premium'] == 0:
                msg = f'{ctx.author.mention}, there are more than maximum allowed `{str(max_allowed)}`. You can request pluton#8888 to allow this for your guild.'
                await ctx.edit_original_message(content=msg)
                await logchanbot(f"{ctx.guild.id} / {ctx.guild.name} reaches number of recievers: `{str(len(listMembers))}` issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}.")
                return
            else:
                await logchanbot(f"{ctx.guild.id} / {ctx.guild.name} reaches number of recievers: `{str(len(listMembers))}` issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}.")
        memids = []  # list of member ID
        for member in listMembers:
            if ctx.author.id != member.id:
                memids.append(str(member.id))

        if len(memids) == 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, no users...'
            await ctx.edit_original_message(content=msg)
            return


        amountDiv = truncate(amount / len(memids), 8)

        tipAmount = num_format_coin(amount, COIN_NAME, coin_decimal, False)
        ActualSpend_str = num_format_coin(amountDiv * len(memids), COIN_NAME, coin_decimal, False)
        amountDiv_str = num_format_coin(amountDiv, COIN_NAME, coin_decimal, False)

        if amountDiv <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, amount truncated to `0 {COIN_NAME}`. Try bigger one.'
            await ctx.edit_original_message(content=msg)
            return

        equivalent_usd = ""
        total_equivalent_usd = ""
        amount_in_usd = 0.0
        total_amount_in_usd = 0.0

        per_unit = None
        if usd_equivalent_enable == 1:
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            COIN_NAME_FOR_PRICE = COIN_NAME
            if native_token_name:
                COIN_NAME_FOR_PRICE = native_token_name
            if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
            else:
                per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
            if per_unit and per_unit > 0:
                amount_in_usd = float(Decimal(per_unit) * Decimal(amountDiv))
                if amount_in_usd > 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
                total_amount_in_usd = float(amount_in_usd * len(memids))
                if total_amount_in_usd > 0.0001:
                    total_equivalent_usd = " ~ {:,.4f} USD".format(total_amount_in_usd)


        if amount / len(memids) < MinTip:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than **{num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display}** for each member. You need at least **{num_format_coin(len(memids) * MinTip, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return


        if ctx.author.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.author.id)
            try:
                tips = await store.sql_user_balance_mv_multiple(str(ctx.author.id), memids, str(ctx.guild.id), str(ctx.channel.id), float(amountDiv), COIN_NAME, "TIPALL", coin_decimal, SERVER_BOT, contract, float(amount_in_usd))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
            self.bot.TX_IN_PROCESS.remove(ctx.author.id)
        else:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish.'
            await ctx.edit_original_message(content=msg)
            return

        if tips:
            # Message mention all in public
            total_found = 0
            max_mention = 40
            numb_mention = 0

            # mention all user
            send_tipped_ping = 0
            list_user_mention = []
            list_user_mention_str = ""
            list_user_not_mention = []
            list_user_not_mention_str = ""
            random.shuffle(listMembers)
            
            for member in listMembers:
                if send_tipped_ping >= config.discord.maxTipAllMessage:
                    total_found += 1
                else:
                    if ctx.author.id != member.id and member.id != self.bot.user.id:
                        if str(member.id) not in notifyList:
                            list_user_mention.append("{}".format(member.mention))
                        else:
                            list_user_not_mention.append("{}#{}".format(member.name, member.discriminator))
                    total_found += 1
                    numb_mention += 1

                    # Check if a batch meets
                    if numb_mention > 0 and numb_mention % max_mention == 0:
                        # send the batch
                        if len(list_user_mention) >= 1:
                            list_user_mention_str = ", ".join(list_user_mention)
                        if len(list_user_not_mention) >= 1:
                            list_user_not_mention_str = ", ".join(list_user_not_mention)
                        try:
                            if len(list_user_mention_str) > 5 or len(list_user_not_mention_str) > 5:
                                msg = f'{EMOJI_MONEYFACE} {list_user_mention_str} {list_user_not_mention_str}, you got a tip of **{amountDiv_str} {token_display}** {equivalent_usd} from {ctx.author.name}#{ctx.author.discriminator}{NOTIFICATION_OFF_CMD}'
                                await ctx.followup.send(msg)
                                send_tipped_ping += 1
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot(traceback.format_exc())
                        # reset
                        list_user_mention = []
                        list_user_mention_str = ""
                        list_user_not_mention = []
                        list_user_not_mention_str = ""
            # if there is still here
            if len(list_user_mention) + len(list_user_not_mention) > 1:
                if len(list_user_mention) >= 1:
                    list_user_mention_str = ", ".join(list_user_mention)
                if len(list_user_not_mention) >= 1:
                    list_user_not_mention_str = ", ".join(list_user_not_mention)
                try:
                    remaining_str = ""
                    if numb_mention < total_found:
                        remaining_str = " and other {} members".format(total_found-numb_mention)
                    msg = f'{EMOJI_MONEYFACE} {list_user_mention_str} {list_user_not_mention_str} {remaining_str}, you got a tip of **{amountDiv_str} {token_display}** {equivalent_usd} from {ctx.author.name}#{ctx.author.discriminator}{NOTIFICATION_OFF_CMD}'
                    await ctx.followup.send(msg)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)

            # tipper shall always get DM. Ignore notifyList
            try:
                msg = f'{EMOJI_ARROW_RIGHTHOOK} Tip of {tipAmount} {token_display} was sent to ({len(memids)}) members in server `{ctx.guild.name}`.\nEach member got: **{amountDiv_str} {token_display}** {equivalent_usd}\nActual spending: **{ActualSpend_str} {token_display}** {total_equivalent_usd}'
                await ctx.author.send(msg)
            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                pass



    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        usage='tipall', 
        options=[
            Option('amount', 'amount', OptionType.string, required=True), 
            Option('token', 'token', OptionType.string, required=True),  
            Option('user', 'user option (ONLINE or ALL)', OptionType.string, required=False)
        ],
        description="Tip all online user"
    )
    async def tipall(
        self, 
        ctx,
        amount: str,
        token: str,
        user: str="ONLINE"
    ):
        try:
            await self.async_tipall(ctx, amount, token, user)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    # End of TipAll

    # Tip Normal
    async def async_tip(self, ctx, amount: str, token: str, args):
        COIN_NAME = token.upper()
        # Token name check
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            await ctx.response.send_message(msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_tip") != 1:
                msg = f'{ctx.author.mention}, **{COIN_NAME}** tipping is disable.'
                await ctx.response.send_message(msg)
                return
        # End token name check
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo['tiponly'] and serverinfo['tiponly'] != "ALLCOIN" and COIN_NAME not in serverinfo['tiponly'].split(","):
            allowed_coins = serverinfo['tiponly']
            msg = f'{ctx.author.mention}, **{COIN_NAME}** is not allowed here. Currently, allowed `{allowed_coins}`. You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`'
            await ctx.response.send_message(msg)
            return

        try:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing tip command...'
            await ctx.response.send_message(msg)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(f"{EMOJI_INFORMATION} {ctx.author.mention}, failed to execute tip message...", ephemeral=True)
            return

        # print("async_tip args: "+ str(args))
        if args == "@everyone":
            get_list_member_n_role = [str(member.id) for member in ctx.guild.members if member.id != ctx.author.id]
        else:
            get_list_member_n_role = re.findall(r'<?\w*\d*>', args)
        list_member_ids = []

        if len(get_list_member_n_role) > 0:
            get_list_member_n_role = [each.replace(">", "").replace("<", "") for each in get_list_member_n_role]
            # There is member or role to check
            # Check member
            for each_m in get_list_member_n_role:
                try:
                    m = self.bot.get_user(int(each_m))
                    list_member_ids.append(m.id)
                except Exception as e:
                    pass
            if len(get_list_member_n_role) > 0:
                for each_r in get_list_member_n_role:
                    try:
                        # get list users in role
                        get_role = disnake.utils.get(ctx.guild.roles, id=int(each_r))
                        role_listMember = [member.id for member in ctx.guild.members if get_role in member.roles]
                        if len(role_listMember) > 0:
                            list_member_ids += role_listMember
                    except Exception as e:
                        pass
            list_member_ids = list(set(list_member_ids))
            if len(list_member_ids) > 0:
                try:
                    await self.multiple_tip(ctx, amount, COIN_NAME, list_member_ids, False)
                except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                    pass
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                return
        if len(get_list_member_n_role) == 0 or len(list_member_ids) == 0:
            # There is no member or role to check
            # Check list talk or last XXu
            split_arg = args.strip().split()
            if len(split_arg) >= 2:
                time_given = None
                if split_arg[0].upper() == "LAST":
                    # try if the param is 1111u
                    num_user = None
                    if split_arg[0].upper() == "LAST":
                        num_user = split_arg[1].lower()
                    if 'u' in num_user or 'user' in num_user or 'users' in num_user or 'person' in num_user or 'people' in num_user:
                        num_user = num_user.replace("people", "").replace("person", "").replace("users", "").replace("user", "").replace("u", "")
                        try:
                            num_user = int(num_user)
                            if len(ctx.guild.members) <= 2:
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please use normal tip command. There are only few users.'
                                await ctx.edit_original_message(content=msg)
                                return
                            # Check if we really have that many user in the guild 20%
                            elif num_user >= len(ctx.guild.members):
                                try:
                                    msg = f'{ctx.author.mention}, you want to tip more than the number of people in this guild!? It can be done :). Wait a while.... I am doing it. (**counting..**)'
                                    await ctx.edit_original_message(content=msg)
                                except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                    # No need to tip if failed to message
                                    return
                                message_talker = await store.sql_get_messages(str(ctx.guild.id), str(ctx.channel.id), 0, len(ctx.guild.members))
                                if ctx.author.id in message_talker:
                                    message_talker.remove(ctx.author.id)
                                if len(message_talker) == 0:
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is not sufficient user to count.'
                                    await ctx.edit_original_message(content=msg)
                                elif len(message_talker) < len(ctx.guild.members) - 1:  # minus bot
                                    msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}** and tip to those **{len(message_talker)}**.'
                                    await ctx.channel.send(msg)
                                    # tip all user who are in the list
                                    try:
                                        await self.multiple_tip_talker(ctx, amount, COIN_NAME, getattr(self.bot.coin_list, COIN_NAME), message_talker, False)
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                return
                            elif num_user > 0:
                                message_talker = await store.sql_get_messages(str(ctx.guild.id), str(ctx.channel.id), 0, num_user + 1)
                                if len(message_talker) == 0:
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is not sufficient user to count.'
                                    await ctx.edit_original_message(content=msg)
                                if ctx.author.id in message_talker:
                                    message_talker.remove(ctx.author.id)
                                else:
                                    # remove the last one
                                    message_talker.pop()

                                if len(message_talker) == 0:
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is not sufficient user to count.'
                                    await ctx.edit_original_message(content=msg)
                                elif len(message_talker) < num_user:
                                    try:
                                        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}** and tip to those **{len(message_talker)}**.'
                                        await ctx.channel.send(msg)
                                    except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                        # No need to tip if failed to message
                                        return
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                    # tip all user who are in the list
                                    try:
                                        await self.multiple_tip_talker(ctx, amount, COIN_NAME, getattr(self.bot.coin_list, COIN_NAME), message_talker, False)
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                else:
                                    try:
                                        await self.multiple_tip_talker(ctx, amount, COIN_NAME, getattr(self.bot.coin_list, COIN_NAME), message_talker, False)
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                return
                            else:
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, what is this **{num_user}** number? Please give a number bigger than 0 :) '
                                await ctx.edit_original_message(content=msg)
                                return
                        except ValueError:
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid param after **LAST**.'
                            await ctx.edit_original_message(content=msg)
                        return
                    else:
                        time_string = split_arg[1].lower()
                        time_second = None
                        try:
                            time_string = time_string.replace("years", "y").replace("yrs", "y").replace("yr", "y").replace("year", "y").replace("months", "mon").replace("month", "mon").replace("mons", "mon").replace("weeks", "w").replace("week", "w")

                            time_string = time_string.replace("day", "d").replace("days", "d").replace("hours", "h").replace("hour", "h").replace("hrs", "h").replace("hr", "h")

                            time_string = time_string.replace("minutes", "mn").replace("mns", "mn").replace("mins", "mn").replace("min", "mn")

                            mult = {'y': 12 * 30 * 24 * 60 * 60, 'mon': 30 * 24 * 60 * 60, 'w': 7 * 24 * 60 * 60, 'd': 24 * 60 * 60, 'h': 60 * 60, 'mn': 60}
                            time_second = sum(int(num) * mult.get(val, 1) for num, val in re.findall('(\d+)(\w+)', time_string))
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot(traceback.format_exc())
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid time given. Please use this example: `tip 10 WRKZ last 12mn`'
                            await ctx.edit_original_message(content=msg)
                            return
                        try:
                            time_given = int(time_second)
                        except ValueError:
                            await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given check.')
                            return
                        if time_given:
                            if time_given < 5 * 60 or time_given > 30 * 24 * 60 * 60:
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please give try time inteval between 5mn to 30d.'
                                await ctx.edit_original_message(content=msg)
                                return
                            else:
                                message_talker = await store.sql_get_messages(str(ctx.guild.id), str(ctx.channel.id), time_given, None)
                                if len(message_talker) == 0:
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is no active talker in such period.'
                                    await ctx.edit_original_message(content=msg)
                                    return
                                else:
                                    try:
                                        await self.multiple_tip_talker(ctx, amount, COIN_NAME, getattr(self.bot.coin_list, COIN_NAME), message_talker, False)
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                            return
                else:
                    try:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you need at least one person to tip to.'
                        await ctx.edit_original_message(content=msg)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                    return
            else:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you need at least one person to tip to.'
                await ctx.edit_original_message(content=msg)


    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        usage='tip <amount> <token> @mention .... [last 10u, last 10mn]', 
        options=[
            Option('amount', 'amount', OptionType.string, required=True), 
            Option('token', 'token', OptionType.string, required=True),  
            Option('args', '<@mention1> <@mention2> ... | <@role> ... | last 10u | last 10mn ', OptionType.string, required=True)
        ],
        description="Tip other people"
    )
    async def tip(
        self, 
        ctx,
        amount: str,
        token: str,
        args: str
    ):
        try:
            await self.async_tip(ctx, amount, token, args)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    async def async_gtip(self, ctx, amount: str, token: str, args):
        COIN_NAME = token.upper()
        # Token name check
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            await ctx.response.send_message(msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_tip") != 1:
                msg = f'{ctx.author.mention}, **{COIN_NAME}** tipping is disable.'
                await ctx.response.send_message(msg)
                return
        # End token name check
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo['tiponly'] and serverinfo['tiponly'] != "ALLCOIN" and COIN_NAME not in serverinfo['tiponly'].split(","):
            allowed_coins = serverinfo['tiponly']
            msg = f'{ctx.author.mention}, **{COIN_NAME}** is not allowed here. Currently, allowed `{allowed_coins}`. You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`'
            await ctx.response.send_message(msg)
            return

        try:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing guild tip command...'
            await ctx.response.send_message(msg)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(f"{EMOJI_INFORMATION} {ctx.author.mention}, failed to execute guild tip message...", ephemeral=True)
            return

        # print("async_tip args: "+ str(args))
        if args == "@everyone":
            get_list_member_n_role = [str(member.id) for member in ctx.guild.members if member.id != ctx.author.id]
        else:
            get_list_member_n_role = re.findall(r'<?\w*\d*>', args)
        list_member_ids = []

        if len(get_list_member_n_role) > 0:
            get_list_member_n_role = [each.replace(">", "").replace("<", "") for each in get_list_member_n_role]
            # There is member or role to check
            # Check member
            for each_m in get_list_member_n_role:
                try:
                    m = self.bot.get_user(int(each_m))
                    list_member_ids.append(m.id)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            if len(get_list_member_n_role) > 0:
                for each_r in get_list_member_n_role:
                    try:
                        # get list users in role
                        get_role = disnake.utils.get(ctx.guild.roles, id=int(each_r))
                        role_listMember = [member.id for member in ctx.guild.members if get_role in member.roles]
                        if len(role_listMember) > 0:
                            list_member_ids += role_listMember
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
            list_member_ids = list(set(list_member_ids))
            if len(list_member_ids) > 0:
                try:
                    await self.multiple_tip(ctx, amount, COIN_NAME, list_member_ids, True)
                except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                    pass
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                return
        if len(get_list_member_n_role) == 0 or len(list_member_ids) == 0:
            # There is no member or role to check
            # Check list talk or last XXu
            split_arg = args.strip().split()
            if len(split_arg) >= 2:
                time_given = None
                if split_arg[0].upper() == "LAST":
                    # try if the param is 1111u
                    num_user = None
                    if split_arg[0].upper() == "LAST":
                        num_user = split_arg[1].lower()
                    if 'u' in num_user or 'user' in num_user or 'users' in num_user or 'person' in num_user or 'people' in num_user:
                        num_user = num_user.replace("people", "").replace("person", "").replace("users", "").replace("user", "").replace("u", "")
                        try:
                            num_user = int(num_user)
                            if len(ctx.guild.members) <= 2:
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please use normal tip command. There are only few users.'
                                await ctx.edit_original_message(content=msg)
                                return
                            # Check if we really have that many user in the guild 20%
                            elif num_user >= len(ctx.guild.members):
                                try:
                                    msg = f'{ctx.author.mention}, you want to tip more than the number of people in this guild!? It can be done :). Wait a while.... I am doing it. (**counting..**)'
                                    await ctx.edit_original_message(content=msg)
                                except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                    # No need to tip if failed to message
                                    return
                                message_talker = await store.sql_get_messages(str(ctx.guild.id), str(ctx.channel.id), 0, len(ctx.guild.members))
                                if ctx.author.id in message_talker:
                                    message_talker.remove(ctx.author.id)
                                if len(message_talker) == 0:
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is not sufficient user to count.'
                                    await ctx.edit_original_message(content=msg)
                                    return
                                elif len(message_talker) < len(ctx.guild.members) - 1:  # minus bot
                                    msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}** and tip to those **{len(message_talker)}**.'
                                    await ctx.channel.send(msg)
                                    # tip all user who are in the list
                                    try:
                                        await self.multiple_tip_talker(ctx, amount, COIN_NAME, getattr(self.bot.coin_list, COIN_NAME), message_talker, True)
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                return
                            elif num_user > 0:
                                message_talker = await store.sql_get_messages(str(ctx.guild.id), str(ctx.channel.id), 0, num_user + 1)
                                if len(message_talker) == 0:
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is not sufficient user to count.'
                                    await ctx.edit_original_message(content=msg)
                                    return
                                if ctx.author.id in message_talker:
                                    message_talker.remove(ctx.author.id)
                                else:
                                    # remove the last one
                                    message_talker.pop()

                                if len(message_talker) == 0:
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is not sufficient user to count.'
                                    await ctx.edit_original_message(content=msg)
                                elif len(message_talker) < num_user:
                                    try:
                                        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}** and tip to those **{len(message_talker)}**.'
                                        await ctx.channel.send(msg)
                                    except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                        # No need to tip if failed to message
                                        return
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                    # tip all user who are in the list
                                    try:
                                        await self.multiple_tip_talker(ctx, amount, COIN_NAME, getattr(self.bot.coin_list, COIN_NAME), message_talker, True)
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                else:
                                    try:
                                        await self.multiple_tip_talker(ctx, amount, COIN_NAME, getattr(self.bot.coin_list, COIN_NAME), message_talker, True)
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                return
                            else:
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, what is this **{num_user}** number? Please give a number bigger than 0 :) '
                                await ctx.edit_original_message(content=msg)
                                return
                        except ValueError:
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid param after **LAST**.'
                            await ctx.edit_original_message(content=msg)
                        return
                    else:
                        time_string = split_arg[1].lower()
                        time_second = None
                        try:
                            time_string = time_string.replace("years", "y").replace("yrs", "y").replace("yr", "y").replace("year", "y").replace("months", "mon").replace("month", "mon").replace("mons", "mon").replace("weeks", "w").replace("week", "w")

                            time_string = time_string.replace("day", "d").replace("days", "d").replace("hours", "h").replace("hour", "h").replace("hrs", "h").replace("hr", "h")

                            time_string = time_string.replace("minutes", "mn").replace("mns", "mn").replace("mins", "mn").replace("min", "mn")

                            mult = {'y': 12 * 30 * 24 * 60 * 60, 'mon': 30 * 24 * 60 * 60, 'w': 7 * 24 * 60 * 60, 'd': 24 * 60 * 60, 'h': 60 * 60, 'mn': 60}
                            time_second = sum(int(num) * mult.get(val, 1) for num, val in re.findall('(\d+)(\w+)', time_string))
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot(traceback.format_exc())
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid time given. Please use this example: `tip 10 WRKZ last 12mn`'
                            await ctx.edit_original_message(content=msg)
                            return
                        try:
                            time_given = int(time_second)
                        except ValueError:
                            await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given check.')
                            return
                        if time_given:
                            if time_given < 5 * 60 or time_given > 30 * 24 * 60 * 60:
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please give try time inteval between 5mn to 30d.'
                                await ctx.edit_original_message(content=msg)
                            else:
                                message_talker = await store.sql_get_messages(str(ctx.guild.id), str(ctx.channel.id), time_given, None)
                                if len(message_talker) == 0:
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is no active talker in such period.'
                                    await ctx.edit_original_message(content=msg)
                                else:
                                    try:
                                        await self.multiple_tip_talker(ctx, amount, COIN_NAME, getattr(self.bot.coin_list, COIN_NAME), message_talker, True)
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                            return
                else:
                    try:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you need at least one person to tip to.'
                        await ctx.edit_original_message(content=msg)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                    return
            else:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you need at least one person to tip to.'
                await ctx.edit_original_message(content=msg)


    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.has_permissions(manage_channels=True)
    @commands.slash_command(
        usage='guildtip <amount> <token> @mention @mention..', 
        options=[
            Option('amount', 'amount', OptionType.string, required=True), 
            Option('token', 'token', OptionType.string, required=True),  
            Option('args', '<@mention1> <@mention2> ... | <@role> ... ', OptionType.string, required=True)
        ],
        description="Tip other people using your guild's balance."
    )
    async def guildtip(
        self, 
        ctx,
        amount: str,
        token: str,
        args: str
    ):
        try:
            await self.async_gtip(ctx, amount, token, args)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    # Multiple tip
    async def multiple_tip(self, ctx, amount, coin: str, listMembers, if_guild: bool = False):
        COIN_NAME = coin.upper()
        guild_name = '**{}**'.format(ctx.guild.name) if if_guild else ''
        tip_type_text = 'guild tip' if if_guild else 'tip'
        guild_or_tip = 'GUILDTIP' if if_guild else 'TIPS'
        id_tipper = str(ctx.guild.id) if if_guild else str(ctx.author.id)

        net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
        contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
        token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")

        MinTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
        MaxTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")

        User_WalletAPI = WalletAPI(self.bot)

        get_deposit = await User_WalletAPI.sql_get_userwallet(str(id_tipper), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await User_WalletAPI.sql_register_user(str(id_tipper), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']


        height = None
        try:
            if type_coin in ["ERC-20", "TRC-20"]:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
            else:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        userdata_balance = await store.sql_user_balance_single(id_tipper, COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])
        # Check if tx in progress
        if int(id_tipper) in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return

        height = None
        try:
            if type_coin in ["ERC-20", "TRC-20"]:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
            else:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        # check if amount is all
        all_amount = False
        if not amount.isdigit() and amount.upper() == "ALL":
            all_amount = True
            userdata_balance = await store.sql_user_balance_single(id_tipper, COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
            amount = float(userdata_balance['adjust'])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]: # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            if usd_equivalent_enable == 0:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{COIN_NAME}`."
                await ctx.edit_original_message(content=msg)
                return
            else:
                native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                COIN_NAME_FOR_PRICE = COIN_NAME
                if native_token_name:
                    COIN_NAME_FOR_PRICE = native_token_name
                per_unit = None
                if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                    id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                    per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                else:
                    per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
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
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.'
                await ctx.edit_original_message(content=msg)
                return
        # end of check if amount is all

        if amount <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
            await ctx.edit_original_message(content=msg)
            return

        if amount < MinTip or amount > MaxTip:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than **{num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display}** or bigger than **{num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, Insufficient balance to send {tip_type_text} of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return

        if len(listMembers) == 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} detect zero number of users.'
            await ctx.edit_original_message(content=msg)
            return

        memids = []  # list of member ID
        list_mentions = []
        for member_id in listMembers:
            member = self.bot.get_user(int(member_id))
            if ctx.author.id != member.id and member in ctx.guild.members:
                memids.append(str(member.id))
                list_mentions.append(member)
        TotalAmount = amount * len(memids)

        if len(memids) == 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, no users...'
            await ctx.edit_original_message(content=msg)
            return

        if TotalAmount > MaxTip:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Total transaction cannot be bigger than **{num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return
        elif actual_balance < TotalAmount:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, not sufficient balance.'
            await ctx.edit_original_message(content=msg)
            return

        tipAmount = num_format_coin(TotalAmount, COIN_NAME, coin_decimal, False)
        amountDiv_str = num_format_coin(amount, COIN_NAME, coin_decimal, False)
        equivalent_usd = ""
        total_equivalent_usd = ""
        amount_in_usd = 0.0
        total_amount_in_usd = 0.0
        per_unit = None
        if usd_equivalent_enable == 1:
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            COIN_NAME_FOR_PRICE = COIN_NAME
            if native_token_name:
                COIN_NAME_FOR_PRICE = native_token_name
            if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
            else:
                per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
            if per_unit and per_unit > 0:
                amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                if amount_in_usd > 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
                total_amount_in_usd = float(amount_in_usd * len(memids))
                if total_amount_in_usd > 0.0001:
                    total_equivalent_usd = " ~ {:,.4f} USD".format(total_amount_in_usd)

        max_allowed = 400
        try:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if len(memids) > max_allowed:
                # Check if premium guild
                if serverinfo and serverinfo['is_premium'] == 0:
                    msg = f'{ctx.author.mention}, there are more than maximum allowed `{str(max_allowed)}`. You can request pluton#8888 to allow this for your guild.'
                    await ctx.edit_original_message(content=msg)
                    await logchanbot(f"{ctx.guild.id} / {ctx.guild.name} reaches number of recievers: `{str(len(memids))}` issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}.")
                    return
                else:
                    await logchanbot(f"{ctx.guild.id} / {ctx.guild.name} reaches number of recievers: `{str(len(memids))}` issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}.")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        notifyList = await store.sql_get_tipnotify()
        try:
            tip_type = "TIP"
            if len(memids) > 1:
                tip_type = "TIPS"
            if int(id_tipper) not in self.bot.TX_IN_PROCESS:
                self.bot.TX_IN_PROCESS.append(int(id_tipper))
            tips = await store.sql_user_balance_mv_multiple(id_tipper, memids, str(ctx.guild.id), str(ctx.channel.id), amount, COIN_NAME, tip_type, coin_decimal, SERVER_BOT, contract, float(amount_in_usd))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        if int(id_tipper) in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.remove(int(id_tipper))
        if tips:
            # tipper shall always get DM. Ignore notifyList
            try:
                if len(memids) > 20:
                    msg = f'{EMOJI_ARROW_RIGHTHOOK} {tip_type_text} of **{tipAmount} {token_display}** {total_equivalent_usd} was sent to ({len(memids)}) members in server `{ctx.guild.name}`.\nEach member got: **{amountDiv_str} {token_display}** {equivalent_usd}\n'
                elif len(memids) >= 1:
                    incl_msg = []
                    incl_msg_str = ""
                    for each_m in list_mentions:
                        if ctx.author.id != member.id and str(member.id) not in notifyList:
                            incl_msg.append(each_m.mention)
                        if ctx.author.id != member.id and str(member.id) in notifyList:
                            incl_msg.append("{}#{}".format(each_m.name, each_m.discriminator))
                    if len(incl_msg) > 0: incl_msg_str = ", ".join(incl_msg)
                    msg = f'{EMOJI_ARROW_RIGHTHOOK} {tip_type_text} of **{tipAmount} {token_display}** {total_equivalent_usd} was sent to {incl_msg_str} in server `{ctx.guild.name}`.'
                    if len(memids) > 1:
                        msg += f'\nEach member got: **{amountDiv_str} {token_display}** {equivalent_usd}\n'
                try:
                    await ctx.author.send(msg)
                except Exception as e:
                    pass
            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                pass
            if len(list_mentions) >= 1:
                for member in list_mentions:
                    # print(member.name) # you'll just print out Member objects your way.
                    if ctx.author.id != member.id and member.id != self.bot.user.id and member.bot == False and str(member.id) not in notifyList:
                        try:
                            msg = f'{EMOJI_MONEYFACE} You got a {tip_type_text} of **{amountDiv_str} {token_display}** {equivalent_usd} from {ctx.author.name}#{ctx.author.discriminator} in server `{ctx.guild.name}`\n{NOTIFICATION_OFF_CMD}'
                            await member.send(msg)
                        except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                            pass



    # Multiple tip
    async def multiple_tip_talker(self, ctx, amount: str, coin: str, coin_dict, list_talker, if_guild: bool = False):
        guild_or_tip = 'GUILDTIP' if if_guild else 'TIPS'
        guild_name = '**{}**'.format(ctx.guild.name) if if_guild else ''
        tip_type_text = 'guild tip' if if_guild else 'tip'
        id_tipper = str(ctx.guild.id) if if_guild else str(ctx.author.id)
        COIN_NAME = coin.upper()

        net_name = coin_dict['net_name']
        type_coin = coin_dict['type']
        deposit_confirm_depth = coin_dict['deposit_confirm_depth']
        coin_decimal = coin_dict['decimal']
        contract = coin_dict['contract']
        token_display = coin_dict['display_name']
        usd_equivalent_enable = coin_dict['usd_equivalent_enable']

        MinTip = float(coin_dict['real_min_tip'])
        MaxTip = float(coin_dict['real_max_tip'])

        User_WalletAPI = WalletAPI(self.bot)

        get_deposit = await User_WalletAPI.sql_get_userwallet(id_tipper, COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await User_WalletAPI.sql_register_user(id_tipper, COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']

        # Check if tx in progress
        if int(id_tipper) in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, there is another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return

        height = None
        try:
            if type_coin in ["ERC-20", "TRC-20"]:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
            else:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        # check if amount is all
        all_amount = False
        if not amount.isdigit() and amount.upper() == "ALL":
            all_amount = True
            userdata_balance = await store.sql_user_balance_single(id_tipper, COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
            amount = float(userdata_balance['adjust'])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]: # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            if usd_equivalent_enable == 0:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{COIN_NAME}`."
                await ctx.edit_original_message(content=msg)
                return
            else:
                native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                COIN_NAME_FOR_PRICE = COIN_NAME
                if native_token_name:
                    COIN_NAME_FOR_PRICE = native_token_name
                per_unit = None
                if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                    id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                    per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                else:
                    per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
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

        try:
            amount = float(amount)
        except ValueError:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid amount.'
            await ctx.edit_original_message(content=msg)
            return

        if amount <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
            await ctx.edit_original_message(content=msg)
            return


        notifyList = await store.sql_get_tipnotify()
        userdata_balance = await store.sql_user_balance_single(id_tipper, COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])

        if amount > MaxTip or amount < MinTip:
            nsg = f'{EMOJI_RED_NO} {ctx.author.mention}, transaction cannot be bigger than **{num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}** or smaller than **{num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to send {tip_type_text} of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return

        list_receivers = []
        for member_id in list_talker:
            try:
                member = self.bot.get_user(int(member_id))
                if member and member in ctx.guild.members and ctx.author.id != member.id:
                    user_to = await User_WalletAPI.sql_get_userwallet(str(member_id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                    if user_to is None:
                        user_to = await User_WalletAPI.sql_register_user(str(member_id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)
                    try:
                        list_receivers.append(str(member_id))
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                        print('Failed creating wallet for tip talk for userid: {}'.format(member_id))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())

        max_allowed = 400
        try:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if len(list_receivers) > max_allowed:
                # Check if premium guild
                if serverinfo and serverinfo['is_premium'] == 0:
                    msg = f'{ctx.author.mention}, there are more than maximum allowed `{str(max_allowed)}`. You can request pluton#8888 to allow this for your guild.'
                    await ctx.edit_original_message(content=msg)
                    await logchanbot(f"{ctx.guild.id} / {ctx.guild.name} reaches number of recievers: `{str(len(list_receivers))}` issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}.")
                    return
                else:
                    await logchanbot(f"{ctx.guild.id} / {ctx.guild.name} reaches number of recievers: `{str(len(list_receivers))}` issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}.")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        if len(list_receivers) == 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, no users or can not find any user to tip...'
            await ctx.edit_original_message(content=msg)
            return

        TotalAmount = amount * len(list_receivers)

        if TotalAmount > MaxTip:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, total transaction cannot be bigger than **{num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return
        elif amount < MinTip:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, total transaction cannot be smaller than **{num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return
        elif TotalAmount > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} {guild_name}, insufficient balance to send total {tip_type_text} of **{num_format_coin(TotalAmount, COIN_NAME, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return

        if len(list_receivers) < 1:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is no active talker in such period. Please increase more duration or tip directly!'
            await ctx.edit_original_message(content=msg)
            return

        # add queue also tip
        if int(id_tipper) not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(int(id_tipper))
        else:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, there is another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return

        tip = None

        equivalent_usd = ""
        total_equivalent_usd = ""
        amount_in_usd = 0.0
        total_amount_in_usd = 0.0

        per_unit = None
        if usd_equivalent_enable == 1:
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            COIN_NAME_FOR_PRICE = COIN_NAME
            if native_token_name:
                COIN_NAME_FOR_PRICE = native_token_name
            if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
            else:
                per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
            if per_unit and per_unit > 0:
                amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                if amount_in_usd > 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
                total_amount_in_usd = float(Decimal(per_unit) * Decimal(TotalAmount))
                if total_amount_in_usd > 0.0001:
                    total_equivalent_usd = " ~ {:,.4f} USD".format(total_amount_in_usd)

        try:
            if int(id_tipper) not in self.bot.TX_IN_PROCESS:
                self.bot.TX_IN_PROCESS.append(int(id_tipper))
            tiptalk = await store.sql_user_balance_mv_multiple(id_tipper, list_receivers, str(ctx.guild.id), str(ctx.channel.id), amount, COIN_NAME, "TIPTALK", coin_decimal, SERVER_BOT, contract, float(amount_in_usd))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

        # remove queue from tip
        if int(id_tipper) in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.remove(int(id_tipper))

        if tiptalk:
            # tipper shall always get DM. Ignore notifyList
            try:
                msg = f'{EMOJI_ARROW_RIGHTHOOK} {tip_type_text} of **{num_format_coin(TotalAmount, COIN_NAME, coin_decimal, False)} {token_display}** {total_equivalent_usd} was sent to ({len(list_receivers)}) members in server `{ctx.guild.name}` for active talking.\nEach member got: **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}** {equivalent_usd}\n'
                try:
                    await ctx.author.send(msg)
                except Exception as e:
                    pass
            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                pass

            # Message mention all in public
            total_found = 0
            max_mention = 40
            numb_mention = 0

            # mention all user
            send_tipped_ping = 0
            list_user_mention = []
            list_user_mention_str = ""
            list_user_not_mention = []
            list_user_not_mention_str = ""
            random.shuffle(list_talker)
            for member_id in list_talker:
                member = self.bot.get_user(int(member_id))
                if not member:
                    continue

                if send_tipped_ping >= config.discord.maxTipTalkMessage:
                    total_found += 1
                else:
                    if ctx.author.id != member.id and member.id != self.bot.user.id:
                        if str(member.id) not in notifyList:
                            list_user_mention.append("{}".format(member.mention))
                        else:
                            list_user_not_mention.append("{}#{}".format(member.name, member.discriminator))
                    total_found += 1
                    numb_mention += 1

                    # Check if a batch meets
                    if numb_mention > 0 and numb_mention % max_mention == 0:
                        # send the batch
                        if len(list_user_mention) >= 1:
                            list_user_mention_str = ", ".join(list_user_mention)
                        if len(list_user_not_mention) >= 1:
                            list_user_not_mention_str = ", ".join(list_user_not_mention)
                        try:
                            if len(list_user_mention_str) > 5 or len(list_user_not_mention_str) > 5:
                                msg = f'{EMOJI_MONEYFACE} {list_user_mention_str} {list_user_not_mention_str}, you got a {tip_type_text} of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} {equivalent_usd} from {ctx.author.name}#{ctx.author.discriminator}{NOTIFICATION_OFF_CMD}'
                                await ctx.followup.send(msg)
                                send_tipped_ping += 1
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot(traceback.format_exc())
                        # reset
                        list_user_mention = []
                        list_user_mention_str = ""
                        list_user_not_mention = []
                        list_user_not_mention_str = ""
            # if there is still here
            if len(list_user_mention) + len(list_user_not_mention) > 1:
                if len(list_user_mention) >= 1:
                    list_user_mention_str = ", ".join(list_user_mention)
                if len(list_user_not_mention) >= 1:
                    list_user_not_mention_str = ", ".join(list_user_not_mention)
                try:
                    remaining_str = ""
                    if numb_mention < total_found:
                        remaining_str = " and other {} members".format(total_found-numb_mention)
                    msg = f'{EMOJI_MONEYFACE} {list_user_mention_str} {list_user_not_mention_str} {remaining_str}, you got a {tip_type_text} of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}** {equivalent_usd} from {ctx.author.name}#{ctx.author.discriminator}{NOTIFICATION_OFF_CMD}'
                    await ctx.followup.send(msg)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)


    # End of Tip Normal

def setup(bot):
    bot.add_cog(Tips(bot))
