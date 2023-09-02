import sys
import time
import traceback
from datetime import datetime
import random
import re
from decimal import Decimal
import asyncio

import disnake
from disnake.ext import commands, tasks
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
from disnake import TextInputStyle

from disnake import ActionRow, Button
from disnake.enums import ButtonStyle
from cachetools import TTLCache

import store
from Bot import logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, \
    EMOJI_MONEYFACE, NOTIFICATION_OFF_CMD, EMOJI_SPEAK, EMOJI_BELL, EMOJI_BELL_SLASH, EMOJI_HOURGLASS_NOT_DONE, \
    EMOJI_INFORMATION, EMOJI_PARTY, SERVER_BOT, seconds_str_days, text_to_num, truncate

from cogs.wallet import WalletAPI
from cogs.utils import Utils, num_format_coin

# Verifying free tip
class FreeTip_Verify(disnake.ui.Modal):
    def __init__(self, ctx, bot, question, answer, from_user_id, message_id) -> None:
        self.ctx = ctx
        self.bot = bot
        self.utils = Utils(self.bot)
        self.question = question
        self.answer = answer
        self.from_user_id = from_user_id
        self.message_id = message_id
        components = [
            disnake.ui.TextInput(
                label="Type answer",
                placeholder="???",
                custom_id="answer_id",
                style=TextInputStyle.paragraph,
                required=True
            )
        ]
        super().__init__(title=f"FreeTip Verification! {question}", custom_id="modal_freetip_verify", components=components)

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        # Check if type of question is bool or multipe
        await interaction.response.send_message(content=f"{interaction.author.mention}, verification starts...", ephemeral=True)

        answer = interaction.text_values['answer_id'].strip()
        if answer == "":
            await interaction.edit_original_message(f"{interaction.author.mention}, answer is empty!")
            return
        try:
            if int(answer) != self.answer:
                await interaction.edit_original_message(f"{interaction.author.mention}, incorrect answer!")
                return
            elif int(answer) == self.answer:
                # correct
                await store.insert_freetip_collector(
                    str(interaction.message.id),
                    self.from_user_id, str(interaction.author.id),
                    "{}#{}".format(interaction.author.name, interaction.author.discriminator)
                )
                try:
                    # Update message
                    _msg: disnake.Message = await interaction.channel.fetch_message(self.message_id)
                    if _msg:
                        embed = _msg.embeds[0] # embeds is list, we take 0
                        embed.clear_fields()
                        get_freetip = await store.get_discord_freetip_by_msgid(str(self.message_id))
                        if get_freetip is not None:
                            amount = get_freetip['real_amount']
                            coin_name = get_freetip['token_name']
                            coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                            coin_emoji = coin_emoji + " " if coin_emoji else ""
                            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                            collectors = await store.get_freetip_collector_by_id(
                                get_freetip['message_id'], get_freetip['from_userid']
                            )
                            indiv_amount = num_format_coin(truncate(amount / len(collectors), 12)) \
                                if len(collectors) > 0 else num_format_coin(truncate(amount, 12))
                            if get_freetip['airdrop_content'] and \
                                len(get_freetip['airdrop_content']) > 0:
                                embed.add_field(
                                    name="Comment",
                                    value=get_freetip['airdrop_content'],
                                    inline=False
                                )
                            if len(collectors) > 0:
                                name_list = []
                                for each_att in collectors:
                                    name_list.append("<@{}>".format(each_att['collector_id']))
                                    if len(name_list) > 0 and len(name_list) % 25 == 0:
                                        embed.add_field(name='Attendees', value=" | ".join(name_list), inline=False)
                                        name_list = []
                                if len(name_list) > 0:
                                    embed.add_field(name='Attendees', value=" | ".join(name_list), inline=False)
                            else:
                                embed.add_field(
                                    name='Attendees',
                                    value="N/A",
                                    inline=False
                                )
                            embed.add_field(
                                name="Num. Attendees",
                                value=f"**{len(collectors)}** member(s)",
                                inline=True
                            )
                            embed.add_field(
                                name='Each Member Receives:',
                                value=f"{coin_emoji}{indiv_amount} {token_display}",
                                inline=True
                            )
                            try:
                                time_left = get_freetip['airdrop_time'] - int(time.time())
                                owner_displayname = ""
                                get_owner = self.bot.get_user(int(get_freetip['from_userid']))
                                if get_owner:
                                    owner_displayname = f" by {get_owner.name}#{get_owner.discriminator}"
                                embed.set_footer(
                                    text=f"FreeTip {owner_displayname}, Time Left: {seconds_str_days(time_left)}")
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            await _msg.edit(embed=embed)
                            if 'fetched_msg' not in self.bot.other_data:
                                self.bot.other_data['fetched_msg'] = {}
                            self.bot.other_data['fetched_msg'][str(self.message_id)] = int(time.time())
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                # nofity freetip owner
                freetip_owner = self.bot.get_user(int(self.from_user_id))
                try:
                    freetip_link = "https://discord.com/channels/{}/{}/{}".format(
                        interaction.guild.id, interaction.channel.id, interaction.message.id
                    )
                    if freetip_owner is not None:
                        await freetip_owner.send(
                            "{}#{} / {} ☑️ completed verififcation with your /freetip {}".format(
                                interaction.author.name, interaction.author.discriminator,
                                interaction.author.mention, freetip_link
                            )
                        )
                except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                    pass
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                msg = "Sucessfully joined airdrop id: {}".format(str(interaction.message.id))
                await interaction.edit_original_message(content=msg)
                return
        except ValueError:
            await interaction.edit_original_message(f"{interaction.author.mention}, incorrect answer!")
        except Exception:
            traceback.print_exc(file=sys.stdout)

