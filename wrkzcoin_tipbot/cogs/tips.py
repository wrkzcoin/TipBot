import asyncio
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
import utils
from Bot import num_format_coin, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, EMOJI_MONEYFACE, NOTIFICATION_OFF_CMD, EMOJI_SPEAK, EMOJI_BELL, EMOJI_BELL_SLASH, EMOJI_HOURGLASS_NOT_DONE, EMOJI_INFORMATION, EMOJI_PARTY, SERVER_BOT, seconds_str, text_to_num, truncate
from config import config
import redis_utils
from cogs.wallet import WalletAPI


# Defines a simple view of row buttons.
class FreeTip_Button(disnake.ui.View):
    message: disnake.Message

    def __init__(self, bot, timeout: float):
        super().__init__(timeout=timeout)
        self.ttlcache = TTLCache(maxsize=500, ttl=60.0)
        self.bot = bot


    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True

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
                    await self.message.edit(embed=embed, view=None)
                    # update status
                    change_status = await store.discord_freetip_update(str(self.message.id), "NOCOLLECT")
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            elif len(attend_list) > 0:
                # re-check balance
                userdata_balance = await store.sql_user_balance(get_freetip['from_userid'], COIN_NAME)
                actual_balance = float(userdata_balance['Adjust'])

                if actual_balance < 0 and get_owner:
                    await self.message.reply(f'{EMOJI_RED_NO} {get_owner.mention} Insufficient balance to do a free tip of {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}.')
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
                        per_unit = get_mathtip['unit_price_usd']
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
                            await self.message.edit(embed=embed, view=None)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                    if tips:
                        link_to_msg = "https://discord.com/channels/{}/{}/{}".format(get_freetip['guild_id'], get_freetip['channel_id'], str(self.message.id))
                        # free tip shall always get DM. Ignore notifyList
                        try:
                            if get_owner:
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
            await self.message.edit(view=None)


    @disnake.ui.button(label="🎁 Collect", style=ButtonStyle.green, custom_id="collect_freetip")
    async def row_enter_airdrop(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        try:
            msg = "Nothing to do!"
            get_message = await store.get_discord_freetip_by_msgid(str(interaction.message.id))
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


    # Notifytip
    async def async_notifytip(self, ctx, onoff: str):
        if onoff.upper() not in ["ON", "OFF"]:
            msg = f'{ctx.author.mention} You need to use only `ON` or `OFF`.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        onoff = onoff.upper()
        notifyList = await store.sql_get_tipnotify()
        if onoff == "ON":
            if str(ctx.author.id) in notifyList:
                msg = f'{ctx.author.mention} {EMOJI_BELL} OK, you will get all notification when tip.'
                await store.sql_toggle_tipnotify(str(ctx.author.id), "ON")
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
            else:
                msg = f'{ctx.author.mention} {EMOJI_BELL} You already have notification ON by default.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
        elif onoff == "OFF":
            if str(ctx.author.id) in notifyList:
                msg = f'{ctx.author.mention} {EMOJI_BELL_SLASH} You already have notification OFF.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
            else:
                await store.sql_toggle_tipnotify(str(ctx.author.id), "OFF")
                msg = f'{ctx.author.mention} {EMOJI_BELL_SLASH} OK, you will not get any notification when anyone tips.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
        return


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


    @commands.command(usage='notifytip <on/off>', aliases=['notifytip'], description='Toggle notify tip notification from bot ON|OFF')
    async def _notifytip(
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
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_tip") != 1:
                msg = f'{ctx.author.mention}, **{COIN_NAME}** tipping is disable.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
        # End token name check

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
            msg = f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                await ctx.reply(msg)
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
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
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
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
        else:
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
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
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Number of random users cannot below **{minimum_users}**.'
                                if type(ctx) == disnake.ApplicationCommandInteraction:
                                    await ctx.response.send_message(msg)
                                else:
                                    await ctx.reply(msg)
                                return
                            elif num_user >= minimum_users:
                                message_talker = await store.sql_get_messages(str(ctx.guild.id), str(ctx.channel.id), 0, num_user + 1)
                                if ctx.author.id in message_talker:
                                    message_talker.remove(ctx.author.id)
                                else:
                                    # remove the last one
                                    message_talker.pop()
                                if len(message_talker) < minimum_users:
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention} There is not sufficient user to count for random tip.'
                                    if type(ctx) == disnake.ApplicationCommandInteraction:
                                        await ctx.response.send_message(msg)
                                    else:
                                        await ctx.reply(msg)
                                    return
                                elif len(message_talker) < num_user:
                                    try:
                                        msg = f'{EMOJI_INFORMATION} {ctx.author.mention} I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}** and will random to one of those **{len(message_talker)}** users.'
                                        if type(ctx) == disnake.ApplicationCommandInteraction:
                                            await ctx.response.send_message(msg)
                                        else:
                                            await ctx.reply(msg)
                                    except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                        # no need tip
                                        return
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        return
                            has_last = True
                        except ValueError:
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid param after **LAST** for random tip. Support only *LAST* **X**u right now.'
                            if type(ctx) == disnake.ApplicationCommandInteraction:
                                await ctx.response.send_message(msg)
                            else:
                                await ctx.reply(msg)
                            return
                    else:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid param after **LAST** for random tip. Support only *LAST* **X**u right now.'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return
                else:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid param after **LAST** for random tip. Support only *LAST* **X**u right now.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
            if has_last is False and listMembers and len(listMembers) >= minimum_users:
                rand_user = random.choice(listMembers)
                max_loop = 0
                while True:
                    if rand_user != ctx.author and rand_user.bot is False:
                        break
                    else:
                        rand_user = random.choice(listMembers)
                    max_loop += 1
                    if max_loop >= 5:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention} {token_display} Please try again, maybe guild doesnot have so many users.'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return

            elif has_last is True and message_talker and len(message_talker) >= minimum_users:
                rand_user_id = random.choice(message_talker)
                max_loop = 0
                while True:
                    rand_user = self.bot.get_user(rand_user_id)
                    if rand_user and rand_user != ctx.author and rand_user.bot is False and rand_user in ctx.guild.members:
                        break
                    else:
                        rand_user_id = random.choice(message_talker)
                        rand_user = self.bot.get_user(rand_user_id)
                    max_loop += 1
                    if max_loop >= 10:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention} {token_display} Please try again, maybe guild doesnot have so many users.'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        break
            else:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} {token_display} not enough member for random tip.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                if ctx.author.id in self.bot.TX_IN_PROCESS:
                    self.bot.TX_IN_PROCESS.remove(ctx.author.id)
            return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
            return

        notifyList = await store.sql_get_tipnotify()
        userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])

        if amount > MaxTip or amount < MinTip:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than **{num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}** or smaller than **{num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display}**.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        elif amount > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a random tip of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}**.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        # add queue also randtip
        if ctx.author.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.author.id)
        else:
            msg = f'{EMOJI_ERROR} {ctx.author.mention} {EMOJI_HOURGLASS_NOT_DONE} You have another tx in progress.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        tip = None
        if rand_user is not None:
            Tip_WalletAPI = WalletAPI(self.bot)
            user_to = await User_WalletAPI.sql_get_userwallet(str(rand_user.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
            if user_to is None:
                user_to = await User_WalletAPI.sql_register_user(str(rand_user.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)

            try:
                tip = await store.sql_user_balance_mv_single(str(ctx.author.id), str(rand_user.id), str(ctx.guild.id), str(ctx.channel.id), amount, COIN_NAME, "RANDTIP", coin_decimal, SERVER_BOT)
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
            randtip_public_respond = False
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} {rand_user.name}#{rand_user.discriminator} got your random tip of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} '
                    f'{token_display}** in server `{ctx.guild.name}`')
            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                pass
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            if str(rand_user.id) not in notifyList:
                try:
                    await rand_user.send(
                        f'{EMOJI_MONEYFACE} You got a random tip of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} '
                        f'{token_display}** from {ctx.author.name}#{ctx.author.discriminator} in server `{ctx.guild.name}`\n'
                        f'{NOTIFICATION_OFF_CMD}')
                except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                    pass
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            try:
                # try message in public also
                msg = f'{rand_user.name}#{rand_user.discriminator} got a random tip of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}** from {ctx.author.name}#{ctx.author.discriminator}'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                randtip_public_respond = True
            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                pass
            except Exception as e:
                traceback.print_exc(file=sys.stdout)


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

    @commands.command(usage='randtip <amount> <token> [all/online/last]', aliases=['randomtip', 'randtip'], description='Tip to random user in the guild')
    async def _randtip(self, ctx, amount: str, token: str, *, rand_option: str = None):
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
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_tip") != 1:
                msg = f'{ctx.author.mention}, **{COIN_NAME}** tipping is disable.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
        # End token name check

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
            msg = f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                await ctx.reply(msg)
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
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
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
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
        else:
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
        # end of check if amount is all

        def hms_to_seconds(time_string):
            duration_in_second = 0
            try:
                time_string = time_string.replace("hours", "h")
                time_string = time_string.replace("hour", "h")
                time_string = time_string.replace("hrs", "h")
                time_string = time_string.replace("hr", "h")

                time_string = time_string.replace("minutes", "mn")
                time_string = time_string.replace("mns", "mn")
                time_string = time_string.replace("mins", "mn")
                time_string = time_string.replace("min", "mn")
                time_string = time_string.replace("mn", "mn")
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
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid duration.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        if duration_s == 0:
            duration_s = default_duration
            # Just info, continue
        elif duration_s < config.freetip.duration_min or duration_s > config.freetip.duration_max:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid duration. Please use between {str(config.freetip.duration_min)}s to {str(config.freetip.duration_max)}s.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        if amount <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        notifyList = await store.sql_get_tipnotify()
        userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])

        if amount > MaxTip or amount < MinTip:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than **{num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}** or smaller than **{num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display}**.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        elif amount > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a free tip of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}**.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
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

        embed = disnake.Embed(title=f"FreeTip appears {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} {equivalent_usd}", description=f"Click to collect", timestamp=datetime.utcnow())
        add_index = 0
        try:
            if comment and len(comment) > 0:
                add_index = 1
                embed.add_field(name="Comment", value=comment, inline=True)
            embed.add_field(name="Attendees", value="React below to join!", inline=False)
            embed.add_field(name="Individual Tip Amount", value=f"{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}", inline=True)
            embed.add_field(name="Num. Attendees", value="**0** members", inline=True)
            embed.set_footer(text=f"FreeTip by {ctx.author.name}#{ctx.author.discriminator}, Time Left: {seconds_str(duration_s)}")
            
            view = FreeTip_Button(self.bot, duration_s)
            view.message = await ctx.channel.send(embed=embed, view=view)

            comment_str = ""
            if comment and len(comment) > 0:
                comment_str = comment
            if ctx.author.id not in self.bot.TX_IN_PROCESS:
                self.bot.TX_IN_PROCESS.append(ctx.author.id)
            insert_freetip = await store.insert_discord_freetip(COIN_NAME, contract, str(ctx.author.id), "{}#{}".format(ctx.author.name, ctx.author.discriminator), str(view.message.id), comment_str, str(ctx.guild.id), str(ctx.channel.id), amount, total_in_usd, equivalent_usd, per_unit, coin_decimal, int(time.time())+duration_s, "ONGOING")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.remove(ctx.author.id)


    @commands.command(usage='freetip <amount> <token> <duration> [comment]', aliases=['airdrop', 'airdrops'], description="Spread free tip by user reacting with emoji")
    async def freetip(self, ctx, amount: str, token: str, duration: str=None, *, comment: str = None):
        try:
            await self.async_freetip(ctx, amount, token, duration, comment)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    # End of FreeTip


def setup(bot):
    bot.add_cog(Tips(bot))