# Defines a simple view of row buttons.
class FreeTip_Button(disnake.ui.View):
    message: disnake.Message

    def __init__(self, bot, verify: str, owner_id: int):
        super().__init__()
        self.ttlcache = TTLCache(maxsize=500, ttl=60.0)
        self.bot = bot
        self.utils = Utils(self.bot)
        self.verify = verify
        self.wallet_api = WalletAPI(self.bot)
        self.owner_id = owner_id

    async def on_timeout(self):
        pass

    @disnake.ui.button(label="🎁 Collect", style=ButtonStyle.green, custom_id="collect_freetip")
    async def row_enter_airdrop(
            self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        try:
            if self.owner_id == interaction.author.id:
                await interaction.response.send_message(content=f"{interaction.author.mention}, you can not join your own /freetip ...", ephemeral=True)
                return

            msg = "Nothing to do!"
            get_message = None
            try:
                msg_id = interaction.message.id
                get_message = await store.get_discord_freetip_by_msgid(str(msg_id))
            except Exception:
                traceback.print_exc(file=sys.stdout)
                original_message = await interaction.original_message()
                get_message = await store.get_discord_freetip_by_msgid(str(original_message.id))

            if get_message is None:
                await interaction.response.send_message(content=f"{interaction.author.mention}, failed to collect /freetip!", ephemeral=True)
                await logchanbot(
                    f"[ERROR FREETIP] Failed to join a free tip in guild "\
                    f"{interaction.guild.name} / {interaction.guild.id} by "\
                    f"{interaction.author.name}#{interaction.author.discriminator}!"
                )
                return

            # Check if user in
            check_if_in = await store.check_if_freetip_collector_in(
                str(interaction.message.id),
                get_message['from_userid'],
                str(interaction.author.id)
            )
            if check_if_in:
                await interaction.response.send_message(content=f"{interaction.author.mention}, you're already in this /freetip!", ephemeral=True)
                return
            else:
                # If time already pass
                if int(time.time()) > get_message['airdrop_time']:
                    await interaction.response.send_message(content=f"{interaction.author.mention}, this /freetip already passed!", ephemeral=True)
                    return
                else:
                    key = "freetip_{}_{}".format(
                        str(interaction.message.id), str(interaction.author.id)
                    )
                    try:
                        if self.ttlcache[key] == key:
                            return
                        else:
                            self.ttlcache[key] = key
                    except Exception:
                        pass
                    # Verify here
                    if self.verify == "ON":
                        try:
                            random.seed(datetime.now())
                            a = random.randint(51, 100)
                            b = random.randint(10, 50)
                            question = "{} + {} = ?".format(a, b)
                            answer = a + b
                            # nofity freetip owner
                            freetip_owner = self.bot.get_user(int(get_message['from_userid']))
                            try:
                                freetip_link = "https://discord.com/channels/{}/{}/{}".format(
                                    get_message['guild_id'], get_message['channel_id'], get_message['message_id']
                                )
                                if freetip_owner is not None:
                                    await freetip_owner.send(
                                        "{}#{} / {} ❓ started to verify with your /freetip {}".format(
                                            interaction.author.name, interaction.author.discriminator,
                                            interaction.author.mention, freetip_link
                                        )
                                    )
                            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                pass
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            await interaction.response.send_modal(
                                modal=FreeTip_Verify(
                                    interaction, self.bot, question, answer,
                                    get_message['from_userid'], int(get_message['message_id'])
                                )
                            )
                            modal_inter: disnake.ModalInteraction = await self.bot.wait_for(
                                "modal_submit",
                                check=lambda i: i.custom_id == "modal_freetip_verify" and i.author.id == interaction.author.id,
                                timeout=30,
                            )
                        except (disnake.InteractionResponded, disnake.InteractionTimedOut, disnake.errors.NotFound) as e:
                            return
                        except asyncio.TimeoutError:
                            # The user didn't submit the modal in the specified period of time.
                            # This is done since Discord doesn't dispatch any event for when a modal is closed/dismissed.
                            await interaction.response.send_message(f"{interaction.author.mention}, timeout to join /freetip!", ephemeral=True)
                            return
                    else:
                        await store.insert_freetip_collector(
                            str(interaction.message.id),
                            get_message['from_userid'], str(interaction.author.id),
                            "{}#{}".format(interaction.author.name, interaction.author.discriminator)
                        )
                        msg = "Sucessfully joined airdrop id: {}".format(str(interaction.message.id))
                        await interaction.response.send_message(content=msg, ephemeral=True)
                        # Update message
                        _msg: disnake.Message = await interaction.channel.fetch_message(int(interaction.message.id))
                        if _msg:
                            embed = _msg.embeds[0] # embeds is list, we take 0
                            embed.clear_fields()
                            get_freetip = await store.get_discord_freetip_by_msgid(str(interaction.message.id))
                            if get_freetip is None:
                                return
                            try:
                                time_left = get_freetip['airdrop_time'] - int(time.time())
                                owner_displayname = ""
                                get_owner = self.bot.get_user(int(get_freetip['from_userid']))
                                if get_owner:
                                    owner_displayname = f" by {get_owner.name}#{get_owner.discriminator}"
                                embed.set_footer(
                                    text=f"FreeTip {owner_displayname}, Time Left: {seconds_str_days(time_left)}")
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            amount = get_freetip['real_amount']
                            coin_name = get_freetip['token_name']
                            coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                            coin_emoji = coin_emoji + " " if coin_emoji else ""
                            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                            collectors = await store.get_freetip_collector_by_id(
                                get_freetip['message_id'], get_freetip['from_userid']
                            )
                            indiv_amount = num_format_coin(truncate(amount / len(collectors), 12)) \
                                if len(collectors) > 0 else num_format_coin(truncate(amount, 12))
                            if get_freetip['airdrop_content'] and \
                                len(get_freetip['airdrop_content']) > 0:
                                embed.add_field(
                                    name="Comment",
                                    value=get_freetip['airdrop_content'],
                                    inline=False
                                )
                            if len(collectors) > 0:
                                name_list = []
                                for each_att in collectors:
                                    name_list.append("<@{}>".format(each_att['collector_id']))
                                    if len(name_list) > 0 and len(name_list) % 25 == 0:
                                        embed.add_field(name='Attendees', value=" | ".join(name_list), inline=False)
                                        name_list = []
                                if len(name_list) > 0:
                                    embed.add_field(name='Attendees', value=" | ".join(name_list), inline=False)
                            else:
                                embed.add_field(
                                    name='Attendees',
                                    value="N/A",
                                    inline=False
                                )
                            embed.add_field(
                                name="Num. Attendees",
                                value=f"**{len(collectors)}** member(s)",
                                inline=True
                            )
                            embed.add_field(
                                name='Each Member Receives:',
                                value=f"{coin_emoji}{indiv_amount} {token_display}",
                                inline=True
                            )
                            await _msg.edit(embed=embed)
                            if 'fetched_msg' not in self.bot.other_data:
                                self.bot.other_data['fetched_msg'] = {}
                            self.bot.other_data['fetched_msg'][str(interaction.message.id)] = int(time.time())
                        return
        except (disnake.InteractionResponded, disnake.InteractionTimedOut, disnake.errors.NotFound) as e:
            return
        except Exception:
            traceback.print_exc(file=sys.stdout)

class Tips(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.max_ongoing_by_user = self.bot.config['discord']['max_ongoing_by_user']
        self.max_ongoing_by_guild = self.bot.config['discord']['max_ongoing_by_guild']

    @tasks.loop(seconds=30.0)
    async def freetip_check(self):
        get_active_freetip = await store.get_active_discord_freetip(lap=7*24*3600)
        get_inactive_freetip = await store.get_inactive_discord_freetip(lap=7*24*3600)
        # Check if task recently run @bot_task_logs
        task_name = "tips_freetip_check"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        if len(get_active_freetip) > 0:
            for each_message_data in get_active_freetip:
                time_left = each_message_data['airdrop_time'] - int(time.time())
                # get message
                try:
                    guild = self.bot.get_guild(int(each_message_data['guild_id']))
                    if guild is None and self.bot.is_ready():
                        print("Guild {} found None".format(each_message_data['guild_id']))
                        await logchanbot("[FREETIP]: can not find guild for message ID: {} of channel {} in guild: {} by {}. Set that to FAILED.".format(
                            each_message_data['message_id'], each_message_data['channel_id'], each_message_data['guild_id'],
                            each_message_data['from_ownername']
                        ))
                        change_status = await store.discord_freetip_update(each_message_data['message_id'], "FAILED")
                        await asyncio.sleep(0.5)
                        continue
                    await self.bot.wait_until_ready()
                    channel = guild.get_channel(int(each_message_data['channel_id']))
                    if channel is None:
                        # check Bot uptime
                        uptime = round((datetime.now() - self.bot.start_time).total_seconds())
                        if uptime + 300 >= int(time.time()):
                            # skipped. Bot just re-connected
                            continue

                        print("Channel {} found None".format(each_message_data['channel_id']))
                        change_status = await store.discord_freetip_update(each_message_data['message_id'], "FAILED")
                        await logchanbot(
                            "Failed to find channel: msg id: {}, channel id: {}, guild: {}/{}. Set it to failed.".format(
                                each_message_data['message_id'], each_message_data['channel_id'],
                                guild.name, each_message_data['guild_id']
                            )
                        )
                        find_owner = self.bot.get_user(int(each_message_data['from_userid']))
                        if find_owner is not None:
                            await find_owner.send("I cancelled your /freetip id: {} in guild {} because I can't find channel.".format(
                                each_message_data['message_id'], guild.name
                            ))
                        continue
                    get_owner = guild.get_member(int(each_message_data['from_userid']))
                    owner_displayname = ""
                    if get_owner is None:
                        # In some case, user left the drop and we can't find them. Let tip process and ignore to DM them.
                        print("Airdroper None {}".format(each_message_data['from_userid']))
                        await asyncio.sleep(2.0)
                        get_owner = guild.get_member(int(each_message_data['from_userid']))
                    if get_owner:
                        owner_displayname = f" by {get_owner.name}#{get_owner.discriminator}"

                    # If time_left is too long
                    if 'fetched_msg' not in self.bot.other_data:
                        self.bot.other_data['fetched_msg'] = {}
                    else:
                        if each_message_data['message_id'] in self.bot.other_data['fetched_msg']:
                            last_fetched = self.bot.other_data['fetched_msg'][each_message_data['message_id']]
                            if int(time.time()) - last_fetched < 90 and time_left > 10*3600:
                                continue
                    _msg: disnake.Message = await channel.fetch_message(int(each_message_data['message_id']))
                    if _msg:
                        # check if coin exist?
                        coin_name = each_message_data['token_name']
                        if not hasattr(self.bot.coin_list, coin_name):
                            change_status = await store.discord_freetip_update(each_message_data['message_id'], "FAILED")
                            await _msg.edit(view=None)
                            continue

                        verify = "ON" if each_message_data['verify'] == 1 else "OFF"
                        view = FreeTip_Button(self.bot, verify, int(each_message_data['from_userid']))
                        try:
                            embed = _msg.embeds[0] # embeds is list, we take 0
                            embed.clear_fields()
                            amount = each_message_data['real_amount']
                            coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                            coin_emoji = coin_emoji + " " if coin_emoji else ""
                            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                            collectors = await store.get_freetip_collector_by_id(
                                each_message_data['message_id'], each_message_data['from_userid']
                            )

                            indiv_amount = num_format_coin(truncate(amount / len(collectors), 12)) \
                                if len(collectors) > 0 else num_format_coin(truncate(amount, 12))
                            if each_message_data['airdrop_content'] and \
                                len(each_message_data['airdrop_content']) > 0:
                                embed.add_field(
                                    name="Comment",
                                    value=each_message_data['airdrop_content'],
                                    inline=False
                                )
                            if len(collectors) > 0:
                                name_list = []
                                for each_att in collectors:
                                    name_list.append("<@{}>".format(each_att['collector_id']))
                                    if len(name_list) > 0 and len(name_list) % 25 == 0:
                                        embed.add_field(name='Attendees', value=" | ".join(name_list), inline=False)
                                        name_list = []
                                if len(name_list) > 0:
                                    embed.add_field(name='Attendees', value=" | ".join(name_list), inline=False)
                            else:
                                embed.add_field(
                                    name='Attendees',
                                    value="N/A",
                                    inline=False
                                )
                            embed.add_field(
                                name="Num. Attendees",
                                value=f"**{len(collectors)}** member(s)",
                                inline=True
                            )
                            embed.add_field(
                                name='Each Member Receives:',
                                value=f"{coin_emoji}{indiv_amount} {token_display}",
                                inline=True
                            )
                            if time_left > 0:
                                if 'fetched_msg' in self.bot.other_data and \
                                    each_message_data['message_id'] in self.bot.other_data['fetched_msg']:
                                    last_fetched = self.bot.other_data['fetched_msg'][each_message_data['message_id']]
                                    if int(time.time()) - last_fetched < 30:
                                        # skip
                                        continue
                                if int(time.time()) - int(_msg.edited_at.timestamp()) > 30:
                                    embed.set_footer(
                                        text=f"FreeTip {owner_displayname}, Time Left: {seconds_str_days(time_left)}")
                                    try:
                                        await _msg.edit(embed=embed, view=view)
                                    except disnake.errors.Forbidden:
                                        change_status = await store.discord_freetip_update(each_message_data['message_id'], "FAILED")
                                        await logchanbot(
                                            "Failed to edit message (Forbidden): msg id: {}, channel id: {}, guild: {}/{}. Set it to failed.".format(
                                                each_message_data['message_id'], each_message_data['channel_id'],
                                                guild.name, each_message_data['guild_id']
                                            )
                                        )
                                        find_owner = self.bot.get_user(int(each_message_data['from_userid']))
                                        if find_owner is not None:
                                            await find_owner.send("I cancelled your /freetip id: {} in guild {} because I got no permission to edit embed message.".format(
                                                each_message_data['message_id'], guild.name
                                            ))
                                    if 'fetched_msg' in self.bot.other_data:
                                        self.bot.other_data['fetched_msg'][each_message_data['message_id']] = int(time.time())
                            else:
                                ## Update content
                                if each_message_data['status'] == "ONGOING":
                                    if len(collectors) == 0:
                                        embed.set_footer(text=f"FreeTip by {owner_displayname}, and no one collected!")
                                        try:
                                            await _msg.edit(embed=embed, view=None)
                                            # update status
                                            change_status = await store.discord_freetip_update(each_message_data['message_id'], "NOCOLLECT")
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        link_to_msg = "https://discord.com/channels/{}/{}/{}".format(
                                            each_message_data['guild_id'], each_message_data['channel_id'],
                                            each_message_data['message_id']
                                        )
                                        # free tip shall always get DM. Ignore notifying list
                                        try:
                                            if get_owner is not None:
                                                await get_owner.send(
                                                    f"FreeTip of {coin_emoji}{num_format_coin(amount)} "\
                                                    f"{token_display} expired and no one collected.\n{link_to_msg}"
                                                )
                                        except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                            pass
                                    elif len(collectors) > 0:
                                        # re-check balance
                                        get_deposit = await self.wallet_api.sql_get_userwallet(
                                            each_message_data['from_userid'], coin_name, net_name, type_coin, SERVER_BOT, 0
                                        )
                                        if get_deposit is None:
                                            get_deposit = await self.wallet_api.sql_register_user(
                                                each_message_data['from_userid'], coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                                            )

                                        wallet_address = get_deposit['balance_wallet_address']
                                        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                            wallet_address = get_deposit['paymentid']
                                        elif type_coin in ["XRP"]:
                                            wallet_address = get_deposit['destination_tag']

                                        height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                                        userdata_balance = await store.sql_user_balance_single(
                                            each_message_data['from_userid'], coin_name, wallet_address, 
                                            type_coin, height, deposit_confirm_depth, SERVER_BOT
                                        )
                                        actual_balance = float(userdata_balance['adjust'])

                                        # We need only to check if balance > 0 his balance already pending.
                                        if actual_balance < 0:
                                            embed.set_footer(text=f"FreeTip by {owner_displayname}, failed!")
                                            try:
                                                await _msg.edit(embed=embed, view=None)
                                                # update status
                                                change_status = await store.discord_freetip_update(each_message_data['message_id'], "FAILED")
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                            # end of re-check balance
                                        else:
                                            # Multiple tip here
                                            amount_div = truncate(amount / len(collectors), 12)
                                            tipAmount = num_format_coin(amount)
                                            ActualSpend_str = num_format_coin(amount_div * len(collectors))
                                            amountDiv_str = num_format_coin(amount_div)
                                            amount_in_usd = 0.0
                                            per_unit = None
                                            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                                            if price_with:
                                                per_unit = each_message_data['unit_price_usd']
                                                if per_unit and per_unit > 0:
                                                    amount_in_usd = per_unit * float(amount_div)

                                            try:
                                                tips = await store.sql_user_balance_mv_multiple(
                                                    each_message_data['from_userid'], [i['collector_id'] for i in collectors],
                                                    each_message_data['guild_id'],
                                                    each_message_data['channel_id'], float(amount_div),
                                                    coin_name, "FREETIP", coin_decimal, SERVER_BOT,
                                                    contract, float(amount_in_usd), None
                                                )
                                                # If tip, update status
                                                change_status = await store.discord_freetip_update(each_message_data['message_id'], "COMPLETED")
                                                embed.set_footer(text=f"Completed! Collected by {len(collectors)} member(s)")
                                                await _msg.edit(embed=embed, view=None)
                                                if tips:
                                                    link_to_msg = "https://discord.com/channels/{}/{}/{}".format(
                                                        each_message_data['guild_id'], each_message_data['channel_id'],
                                                        each_message_data['message_id']
                                                    )
                                                    # free tip shall always get DM. Ignore notifying list
                                                    try:
                                                        guild = self.bot.get_guild(int(each_message_data['guild_id']))
                                                        msg_freetip = f"{EMOJI_ARROW_RIGHTHOOK} FreeTip of {coin_emoji}{tipAmount} {token_display} "\
                                                            f"was sent to ({len(collectors)}) members in server __{guild.name}__.\n"\
                                                            f"Each member got: {coin_emoji}**{amountDiv_str} {token_display}**\n"\
                                                            f"Actual spending: {coin_emoji}**{ActualSpend_str} {token_display}**\n{link_to_msg}"
                                                        if get_owner is not None:
                                                            await get_owner.send(
                                                                msg_freetip
                                                            )
                                                        await _msg.reply(msg_freetip)
                                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                                        pass
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                                await logchanbot("tips " +str(traceback.format_exc()))
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    else:
                        await logchanbot(
                            "I cannot fetch message: {}, channel id: {}".format(
                                each_message_data['message_id'], each_message_data['channel_id']
                            )
                        )
                        await asyncio.sleep(1.0)
                except disnake.errors.NotFound:
                    await logchanbot("[FREETIP]: can not find message ID: {} of channel {} in guild: {} by {}. Set that to FAILED.".format(
                        each_message_data['message_id'], each_message_data['channel_id'], each_message_data['guild_id'],
                        each_message_data['from_ownername']
                    ))
                    change_status = await store.discord_freetip_update(each_message_data['message_id'], "FAILED")
                    await asyncio.sleep(0.5)
                except disnake.errors.Forbidden:
                    # disnake.errors.Forbidden: 403 Forbidden (error code: 50001): Missing Access
                    change_status = await store.discord_freetip_update(each_message_data['message_id'], "FAILED")
                    await asyncio.sleep(0.5)
                    await logchanbot("[FREETIP]: I have no permission for message ID: {} of channel {} in guild: {} by {}. Set that to FAILED.".format(
                        each_message_data['message_id'], each_message_data['channel_id'], each_message_data['guild_id'],
                        each_message_data['from_ownername']
                    ))
                    # Tell owner that Bot has no permission
                    get_member = self.bot.get_user(int(each_message_data['from_userid']))
                    if get_member is not None:
                        await get_member.send("/freetip failed: I have no permission to get message: {} of channel {} in guild: {}.".format(
                            each_message_data['message_id'], each_message_data['channel_id'], each_message_data['guild_id']
                        ))
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(2.0)
        else:
            # Nothing to do, sleep
            await asyncio.sleep(3.0)
        # Check in active
        if len(get_inactive_freetip) > 0:
            for each_message_data in get_inactive_freetip:
                change_status = await store.discord_freetip_update(each_message_data['message_id'], "FAILED")
                if change_status is True:
                    await logchanbot(
                        "[{}] /freetip changed status to {} for ID: {} in guild: {} an channel: {} by user {} / {}".format(
                            SERVER_BOT, "FAILED", each_message_data['message_id'], each_message_data['guild_id'],
                            each_message_data['channel_id'], each_message_data['from_ownername'],
                            each_message_data['from_userid']))

                    # Notifytip
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))

    # called before the task/loop starts running
    @freetip_check.before_loop
    async def before_freetip_check(self):
        await self.bot.wait_until_ready()  # wait until the cache is populated

    async def async_notifytip(self, ctx, onoff: str):
        if onoff.upper() not in ["ON", "OFF"]:
            msg = f'{ctx.author.mention} You need to use only `ON` or `OFF`.'
            await ctx.response.send_message(msg)
            return

        onoff = onoff.upper()
        notifying_list = await store.sql_get_tipnotify()
        if onoff == "ON":
            if str(ctx.author.id) in notifying_list:
                msg = f'{ctx.author.mention} {EMOJI_BELL} OK, you will get all notification when tip.'
                await store.sql_toggle_tipnotify(str(ctx.author.id), "ON")
                await ctx.response.send_message(msg)
            else:
                msg = f'{ctx.author.mention} {EMOJI_BELL}, you already have notification ON by default.'
                await ctx.response.send_message(msg)
        elif onoff == "OFF":
            if str(ctx.author.id) in notifying_list:
                msg = f'{ctx.author.mention} {EMOJI_BELL_SLASH}, you already have notification OFF.'
                await ctx.response.send_message(msg)
            else:
                await store.sql_toggle_tipnotify(str(ctx.author.id), "OFF")
                msg = f'{ctx.author.mention} {EMOJI_BELL_SLASH} OK, you will not get any notification when anyone tips.'
                await ctx.response.send_message(msg)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/notifytip", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)


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
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing random tip...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/randtip", int(time.time())))
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

        coin_name = token.upper()
        # Token name check
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.edit_original_message(content=msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, coin_name), "enable_tip") != 1:
                msg = f'{ctx.author.mention}, **{coin_name}** tipping is disable.'
                await ctx.edit_original_message(content=msg)
                return
        # End token name check
        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo and serverinfo['tiponly'] and serverinfo['tiponly'] != "ALLCOIN" and coin_name not in serverinfo[
            'tiponly'].split(","):
            allowed_coins = serverinfo['tiponly']
            msg = f"{ctx.author.mention}, **{coin_name}** is not allowed here. Currently, allowed __{allowed_coins}__. "\
                f"You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`"
            await ctx.edit_original_message(content=msg)
            return

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
            if len(coin_emoji) > 0:
                await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, executing /randtip with {coin_emoji}...")
        except Exception:
            traceback.print_exc(file=sys.stdout)

        min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
        max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")

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

        # Check if tx in progress
        if str(ctx.author.id) in self.bot.tipping_in_progress and \
            int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 150:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
            await ctx.edit_original_message(content=msg)
            return

        height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        # check if amount is all
        all_amount = False
        if not amount.isdigit() and amount.upper() == "ALL":
            all_amount = True
            userdata_balance = await store.sql_user_balance_single(
                str(ctx.author.id), coin_name, wallet_address, type_coin, height,
                deposit_confirm_depth, SERVER_BOT
            )
            amount = float(userdata_balance['adjust'])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]:  # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
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
                        "Try with different method."
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
                listMembers = [member for member in ctx.guild.members if
                               member.bot is False and member.status != disnake.Status.offline]
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
                                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, number of random users cannot "\
                                    f"below **{minimum_users}**."
                                await ctx.edit_original_message(content=msg)
                                return
                            elif num_user >= minimum_users:
                                message_talker = await store.sql_get_messages(
                                    str(ctx.guild.id), str(ctx.channel.id), 0, num_user + 1
                                )
                                if len(message_talker) == 0:
                                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, there is not sufficient user to count."
                                    await ctx.edit_original_message(content=msg)
                                if ctx.author.id in message_talker:
                                    message_talker.remove(ctx.author.id)
                                else:
                                    # remove the last one
                                    message_talker.pop()
                                if len(message_talker) < minimum_users:
                                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, there is not sufficient user to count for random tip."
                                    await ctx.edit_original_message(content=msg)
                                    return
                                elif len(message_talker) < num_user:
                                    try:
                                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention} I could not find sufficient talkers up "\
                                            f"to **{num_user}**. I found only **{len(message_talker)}** and random to one of "\
                                            f"those **{len(message_talker)}** users."
                                        await ctx.channel.send(msg)
                                    except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                        # no need tip
                                        return
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                            has_last = True
                        except ValueError:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid param after **LAST** for random tip. "\
                                f"Support only *LAST* **X**u right now."
                            await ctx.edit_original_message(content=msg)
                            return
                    else:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid param after **LAST** for random tip. "\
                            f"Support only *LAST* **X**u right now."
                        await ctx.edit_original_message(content=msg)
                        return
                else:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid param after **LAST** for random tip. "\
                        "Support only *LAST* **X**u right now."
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
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention} {token_display}, "\
                                f"please try again, maybe guild doesn't have so many users."
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
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention} {token_display}, "\
                                f"please try again, maybe guild doesnot have so many users."
                            await ctx.edit_original_message(content=msg)
                            break
            else:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention} {token_display} not enough member for random tip."
                await ctx.edit_original_message(content=msg)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("tips " +str(traceback.format_exc()))
        try:
            del self.bot.tipping_in_progress[str(ctx.author.id)]
        except Exception:
            pass

        notifying_list = await store.sql_get_tipnotify()
        userdata_balance = await store.sql_user_balance_single(
            str(ctx.author.id), coin_name, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT
        )
        actual_balance = float(userdata_balance['adjust'])

        if amount > max_tip or amount < min_tip:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, transactions cannot be bigger than "\
                f"**{num_format_coin(max_tip)} {token_display}** or "\
                f"smaller than **{num_format_coin(min_tip)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to do a random tip of "\
                f"**{num_format_coin(amount)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return

        # add queue also randtip
        if str(ctx.author.id) in self.bot.tipping_in_progress and \
            int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 150:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
            await ctx.edit_original_message(content=msg)
            return

        equivalent_usd = ""
        amount_in_usd = 0.0
        per_unit = None
        price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
        if price_with:
            per_unit = await self.utils.get_coin_price(coin_name, price_with)
            if per_unit and per_unit['price'] and per_unit['price'] > 0:
                per_unit = per_unit['price']
                amount_in_usd = float(Decimal(amount) * Decimal(per_unit))
                if amount_in_usd >= 0.01:
                    equivalent_usd = " ~ {:,.2f}$".format(amount_in_usd)
                elif amount_in_usd >= 0.0001:
                    equivalent_usd = " ~ {:,.4f}$".format(amount_in_usd)

        tip = None
        if rand_user is not None:
            if str(ctx.author.id) not in self.bot.tipping_in_progress:
                self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())
            user_to = await self.wallet_api.sql_get_userwallet(
                str(rand_user.id), coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            if user_to is None:
                user_to = await self.wallet_api.sql_register_user(
                    str(rand_user.id), coin_name, net_name, type_coin, SERVER_BOT, 0
                )

            try:
                tip = await store.sql_user_balance_mv_single(
                    str(ctx.author.id), str(rand_user.id), str(ctx.guild.id),
                    str(ctx.channel.id), amount, coin_name, "RANDTIP",
                    coin_decimal, SERVER_BOT, contract, amount_in_usd, None
                )
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("tips " +str(traceback.format_exc()))
        else:
            # remove queue from randtip
            try:
                del self.bot.tipping_in_progress[str(ctx.author.id)]
            except Exception:
                pass
            await logchanbot(f"{ctx.author.id} randtip got None rand_user.")
            return

        # remove queue from randtip
        try:
            del self.bot.tipping_in_progress[str(ctx.author.id)]
        except Exception:
            pass

        if tip:
            # tipper shall always get DM. Ignore notifying list
            try:
                msg = f"{EMOJI_ARROW_RIGHTHOOK} {rand_user.name}#{rand_user.discriminator} got your random tip of "\
                    f"{num_format_coin(amount)} {token_display}{equivalent_usd} in server __{ctx.guild.name}__"
                await ctx.edit_original_message(content=msg)
            except Exception:
                traceback.print_exc(file=sys.stdout)
            if str(rand_user.id) not in notifying_list:
                try:
                    await rand_user.send(
                        f"{EMOJI_MONEYFACE} You got a random tip of {coin_emoji}{num_format_coin(amount)} "
                        f"{token_display}{equivalent_usd} from {ctx.author.name}#{ctx.author.discriminator} in server __{ctx.guild.name}__\n"
                        f"{NOTIFICATION_OFF_CMD}"
                    )
                except Exception:
                    pass

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        dm_permission=False,
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
        rand_option: str = None
    ):
        try:
            await self.async_randtip(ctx, amount, token, rand_option)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @randtip.autocomplete("token")
    async def randtip_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]
    # End of RandomTip

    # FreeTip
    async def async_freetip(
        self, ctx, amount: str, token: str, duration: int, comment: str = None, verify: str="OFF"
    ):
        cmd_name = ctx.application_command.qualified_name
        command_mention = f"__/{cmd_name}__"
        try:
            if self.bot.config['discord']['enable_command_mention'] == 1:
                cmd = self.bot.get_global_command_named(cmd_name.split()[0])
                command_mention = f"</{ctx.application_command.qualified_name}:{cmd.id}>"
        except Exception:
            traceback.print_exc(file=sys.stdout)

        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, executing {command_mention}"
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/freetip", int(time.time())))
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

        try:
            coin_name = token.upper()
            if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                coin_name = self.bot.coin_alias_names[coin_name]
            # Token name check
            if not hasattr(self.bot.coin_list, coin_name):
                msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
                await ctx.edit_original_message(content=msg)
                return
            else:
                if getattr(getattr(self.bot.coin_list, coin_name), "enable_tip") != 1:
                    msg = f'{ctx.author.mention}, **{coin_name}** tipping is disable.'
                    await ctx.edit_original_message(content=msg)
                    return
            # End token name check
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
            if serverinfo and serverinfo['tiponly'] and serverinfo['tiponly'] != "ALLCOIN" and coin_name not in serverinfo[
                'tiponly'].split(","):
                allowed_coins = serverinfo['tiponly']
                msg = f"{ctx.author.mention}, **{coin_name}** is not allowed here. Currently, allowed __{allowed_coins}__. "\
                    "You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`"
                await ctx.edit_original_message(content=msg)
                return

            # Check if there is many airdrop/mathtip/triviatip
            try:
                count_ongoing = await store.discord_freetip_ongoing(str(ctx.author.id), "ONGOING")
                if count_ongoing >= self.max_ongoing_by_user and ctx.author.id != self.bot.config['discord']['owner_id']:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you still have some ongoing tips. "\
                        "Please wait for them to complete first!"
                    await ctx.edit_original_message(content=msg)
                    return
                count_ongoing = await store.discord_freetip_ongoing_guild(str(ctx.guild.id), "ONGOING")
                # Check max if set in guild
                if serverinfo and count_ongoing >= serverinfo['max_ongoing_drop'] and ctx.author.id != self.bot.config['discord']['owner_id']:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, there are still some ongoing drops or tips in this guild. "\
                        "Please wait for them to complete first!"
                    await ctx.edit_original_message(content=msg)
                    return
                elif serverinfo is None and count_ongoing >= self.max_ongoing_by_guild and ctx.author.id != self.bot.config['discord']['owner_id']:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, there are still some ongoing drops or tips in this guild. "\
                        "Please wait for them to complete first!"
                    await ctx.edit_original_message(content=msg)
                    await logchanbot(f"[FREETIP] server {str(ctx.guild.id)} has no data in discord_server.")
                    return
            except Exception:
                traceback.print_exc(file=sys.stdout)
            # End of ongoing check

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

            # token_info = getattr(self.bot.coin_list, coin_name)
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")

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

            # Check if tx in progress
            if str(ctx.author.id) in self.bot.tipping_in_progress and \
                int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 150:
                msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
                await ctx.edit_original_message(content=msg)
                return

            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
            # check if amount is all
            all_amount = False
            if not amount.isdigit() and amount.upper() == "ALL":
                all_amount = True
                userdata_balance = await store.sql_user_balance_single(
                    str(ctx.author.id), coin_name, wallet_address,
                    type_coin, height, deposit_confirm_depth, SERVER_BOT
                )
                amount = float(userdata_balance['adjust'])
            # If $ is in amount, let's convert to coin/token
            elif "$" in amount[-1] or "$" in amount[0]:  # last is $
                # Check if conversion is allowed for this coin.
                amount = amount.replace(",", "").replace("$", "")
                price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
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
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method."
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

            notifying_list = await store.sql_get_tipnotify()
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
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, transactions cannot be bigger than "\
                    f"**{num_format_coin(max_tip)} {token_display}** or smaller than "\
                    f"**{num_format_coin(min_tip)} {token_display}**."
                await ctx.edit_original_message(content=msg)
                return
            elif amount > actual_balance:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to do a free tip of "\
                    f"**{num_format_coin(amount)} {token_display}**."
                await ctx.edit_original_message(content=msg)
                return

            equivalent_usd = ""
            total_in_usd = 0.0
            per_unit = None
            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
            if price_with:
                per_unit = await self.utils.get_coin_price(coin_name, price_with)
                if per_unit and per_unit['price'] and per_unit['price'] > 0:
                    per_unit = per_unit['price']
                    total_in_usd = float(Decimal(amount) * Decimal(per_unit))
                    if total_in_usd >= 0.0001:
                        equivalent_usd = " ~ {:,.4f} USD".format(total_in_usd)

            embed = disnake.Embed(
                title=f"FreeTip appears {coin_emoji}{num_format_coin(amount)} {token_display} {equivalent_usd}",
                description=f"Click to collect", timestamp=datetime.fromtimestamp(int(time.time()) + duration))
            try:
                if comment and len(comment) > 0:
                    embed.add_field(name="Comment", value=comment, inline=True)
                embed.add_field(name="Attendees", value="Click to collect!", inline=False)
                embed.add_field(
                    name="Individual Tip Amount",
                    value=f"{coin_emoji}{num_format_coin(amount)} {token_display}",
                    inline=True
                )
                embed.add_field(name="Num. Attendees", value="**0** members", inline=True)
                embed.set_footer(
                    text=f"FreeTip by {ctx.author.name}#{ctx.author.discriminator}, Time Left: {seconds_str_days(duration)}")

                comment_str = ""
                if comment and len(comment) > 0:
                    comment_str = comment
                if str(ctx.author.id) not in self.bot.tipping_in_progress:
                    self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())
                    try:
                        verify_int = 1 if verify == "ON" else 0
                        view = FreeTip_Button(self.bot, verify, ctx.author.id)
                        view.message = await ctx.original_message()
                        await store.insert_discord_freetip(
                            coin_name, contract, str(ctx.author.id),
                            "{}#{}".format(
                                ctx.author.name,
                                ctx.author.discriminator
                            ),
                            str(view.message.id), comment_str,
                            str(ctx.guild.id), str(ctx.channel.id), amount,
                            total_in_usd, equivalent_usd, per_unit,
                            coin_decimal, int(time.time()) + duration,
                            "ONGOING", verify_int
                        )
                        try:
                            await ctx.edit_original_message(content=None, embed=embed, view=view)
                        except disnake.errors.Forbidden:
                            # cancelled it
                            change_status = await store.discord_freetip_update(str(view.message.id), "FAILED")
                            await ctx.edit_original_message(
                                content=f"{EMOJI_RED_NO} {ctx.author.mention}, failed to edit embed message (no permission)!"
                            )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
            except Exception:
                traceback.print_exc(file=sys.stdout)
            try:
                del self.bot.tipping_in_progress[str(ctx.author.id)]
            except Exception:
                pass
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        dm_permission=False,
        usage='freetip',
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option('duration', 'duration', OptionType.string, required=True, choices=[
                OptionChoice("2mn", "2mn"),
                OptionChoice("5mn", "5mn"),
                OptionChoice("30mn", "30mn"),
                OptionChoice("42mn", "42mn"),
                OptionChoice("1 Hour", "60mn"),
                OptionChoice("2 Hours", "120mn"),
                OptionChoice("6 Hours", "360mn"),
                OptionChoice("12 Hours", "720mn"),
                OptionChoice("1 Day", "1440mn"),
                OptionChoice("2 Days", "2880mn"),
                OptionChoice("3 Days", "4320mn")
            ]),
            Option('comment', 'comment', OptionType.string, required=False),
            Option('verify', 'verify (ON | OFF)', OptionType.string, required=False, choices=[
                OptionChoice("ON", "ON"),
                OptionChoice("OFF", "OFF")
            ]
            )
        ],
        description="Spread free crypto tip by user's click"
    )
    async def freetip(
        self,
        ctx,
        amount: str,
        token: str,
        duration: str,
        comment: str = None,
        verify: str="OFF"
    ):
        try:
            duration = int(duration.replace("mn", ""))*60 # in seconds
            if duration == 0:
                duration = 60
                # Just info, continue
            await self.async_freetip(ctx, amount, token, duration, comment, verify)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @freetip.autocomplete("token")
    async def freetip_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]
    # End of FreeTip

    # TipAll
    async def async_tipall(self, ctx, amount: str, token: str, ping: str, user: str):
        mention_all = True if ping == "YES" else False
        mute_tip = False
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, executing /tipall..."
        await ctx.response.send_message(msg)

        cmd_name = ctx.application_command.qualified_name
        command_mention = f"__/{cmd_name}__"
        try:
            if self.bot.config['discord']['enable_command_mention'] == 1:
                cmd = self.bot.get_global_command_named(cmd_name.split()[0])
                command_mention = f"</{ctx.application_command.qualified_name}:{cmd.id}>"
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/tipall", int(time.time())))
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

        coin_name = token.upper()
        # Token name check
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.edit_original_message(content=msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, coin_name), "enable_tip") != 1:
                msg = f'{ctx.author.mention}, **{coin_name}** tipping is disable.'
                await ctx.edit_original_message(content=msg)
                return
        # End token name check
        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo and serverinfo['tiponly'] and serverinfo['tiponly'] != "ALLCOIN" and coin_name not in serverinfo[
            'tiponly'].split(","):
            allowed_coins = serverinfo['tiponly']
            msg = f"{ctx.author.mention}, **{coin_name}** is not allowed here. Currently, allowed __{allowed_coins}__. "\
                f"You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`"
            await ctx.edit_original_message(content=msg)
            return
        if serverinfo and serverinfo['mute_tip'] == "YES":
            mute_tip = True
            mention_all = False

        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
        max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")

        # token_info = getattr(self.bot.coin_list, coin_name)
        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")

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

        # Check if tx in progress
        if str(ctx.author.id) in self.bot.tipping_in_progress and \
            int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 150:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
            await ctx.edit_original_message(content=msg)
            return

        height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        # check if amount is all
        all_amount = False
        if not amount.isdigit() and amount.upper() == "ALL":
            all_amount = True
            userdata_balance = await store.sql_user_balance_single(
                str(ctx.author.id), coin_name, wallet_address,
                type_coin, height, deposit_confirm_depth, SERVER_BOT
            )
            amount = float(userdata_balance['adjust'])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]:  # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
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
                        "Try with different method."
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

        coin_emoji = ""
        try:
            if ctx.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is True:
                coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                coin_emoji = coin_emoji + " " if coin_emoji else ""
            if len(coin_emoji) > 0:
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, executing {command_mention} with {coin_emoji} "\
                        f"amount {num_format_coin(amount)} {coin_name}..."
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

        notifying_list = await store.sql_get_tipnotify()
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
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, transactions cannot be bigger than "\
                f"**{num_format_coin(max_tip)} {token_display}** or smaller than "\
                f"**{num_format_coin(min_tip)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to tip of "\
                f"**{num_format_coin(amount)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return

        listMembers = []
        if user.upper() == "ANY" or user.upper() == "ALL":
            listMembers = [member for member in ctx.guild.members]
        elif user.upper() == "ONLINE_EXCEPT_NO_NOTIFICATION":
            listMembers = [member for member in ctx.guild.members if
                           str(member.id) not in notifying_list and member.status != disnake.Status.offline and member.bot is False]
        elif user.upper() == "ALL_EXCEPT_NO_NOTIFICATION":
            listMembers = [member for member in ctx.guild.members if str(member.id) not in notifying_list]
        else:
            listMembers = [member for member in ctx.guild.members if
                           member.status != disnake.Status.offline and member.bot is False]
        if len(listMembers) == 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is no number of users.'
            await ctx.edit_original_message(content=msg)
            return

        print("Number of tip-all in {}: {}".format(ctx.guild.name, len(listMembers)))
        default_max_tip = 400
        max_allowed = default_max_tip # default
        if serverinfo and serverinfo['max_tip_users']:
            max_allowed = serverinfo['max_tip_users']
        if len(listMembers) > default_max_tip:
            await logchanbot(
                f"⚠️ {ctx.guild.id} / {ctx.guild.name} reaches number of receivers: __{str(len(listMembers))}__ "\
                f"issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}."
            )
        if len(listMembers) > max_allowed:
            msg = f"{ctx.author.mention}, there are more than maximum allowed __{str(max_allowed)}__. "\
                f"You can request pluton#8888 to increase this for your guild."
            await ctx.edit_original_message(content=msg)
            await logchanbot(
                f"🔴 {ctx.guild.id} / {ctx.guild.name} couldreaches number of receivers: __{str(len(listMembers))}__ "\
                f"/tipall issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}."
            )
            return

        memids = []  # list of member ID
        for member in listMembers:
            if ctx.author.id != member.id:
                memids.append(str(member.id))

        if len(memids) == 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, no users for such condition...'
            await ctx.edit_original_message(content=msg)
            return

        amount_div = truncate(amount / len(memids), 12)

        tipAmount = num_format_coin(amount)
        ActualSpend_str = num_format_coin(amount_div * len(memids))
        amountDiv_str = num_format_coin(amount_div)

        if amount_div <= 0:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, amount truncated to `0 {coin_name}`. Try bigger one."
            await ctx.edit_original_message(content=msg)
            return

        equivalent_usd = ""
        total_equivalent_usd = ""
        amount_in_usd = 0.0
        total_amount_in_usd = 0.0
        per_unit = None
        price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
        if price_with:
            per_unit = await self.utils.get_coin_price(coin_name, price_with)
            if per_unit and per_unit['price'] and per_unit['price'] > 0:
                per_unit = per_unit['price']
                amount_in_usd = float(Decimal(per_unit) * Decimal(amount_div))
                if amount_in_usd > 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
                total_amount_in_usd = float(amount_in_usd * len(memids))
                if total_amount_in_usd > 0.0001:
                    total_equivalent_usd = " ~ {:,.4f} USD".format(total_amount_in_usd)

        if amount / len(memids) < min_tip:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, transactions cannot be smaller "\
                f"than **{num_format_coin(min_tip)} "\
                f"{token_display}** for each member. You need at least "\
                f"**{num_format_coin(len(memids) * min_tip)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return

        if str(ctx.author.id) not in self.bot.tipping_in_progress:
            self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())
            try:
                tips = await store.sql_user_balance_mv_multiple(
                    str(ctx.author.id), memids, str(ctx.guild.id),
                    str(ctx.channel.id), float(amount_div), coin_name,
                    "TIPALL", coin_decimal, SERVER_BOT, contract,
                    float(amount_in_usd), None
                )
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("tips " +str(traceback.format_exc()))
        else:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish."
            await ctx.edit_original_message(content=msg)
            return
        try:
            del self.bot.tipping_in_progress[str(ctx.author.id)]
        except Exception:
            pass

        if tips:
            # Message mention all in public
            total_found = 0
            max_mention = 40
            numb_mention = 0

            # mention all user
            send_tipped_ping = 0
            list_user_mention = []
            list_user_not_mention = []
            random.shuffle(listMembers)

            extra_msg = NOTIFICATION_OFF_CMD
            if mute_tip is True:
                extra_msg = "*Guild owner mutes all mention.*"
            for member in listMembers:
                if send_tipped_ping >= self.bot.config['discord']['maxTipAllMessage']:
                    total_found += 1
                else:
                    if ctx.author.id != member.id and member.id != self.bot.user.id:
                        if mute_tip is True:
                            list_user_not_mention.append("{}#{}".format(member.name, member.discriminator))
                        elif mention_all is True and str(member.id) not in notifying_list:
                            list_user_mention.append("{}".format(member.mention))
                        else:
                            list_user_not_mention.append("{}#{}".format(member.name, member.discriminator))
                    total_found += 1
                    numb_mention += 1

                    # Check if a batch meets
                    if numb_mention > 0 and numb_mention % max_mention == 0:
                        # send the batch
                        mention_users = ""
                        if len(list_user_mention) >= 1:
                            mention_users = ", ".join(list_user_mention)
                        if len(list_user_not_mention) >= 1:
                            mention_users += ", " + ", ".join(list_user_not_mention)
                        try:
                            if len(mention_users) > 0:
                                msg = f"{EMOJI_MONEYFACE} {mention_users}, "\
                                    f"you got a tip of {coin_emoji}**{amountDiv_str} {token_display}** {equivalent_usd} from "\
                                    f"{ctx.author.name}#{ctx.author.discriminator}\n{extra_msg}"
                                await ctx.followup.send(msg)
                                send_tipped_ping += 1
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("tips " +str(traceback.format_exc()))
                        # reset
                        list_user_mention = []
                        list_user_not_mention = []
            # if there is still here
            if len(list_user_mention) + len(list_user_not_mention) >= 1:
                mention_users = ""
                if len(list_user_mention) >= 1:
                    mention_users = ", ".join(list_user_mention)
                if len(list_user_not_mention) >= 1:
                    mention_users += ", " + ", ".join(list_user_not_mention)
                try:
                    remaining_str = ""
                    if numb_mention < total_found:
                        remaining_str = " and other {} members".format(total_found - numb_mention)
                    msg = f"{EMOJI_MONEYFACE} {mention_users}{remaining_str}, "\
                        f"you got a tip of {coin_emoji}**{amountDiv_str} {token_display}** {equivalent_usd} from "\
                        f"{ctx.author.name}#{ctx.author.discriminator}\n{extra_msg}"
                    await ctx.followup.send(msg)
                except Exception:
                    traceback.print_exc(file=sys.stdout)

            # tipper shall always get DM. Ignore notifying list
            try:
                msg = f"{EMOJI_ARROW_RIGHTHOOK}, you tip {coin_emoji}{tipAmount} {token_display} to ({len(memids)}) members "\
                    f"in server __{ctx.guild.name}__.\nEach member got: {coin_emoji}**{amountDiv_str} {token_display}** "\
                    f"{equivalent_usd}\nActual spending: **{ActualSpend_str} {token_display}** {total_equivalent_usd}"
                await ctx.author.send(msg)
            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                pass

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        dm_permission=False,
        usage='tipall',
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option('ping', 'mention or no mention', OptionType.string, required=False, choices=[
                OptionChoice("YES", "YES"),
                OptionChoice("NO", "NO")
            ]),
            Option('user', 'user option (ONLINE or ALL)', OptionType.string, required=False, choices=[
                OptionChoice("ONLINE", "ONLINE"),
                OptionChoice("ONLINE EXCEPT FOR NO NOTIFICATION", "ONLINE_EXCEPT_NO_NOTIFICATION"),
                OptionChoice("ALL EXCEPT FOR NO NOTIFICATION", "ALL_EXCEPT_NO_NOTIFICATION"),
                OptionChoice("ALL", "ALL")
            ])
        ],
        description="Tip all online user"
    )
    async def tipall(
        self,
        ctx,
        amount: str,
        token: str,
        ping: str = "YES",
        user: str = "ONLINE"
    ):
        try:
            await self.async_tipall(ctx, amount, token, ping, user)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @tipall.autocomplete("token")
    async def tipall_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]
    # End of TipAll

    # Tip Normal
    async def async_tip(self, ctx, amount: str, token: str, args, split: str, ping: str):
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing tip command...'
        await ctx.response.send_message(msg)
        mention_all = True if ping == "YES" else False
        mute_tip = False
        split_amount = False
        if split == "SPLIT":
            split_amount = True

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/tip", int(time.time())))
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

        coin_name = token.upper()
        # Token name check
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.edit_original_message(content=msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, coin_name), "enable_tip") != 1:
                msg = f'{ctx.author.mention}, **{coin_name}** tipping is disable.'
                await ctx.edit_original_message(content=msg)
                return
        # End token name check
        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo and serverinfo['tiponly'] and serverinfo['tiponly'] != "ALLCOIN" and coin_name not in serverinfo[
            'tiponly'].split(","):
            allowed_coins = serverinfo['tiponly']
            msg = f"{ctx.author.mention}, **{coin_name}** is not allowed here. Currently, allowed __{allowed_coins}__. "\
                f"You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`"
            await ctx.edit_original_message(content=msg)
            return
        if serverinfo and serverinfo['mute_tip'] == "YES":
            mute_tip = True
            mention_all = False

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
                    if m:
                        list_member_ids.append(m.id)
                except Exception:
                    pass
            if len(get_list_member_n_role) > 0:
                for each_r in get_list_member_n_role:
                    try:
                        # get list users in role
                        get_role = disnake.utils.get(ctx.guild.roles, id=int(each_r))
                        role_list_members = [member.id for member in ctx.guild.members if get_role in member.roles]
                        if len(role_list_members) > 0:
                            list_member_ids += role_list_members
                    except Exception:
                        pass
            list_member_ids = list(set(list_member_ids))
            if len(list_member_ids) > 0:
                try:
                    await self.multiple_tip(ctx, amount, coin_name, list_member_ids, False, mention_all, split_amount)
                except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                    pass
                except Exception:
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
                        num_user = num_user.replace("people", "").replace("person", "").replace("users", "").replace(
                            "user", "").replace("u", "")
                        try:
                            num_user = int(num_user)
                            if len(ctx.guild.members) <= 2:
                                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, please use normal tip command. There are only few users."
                                await ctx.edit_original_message(content=msg)
                                return
                            # Check if we really have that many user in the guild 20%
                            elif num_user >= len(ctx.guild.members):
                                try:
                                    msg = f"{ctx.author.mention}, you want to tip more than the number of people in this guild!? "\
                                        f"It can be done :). Wait a while.... I am doing it. (**counting..**)"
                                    await ctx.edit_original_message(content=msg)
                                except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                    # No need to tip if failed to message
                                    return
                                message_talker = await store.sql_get_messages(
                                    str(ctx.guild.id), str(ctx.channel.id), 0, len(ctx.guild.members)
                                )
                                if ctx.author.id in message_talker:
                                    message_talker.remove(ctx.author.id)
                                if len(message_talker) == 0:
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is not sufficient user to count.'
                                    await ctx.edit_original_message(content=msg)
                                elif len(message_talker) < len(ctx.guild.members) - 1:  # minus bot
                                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, I could not find sufficient talkers up to **{num_user}**. "\
                                        f"I found only **{len(message_talker)}** and tip to those **{len(message_talker)}**."
                                    await ctx.channel.send(msg)
                                    # tip all user who are in the list
                                    try:
                                        await self.multiple_tip_talker(
                                            ctx, amount, coin_name,
                                            getattr(self.bot.coin_list, coin_name),
                                            message_talker, False, mention_all,
                                            split_amount
                                        )
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                return
                            elif num_user > 0:
                                message_talker = await store.sql_get_messages(
                                    str(ctx.guild.id), str(ctx.channel.id), 0, num_user + 1
                                )
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
                                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, I could not find sufficient talkers up to "\
                                            f"**{num_user}**. I found only **{len(message_talker)}** and tip to those **{len(message_talker)}**."
                                        await ctx.channel.send(msg)
                                    except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                        # No need to tip if failed to message
                                        return
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    # tip all user who are in the list
                                    try:
                                        await self.multiple_tip_talker(
                                            ctx, amount, coin_name, getattr(self.bot.coin_list, coin_name),
                                            message_talker, False, mention_all,
                                            split_amount
                                        )
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                else:
                                    try:
                                        await self.multiple_tip_talker(
                                            ctx, amount, coin_name, getattr(self.bot.coin_list, coin_name),
                                            message_talker, False, mention_all,
                                            split_amount
                                        )
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                return
                            else:
                                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, what is this **{num_user}** number? "\
                                    "Please give a number bigger than 0 :) "
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
                            time_string = time_string.replace("years", "y").replace("yrs", "y").replace("yr", "y").replace("year", "y")
                            time_string = time_string.replace("months", "mon").replace("month", "mon").replace("mons", "mon").replace("weeks", "w").replace("week", "w")
                            time_string = time_string.replace("day", "d").replace("days", "d").replace("hours", "h").replace("hour", "h").replace("hrs", "h").replace("hr", "h")
                            time_string = time_string.replace("minutes", "mn").replace("mns", "mn").replace("mins", "mn").replace("min", "mn")

                            mult = {'y': 12 * 30 * 24 * 60 * 60, 'mon': 30 * 24 * 60 * 60, 'w': 7 * 24 * 60 * 60,
                                    'd': 24 * 60 * 60, 'h': 60 * 60, 'mn': 60}
                            time_second = sum(
                                int(num) * mult.get(val, 1) for num, val in re.findall('(\d+)(\w+)', time_string))
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("tips " +str(traceback.format_exc()))
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid time given. "\
                                "Please use this example: `tip 10 WRKZ last 12mn`"
                            await ctx.edit_original_message(content=msg)
                            return
                        try:
                            time_given = int(time_second)
                        except ValueError:
                            await ctx.edit_original_message(
                                content=f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given check.')
                            return
                        if time_given:
                            if time_given < 5 * 60 or time_given > 30 * 24 * 60 * 60:
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please give try time inteval between 5mn to 30d.'
                                await ctx.edit_original_message(content=msg)
                                return
                            else:
                                message_talker = await store.sql_get_messages(
                                    str(ctx.guild.id), str(ctx.channel.id), time_given, None
                                )
                                if len(message_talker) == 0:
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is no active talker in such period.'
                                    await ctx.edit_original_message(content=msg)
                                    return
                                else:
                                    try:
                                        await self.multiple_tip_talker(
                                            ctx, amount, coin_name, getattr(self.bot.coin_list, coin_name), 
                                            message_talker, False, mention_all,
                                            split_amount
                                        )
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                            return
                else:
                    try:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you need at least one person to tip to.'
                        await ctx.edit_original_message(content=msg)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("tips " +str(traceback.format_exc()))
                    return
            else:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you need at least one person to tip to.'
                await ctx.edit_original_message(content=msg)

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        dm_permission=False,
        usage='tip <amount> <token> @mention .... [last 10u, last 10mn]',
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option(
                'args',
                '<@mention1> <@mention2> ... | <@role> ... | last 10u | last 10mn ',
                OptionType.string,
                required=True
            ),
            Option('split', 'split or each', OptionType.string, required=False, choices=[
                OptionChoice("SPLIT", "SPLIT"),
                OptionChoice("EACH", "EACH")
            ]),
            Option('ping', 'mention or no mention', OptionType.string, required=False, choices=[
                OptionChoice("YES", "YES"),
                OptionChoice("NO", "NO")
            ])
        ],
        description="Tip other people"
    )
    async def tip(
        self,
        ctx,
        amount: str,
        token: str,
        args: str,
        split: str = "EACH",
        ping: str = "YES"
    ):
        try:
            await self.async_tip(ctx, amount, token, args, split, ping)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @tip.autocomplete("token")
    async def tip_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

    async def async_gtip(self, ctx, amount: str, token: str, args, split: str):
        coin_name = token.upper()
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing guild tip command...'
        await ctx.response.send_message(msg)

        split_amount = False
        if split == "SPLIT":
            split_amount = True

        mute_tip = False
        mention_all = True
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/guildtip", int(time.time())))
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
        else:
            if getattr(getattr(self.bot.coin_list, coin_name), "enable_tip") != 1:
                msg = f'{ctx.author.mention}, **{coin_name}** tipping is disable.'
                await ctx.edit_original_message(content=msg)
                return
        # End token name check
        serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
        if serverinfo and serverinfo['tiponly'] and serverinfo['tiponly'] != "ALLCOIN" and coin_name not in serverinfo[
            'tiponly'].split(","):
            allowed_coins = serverinfo['tiponly']
            msg = f"{ctx.author.mention}, **{coin_name}** is not allowed here. Currently, allowed __{allowed_coins}__. "\
                f"You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`"
            await ctx.edit_original_message(content=msg)
            return

        if serverinfo and serverinfo['mute_tip'] == "YES":
            mute_tip = True
            mention_all = False

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
                    if m:
                        list_member_ids.append(m.id)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            if len(get_list_member_n_role) > 0:
                for each_r in get_list_member_n_role:
                    try:
                        # get list users in role
                        get_role = disnake.utils.get(ctx.guild.roles, id=int(each_r))
                        role_list_members = [member.id for member in ctx.guild.members if get_role in member.roles]
                        if len(role_list_members) > 0:
                            list_member_ids += role_list_members
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
            list_member_ids = list(set(list_member_ids))
            if len(list_member_ids) > 0:
                try:
                    await self.multiple_tip(ctx, amount, coin_name, list_member_ids, True, False, split_amount)
                except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                    pass
                except Exception:
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
                        num_user = num_user.replace("people", "").replace("person", "").replace("users", "").replace(
                            "user", "").replace("u", "")
                        try:
                            num_user = int(num_user)
                            if len(ctx.guild.members) <= 2:
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please use normal tip command. There are only few users.'
                                await ctx.edit_original_message(content=msg)
                                return
                            # Check if we really have that many user in the guild 20%
                            elif num_user >= len(ctx.guild.members):
                                try:
                                    msg = f"{ctx.author.mention}, you want to tip more than the number of people in this guild!? "\
                                        f"It can be done :). Wait a while.... I am doing it. (**counting..**)"
                                    await ctx.edit_original_message(content=msg)
                                except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                    # No need to tip if failed to message
                                    return
                                message_talker = await store.sql_get_messages(
                                    str(ctx.guild.id), str(ctx.channel.id), 0, len(ctx.guild.members)
                                )
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
                                        await self.multiple_tip_talker(
                                            ctx, amount, coin_name, getattr(self.bot.coin_list, coin_name),
                                            message_talker, True, mention_all, split_amount
                                        )
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                return
                            elif num_user > 0:
                                message_talker = await store.sql_get_messages(
                                    str(ctx.guild.id), str(ctx.channel.id), 0, num_user + 1
                                )
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
                                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, I could not find sufficient talkers up "\
                                            f"to **{num_user}**. I found only **{len(message_talker)}** and tip to those "\
                                            f"**{len(message_talker)}**."
                                        await ctx.channel.send(msg)
                                    except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                        # No need to tip if failed to message
                                        return
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    # tip all user who are in the list
                                    try:
                                        await self.multiple_tip_talker(
                                            ctx, amount, coin_name, getattr(self.bot.coin_list, coin_name),
                                            message_talker, True, mention_all, split_amount
                                        )
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                else:
                                    try:
                                        await self.multiple_tip_talker(
                                            ctx, amount, coin_name, getattr(self.bot.coin_list, coin_name),
                                            message_talker, True, mention_all, split_amount
                                        )
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                return
                            else:
                                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, what is this **{num_user}** number? "\
                                    f"Please give a number bigger than 0 :) "
                                await ctx.edit_original_message(content=msg)
                                return
                        except ValueError:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid param after **LAST**."
                            await ctx.edit_original_message(content=msg)
                        return
                    else:
                        time_string = split_arg[1].lower()
                        time_second = None
                        try:
                            time_string = time_string.replace("years", "y").replace("yrs", "y").replace("yr", "y").replace("year", "y")
                            time_string = time_string.replace("months", "mon").replace("month", "mon").replace("mons", "mon").replace("weeks", "w").replace("week", "w")
                            time_string = time_string.replace("day", "d").replace("days", "d").replace("hours", "h").replace("hour", "h").replace("hrs", "h").replace("hr", "h")
                            time_string = time_string.replace("minutes", "mn").replace("mns", "mn").replace("mins", "mn").replace("min", "mn")

                            mult = {'y': 12 * 30 * 24 * 60 * 60, 'mon': 30 * 24 * 60 * 60, 'w': 7 * 24 * 60 * 60,
                                    'd': 24 * 60 * 60, 'h': 60 * 60, 'mn': 60}
                            time_second = sum(
                                int(num) * mult.get(val, 1) for num, val in re.findall('(\d+)(\w+)', time_string))
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("tips " +str(traceback.format_exc()))
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid time given. Please use this example: `tip 10 WRKZ last 12mn`'
                            await ctx.edit_original_message(content=msg)
                            return
                        try:
                            time_given = int(time_second)
                        except ValueError:
                            await ctx.edit_original_message(
                                content=f'{EMOJI_RED_NO} {ctx.author.mention}, invalid time given check.'
                            )
                            return
                        if time_given:
                            if time_given < 5 * 60 or time_given > 30 * 24 * 60 * 60:
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please give try time inteval between 5mn to 30d.'
                                await ctx.edit_original_message(content=msg)
                            else:
                                message_talker = await store.sql_get_messages(
                                    str(ctx.guild.id), str(ctx.channel.id), time_given, None
                                )
                                if len(message_talker) == 0:
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is no active talker in such period.'
                                    await ctx.edit_original_message(content=msg)
                                else:
                                    try:
                                        await self.multiple_tip_talker(
                                            ctx, amount, coin_name,
                                            getattr(self.bot.coin_list, coin_name),
                                            message_talker, True, mention_all, split_amount
                                        )
                                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                        pass
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                            return
                else:
                    try:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you need at least one person to tip to.'
                        await ctx.edit_original_message(content=msg)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("tips " +str(traceback.format_exc()))
                    return
            else:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you need at least one person to tip to.'
                await ctx.edit_original_message(content=msg)

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.has_permissions(manage_channels=True)
    @commands.slash_command(
        dm_permission=False,
        usage='guildtip <amount> <token> @mention @mention..',
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option('args', '<@mention1> <@mention2> ... | <@role> ... ', OptionType.string, required=True),
            Option('split', 'split or each', OptionType.string, required=False, choices=[
                OptionChoice("SPLIT", "SPLIT"),
                OptionChoice("EACH", "EACH")
            ])
        ],
        description="Tip other people using your guild's balance."
    )
    async def guildtip(
        self,
        ctx,
        amount: str,
        token: str,
        args: str,
        split: str = "EACH"
    ):
        try:
            await self.async_gtip(ctx, amount, token.strip(), args.strip(), split)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @guildtip.autocomplete("token")
    async def guildtip_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        dm_permission=False,
        usage='z <amount coin1, amount coin2> <@mention @mention @role>',
        options=[
            Option('amount_coin_list_to', 'amount_coin_list_to', OptionType.string, required=True)
        ],
        description="Tip various amount and coins to users"
    )
    async def z(
        self,
        ctx,
        amount_coin_list_to: str
    ):
        try:
            await self.async_ztip(ctx, amount_coin_list_to)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def async_ztip(self, ctx, amount_list_to):
        mute_tip = False
        has_amount_error = False
        error_msg = None
        try:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing z tip command...'
            await ctx.response.send_message(msg)
            try:
                self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                             str(ctx.author.id), SERVER_BOT, "/z", int(time.time())))
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

            list_member_ids = []
            if "@everyone" in amount_list_to.lower() or "@here" in amount_list_to.lower():
                list_member_ids = [str(member.id) for member in ctx.guild.members if member.id != ctx.author.id]
            else:
                get_list_member_n_role = re.findall(r"([0-9]{15,20})", amount_list_to)
                if len(get_list_member_n_role) > 0:
                    get_list_member_n_role = [each.replace(">", "").replace("<", "") for each in get_list_member_n_role]
                    # There is member or role to check
                    # Check member
                    for each_m in get_list_member_n_role:
                        try:
                            m = self.bot.get_user(int(each_m))
                            list_member_ids.append(str(m.id))
                        except Exception:
                            pass
                    if len(get_list_member_n_role) > 0:
                        for each_r in get_list_member_n_role:
                            try:
                                # get list users in role
                                get_role = disnake.utils.get(ctx.guild.roles, id=int(each_r))
                                role_list_members = [
                                    str(member.id) for member in ctx.guild.members if get_role in member.roles
                                ]
                                if len(role_list_members) > 0:
                                    list_member_ids += role_list_members
                            except Exception:
                                pass
                    list_member_ids = list(set(list_member_ids))

            if len(list_member_ids) == 0 and amount_list_to.lower().endswith(('all online', 'online')):
                list_member_ids = [
                    str(member.id) for member in ctx.guild.members if member.id != ctx.author.id \
                        and member.status != disnake.Status.offline
                ]
            elif len(list_member_ids) == 0 and amount_list_to.lower().endswith(('all offline', 'offline')):
                list_member_ids = [
                    str(member.id) for member in ctx.guild.members if member.id != ctx.author.id and \
                        member.status == disnake.Status.offline
                ]

            if str(ctx.author.id) in list_member_ids:
                list_member_ids.remove(str(ctx.author.id))

            if len(list_member_ids) == 0:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, there is no one to tip to.")
                return

            list_amount_and_tokens = {}
            list_coin_decimal = {}
            list_contract = {}
            list_amount_in_usd = {}
            list_equivalent_usd = {}
            list_tokens = []

            sum_in_usd = 0.0
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
            amount_token = amount_list_to.split(",")

            try:
                if serverinfo and serverinfo['mute_tip'] == "YES":
                    mute_tip = True
            except Exception:
                traceback.print_exc(file=sys.stdout)

            for each_token in amount_token:
                if len(each_token) > 0:
                    split_amount_token = each_token.split()
                    if len(split_amount_token) >= 2:
                        amount = split_amount_token[0]
                        coin_name = split_amount_token[1].upper()
                        if hasattr(self.bot.coin_list, coin_name):
                            if getattr(getattr(self.bot.coin_list, coin_name), "enable_tip") != 1:
                                error_msg = f'**{coin_name}** tipping is disable.'
                                has_amount_error = True
                                break
                            try:
                                if serverinfo and serverinfo['tiponly'] and serverinfo[
                                    'tiponly'] != "ALLCOIN" and coin_name not in serverinfo['tiponly'].split(","):
                                    allowed_coins = serverinfo['tiponly']
                                    error_msg = f"**{coin_name}** is not allowed here. Currently, allowed __{allowed_coins}__. "\
                                        f"You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`"
                                    has_amount_error = True
                                    break
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name),
                                                            "deposit_confirm_depth")
                            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                            min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
                            max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")

                            # token_info = getattr(self.bot.coin_list, coin_name)
                            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                            list_coin_decimal[coin_name] = coin_decimal
                            list_contract[coin_name] = contract
                            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
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
                                price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                                if price_with is None:
                                    error_msg = f"dollar conversion is not enabled for __{coin_name}__."
                                    has_amount_error = True
                                    break
                                else:
                                    per_unit = await self.utils.get_coin_price(coin_name, price_with)
                                    if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                        per_unit = per_unit['price']
                                        amount = float(Decimal(amount) / Decimal(per_unit))
                                    else:
                                        error_msg = f"I cannot fetch equivalent price for __{coin_name}__. Try with different method."
                                        has_amount_error = True
                                        break
                            else:
                                amount_original = amount
                                amount = amount.replace(",", "")
                                amount = text_to_num(amount)
                                if amount is None:
                                    error_msg = f'invalid given amount __{amount_original}__.'
                                    has_amount_error = True
                                    break
                            try:
                                amount = float(amount)
                                if coin_name in list_tokens:
                                    error_msg = f'can not have two __{coin_name}__.'
                                    has_amount_error = True
                                    break
                                else:
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
                                    userdata_balance = await store.sql_user_balance_single(
                                        str(ctx.author.id), coin_name, wallet_address,
                                        type_coin, height, deposit_confirm_depth, SERVER_BOT
                                    )
                                    actual_balance = float(userdata_balance['adjust'])
                                    # Check min. max.
                                    if amount <= 0 or actual_balance <= 0:
                                        error_msg = f'please get more {token_display}.'
                                        has_amount_error = True
                                        break

                                    if amount < min_tip or amount > max_tip:
                                        error_msg = f"tipping for {coin_name} cannot be smaller than "\
                                            f"**{num_format_coin(min_tip)} {token_display}** "\
                                            f"or bigger than **{num_format_coin(max_tip)} {token_display}**."
                                        has_amount_error = True
                                        break
                                    elif amount * len(list_member_ids) > actual_balance:
                                        error_msg = f"insufficient balance to tip "\
                                            f"**{num_format_coin(amount * len(list_member_ids))} "\
                                            f"{token_display}**. Having {num_format_coin(actual_balance)} "\
                                            f"{token_display}."
                                        has_amount_error = True
                                        break
                                    else:
                                        list_equivalent_usd[coin_name] = ""
                                        list_amount_in_usd[coin_name] = 0.0
                                        price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                                        if price_with:
                                            per_unit = await self.utils.get_coin_price(coin_name, price_with)
                                            if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                                per_unit = per_unit['price']
                                                amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                                                if amount_in_usd > 0.0001:
                                                    list_equivalent_usd[coin_name] = " ~ {:,.4f} USD".format(
                                                        amount_in_usd)
                                                    list_amount_in_usd[coin_name] = amount_in_usd
                                                    sum_in_usd += amount_in_usd

                                        list_tokens.append(coin_name)
                                        list_amount_and_tokens[coin_name] = amount
                            except ValueError:
                                error_msg = f'invalid amount __{split_amount_token}__.'
                                has_amount_error = True
                                break
                            # end of check if amount is all

            if has_amount_error is True:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, {error_msg}")
                return
            else:
                if len(list_amount_and_tokens) == 0:
                    await ctx.edit_original_message(content=f"{ctx.author.mention}, invalid amount or token.")
                    return

                default_max_tip = 400
                max_allowed = default_max_tip # default
                serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
                if serverinfo and serverinfo['max_tip_users']:
                    max_allowed = serverinfo['max_tip_users']
                if len(list_member_ids) > default_max_tip:
                    await logchanbot(
                        f"⚠️ {ctx.guild.id} / {ctx.guild.name} reaches number of receivers: __{str(len(list_member_ids))}__ "\
                        f"issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}."
                    )
                try:
                    if len(list_member_ids) > max_allowed:
                        msg = f"{ctx.author.mention}, there are more than maximum allowed __{str(max_allowed)}__. "\
                            f"You can request pluton#8888 to increase this for your guild."
                        await ctx.edit_original_message(content=msg)
                        await logchanbot(
                            f"🔴 {ctx.guild.id} / {ctx.guild.name} reaches number of receivers: __{str(len(list_member_ids))}__ "\
                            f"issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}."
                        )
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)

                passed_tips = []
                each_tips = []
                notifying_list = await store.sql_get_tipnotify()
                try:
                    tip_type = "TIP"
                    if len(list_member_ids) > 1:
                        tip_type = "TIPS"

                    if str(ctx.author.id) not in self.bot.tipping_in_progress:
                        self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())

                    for k, v in list_amount_and_tokens.items():
                        try:
                            tips = await store.sql_user_balance_mv_multiple(
                                str(ctx.author.id), list_member_ids, str(ctx.guild.id), str(ctx.channel.id), v,
                                k, tip_type, list_coin_decimal[k], SERVER_BOT, list_contract[k],
                                float(list_amount_in_usd[k]), None)
                            coin_emoji = ""
                            try:
                                if ctx.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is True:
                                    coin_emoji = getattr(getattr(self.bot.coin_list, k), "coin_emoji_discord")
                                    coin_emoji = coin_emoji + " " if coin_emoji else ""
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            passed_tips.append("{}{} {}".format(
                                coin_emoji, num_format_coin(v * len(list_member_ids)), k
                            ))
                            each_tips.append("{}{} {}".format(coin_emoji, num_format_coin(v), k))
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("tips " +str(traceback.format_exc()))
                try:
                    del self.bot.tipping_in_progress[str(ctx.author.id)]
                except Exception:
                    pass
                if len(passed_tips) > 0:
                    list_mentions = []
                    # tipper shall always get DM. Ignore notifying list
                    joined_tip_list = " / ".join(passed_tips)
                    each_tips_list = " / ".join(each_tips)
                    sum_in_usd_text = ""
                    if sum_in_usd > 0:
                        sum_in_usd_text = " ~ {:,.4f} USD".format(sum_in_usd)
                    try:
                        if len(list_member_ids) > 20:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} tip of **{joined_tip_list}** was sent to ({str(len(list_member_ids))}) "\
                                f"members in server __{ctx.guild.name}__.\nEach member got: **{each_tips_list}{sum_in_usd_text}**"
                        elif len(list_member_ids) >= 1:
                            incl_msg = []
                            incl_msg_str = ""
                            for each_m in list_member_ids:
                                try:
                                    each_user = self.bot.get_user(int(each_m))
                                except Exception:
                                    continue
                                if mute_tip is False and ctx.author.id != int(each_m) and each_m not in notifying_list:
                                    incl_msg.append(each_user.mention)
                                    list_mentions.append(each_user)
                                elif mute_tip is True and ctx.author.id != int(each_m) and each_m not in notifying_list:
                                    incl_msg.append(each_user.mention)
                                if ctx.author.id != int(each_m) and each_m in notifying_list:
                                    incl_msg.append("{}#{}".format(each_user.name, each_user.discriminator))
                            if len(incl_msg) > 0: incl_msg_str = ", ".join(incl_msg)
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} tip of **{joined_tip_list}** was sent to {incl_msg_str} "\
                                f"in server __{ctx.guild.name}__."
                            if len(list_member_ids) > 1:
                                msg += f"\nEach member got: **{each_tips_list}{sum_in_usd_text}**\n"
                        try:
                            await ctx.author.send(msg)
                        except Exception:
                            pass
                        try:
                            await ctx.edit_original_message(content=msg)
                        except Exception:
                            pass
                    except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                        pass
                    if 20 >= len(list_mentions) >= 1:
                        extra_msg = NOTIFICATION_OFF_CMD
                        if mute_tip is True:
                            extra_msg = "*Guild owner mutes all mention.*"
                        tip_text = "a tip"
                        if len(each_tips) > 1:
                            tip_text = "tips"
                        for member in list_mentions:
                            # print(member.name) # you'll just print out Member objects your way.
                            if ctx.author.id != member.id and member.id != self.bot.user.id and member.bot == False \
                                and str(member.id) not in notifying_list:
                                try:
                                    msg = f"{EMOJI_MONEYFACE}, you got {tip_text} of **{each_tips_list}{sum_in_usd_text}** "\
                                        f"from {ctx.author.name}#{ctx.author.discriminator} in server "\
                                        f"__{ctx.guild.name}__\n{extra_msg}"
                                    await member.send(msg)
                                except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                    pass
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(
                f"{EMOJI_INFORMATION} {ctx.author.mention}, failed to execute /z tip message...",
                ephemeral=True
            )

    # Multiple tip
    async def multiple_tip(self, ctx, amount, coin: str, listMembers, if_guild: bool = False, ping: bool = True, split_amount: bool = False):
        coin_name = coin.upper()
        guild_name = '**{}**'.format(ctx.guild.name) if if_guild else ''
        tip_type_text = 'guild tip' if if_guild else 'tip'
        guild_or_tip = 'GUILDTIP' if if_guild else 'TIPS'
        id_tipper = str(ctx.guild.id) if if_guild else str(ctx.author.id)
        mute_tip = False

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
        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")

        min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
        max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")

        get_deposit = await self.wallet_api.sql_get_userwallet(
            str(id_tipper), coin_name, net_name, type_coin, SERVER_BOT, 0
        )
        if get_deposit is None:
            get_deposit = await self.wallet_api.sql_register_user(
                str(id_tipper), coin_name, net_name, type_coin,
                SERVER_BOT, 0, 1 if if_guild else 0
            )

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']
        elif type_coin in ["XRP"]:
            wallet_address = get_deposit['destination_tag']

        height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        userdata_balance = await store.sql_user_balance_single(
            id_tipper, coin_name, wallet_address, type_coin, height,
            deposit_confirm_depth, SERVER_BOT
        )
        actual_balance = float(userdata_balance['adjust'])
        # Check if tx in progress
        if id_tipper in self.bot.tipping_in_progress and \
            int(time.time()) - self.bot.tipping_in_progress[id_tipper] < 150:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, there is another transaction in progress."
            await ctx.edit_original_message(content=msg)
            return

        # check if amount is all
        all_amount = False
        if not amount.isdigit() and amount.upper() == "ALL":
            all_amount = True
            userdata_balance = await store.sql_user_balance_single(
                id_tipper, coin_name, wallet_address, type_coin,
                height, deposit_confirm_depth, SERVER_BOT
            )
            amount = float(userdata_balance['adjust'])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]:  # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
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
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                await ctx.edit_original_message(content=msg)
                return
        # end of check if amount is all

        if amount <= 0 or actual_balance <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
            await ctx.edit_original_message(content=msg)
            return

        if amount < min_tip or amount > max_tip:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, transactions cannot be smaller than "\
                f"**{num_format_coin(min_tip)} {token_display}** "\
                f"or bigger than **{num_format_coin(max_tip)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to send {tip_type_text} of "\
                f"**{num_format_coin(amount)} {token_display}**."
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

        if len(memids) == 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, no users...'
            await ctx.edit_original_message(content=msg)
            return

        total_amount = amount * len(memids)
        if split_amount is True:
            amount = amount / len(memids)
            total_amount = amount * len(memids)

        if total_amount > max_tip:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, total transaction cannot be bigger than "\
                f"**{num_format_coin(max_tip)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return
        elif actual_balance < total_amount:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, not sufficient balance.'
            await ctx.edit_original_message(content=msg)
            return

        tipAmount = num_format_coin(total_amount)
        amountDiv_str = num_format_coin(amount)
        equivalent_usd = ""
        total_equivalent_usd = ""
        amount_in_usd = 0.0
        total_amount_in_usd = 0.0
        per_unit = None
        price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
        if price_with:
            per_unit = await self.utils.get_coin_price(coin_name, price_with)
            if per_unit and per_unit['price'] and per_unit['price'] > 0:
                per_unit = per_unit['price']
                amount_in_usd = float(Decimal(amount) * Decimal(per_unit))
                if amount_in_usd > 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
                total_amount_in_usd = float(Decimal(per_unit) * Decimal(total_amount))
                if total_amount_in_usd > 0.0001:
                    total_equivalent_usd = " ~ {:,.4f} USD".format(total_amount_in_usd)

        try:
            default_max_tip = 400
            max_allowed = default_max_tip # default
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
            if serverinfo and serverinfo['max_tip_users']:
                max_allowed = serverinfo['max_tip_users']
            if len(memids) > default_max_tip:
                await logchanbot(
                    f"⚠️ {ctx.guild.id} / {ctx.guild.name} reaches number of receivers: __{str(len(memids))}__ "\
                    f"issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}."
                )
            if serverinfo and serverinfo['mute_tip'] == "YES":
                mute_tip = True
            if len(memids) > max_allowed:
                msg = f"{ctx.author.mention}, there are more than maximum allowed __{str(max_allowed)}__. "\
                    f"You can request pluton#8888 to increase this for your guild."
                await ctx.edit_original_message(content=msg)
                await logchanbot(
                    f"🔴 {ctx.guild.id} / {ctx.guild.name} reaches number of receivers: __{str(len(memids))}__ "\
                    f"issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}."
                    )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)

        notifying_list = await store.sql_get_tipnotify()
        try:
            tip_type = "TIP"
            if len(memids) > 1:
                tip_type = "TIPS"

            if id_tipper not in self.bot.tipping_in_progress:
                self.bot.tipping_in_progress[id_tipper] = int(time.time())
            tips = await store.sql_user_balance_mv_multiple(
                id_tipper, memids, str(ctx.guild.id), str(ctx.channel.id),
                amount, coin_name, tip_type, coin_decimal, SERVER_BOT,
                contract, float(amount_in_usd),
                "By {}#{} / {}".format(ctx.author.name,  ctx.author.discriminator, ctx.author.id) if if_guild else None
            )  # if_guild, put extra message as who execute command
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("tips " +str(traceback.format_exc()))

        try:
            del self.bot.tipping_in_progress[id_tipper]
        except Exception:
            pass

        if tips:
            # tipper shall always get DM. Ignore notifying list
            try:
                if len(memids) > 20:
                    msg = f"{EMOJI_ARROW_RIGHTHOOK} {tip_type_text} of {coin_emoji}**{tipAmount} {token_display}** {total_equivalent_usd} "\
                        f"was sent to ({len(memids)}) members in server __{ctx.guild.name}__.\nEach member got: "\
                        f"{coin_emoji}**{amountDiv_str} {token_display}** {equivalent_usd}\n"
                elif len(memids) >= 1:
                    incl_msg = []
                    incl_msg_str = ""
                    for each_m in list_mentions:
                        if mute_tip is True:
                            incl_msg.append("{}#{}".format(each_m.name, each_m.discriminator))
                        elif ping is True and ctx.author.id != member.id and str(member.id) not in notifying_list:
                            incl_msg.append(each_m.mention)
                        else:
                            incl_msg.append("{}#{}".format(each_m.name, each_m.discriminator))
                    if len(incl_msg) > 0: incl_msg_str = ", ".join(incl_msg)
                    msg = f"{EMOJI_ARROW_RIGHTHOOK} {tip_type_text} of {coin_emoji}**{tipAmount} {token_display}** "\
                        f"{total_equivalent_usd} was sent to {incl_msg_str} in server __{ctx.guild.name}__."
                    if len(memids) > 1:
                        msg += f'\nEach member got: {coin_emoji}**{amountDiv_str} {token_display}** {equivalent_usd}\n'
                try:
                    await ctx.author.send(msg)
                except Exception:
                    pass
                try:
                    await ctx.edit_original_message(content=msg)
                except Exception:
                    pass
            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                pass
            if 20 >= len(list_mentions) >= 1 and ping is True and mute_tip is False:
                extra_msg = NOTIFICATION_OFF_CMD
                if mute_tip is True:
                    extra_msg = "*Guild owner mutes all mention.*"
                for member in list_mentions:
                    # print(member.name) # you'll just print out Member objects your way.
                    if ping is True and ctx.author.id != member.id and member.id != self.bot.user.id and \
                        member.bot == False and str(member.id) not in notifying_list:
                        try:
                            msg = f"{EMOJI_MONEYFACE}, you got a {tip_type_text} of {coin_emoji}**{amountDiv_str} {token_display}** "\
                                f"{equivalent_usd} from {ctx.author.name}#{ctx.author.discriminator} in server "\
                                f"__{ctx.guild.name}__\n{extra_msg}"
                            await member.send(msg)
                        except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                            pass

    # Multiple tip
    async def multiple_tip_talker(
        self, ctx, amount: str, coin: str, coin_dict, list_talker, if_guild: bool = False, ping: bool = True, split_amount: bool = False
    ):
        guild_or_tip = 'GUILDTIP' if if_guild else 'TIPS'
        guild_name = '**{}**'.format(ctx.guild.name) if if_guild else ''
        tip_type_text = 'guild tip' if if_guild else 'tip'
        id_tipper = str(ctx.guild.id) if if_guild else str(ctx.author.id)
        coin_name = coin.upper()

        coin_emoji = ""
        try:
            if ctx.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is True:
                coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                coin_emoji = coin_emoji + " " if coin_emoji else ""
        except Exception:
            traceback.print_exc(file=sys.stdout)
        net_name = coin_dict['net_name']
        type_coin = coin_dict['type']
        deposit_confirm_depth = coin_dict['deposit_confirm_depth']
        coin_decimal = coin_dict['decimal']
        contract = coin_dict['contract']
        token_display = coin_dict['display_name']

        min_tip = float(coin_dict['real_min_tip'])
        max_tip = float(coin_dict['real_max_tip'])

        get_deposit = await self.wallet_api.sql_get_userwallet(
            id_tipper, coin_name, net_name, type_coin, SERVER_BOT, 0
        )
        if get_deposit is None:
            get_deposit = await self.wallet_api.sql_register_user(
                id_tipper, coin_name, net_name, type_coin, SERVER_BOT, 0, 1 if if_guild else 0
            )

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']
        elif type_coin in ["XRP"]:
            wallet_address = get_deposit['destination_tag']

        # Check if tx in progress
        if id_tipper in self.bot.tipping_in_progress and \
            int(time.time()) - self.bot.tipping_in_progress[id_tipper] < 150:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, there is another transaction in progress."
            await ctx.edit_original_message(content=msg)
            return

        height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        # check if amount is all
        all_amount = False
        if not amount.isdigit() and amount.upper() == "ALL":
            all_amount = True
            userdata_balance = await store.sql_user_balance_single(
                id_tipper, coin_name, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT
            )
            amount = float(userdata_balance['adjust'])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]:  # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
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

        list_receivers = []
        for member_id in list_talker:
            try:
                member = self.bot.get_user(int(member_id))
                if member and member in ctx.guild.members and ctx.author.id != member.id:
                    user_to = await self.wallet_api.sql_get_userwallet(
                        str(member_id), coin_name, net_name, type_coin, SERVER_BOT, 0
                    )
                    if user_to is None:
                        user_to = await self.wallet_api.sql_register_user(
                            str(member_id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                        )
                    try:
                        list_receivers.append(str(member_id))
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("tips " +str(traceback.format_exc()))
                        print('Failed creating wallet for tip talk for userid: {}'.format(member_id))
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("tips " +str(traceback.format_exc()))
    
        if len(list_receivers) == 0:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, no users or can not find any user to tip..."
            await ctx.edit_original_message(content=msg)
            return

        if split_amount is True:
            amount = float(truncate(amount / len(list_receivers), 12))

        notifying_list = await store.sql_get_tipnotify()
        userdata_balance = await store.sql_user_balance_single(
            id_tipper, coin_name, wallet_address, type_coin, height,
            deposit_confirm_depth, SERVER_BOT
        )
        actual_balance = float(userdata_balance['adjust'])

        if amount <= 0 or actual_balance <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
            await ctx.edit_original_message(content=msg)
            return

        if amount > max_tip or amount < min_tip:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, transaction cannot be bigger than "\
                f"**{num_format_coin(max_tip)} {token_display}** "\
                f"or smaller than **{num_format_coin(min_tip)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to send "\
                f"{tip_type_text} of **{num_format_coin(amount)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return
        try:
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
            default_max_tip = 400
            max_allowed = default_max_tip # default
            if serverinfo and serverinfo['max_tip_users']:
                max_allowed = serverinfo['max_tip_users']
            if len(list_receivers) > default_max_tip:
                await logchanbot(
                    f"⚠️ {ctx.guild.id} / {ctx.guild.name} reaches number of receivers: __{str(len(list_receivers))}__ "\
                    f"issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}."
                )
            if len(list_receivers) > max_allowed:
                msg = f"{ctx.author.mention}, there are more than maximum allowed __{str(max_allowed)}__. "\
                    f"You can request pluton#8888 to increase this for your guild."
                await ctx.edit_original_message(content=msg)
                await logchanbot(
                    f"🔴 {ctx.guild.id} / {ctx.guild.name} reaches number of receivers: __{str(len(list_receivers))}__ "\
                    f"issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}."
                )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)

        total_amount = amount * len(list_receivers)

        if total_amount > max_tip:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, total transaction cannot be bigger than "\
                f"**{num_format_coin(max_tip)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return
        elif amount < min_tip:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, total transaction cannot be smaller than "\
                f"**{num_format_coin(min_tip)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return
        elif total_amount > actual_balance:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention} {guild_name}, insufficient balance to send total "\
                f"{tip_type_text} of **{num_format_coin(total_amount)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return

        if len(list_receivers) < 1:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, there is no active talker in such period. "\
                f"Please increase more duration or tip directly!"
            await ctx.edit_original_message(content=msg)
            return

        # add queue also tip
        if id_tipper not in self.bot.tipping_in_progress:
            self.bot.tipping_in_progress[id_tipper] = int(time.time())
        else:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, there is another transaction in progress."
            await ctx.edit_original_message(content=msg)
            return

        tip = None
        equivalent_usd = ""
        total_equivalent_usd = ""
        amount_in_usd = 0.0
        total_amount_in_usd = 0.0

        per_unit = None
        price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
        if price_with:
            per_unit = await self.utils.get_coin_price(coin_name, price_with)
            if per_unit and per_unit['price'] and per_unit['price'] > 0:
                per_unit = per_unit['price']
                amount_in_usd = float(Decimal(amount) * Decimal(per_unit))
                if amount_in_usd > 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
                total_amount_in_usd = float(Decimal(per_unit) * Decimal(total_amount))
                if total_amount_in_usd > 0.0001:
                    total_equivalent_usd = " ~ {:,.4f} USD".format(total_amount_in_usd)
        try:
            if id_tipper not in self.bot.tipping_in_progress:
                self.bot.tipping_in_progress[id_tipper] = int(time.time())
            tiptalk = await store.sql_user_balance_mv_multiple(
                id_tipper, list_receivers, str(ctx.guild.id), str(ctx.channel.id), amount, coin_name, "TIPTALK",
                coin_decimal, SERVER_BOT, contract, float(amount_in_usd),
                "By {}#{} / {}".format(ctx.author.name, ctx.author.discriminator, 
                ctx.author.id) if if_guild else None
            )  # if_guild, put extra message as who execute command
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("tips " +str(traceback.format_exc()))

        # remove queue from tip
        try:
            del self.bot.tipping_in_progress[id_tipper]
        except Exception:
            pass

        if tiptalk:
            # tipper shall always get DM. Ignore notifying list
            try:
                msg = f"{EMOJI_ARROW_RIGHTHOOK} {tip_type_text} of {coin_emoji}**{num_format_coin(total_amount)}"\
                    f" {token_display}** {total_equivalent_usd} was sent to ({len(list_receivers)}) members in "\
                    f"server __{ctx.guild.name}__ for active talking.\nEach member got: "\
                    f"{coin_emoji}**{num_format_coin(amount)} {token_display}** {equivalent_usd}\n"
                try:
                    await ctx.author.send(msg)
                except Exception:
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
            list_user_not_mention = []
            random.shuffle(list_receivers)

            extra_msg = NOTIFICATION_OFF_CMD
            if ping is False:
                extra_msg = "*PING is disable within command or mention is disable by Guild.*"

            for member_id in list_receivers:
                member = self.bot.get_user(int(member_id))
                if not member:
                    continue

                if send_tipped_ping >= self.bot.config['discord']['maxTipTalkMessage']:
                    total_found += 1
                else:
                    if ctx.author.id != member.id and member.id != self.bot.user.id:
                        if ping is True and str(member.id) not in notifying_list:
                            list_user_mention.append("{}".format(member.mention))
                        else:
                            list_user_not_mention.append("{}#{}".format(member.name, member.discriminator))
                    total_found += 1
                    numb_mention += 1

                    # Check if a batch meets
                    if numb_mention > 0 and numb_mention % max_mention == 0:
                        # send the batch
                        mention_users = ""
                        if len(list_user_mention) >= 1:
                            mention_users = ", ".join(list_user_mention)
                        if len(list_user_not_mention) >= 1:
                            mention_users += ", " + ", ".join(list_user_not_mention)
                        try:
                            if len(mention_users) > 0:
                                msg = f"{EMOJI_MONEYFACE} {mention_users}, "\
                                    f"you got a {tip_type_text} of {coin_emoji}**{num_format_coin(amount)}"\
                                    f" {token_display}** {equivalent_usd} from {ctx.author.name}#{ctx.author.discriminator}"\
                                    f"\n{extra_msg}"
                                await ctx.followup.send(msg)
                                send_tipped_ping += 1
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("tips " +str(traceback.format_exc()))
                        # reset
                        list_user_mention = []
                        list_user_not_mention = []
            # if there is still here
            if len(list_user_mention) + len(list_user_not_mention) >= 1:
                mention_users = ""
                if len(list_user_mention) >= 1:
                    mention_users = ", ".join(list_user_mention)
                if len(list_user_not_mention) >= 1:
                    mention_users += ", " + ", ".join(list_user_not_mention)
                try:
                    remaining_str = ""
                    if numb_mention < total_found:
                        remaining_str = " and other {} members".format(total_found - numb_mention)
                    msg = f"{EMOJI_MONEYFACE} {mention_users}{remaining_str}, "\
                        f"you got a {tip_type_text} of {coin_emoji}**{num_format_coin(amount)} {token_display}** "\
                        f"{equivalent_usd} from {ctx.author.name}#{ctx.author.discriminator}\n{extra_msg}"
                    await ctx.followup.send(msg)
                except Exception:
                    traceback.print_exc(file=sys.stdout)

    # Message command
    @commands.guild_only()
    @commands.command(
        name="tip",
        usage="tip <amount> <token> <user(s)/role(s)",
        description="Tip users"
    )
    async def cmd_message_tip(self, ctx, amount: str, ticker: str, *, users):
        try:
            coin_name = ticker.upper()
            mute_tip = False
            if not hasattr(self.bot.coin_list, coin_name):
                msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
                await ctx.reply(content=msg)
                return

            async with ctx.typing():
                serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
                if serverinfo and serverinfo['tiponly'] and serverinfo['tiponly'] != "ALLCOIN" and coin_name not in serverinfo[
                    'tiponly'].split(","):
                    allowed_coins = serverinfo['tiponly']
                    msg = f"{ctx.author.mention}, **{coin_name}** is not allowed here. Currently, allowed __{allowed_coins}__. "\
                        f"You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`"
                    await ctx.reply(content=msg)
                    return
                extra_msg = NOTIFICATION_OFF_CMD
                if serverinfo and serverinfo['mute_tip'] == "YES":
                    mute_tip = True
                    extra_msg = "*Guild owner mutes all mention.*"

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
                contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")

                min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
                max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")

                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
                )
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(ctx.author.id), coin_name, net_name, type_coin,
                        SERVER_BOT, 0, 0
                    )

                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                elif type_coin in ["XRP"]:
                    wallet_address = get_deposit['destination_tag']

                height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                userdata_balance = await store.sql_user_balance_single(
                    str(ctx.author.id), coin_name, wallet_address, type_coin, height,
                    deposit_confirm_depth, SERVER_BOT
                )
                actual_balance = float(userdata_balance['adjust'])
                # Check if tx in progress
                if str(ctx.author.id) in self.bot.tipping_in_progress and \
                    int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 150:
                    msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
                    await ctx.edit_original_message(content=msg)
                    return

                # check if amount is all
                all_amount = False
                if not amount.isdigit() and amount.upper() == "ALL":
                    all_amount = True
                    userdata_balance = await store.sql_user_balance_single(
                        str(ctx.author.id), coin_name, wallet_address, type_coin,
                        height, deposit_confirm_depth, SERVER_BOT
                    )
                    amount = float(userdata_balance['adjust'])
                # If $ is in amount, let's convert to coin/token
                elif "$" in amount[-1] or "$" in amount[0]:  # last is $
                    # Check if conversion is allowed for this coin.
                    amount = amount.replace(",", "").replace("$", "")
                    price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                    if price_with is None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this __{coin_name}__."
                        await ctx.reply(msg)
                        return
                    else:
                        per_unit = await self.utils.get_coin_price(coin_name, price_with)
                        if per_unit and per_unit['price'] and per_unit['price'] > 0:
                            per_unit = per_unit['price']
                            amount = float(Decimal(amount) / Decimal(per_unit))
                        else:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method."
                            await ctx.edit_original_message(content=msg)
                            return
                else:
                    amount = amount.replace(",", "")
                    amount = text_to_num(amount)
                    if amount is None:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                        await ctx.reply(msg)
                        return
                # end of check if amount is all

                if amount <= 0 or actual_balance <= 0:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
                    await ctx.reply(msg)
                    return

                if amount < min_tip or amount > max_tip:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, transactions cannot be smaller than **"\
                        f"{num_format_coin(min_tip)} {token_display}** "\
                        f"or bigger than **{num_format_coin(max_tip)} {token_display}**."
                    await ctx.reply(msg)
                    return
                elif amount > actual_balance:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to send tip of "\
                        f"**{num_format_coin(amount)} {token_display}**."
                    await ctx.reply(msg)
                    return
                
                user_mentions = ctx.message.mentions
                role_mentions = ctx.message.role_mentions
                if self.bot.user in user_mentions:
                    user_mentions.remove(self.bot.user)
                if "@everyone" in role_mentions:
                    role_mentions.remove("@everyone")

                if len(user_mentions) == 0 and len(role_mentions) == 0:
                    await ctx.reply(f"{EMOJI_RED_NO} {ctx.author.mention}, there is no one to tip to.")
                    return

                list_users = []
                if len(role_mentions) >= 1:
                    for each_role in role_mentions:
                        role_list_members = [member for member in ctx.guild if member.bot == False and each_role in member.roles]
                        if len(role_list_members) >= 1:
                            for each_member in role_list_members:
                                if each_member not in list_users and each_member != ctx.author:
                                    list_users.append(each_member.id)
                if len(user_mentions) >= 1:
                    for each_member in user_mentions:
                        if each_member not in list_users and each_member != ctx.author:
                            list_users.append(each_member.id)
                
                list_users = list(set(list_users))
                if ctx.author in list_users:
                    list_users.remove(ctx.author)
                if len(list_users) == 0:
                    await ctx.reply(f"{EMOJI_RED_NO} {ctx.author.mention}, there is no one to tip to.")
                    return
                else:
                    default_max_tip = 400
                    max_allowed = default_max_tip # default
                    if serverinfo and serverinfo['max_tip_users']:
                        max_allowed = serverinfo['max_tip_users']
                    if len(list_users) > default_max_tip:
                        await logchanbot(
                            f"⚠️ {ctx.guild.id} / {ctx.guild.name} reaches number of receivers: __{str(len(list_users))}__ "\
                            f"issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}."
                        )
                    try:
                        if len(list_users) > max_allowed:
                            msg = f'{ctx.author.mention}, there are more than maximum allowed __{str(max_allowed)}__. "\
                                f"You can request pluton#8888 to increase this for your guild.'
                            await ctx.reply(msg)
                            await logchanbot(
                                f"🔴 {ctx.guild.id} / {ctx.guild.name} reaches number of receivers: __{str(len(list_users))}__ "\
                                f"issued by {ctx.author.id} / {ctx.author.name}#{ctx.author.discriminator}."
                            )
                            return
                    except Exception:
                        traceback.print_exc(file=sys.stdout)

                    list_receivers = []
                    for member_id in list_users:
                        try:
                            user_to = await self.wallet_api.sql_get_userwallet(
                                str(member_id), coin_name, net_name, type_coin, SERVER_BOT, 0
                            )
                            if user_to is None:
                                user_to = await self.wallet_api.sql_register_user(
                                    str(member_id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                                )
                            try:
                                list_receivers.append(str(member_id))
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                await logchanbot("tips " +str(traceback.format_exc()))
                                print('Failed creating wallet for tip talk for userid: {}'.format(member_id))
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("tips " +str(traceback.format_exc()))

                    total_amount = amount * len(list_receivers)

                    if total_amount > max_tip:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, total transaction cannot be bigger than "\
                            f"**{num_format_coin(max_tip)} {token_display}**."
                        await ctx.reply(msg)
                        return
                    elif amount < min_tip:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, total transaction cannot be smaller than "\
                            f"**{num_format_coin(min_tip)} {token_display}**."
                        await ctx.reply(msg)
                        return
                    elif total_amount > actual_balance:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to send total "\
                            f"tip of **{num_format_coin(total_amount)} {token_display}**."
                        await ctx.reply(msg)
                        return

                    # add queue also tip
                    if str(ctx.author.id) not in self.bot.tipping_in_progress:
                        self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())
                    else:
                        msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
                        await ctx.edit_original_message(content=msg)
                        return

                    tip = None

                    equivalent_usd = ""
                    total_equivalent_usd = ""
                    amount_in_usd = 0.0
                    total_amount_in_usd = 0.0

                    per_unit = None
                    price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                    if price_with:
                        per_unit = await self.utils.get_coin_price(coin_name, price_with)
                        if per_unit and per_unit['price'] and per_unit['price'] > 0:
                            per_unit = per_unit['price']
                            amount_in_usd = float(Decimal(amount) * Decimal(per_unit))
                            total_amount_in_usd = float(Decimal(per_unit) * Decimal(total_amount))
                            if total_amount_in_usd > 0.0001:
                                total_equivalent_usd = " ~ {:,.4f} USD".format(total_amount_in_usd)
                            if amount_in_usd >= 0.0001:
                                equivalent_usd = " ~ {:,.4f}$".format(amount_in_usd)
                    try:
                        if str(ctx.author.id) not in self.bot.tipping_in_progress:
                            self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())
                        tip = await store.sql_user_balance_mv_multiple(
                            str(ctx.author.id), list_receivers, str(ctx.guild.id), str(ctx.channel.id), amount, coin_name, "TIP",
                            coin_decimal, SERVER_BOT, contract, float(amount_in_usd), "Message Command"
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("tips " +str(traceback.format_exc()))

                    # remove queue from tip
                    try:
                        del self.bot.tipping_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                    if tip is not None:
                        # tipper shall always get DM. Ignore notifying_list
                        try:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} tip of {coin_emoji}**{num_format_coin(total_amount)}"\
                                f" {token_display}** {total_equivalent_usd} was sent to ({len(list_receivers)}) member(s) in "\
                                f"server __{ctx.guild.name}__.\nEach member got: "\
                                f"{coin_emoji}**{num_format_coin(amount)} {token_display}** {equivalent_usd}\n"
                            try:
                                await ctx.author.send(msg)
                            except Exception:
                                pass
                        except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                            pass
                        try:
                            await ctx.message.add_reaction(EMOJI_MONEYFACE)
                        except Exception:
                            pass

                        notifying_list = await store.sql_get_tipnotify()

                        if 0 < len(list_receivers) <= 40:
                            list_user_mention = []
                            list_user_not_mention = []
                            for member_id in list_receivers:
                                member = self.bot.get_user(int(member_id))
                                if not member:
                                    continue
                                if str(member.id) not in notifying_list:
                                    list_user_mention.append("{}".format(member.mention))
                                else:
                                    list_user_not_mention.append("{}#{}".format(member.name, member.discriminator))

                            mention_users = ""
                            if len(list_user_mention) >= 1:
                                mention_users = ", ".join(list_user_mention)
                            if len(list_user_not_mention) >= 1:
                                mention_users += ", " + ", ".join(list_user_not_mention)

                            try:
                                msg = f"{EMOJI_MONEYFACE} {mention_users}, "\
                                    f"you got a tip of {coin_emoji}**{num_format_coin(amount)}"\
                                    f" {token_display}** {equivalent_usd} from {ctx.author.name}#{ctx.author.discriminator}"\
                                    f"\n{extra_msg}"
                                await ctx.reply(msg)
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                await logchanbot("tips " +str(traceback.format_exc()))
                        else:
                            # Message mention all in public
                            total_found = 0
                            max_mention = 40
                            numb_mention = 0

                            # mention all user
                            send_tipped_ping = 0
                            list_user_mention = []
                            list_user_not_mention = []
                            random.shuffle(list_receivers)
                            for member_id in list_receivers:
                                member = self.bot.get_user(int(member_id))
                                if not member:
                                    continue

                                if send_tipped_ping >= self.bot.config['discord']['maxTipTalkMessage']:
                                    total_found += 1
                                else:
                                    if ctx.author.id != member.id and member.id != self.bot.user.id:
                                        if mute_tip is True:
                                            list_user_not_mention.append("{}#{}".format(member.name, member.discriminator))
                                        elif str(member.id) not in notifying_list:
                                            list_user_mention.append("{}".format(member.mention))
                                        else:
                                            list_user_not_mention.append("{}#{}".format(member.name, member.discriminator))
                                    total_found += 1
                                    numb_mention += 1

                                    # Check if a batch meets
                                    if numb_mention > 0 and numb_mention % max_mention == 0:
                                        # send the batch
                                        mention_users = ""
                                        if len(list_user_mention) >= 1:
                                            mention_users = ", ".join(list_user_mention)
                                        if len(list_user_not_mention) >= 1:
                                            mention_users += ", " + ", ".join(list_user_not_mention)
                                        try:
                                            if len(mention_users) > 0:
                                                msg = f"{EMOJI_MONEYFACE} {mention_users}, "\
                                                    f"you got a tip of {coin_emoji}**{num_format_coin(amount)}"\
                                                    f" {token_display}** {equivalent_usd} from {ctx.author.name}#{ctx.author.discriminator}"\
                                                    f"\n{extra_msg}"
                                                await ctx.reply(msg)
                                                send_tipped_ping += 1
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                            await logchanbot("tips " +str(traceback.format_exc()))
                                        # reset
                                        list_user_mention = []
                                        list_user_not_mention = []
                            # if there is still here
                            if len(list_user_mention) + len(list_user_not_mention) >= 1:
                                mention_users = ""
                                if len(list_user_mention) >= 1:
                                    mention_users = ", ".join(list_user_mention)
                                if len(list_user_not_mention) >= 1:
                                    mention_users += ", " + ", ".join(list_user_not_mention)
                                try:
                                    remaining_str = ""
                                    if numb_mention < total_found:
                                        remaining_str = " and other {} members".format(total_found - numb_mention)
                                    msg = f"{EMOJI_MONEYFACE} {mention_users}{remaining_str}, "\
                                        f"you got a tip of {coin_emoji}**{num_format_coin(amount)} {token_display}**"\
                                        f" {equivalent_usd} from {ctx.author.name}#{ctx.author.discriminator}\n{extra_msg}"
                                    await ctx.reply(msg)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    # End of Tip Normal
    @commands.Cog.listener()
    async def on_ready(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.freetip_check.is_running():
                self.freetip_check.start()

    async def cog_load(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.freetip_check.is_running():
                self.freetip_check.start()

    def cog_unload(self):
        # Ensure the task is stopped when the cog is unloaded.
        self.freetip_check.cancel()


def setup(bot):
    bot.add_cog(Tips(bot))
