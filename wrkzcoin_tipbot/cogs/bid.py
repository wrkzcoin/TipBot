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
import aiohttp
import hashlib
import magic
from io import BytesIO
import uuid
from typing import Optional

import disnake
import store
from Bot import logchanbot, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_INFORMATION, SERVER_BOT, text_to_num, \
    truncate, seconds_str_days, log_to_channel, RowButtonRowCloseAnyMessage
from cogs.wallet import WalletAPI
from disnake.app_commands import Option
from disnake.enums import ButtonStyle
from disnake.enums import OptionType
from disnake import TextInputStyle
from disnake.app_commands import Option, OptionChoice

from disnake.ext import commands, tasks
from cogs.utils import Utils, num_format_coin


class ConfirmName(disnake.ui.View):
    def __init__(self, bot, owner_id: int):
        super().__init__(timeout=10.0)
        self.value: Optional[bool] = None
        self.bot = bot
        self.owner_id = owner_id

    @disnake.ui.button(label="Yes, please!", emoji="✅", style=disnake.ButtonStyle.green)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, this is not your menu!", delete_after=5.0)
        else:
            self.value = True
            self.stop()
            await inter.response.defer()

    @disnake.ui.button(label="No", emoji="❌", style=disnake.ButtonStyle.grey)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, this is not your menu!", delete_after=5.0)
        else:
            self.value = False
            self.stop()
            await inter.response.defer()

class ReportBid(disnake.ui.Modal):
    def __init__(self, ctx, bot, message_id: str, owner_userid: str) -> None:
        self.ctx = ctx
        self.bot = bot
        self.utils = Utils(self.bot)
        self.message_id = message_id
        self.owner_userid = owner_userid

        components = [
            disnake.ui.TextInput(
                label="Report content",
                placeholder="Describe ...",
                custom_id="desc_id",
                style=TextInputStyle.paragraph
            ),
            disnake.ui.TextInput(
                label="Your contact",
                placeholder="How we contact your, like Discord ID/name? Better you join our Discord guild.",
                custom_id="contact_id",
                style=TextInputStyle.paragraph
            )
        ]
        super().__init__(title="Report bid ID: {}".format(self.message_id), custom_id="modal_bidding_report", components=components)

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        # Check if type of question is bool or multipe
        await interaction.response.send_message(content=f"{interaction.author.mention}, checking bidding report...", ephemeral=True)
        desc_id = interaction.text_values['desc_id'].strip()
        if desc_id == "":
            await interaction.edit_original_message(f"{interaction.author.mention}, report content can't be empty!")
            return

        contact_id = interaction.text_values['contact_id'].strip()
        if contact_id == "":
            await interaction.edit_original_message(f"{interaction.author.mention}, contact field can't be empty!")
            return

        try:
            adding_report = await self.utils.bid_add_report(
                str(interaction.author.id), "{}#{}".format(interaction.author.name, interaction.author.discriminator), 
                str(self.message_id), str(self.owner_userid), str(interaction.channel.id), str(interaction.guild.id), 
                str(interaction.guild.name), desc_id, contact_id
            )
            if adding_report is True:
                msg = f"{EMOJI_INFORMATION} {self.ctx.author.mention}, we received your report! "\
                    f"We suggest you to join in our Discord guild <http://chat.wrkz.work> as well for quick checking and reporting!"
                await interaction.edit_original_message(content=msg)
                await log_to_channel(
                    "bid",
                    f"[BID REPORT]: User {interaction.author.mention} submitted a report in Guild "\
                    f"{interaction.guild.name} / {interaction.guild.id} for bid id: {str(self.message_id)} owner <@{str(self.owner_userid)}>. Content:\n\n"\
                    f"{desc_id[:1000]}"\
                    "\n\n"\
                    f"How to contact: {contact_id[:200]}",
                    self.bot.config['discord']['general_report_webhook']
                )
            else:
                msg = f"{EMOJI_INFORMATION} {self.ctx.author.mention}, internal error!"
                await interaction.edit_original_message(content=msg)
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)

class EditBid(disnake.ui.Modal):
    def __init__(self, ctx, bot, message_id: str, owner_userid: str, title: str, desc: str=None) -> None:
        self.ctx = ctx
        self.bot = bot
        self.utils = Utils(self.bot)
        self.message_id = message_id
        self.owner_userid = owner_userid
        self.caption_new = title
        self.desc = desc

        components = [
            disnake.ui.TextInput(
                label="Description",
                placeholder="Describe ...",
                value=self.desc,
                custom_id="desc_id",
                style=TextInputStyle.paragraph
            )
        ]
        super().__init__(title="Edit description", custom_id="modal_bidding_description", components=components)

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        # Check if type of question is bool or multipe
        await interaction.response.send_message(content=f"{interaction.author.mention}, checking bidding description...", ephemeral=True)
        desc_id = interaction.text_values['desc_id'].strip()
        if desc_id == "":
            await interaction.edit_original_message(f"{interaction.author.mention}, description can't be empty!")
            return
        try:
            update_bid = await self.utils.bid_update_desc(
                str(self.message_id), str(interaction.author.id),
                desc_id, str(interaction.guild.id), str(interaction.channel.id)
            )
            if update_bid:
                msg = f"{EMOJI_INFORMATION} {self.ctx.author.mention}, successfully updating description!"
                await interaction.edit_original_message(content=msg)
                try:
                    get_message = await self.utils.get_bid_id(str(self.message_id))
                    _msg: disnake.Message = await interaction.channel.fetch_message(self.message_id)
                    embed = _msg.embeds[0] # embeds is list, we take 0
                    embed.title = "NEW BID | {}".format(self.caption_new)
                    embed.description = get_message['description'][:1024]
                    await _msg.edit(content=None, embed=embed)
                    await log_to_channel(
                        "bid",
                        f"[BID EDIT]: User {interaction.author.mention} edited a bid in Guild ID {interaction.guild.id}. "\
                        f"Ref: {self.message_id} / Guild name: {interaction.guild.name}!",
                        self.bot.config['discord']['bid_webhook']
                    )
                    if 'fetched_msg' not in self.bot.other_data:
                        self.bot.other_data['fetched_msg'] = {}
                    self.bot.other_data['fetched_msg'][str(self.message_id)] = int(time.time())
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                await interaction.delete_original_message()
                return
            else:
                msg = f"{EMOJI_INFORMATION} {self.ctx.author.mention}, internal error!"
                await interaction.edit_original_message(content=msg)
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)

class PlaceBid(disnake.ui.Modal):
    def __init__(
        self, ctx, bot, message_id: str, owner_userid: str,
        coin_name: str, min_amount: float, step_amount: float
    ) -> None:
        self.ctx = ctx
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.message_id = message_id
        self.owner_userid = owner_userid
        self.coin_name = coin_name
        self.min_amount = min_amount
        self.step_amount = step_amount

        components = [
            disnake.ui.TextInput(
                label="Amount",
                placeholder="10000",
                custom_id="amount_id",
                style=TextInputStyle.short,
                max_length=16
            ),
        ]
        super().__init__(title="Place your bid amount {}".format(self.coin_name), custom_id="modal_bidding_amount", components=components)

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        # Check if type of question is bool or multipe
        await interaction.response.send_message(content=f"{interaction.author.mention}, checking bidding amount...", ephemeral=True)
        # Check if he is at the top and ask for confirmation
        get_message = await self.utils.get_bid_id(str(self.message_id))
        attend_list = await self.utils.get_bid_attendant(str(self.message_id))
        previous_user_id = None
        # notify top previous bid that someone higher than him
        try:
            if self.bot.config['bidding']['enable_bid_pass_notify'] == 1:
                if len(attend_list) > 0:
                    previous_user_id = int(attend_list[0]['user_id'])
                    if previous_user_id == interaction.author.id:
                        # add for confirmation
                        view = ConfirmName(self.bot, interaction.author.id)
                        msg = f"{EMOJI_INFORMATION} {interaction.author.mention}, you are the top bidder for this bid ({get_message['title']}). Do you still want to place a higher bid?"
                        await interaction.edit_original_message(content=msg, view=view)
                        # Wait for the View to stop listening for input...
                        await view.wait()
                        # Check the value to determine which button was pressed, if any.
                        if view.value is False:
                            await interaction.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {interaction.author.mention}, you rejected to place another bid.", view=None
                            )
                            return
                        elif view.value is None:
                            await interaction.edit_original_message(
                                content=msg + "\n**Timeout!**",
                                view=None
                            )
                        elif view.value:
                            await interaction.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {interaction.author.mention}, processing with a new bid amount...",
                                view=None
                            )
        except Exception:
            traceback.print_exc(file=sys.stdout)

        amount = interaction.text_values['amount_id'].strip()
        if amount == "":
            await interaction.edit_original_message(f"{interaction.author.mention}, amount is empty!")
            return
        try:
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f'{EMOJI_RED_NO} {interaction.author.mention}, invalid given amount.'
                await interaction.edit_original_message(content=msg)
                return

            amount = float(amount)
            coin_name = self.coin_name.upper()
            if not hasattr(self.bot.coin_list, coin_name):
                msg = f'{interaction.author.mention}, **{coin_name}** does not exist with us.'
                await interaction.edit_original_message(content=msg)
                return
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")

            min_bid_start = getattr(getattr(self.bot.coin_list, coin_name), "min_bid_start")
            step_amount = self.step_amount
            if step_amount is None:
                step_amount = getattr(getattr(self.bot.coin_list, coin_name), "min_bid_lap")

            get_deposit = await self.wallet_api.sql_get_userwallet(
                str(interaction.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(
                    str(interaction.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                )

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

            current_max = 0.0
            get_max_bid = await self.utils.discord_bid_max_bid(str(self.message_id))
            if get_max_bid is not None:
                current_max = get_max_bid['bid_amount'] + step_amount
            current_max = max(self.min_amount, min_bid_start, current_max)

            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
            userdata_balance = await store.sql_user_balance_single(
                str(interaction.author.id), coin_name, wallet_address,
                type_coin, height, deposit_confirm_depth, SERVER_BOT
            )
            actual_balance = float(userdata_balance['adjust'])
            previous_bid = 0.0
            additional_bid_amount = amount
            key = str(self.message_id) + "_" + str(interaction.author.id)
            if amount <= 0:
                msg = f"{EMOJI_RED_NO} {interaction.author.mention}, please get more {token_display}."
                await interaction.edit_original_message(content=msg)
                return
            elif amount > actual_balance:
                # Check if he already placed a bit, then we just compare with remaining.
                try:
                    previous_bid = await self.utils.async_get_cache_kv(
                        "bidding_amount",
                        key
                    )
                    if previous_bid and previous_bid > 0:
                        additional_bid_amount = amount - previous_bid
                        if additional_bid_amount > actual_balance:
                            msg = f"{EMOJI_RED_NO} {self.ctx.author.mention}, insufficient balance to place a bid of "\
                                f"**{num_format_coin(amount)} {token_display}**."
                            await interaction.edit_original_message(content=msg)
                            return
                        elif additional_bid_amount < 0:
                            msg = f"{EMOJI_INFORMATION} {self.ctx.author.mention}, internal error with a new amount {num_format_coin(amount)} {coin_name}!"
                            await interaction.edit_original_message(content=msg)
                            return
                    elif previous_bid is None or previous_bid == 0:
                        msg = f"{EMOJI_RED_NO} {self.ctx.author.mention}, insufficient balance to place a bid of "\
                            f"**{num_format_coin(amount)} {token_display}**."
                        await interaction.edit_original_message(content=msg)
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    msg = f"{EMOJI_RED_NO} {self.ctx.author.mention}, internal error during checking bid and balance. Please report!"
                    await interaction.edit_original_message(content=msg)
                    return
            elif amount < current_max:
                msg = f"{EMOJI_RED_NO} {self.ctx.author.mention}, bid amount can't be smaller than "\
                    f"**{num_format_coin(current_max)} {token_display}**."
                await interaction.edit_original_message(content=msg)
                return
            try:
                current_closed_time = get_message['bid_open_time']
                is_extending = False
                num_extension = get_message['number_extension']
                if get_message['bid_extended_time'] is not None:
                    current_closed_time = get_message['bid_extended_time'] 
                
                if current_closed_time < int(time.time()):
                    msg = f"{EMOJI_INFORMATION} {self.ctx.author.mention}, that bidding is closed!"
                    await interaction.edit_original_message(content=msg)
                    return
                elif current_closed_time - 90 < int(time.time()):
                    current_closed_time += 120
                    is_extending = True
                    num_extension += 1

                # get his previous bid amount
                # Check if tx in progress
                if str(interaction.author.id) in self.bot.tipping_in_progress and \
                    int(time.time()) - self.bot.tipping_in_progress[str(interaction.author.id)] < 150:
                    msg = f"{EMOJI_ERROR} {interaction.author.mention}, you have another transaction in progress."
                    await interaction.edit_original_message(content=msg)
                    return
                else:
                    self.bot.tipping_in_progress[str(interaction.author.id)] = int(time.time())
                try:
                    previous_bid = await self.utils.async_get_cache_kv(
                        "bidding_amount",
                        key
                    )
                    if previous_bid and previous_bid > 0:
                        additional_bid_amount = amount - previous_bid
                    await self.utils.async_set_cache_kv(
                        "bidding_amount",
                        key,
                        amount
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)

                adding_bid = await self.utils.bid_new_join(
                    str(self.message_id), str(interaction.author.id), "{}#{}".format(interaction.author.name, interaction.author.discriminator),
                    amount, coin_name, str(interaction.guild.id), str(interaction.channel.id), SERVER_BOT, additional_bid_amount,
                    is_extending, current_closed_time
                )
                try:
                    del self.bot.tipping_in_progress[str(interaction.author.id)]
                except Exception:
                    pass
                if adding_bid:
                    msg = f"{EMOJI_INFORMATION} {interaction.author.mention}, successfully placing a bid with a new amount {num_format_coin(amount)} {coin_name}!"
                    await interaction.edit_original_message(content=msg)
                    if previous_user_id is not None and previous_user_id != interaction.author.id:
                        try:
                            get_user = self.bot.get_user(previous_user_id)
                            if get_user is not None:
                                await get_user.send(f"{EMOJI_INFORMATION} {interaction.author.mention} placed a higher bid than "\
                                                    f"yours in guild {interaction.guild.name}/{interaction.guild.id} for item __{str(self.message_id)}__!")
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    # update embed
                    try:
                        _msg: disnake.Message = await interaction.channel.fetch_message(self.message_id)
                        embed = _msg.embeds[0] # embeds is list, we take 0
                        embed.clear_fields()
                        embed.add_field(
                            name='Started amount',
                            value=num_format_coin(get_message['minimum_amount']) + " " + coin_name,
                            inline=True
                        )
                        embed.add_field(
                            name='Step amount',
                            value=num_format_coin(step_amount) + " " + coin_name,
                            inline=True
                        )
                        list_joined_key = []
                        list_joined = []

                        attend_list = await self.utils.get_bid_attendant(str(self.message_id))
                        if len(attend_list) > 0:
                            for i in attend_list:
                                if i['user_id'] not in list_joined_key:
                                    list_joined_key.append(i['user_id'])
                                    list_joined.append("<@{}>: {} {}".format(i['user_id'], num_format_coin(i['bid_amount']), coin_name))
                                if len(list_joined) > 0 and len(list_joined) % 15 == 0:
                                    embed.add_field(name='Bidder(s)', value="\n".join(list_joined), inline=False)
                                    list_joined = []
                            if len(list_joined) > 0:
                                embed.add_field(name='Bidder(s)', value="\n".join(list_joined), inline=False)
                        if num_extension > 0:
                            embed.add_field(name='Number of Extension', value="{}".format(num_extension), inline=True)
                        bid_note = self.bot.config['bidding']['bid_note']
                        if self.bot.config['bidding']['bid_collecting_fee'] > 0:
                            bid_note += " There will be {:,.2f}{} charged for each successful bid.".format(
                                self.bot.config['bidding']['bid_collecting_fee']*100, "%"
                            )
                        status_msg = "ONGOING"
                        embed.add_field(
                            name='Status',
                            value=status_msg,
                            inline=False
                        )
                        embed.add_field(
                            name='Note',
                            value=bid_note,
                            inline=False
                        )
                        await _msg.edit(content=None, embed=embed)
                        await log_to_channel(
                            "bid",
                            f"[NEW BID]: User {interaction.author.mention} joined/updated a bid in Guild ID: {interaction.guild.name} / {interaction.guild.id}. "\
                            f"Ref: {self.message_id} and new amount {num_format_coin(amount)} {coin_name}.",
                            self.bot.config['discord']['bid_webhook']
                        )
                        if 'fetched_msg' not in self.bot.other_data:
                            self.bot.other_data['fetched_msg'] = {}
                        self.bot.other_data['fetched_msg'][str(self.message_id)] = int(time.time())
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    return
                else:
                    msg = f"{EMOJI_INFORMATION} {self.ctx.author.mention}, internal error!"
                    await interaction.edit_original_message(content=msg)
                    return
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        except Exception:
            traceback.print_exc(file=sys.stdout)

class OwnerWinnerInput(disnake.ui.Modal):
    def __init__(
        self, ctx, bot, message_id: str, owner_userid: str,
        winner_user_id: str, amount: float, method_for: str,
        bid_info
    ) -> None:
        self.ctx = ctx
        self.bot = bot
        self.utils = Utils(self.bot)
        self.message_id = message_id
        self.owner_userid = owner_userid
        self.winner_user_id = winner_user_id
        self.winner_amount = amount
        self.method_for = method_for
        self.bid_info = bid_info

        placeholder = "Write how you want to deliver..." if self.method_for == "winner" else "Proof of delivery"
        components = [
            disnake.ui.TextInput(
                label="instruction",
                placeholder=placeholder,
                custom_id="instruction_id",
                style=TextInputStyle.paragraph
            ),
        ]
        title = "Method of delivery" if self.method_for == "winner" else "Update status to winner"
        super().__init__(title=title, custom_id="modal_winning_instruction", components=components)

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        # Check if type of question is bool or multipe
        await interaction.response.send_message(content=f"{interaction.author.mention}, checking information...", ephemeral=True)
        instruction = interaction.text_values['instruction_id'].strip()
        if instruction == "":
            await interaction.edit_original_message(f"{interaction.author.mention}, instruction is empty!")
            return
        try:
            get_message = await self.utils.get_bid_id(str(self.message_id))
            if get_message['winner_instruction'] is None and self.method_for == "winner" and interaction.author.id != self.winner_user_id:
                await interaction.edit_original_message(f"{interaction.author.mention}, you clicked on wrong button!")
                return
            elif get_message['owner_respond'] is None and self.method_for == "owner" and interaction.author.id != self.owner_userid:
                await interaction.edit_original_message(f"{interaction.author.mention}, you clicked on wrong button!")
                return
            elif get_message['winner_instruction'] is not None and get_message['owner_request_to_update'] == 0 and self.method_for == "winner" \
                and interaction.author.id in [self.owner_userid, self.winner_user_id, self.bot.config['discord']['owner_id']]:
                await interaction.edit_original_message(f"{interaction.author.mention}, winner's input:\n\n{get_message['winner_instruction']}")
                return
            elif get_message['owner_respond'] is not None and self.method_for == "owner" and interaction.author.id in [self.owner_userid, self.winner_user_id, self.bot.config['discord']['owner_id']]:
                await interaction.edit_original_message(f"{interaction.author.mention}, owner's input:\n\n{get_message['owner_respond']}")
                return
            # check if input already
            if get_message['winner_instruction'] is None and self.method_for == "owner":
                await interaction.edit_original_message(f"{interaction.author.mention}, please inform to winner to update his delivery method first!")
                return
            elif (get_message['winner_instruction'] is None or (get_message['winner_instruction'] is not None \
                                                                and get_message['owner_request_to_update'] == 1)) and \
                                                                    self.method_for == "winner" and interaction.author.id == self.winner_user_id:
                await self.utils.update_bid_winner_instruction(
                    str(self.message_id), instruction, self.method_for, None, None,
                    str(interaction.author.id)
                )
                # find owner to message
                try:
                    link_bid = "https://discord.com/channels/{}/{}/{}".format(
                        get_message['guild_id'], get_message['channel_id'], get_message['message_id']
                    )
                    owner_user = self.bot.get_user(self.owner_userid)
                    if owner_user is not None:
                        await owner_user.send(
                            f"One of your bidding winner <@{str(self.winner_user_id)}> for __{str(self.message_id)}__ at guild __{get_message['guild_name']}__ updated an "\
                            f"instruction/information as the following:\n\n{instruction}\n{link_bid}"
                        )
                        await interaction.edit_original_message(f"{interaction.author.mention}, we updated your input and notified the bidding owner.")
                    else:
                        await interaction.edit_original_message(f"{interaction.author.mention}, we updated your input and but we failed to find the bidding owner user!")
                except disnake.errors.Forbidden:
                    await interaction.edit_original_message(f"{interaction.author.mention}, we updated your input but we failed "\
                                                            f"to message to the bidding owner. Please inform him/her.")
                view = ClearButton(
                    self.bot.coin_list, self.bot,
                    interaction.channel.id, int(self.bid_info['user_id']), int(self.winner_user_id),
                    self.winner_amount, self.bid_info,
                    False, False, True, False
                )
                view.message = interaction.message
                view.channel_interact = interaction.channel.id
                await interaction.message.edit(
                    content = None,
                    view = view
                )
                await log_to_channel(
                    "bid",
                    f"[WINNER INFO]: User {interaction.author.mention} updated delivery info. "\
                    f"Ref: {self.bid_info['message_id']} and at Guild {interaction.guild.name} / {interaction.guild.id}!",
                    self.bot.config['discord']['bid_webhook']
                )
                return
            elif get_message['winner_instruction'] is not None and self.method_for == "winner":
                await interaction.edit_original_message(f"{interaction.author.mention}, you already input the necessary information! Here they are:\n\n{get_message['winner_instruction']}")
                return
            # owner
            elif get_message['owner_respond'] is None and self.method_for == "owner":
                link_bid = "https://discord.com/channels/{}/{}/{}".format(
                    get_message['guild_id'], get_message['channel_id'], get_message['message_id']
                )
                await self.utils.update_bid_winner_instruction(
                    str(self.message_id), instruction, self.method_for, None, None,
                    str(interaction.author.id)
                )
                # find winner to message
                try:
                    winner_user = self.bot.get_user(self.winner_user_id)
                    if winner_user is not None:
                        await winner_user.send(
                            f"Updated: Your bidding id __{str(self.message_id)}__ at guild __{get_message['guild_name']}__: <@{str(self.owner_userid)}> just updated "\
                            f"instruction/information as the following:\n\n{instruction}\n\nPlease Tap on **Complete** button if you confirm you get the item. "\
                            f"You bidding amount will be transferred to him/her after completion and can't be undone.\n{link_bid}"
                        )
                        await interaction.edit_original_message(f"{interaction.author.mention}, we updated your input and notified the winner <@{str(self.winner_user_id)}>.")
                    else:
                        await interaction.edit_original_message(f"{interaction.author.mention}, we updated your input and but we failed to find the winner <@{str(self.winner_user_id)}>!")
                except disnake.errors.Forbidden:
                    await interaction.edit_original_message(f"{interaction.author.mention}, we updated your input but we failed "\
                                                            f"to message to the winner. Please inform him/her.")
                view = ClearButton(
                    self.bot.coin_list, self.bot,
                    interaction.channel.id, int(self.bid_info['user_id']), int(self.winner_user_id),
                    self.winner_amount, self.bid_info,
                    False, False, False, False
                )
                view.message = interaction.message
                view.channel_interact = interaction.channel.id
                await interaction.message.edit(
                    content = None,
                    view = view
                )
                await log_to_channel(
                    "bid",
                    f"[OWNER UPDATE INFO]: User {interaction.author.mention} updated delivery info. "\
                    f"Ref: {self.bid_info['message_id']} and at Guild {interaction.guild.name} / {interaction.guild.id}!",
                    self.bot.config['discord']['bid_webhook']
                )
                return
            elif get_message['owner_respond'] is not None and self.method_for == "owner":
                await interaction.edit_original_message(f"{interaction.author.mention}, you already input the necessary information! Here they are:\n\n{get_message['owner_respond']}")
                return
            else:
                await interaction.edit_original_message(f"{interaction.author.mention}, internal error!")
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

class ClearButton(disnake.ui.View):
    message: disnake.Message
    channel_interact: disnake.TextChannel
    coin_list: Dict

    def __init__(
        self, coin_list, bot, channel_interact,
        owner_id: int, winner_id: int, winner_amount: float,
        bid_info,
        disable_winner_btn: bool=False, disable_owner_btn: bool=True,
        complete_btn: bool=True, owner_request_btn: bool=True
    ):
        super().__init__()
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.coin_list = coin_list
        self.channel_interact = channel_interact
        self.owner_id = owner_id
        self.winner_id = winner_id
        self.winner_amount = winner_amount
        self.bid_info = bid_info

        self.winner_input.disabled = disable_winner_btn
        self.owner_input.disabled = disable_owner_btn
        self.complete_all.disabled = complete_btn
        self.owner_request_update = owner_request_btn


    @disnake.ui.button(label="1️⃣ Winner Click", style=ButtonStyle.primary, custom_id="bidding_clearbtn_winner_input")
    async def winner_input(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        if interaction.author.id == self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, checking <@{str(self.winner_id)}> 's message...", ephemeral=True)
            get_message = await self.utils.get_bid_id(str(self.message.id))
            if get_message['winner_instruction'] is not None:
                await interaction.edit_original_message(f"{interaction.author.mention}, winner <@{str(self.winner_id)}> input information as below:\n\n{get_message['winner_instruction']}")
            else:
                await interaction.edit_original_message(f"{interaction.author.mention}, winner <@{str(self.winner_id)}> hasn't input anything yet!")
        elif interaction.author.id != self.winner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not yours!", ephemeral=True)
        else:
            try:
                await interaction.response.send_modal(
                    modal=OwnerWinnerInput(
                        interaction, self.bot, self.message.id, int(self.bid_info['user_id']),
                        self.winner_id, self.winner_amount, "winner",
                        self.bid_info
                    )
                )
            except disnake.errors.NotFound:
                await interaction.response.send_message(
                    f"{interaction.author.mention}, failed to retreive bidding information! Try again later!", ephemeral=True)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    @disnake.ui.button(label="2️⃣ Owner Click", style=ButtonStyle.primary, custom_id="bidding_clearbtn_owner_input")
    async def owner_input(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        if interaction.author.id == self.winner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, checking <@{str(self.owner_id)}>'s respond...", ephemeral=True)
            get_message = await self.utils.get_bid_id(str(self.message.id))
            if get_message['owner_respond'] is not None:
                await interaction.edit_original_message(f"{interaction.author.mention}, <@{str(self.owner_id)}> updates information as below:\n\n{get_message['owner_respond']}")
            else:
                await interaction.edit_original_message(f"{interaction.author.mention}, <@{str(self.owner_id)}> hasn't update anything yet!")
        elif interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not yours!", ephemeral=True)
        else:
            try:
                # check if winner already input method
                await interaction.response.send_modal(
                    modal=OwnerWinnerInput(
                        interaction, self.bot, self.message.id, int(self.bid_info['user_id']),
                        self.winner_id, self.winner_amount,  "owner",
                        self.bid_info
                    )
                )
            except disnake.errors.NotFound:
                await interaction.response.send_message(
                    f"{interaction.author.mention}, failed to retreive bidding information! Try again later!", ephemeral=True)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    @disnake.ui.button(label="3️⃣ Complete", style=ButtonStyle.primary, custom_id="bidding_clearbtn_winner_complete")
    async def complete_all(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        if interaction.author.id != self.winner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not yours!", ephemeral=True)
        else:
            try:
                await interaction.response.send_message(f"{interaction.author.mention}, in progress...", ephemeral=True)
                for child in self.children:
                    if isinstance(child, disnake.ui.Button):
                        child.disabled = True

                # check if that was processed already which may not happen?
                get_message = await self.utils.get_bid_id(str(self.message.id))
                if get_message['winner_confirmation_date'] is not None:
                    await interaction.edit_original_message(f"{interaction.author.mention}, that was already paid and processed!")
                    return

                # take balance from owner 100%
                # deduct fee to system if set
                # pay remaining balance to bid owner
                payment_list = []
                payment_list_msg = []
                payment_logs = []
                # We already deducted previously during bidding, no need to deduct one more time.
                payment_logs.append((
                    "PAYMENT", self.bid_info['message_id'], str(self.winner_id),
                    self.bid_info['guild_id'], self.bid_info['channel_id'], int(time.time()),
                    "-" + num_format_coin(self.winner_amount)
                ))
                remaining = self.winner_amount
                payment_list_msg.append(f"Processing deduct from winner <@{str(self.winner_id)}>: "\
                                        f"{num_format_coin(self.winner_amount)} {self.bid_info['token_name']}")
                if self.bot.config['bidding']['bid_collecting_fee'] > 0:
                    payment_list.append((
                        "SYSTEM", self.bid_info['token_name'], SERVER_BOT, 
                        self.bot.config['bidding']['bid_collecting_fee']*self.winner_amount, int(time.time())
                    ))
                    remaining -= self.bot.config['bidding']['bid_collecting_fee']*self.winner_amount
                    payment_list_msg.append(f"Processing to SYSTEM: "\
                        f"{num_format_coin(self.bot.config['bidding']['bid_collecting_fee']*self.winner_amount)} "\
                        f"{self.bid_info['token_name']} from winner"
                    )
                    payment_logs.append((
                        "PAYMENT", self.bid_info['message_id'], "SYSTEM",
                        self.bid_info['guild_id'], self.bid_info['channel_id'], int(time.time()),
                        num_format_coin(self.bot.config['bidding']['bid_collecting_fee']*self.winner_amount)
                    ))
                payment_list.append((
                    self.bid_info['user_id'], self.bid_info['token_name'], SERVER_BOT, remaining, int(time.time())
                ))
                payment_logs.append((
                    "PAYMENT", self.bid_info['message_id'], self.bid_info['user_id'],
                    self.bid_info['guild_id'], self.bid_info['channel_id'], int(time.time()),
                    num_format_coin(remaining)
                ))
                payment_list_msg.append(f"Processing to auction owner <@{str(self.owner_id)}>: {num_format_coin(remaining)} {self.bid_info['token_name']}")
                await self.utils.update_bid_winner_instruction(
                    str(self.bid_info['message_id']), "placeholder", "final",
                    payment_list, payment_logs,
                    str(interaction.author.id)
                )
                payment_list_msg = "\n".join(payment_list_msg)
                await self.message.edit(view=self)
                await log_to_channel(
                    "bid",
                    f"[BID COMPLETED]: User {interaction.author.mention} marked the bid as completed. "\
                    f"Ref: {self.bid_info['message_id']} and at Guild name: {self.bid_info['guild_name']} / {self.bid_info['guild_id']}!\n{payment_list_msg}",
                    self.bot.config['discord']['bid_webhook']
                )
                await interaction.edit_original_message(f"{interaction.author.mention}, Completed! Payment also paid to the Owner!")
                get_owner = self.bot.get_user(int(self.bid_info['user_id']))
                if get_owner is not None:
                    await get_owner.send(f"{interaction.author.mention} marked your bid as completed. "\
                                         f"You got paid {num_format_coin(self.bid_info['winner_amount']*(1-self.bot.config['bidding']['bid_collecting_fee']))} "\
                                         f"{self.bid_info['token_name']} to your balance!")
            except disnake.errors.NotFound:
                await interaction.response.send_message(
                    f"{interaction.author.mention}, failed to retreive bidding information! Try again later!", ephemeral=True)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    @disnake.ui.button(label="📝 Owner Request Update", style=ButtonStyle.primary, custom_id="bidding_clearbtn_owner_request")
    async def owner_request_update(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not yours!", ephemeral=True)
        else:
            try:
                await interaction.response.send_message(f"{interaction.author.mention}, in progress...", ephemeral=True)
                # check if that was processed already which may not happen?
                get_message = await self.utils.get_bid_id(str(self.message.id))
                if get_message['winner_confirmation_date'] is not None:
                    await interaction.edit_original_message(f"{interaction.author.mention}, that was already paid and processed!")
                    return
                elif get_message['winner_instruction'] is None:
                    await interaction.edit_original_message(f"{interaction.author.mention}, winner didn't input anything yet!")
                    return
                elif get_message['owner_request_to_update'] == 1:
                    await interaction.edit_original_message(f"{interaction.author.mention}, this bid previously requested to update already!")
                    return
                elif get_message['owner_respond'] is not None:
                    await interaction.edit_original_message(f"{interaction.author.mention}, you already updated your respond for this bid!")
                    return
                else:
                    req = await self.utils.bid_req_winner_update(
                        str(self.message.id), str(interaction.author), str(interaction.channel.id), str(interaction.guild.id)
                    )
                    if req is True:
                        link_bid = "https://discord.com/channels/{}/{}/{}".format(
                            interaction.guild.id, interaction.channel.id, self.message.id
                        )
                        get_winner = self.bot.get_user(int(get_message['winner_user_id']))
                        if get_winner is not None:
                            try:
                                await get_winner.send(f"{interaction.author.mention} requested you to re-update the information for this {link_bid}!")
                                await interaction.edit_original_message(f"{interaction.author.mention}, successfully requested him/her to updated!")
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                                await interaction.edit_original_message(f"{interaction.author.mention}, I failed to DM <@{get_message['winner_user_id']}> about requesting update!")
                        else:
                            await interaction.edit_original_message(f"{interaction.author.mention}, updated to request more "
                                                                    f"information but I can't find the user <@{get_message['winner_user_id']}>.")
                    return
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    @disnake.ui.button(label="⚠️Report", style=ButtonStyle.gray, custom_id="bidding_report_clear")
    async def clear_bid_report(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        try:
            await interaction.response.send_modal(
                modal=ReportBid(
                    interaction, self.bot, self.bid_info['message_id'], int(self.bid_info['user_id'])
                )
            )
        except disnake.errors.NotFound:
            await interaction.response.send_message(
                f"{interaction.author.mention}, failed to retreive bidding information! Try again later!", ephemeral=True)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

class BidButton(disnake.ui.View):
    message: disnake.Message
    channel_interact: disnake.TextChannel
    coin_list: Dict

    def __init__(
        self, timeout, coin_list, bot, channel_interact,
        owner_id: int, coin_name: str, min_amount: float, step_amount: float,
        title: str, desc: str = None
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.coin_list = coin_list
        self.channel_interact = channel_interact
        self.owner_id = owner_id
        self.coin_name = coin_name
        self.min_amount = min_amount
        self.step_amount = step_amount
        self.caption_new = title
        self.desc = desc

    async def on_timeout(self):
        try:
            self.bid_place.disabled = True
            self.bid_edit.disabled = True
            self.bid_cancel.disabled = True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # for child in self.children:
        #     if isinstance(child, disnake.ui.Button):
        #         child.disabled = True

        ## Update content
        try:
            channel = self.bot.get_channel(self.channel_interact)
            _msg: disnake.Message = await channel.fetch_message(self.message.id)
            await _msg.edit(content=None, view=self)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @disnake.ui.button(label="Place Bid", style=ButtonStyle.primary, custom_id="bidding_place_bid")
    async def bid_place(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        if interaction.author.id == self.owner_id and self.bot.config['bidding']['allow_own_bid'] != 1:
            await interaction.response.send_message(f"{interaction.author.mention}, you can't bid on your own!", delete_after=5.0)
        else:
            try:
                await interaction.response.send_modal(
                    modal=PlaceBid(interaction, self.bot, self.message.id, self.owner_id, self.coin_name, self.min_amount, self.step_amount))
            except disnake.errors.NotFound:
                await interaction.response.send_message(f"{interaction.author.mention}, failed to retreive bidding information! Try again later!", ephemeral=True)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    @disnake.ui.button(label="Edit", style=ButtonStyle.green, custom_id="bidding_edit")
    async def bid_edit(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not your listing!", ephemeral=True)
        else:
            try:
                await interaction.response.send_modal(
                    modal=EditBid(interaction, self.bot, self.message.id, self.owner_id, self.caption_new, self.desc))
            except disnake.errors.NotFound:
                await interaction.response.send_message(f"{interaction.author.mention}, failed to retreive bidding information! Try again later!", ephemeral=True)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    @disnake.ui.button(label="🔴 Cancel", style=ButtonStyle.danger, custom_id="bidding_cancel")
    async def bid_cancel(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not your listing!", ephemeral=True)
        else:
            await interaction.response.send_message(f"{interaction.author.mention}, checking cancellation!", ephemeral=True)
            try:
                # add for confirmation
                view = ConfirmName(self.bot, interaction.author.id)
                msg = f"{EMOJI_INFORMATION} {interaction.author.mention}, Do you want to cancel this bidding for {self.caption_new}? And all bidders will get their refund."
                await interaction.edit_original_message(content=msg, view=view)

                # Wait for the View to stop listening for input...
                await view.wait()

                # Check the value to determine which button was pressed, if any.
                if view.value is False:
                    await interaction.edit_original_message(
                        content=f"{EMOJI_INFORMATION} {interaction.author.mention}, the bid is not cancelled. Thank you!", view=None
                    )
                    return
                elif view.value is None:
                    await interaction.edit_original_message(
                        content=msg + "\n**Timeout!**",
                        view=None
                    )
                elif view.value:
                    # set status to cancelled, log, refund to all bidders.
                    try:
                        # get list bidders and amounts
                        attend_list = await self.utils.get_bid_attendant(str(self.message.id))
                        refund_list = []
                        list_key_update = []
                        payment_logs = []
                        if len(attend_list) > 0:
                            for i in attend_list:
                                refund_list.append((
                                    i['user_id'], i['bid_coin'], SERVER_BOT, i['bid_amount'], int(time.time())
                                ))
                                list_key_update.append(i['user_id'] + "_" + i['bid_coin'] + "_" + SERVER_BOT)
                                payment_logs.append((
                                    "REFUND", str(self.message.id), i['user_id'],
                                    str(interaction.guild.id), str(interaction.channel.id), int(time.time()),
                                    num_format_coin(i['bid_amount'])
                                ))
                        cancelling = await self.utils.discord_bid_cancel(
                            str(self.message.id), str(interaction.author.id),
                            str(interaction.guild.id), str(interaction.channel.id),
                            refund_list, payment_logs
                        )
                        if cancelling is True:
                            link_bid = "https://discord.com/channels/{}/{}/{}".format(
                                interaction.guild.id, interaction.channel.id, self.message.id
                            )
                            ## Update content
                            try:
                                for child in self.children:
                                    if isinstance(child, disnake.ui.Button):
                                        child.disabled = True
                                _msg: disnake.Message = await interaction.channel.fetch_message(self.message.id)
                                await _msg.edit(content=None, view=self)
                                await log_to_channel(
                                    "bid",
                                    f"[BID CANCELLED]: User {interaction.author.mention} cancelled a bid in Guild ID {interaction.guild.id}.\n"\
                                    f"Ref: {self.message.id} / Guild name: {interaction.guild.name}!",
                                    self.bot.config['discord']['bid_webhook']
                                )
                                if 'fetched_msg' not in self.bot.other_data:
                                    self.bot.other_data['fetched_msg'] = {}
                                self.bot.other_data['fetched_msg'][str(self.message.id)] = int(time.time())
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            await interaction.edit_original_message(f"{interaction.author.mention}, successfully cancelled!\n{link_bid}", view=None)
                            # DM refund
                            for i in refund_list:
                                try:
                                    get_u = self.bot.get_user(int(i[0]))
                                    if get_u is not None:
                                        await get_u.send(f"Bid __{str(self.message.id)}__ cancelled in guild {interaction.guild.name}/{interaction.guild.id}!"\
                                                        " You get a refund of "\
                                                        f"{num_format_coin(i[3])} {self.coin_name}.\n{link_bid}")
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                        else:
                            await interaction.edit_original_message(f"{interaction.author.mention}, internal error!", view=None)
                    except disnake.errors.NotFound:
                        await interaction.edit_original_message(f"{interaction.author.mention}, failed to retreive bidding information! Try again later!", ephemeral=True)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    @disnake.ui.button(label="⚠️Report", style=ButtonStyle.gray, custom_id="bidding_report")
    async def bid_report(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        try:
            await interaction.response.send_modal(
                modal=ReportBid(
                    interaction, self.bot, self.message.id, self.owner_id
                )
            )
        except disnake.errors.NotFound:
            await interaction.response.send_message(
                f"{interaction.author.mention}, failed to retreive bidding information! Try again later!", ephemeral=True)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

class Bidding(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.max_ongoing_by_guild = 5
        self.bidding_cache = TTLCache(maxsize=2000, ttl=60.0) # if previous value and new value the same, no need to edit
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

        self.file_accept = ["image/jpeg", "image/gif", "image/png"]
        self.bid_storage = "./discordtip_v2_bidding/"
        self.bid_web_path = self.bot.config['bidding']['web_path']
        self.bid_channel_upload = self.bot.config['bidding']['upload_channel_log']

    @tasks.loop(seconds=30.0)
    async def bidding_check(self):
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "bidding_check"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 5: # not running if less than 15s
            return
        try:
            get_list_bids = await self.utils.get_all_bids("ONGOING")
            # For some reason, the clear button menu is gone
            get_list_bid_complete = await self.utils.get_all_bids("COMPLETED")
            list_complete_gone = []
            for i in get_list_bid_complete:
                if i['winner_confirmation_date'] is None:
                    list_complete_gone.append(i)
            # COMPLETE BUT NOT PAID
            if len(list_complete_gone) > 0:
                for each_bid in list_complete_gone:
                    await self.bot.wait_until_ready()
                    _msg = None
                    get_message = await self.utils.get_bid_id(each_bid['message_id'])
                    attend_list = await self.utils.get_bid_attendant(each_bid['message_id'])
                    if len(attend_list) == 0:
                        await self.utils.update_bid_failed(each_bid['message_id'], True)
                        await log_to_channel(
                            "bid",
                            "[BIDDING STATUS CANCELLED]: message ID: {} of channel {}/guild: {} completed but no attendee(s).".format(
                                each_bid['message_id'], each_bid['channel_id'], each_bid['guild_id']
                            ),
                            self.bot.config['discord']['bid_webhook']
                        )
                        continue
                    try:
                        # Update view
                        owner_displayname = get_message['username']
                        coin_name = get_message['token_name']
                        coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                        coin_emoji = coin_emoji + " " if coin_emoji else ""
                        min_amount = get_message['minimum_amount']

                        list_joined = []
                        list_joined_key = []
                        try:
                            channel = self.bot.get_channel(int(get_message['channel_id']))
                            if channel is None:
                                await logchanbot("bidding_check: can not find channel ID: {}".format(each_bid['channel_id']))
                                await asyncio.sleep(2.0)
                                continue
                            else:
                                # If time_left is too long
                                if 'fetched_msg' not in self.bot.other_data:
                                    self.bot.other_data['fetched_msg'] = {}
                                else:
                                    if each_bid['message_id'] in self.bot.other_data['fetched_msg']:
                                        time_left = each_bid['bid_open_time'] - int(time.time())
                                        last_fetched = self.bot.other_data['fetched_msg'][each_bid['message_id']]
                                        if int(time.time()) - last_fetched < 90 and time_left > 10*3600:
                                            continue
                                _msg: disnake.Message = await channel.fetch_message(int(each_bid['message_id']))
                                embed = _msg.embeds[0] # embeds is list, we take 0
                                embed.clear_fields()
                                embed.add_field(
                                    name='Started amount',
                                    value=num_format_coin(min_amount) + " " + coin_name,
                                    inline=True
                                )
                                # min_bid_lap
                                step_amount = get_message['step_amount']
                                if step_amount is None:
                                    step_amount = getattr(getattr(self.bot.coin_list, coin_name), "min_bid_lap")
                                embed.add_field(
                                    name='Step amount',
                                    value=num_format_coin(step_amount) + " " + coin_name,
                                    inline=True
                                )
                                if len(attend_list) > 0:
                                    for i in attend_list:
                                        if i['user_id'] not in list_joined_key:
                                            list_joined_key.append(i['user_id'])
                                            list_joined.append("<@{}>: {} {}".format(i['user_id'], num_format_coin(i['bid_amount']), coin_name))
                                        if len(list_joined) > 0 and len(list_joined) % 15 == 0:
                                            embed.add_field(name='Bidder(s)', value="\n".join(list_joined), inline=False)
                                            list_joined = []
                                    if len(list_joined) > 0:
                                        embed.add_field(name='Bidder(s)', value="\n".join(list_joined), inline=False)
                                if each_bid['number_extension'] > 0:
                                    embed.add_field(name='Number of Extension', value="{}".format(each_bid['number_extension']), inline=True)
                                bid_note = self.bot.config['bidding']['bid_note']
                                if self.bot.config['bidding']['bid_collecting_fee'] > 0:
                                    bid_note += " There will be {:,.2f}{} charged for each successful bid.".format(
                                        self.bot.config['bidding']['bid_collecting_fee']*100, "%"
                                    )

                                status_msg = "ONGOING"
                                if each_bid['status'] == "CANCELLED":
                                    status_msg = "CANCELLED"
                                elif each_bid['winner_user_id'] is not None and each_bid['winner_instruction'] is None:
                                    status_msg = "Waiting for winner's information."
                                elif each_bid['winner_user_id'] is not None and each_bid['owner_respond'] is None:
                                    status_msg = "Waiting for owner's update."
                                elif each_bid['winner_user_id'] is not None and each_bid['winner_confirmation_date'] is None:
                                    status_msg = "Waiting for winner's final confirmation."
                                elif each_bid['winner_user_id'] is not None:
                                    status_msg = "UNKNOWN"
                                embed.add_field(
                                    name='Status',
                                    value=status_msg,
                                    inline=False
                                )
                                embed.add_field(
                                    name='Note',
                                    value=bid_note,
                                    inline=False
                                )
                                if _msg is not None and len(_msg.components) == 0:
                                    print("BID {} complete but not paid..".format(each_bid['message_id']))
                                    # no compoents, Add view
                                    winner_btn = False if each_bid['winner_confirmation_date'] is None else True
                                    owner_btn = False if each_bid['winner_confirmation_date'] is None else True
                                    complete_btn = False if each_bid['winner_confirmation_date'] is None else True
                                    owner_req_btn = False if each_bid['winner_instruction'] is not None else True
                                    if each_bid['owner_respond'] is None:
                                       complete_btn = True 
                                    view = ClearButton(
                                        self.bot.coin_list, self.bot,
                                        channel.id, int(each_bid['user_id']), int(attend_list[0]['user_id']),
                                        attend_list[0]['bid_amount'], each_bid,
                                        winner_btn, owner_btn, complete_btn, owner_req_btn
                                    )
                                    view.message = _msg
                                    view.channel_interact = channel.id
                                    await _msg.edit(content=None, embed=embed, view=view)
                                    # update winner and status
                                    await log_to_channel(
                                        "bid",
                                        f"[ADD MENU BACK]: {each_bid['guild_name']} / {each_bid['guild_id']} ref: {each_bid['message_id']}. "\
                                        f"Winner <@{attend_list[0]['user_id']}>, amount {attend_list[0]['bid_amount']} {each_bid['token_name']}",
                                        self.bot.config['discord']['bid_webhook']
                                    )
                                elif _msg is not None and len(_msg.components) > 0 and int(time.time()) - int(_msg.edited_at.timestamp()) > 2*60:
                                    # re-edit if bigger than 10mn
                                    # no compoents, Add view
                                    winner_btn = False if each_bid['winner_confirmation_date'] is None else True
                                    owner_btn = False if each_bid['winner_confirmation_date'] is None else True
                                    complete_btn = False if each_bid['winner_confirmation_date'] is None else True
                                    owner_req_btn = False if each_bid['winner_instruction'] is not None else True
                                    if each_bid['owner_respond'] is None:
                                       complete_btn = True 
                                    view = ClearButton(
                                        self.bot.coin_list, self.bot,
                                        channel.id, int(each_bid['user_id']), int(attend_list[0]['user_id']),
                                        attend_list[0]['bid_amount'], each_bid,
                                        winner_btn, owner_btn, complete_btn, owner_req_btn
                                    )
                                    view.message = _msg
                                    view.channel_interact = channel.id
                                    await _msg.edit(content=None, embed=embed, view=view)
                                    # update winner and status
                                    # await log_to_channel(
                                    #     "bid",
                                    #     f"[EDIT MENU]: {each_bid['guild_name']} / {each_bid['guild_id']} ref: {each_bid['message_id']}. "\
                                    #     f"Winner <@{attend_list[0]['user_id']}>, amount {attend_list[0]['bid_amount']} {each_bid['token_name']}",
                                    #     self.bot.config['discord']['bid_webhook']
                                    # )
                                continue
                        except disnake.errors.NotFound:
                            await log_to_channel(
                                "bid",
                                "[NOT FOUND BIDDING]: can not find message ID: {} of channel {} in guild: {}.".format(
                                    each_bid['message_id'], each_bid['channel_id'], each_bid['guild_id']
                                ),
                                self.bot.config['discord']['bid_webhook']
                            )
                            continue
                        except disnake.errors.DiscordServerError:
                            await log_to_channel(
                                "bid",
                                "[BIDDING]: DiscordServerError message ID: {} of channel {} in guild: {}/{}.".format(
                                    each_bid['message_id'], each_bid['channel_id'], each_bid['guild_id'], each_bid['guild_name']
                                ),
                                self.bot.config['discord']['bid_webhook']
                            )
                            await asyncio.sleep(1.0)
                            continue
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
            # ONGOING
            if len(get_list_bids) > 0:
                for each_bid in get_list_bids:
                    link_bid = "https://discord.com/channels/{}/{}/{}".format(
                        each_bid['guild_id'], each_bid['channel_id'], each_bid['message_id']
                    )
                    await self.bot.wait_until_ready()
                    _msg = None
                    get_message = await self.utils.get_bid_id(each_bid['message_id'])
                    attend_list = await self.utils.get_bid_attendant(each_bid['message_id'])
                    try:
                        # Update view
                        owner_displayname = get_message['username']
                        coin_name = get_message['token_name']
                        coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                        coin_emoji = coin_emoji + " " if coin_emoji else ""
                        min_amount = get_message['minimum_amount']

                        duration = each_bid['bid_open_time'] - int(time.time())
                        if each_bid['bid_extended_time'] is not None:
                            duration = each_bid['bid_extended_time'] - int(time.time())
                        if duration < 0:
                            duration = 0

                        time_left = seconds_str_days(duration)
                        list_joined = []
                        list_joined_key = []
                        try:
                            channel = self.bot.get_channel(int(get_message['channel_id']))
                            if channel is None:
                                await logchanbot("bidding_check: can not find channel ID: {}".format(each_bid['channel_id']))
                                await asyncio.sleep(2.0)
                                continue
                            else:
                                if 'fetched_msg' not in self.bot.other_data:
                                    self.bot.other_data['fetched_msg'] = {}
                                else:
                                    if each_bid['message_id'] in self.bot.other_data['fetched_msg']:
                                        last_fetched = self.bot.other_data['fetched_msg'][each_bid['message_id']]
                                        if int(time.time()) - last_fetched < 90 and duration > 10*3600:
                                            continue
                                _msg: disnake.Message = await channel.fetch_message(int(each_bid['message_id']))
                                embed = _msg.embeds[0] # embeds is list, we take 0
                                embed.clear_fields()
                                embed.add_field(
                                    name='Started amount',
                                    value=num_format_coin(min_amount) + " " + coin_name,
                                    inline=True
                                )
                                # min_bid_lap
                                step_amount = get_message['step_amount']
                                if step_amount is None:
                                    step_amount = getattr(getattr(self.bot.coin_list, coin_name), "min_bid_lap")
                                embed.add_field(
                                    name='Step amount',
                                    value=num_format_coin(step_amount) + " " + coin_name,
                                    inline=True
                                )
                                link = self.bot.config['bidding']['web_path'] + each_bid['saved_name']
                                embed.set_image(url=link)
                                embed.set_footer(text=f"Created by {owner_displayname} | /bid add | Time left: {time_left}")
                                if duration <= 0:
                                    embed.set_footer(text=f"Created by {owner_displayname} | /bid add | Ended!")
                                if len(attend_list) > 0:
                                    for i in attend_list:
                                        if i['user_id'] not in list_joined_key:
                                            list_joined_key.append(i['user_id'])
                                            list_joined.append("<@{}>: {} {}".format(i['user_id'], num_format_coin(i['bid_amount']), coin_name))
                                        if len(list_joined) > 0 and len(list_joined) % 15 == 0:
                                            embed.add_field(name='Bidder(s)', value="\n".join(list_joined), inline=False)
                                            list_joined = []
                                    if len(list_joined) > 0:
                                        embed.add_field(name='Bidder(s)', value="\n".join(list_joined), inline=False)
                                if each_bid['number_extension'] > 0:
                                    embed.add_field(name='Number of Extension', value="{}".format(each_bid['number_extension']), inline=True)
                                bid_note = self.bot.config['bidding']['bid_note']
                                if self.bot.config['bidding']['bid_collecting_fee'] > 0:
                                    bid_note += " There will be {:,.2f}{} charged for each successful bid.".format(
                                        self.bot.config['bidding']['bid_collecting_fee']*100, "%"
                                    )

                                status_msg = "ONGOING"
                                if each_bid['status'] == "CANCELLED":
                                    status_msg = "CANCELLED"
                                elif each_bid['winner_user_id'] is not None and each_bid['winner_instruction'] is None:
                                    status_msg = "Waiting for winner's information."
                                elif each_bid['winner_user_id'] is not None and each_bid['owner_respond'] is None:
                                    status_msg = "Waiting for owner's update."
                                elif each_bid['winner_user_id'] is not None and each_bid['winner_confirmation_date'] is None:
                                    status_msg = "Waiting for winner's final confirmation."
                                elif each_bid['winner_user_id'] is not None:
                                    status_msg = "UNKNOWN"
                                embed.add_field(
                                    name='Status',
                                    value=status_msg,
                                    inline=False
                                )
                                embed.add_field(
                                    name='Note',
                                    value=bid_note,
                                    inline=False
                                )
                        except disnake.errors.NotFound:
                            await log_to_channel(
                                "bid",
                                "[NOT FOUND BIDDING]: can not find message ID: {} of channel {} in guild: {}.".format(
                                    each_bid['message_id'], each_bid['channel_id'], each_bid['guild_id']
                                ),
                                self.bot.config['discord']['bid_webhook']
                            )
                            # add fail check
                            if each_bid['failed_check'] <= 3:
                                await self.utils.update_bid_failed(each_bid['message_id'], False)
                            elif len(attend_list) == 0:
                                # nothing to refund
                                await self.utils.update_bid_failed(each_bid['message_id'], True)
                            elif len(attend_list) > 0:
                                try:
                                    # refund
                                    refund_list = []
                                    list_key_update = []
                                    payment_logs = []
                                    for i in attend_list:
                                        refund_list.append((
                                            i['user_id'], i['bid_coin'], SERVER_BOT, i['bid_amount'], int(time.time())
                                        ))
                                        list_key_update.append(i['user_id'] + "_" + i['bid_coin'] + "_" + SERVER_BOT)
                                        payment_logs.append((
                                            "REFUND", each_bid['message_id'], i['user_id'],
                                            each_bid['guild_id'], each_bid['channel_id'], int(time.time()),
                                            num_format_coin(i['bid_amount'])
                                        ))
                                    await self.utils.discord_bid_cancel(
                                        each_bid['message_id'], each_bid['user_id'],
                                        each_bid['guild_id'], each_bid['channel_id'],
                                        refund_list, payment_logs
                                    )
                                    await log_to_channel(
                                        "bid",
                                        "[REFUND]: can not find message ID: {} of channel {} in guild: {}. Refund to {} user(s).".format(
                                            each_bid['message_id'], each_bid['channel_id'], each_bid['guild_id'],
                                            len(refund_list)
                                        ),
                                        self.bot.config['discord']['bid_webhook']
                                    )
                                    for i in refund_list:
                                        # DM all people to refund
                                        try:
                                            get_u = self.bot.get_user(int(i[0]))
                                            if get_u is not None:
                                                await get_u.send(f"You get a refund of "\
                                                                 f"{num_format_coin(i[3])} {each_bid['coin_name']} "\
                                                                 f"from bidding no. __{each_bid['message_id']}__ in "\
                                                                 f"guild {each_bid['guild_name']}/{each_bid['guild_id']}.\n{link_bid}")
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            continue
                        except disnake.errors.DiscordServerError:
                            await log_to_channel(
                                "bid",
                                "[BIDDING]: DiscordServerError message ID: {} of channel {} in guild: {}/{}.".format(
                                    each_bid['message_id'], each_bid['channel_id'], each_bid['guild_id'], each_bid['guild_name'],
                                ),
                                self.bot.config['discord']['bid_webhook']
                            )
                            await asyncio.sleep(1.0)
                            continue
                        except Exception:
                            traceback.print_exc(file=sys.stdout)

                        if each_bid['bid_open_time'] < int(time.time()):
                            link_bid = "https://discord.com/channels/{}/{}/{}".format(
                                each_bid['guild_id'], each_bid['channel_id'], each_bid['message_id']
                            )
                            try:
                                msg_owner = ""
                                msg_winner = ""
                                if len(attend_list) == 0:
                                    await _msg.edit(content=None, embed=embed, view=None)
                                    await self.utils.update_bid_no_winning(each_bid['message_id'])
                                    # notify owner, no winner
                                    msg_owner = "One of your bidding is completed! "\
                                        "There is no winner for bidding __{}__ in guild __{}__.\n{}".format(
                                            each_bid['message_id'], each_bid['guild_name'], link_bid
                                        )
                                    await log_to_channel(
                                        "bid",
                                        f"[BIDDING CLOSED]: Guild {each_bid['guild_name']} / {each_bid['guild_id']} closed a bid {each_bid['message_id']} because no one bid.",
                                        self.bot.config['discord']['bid_webhook']
                                    )
                                else:
                                    refund_list = []
                                    list_key_update = []
                                    payment_logs = []
                                    if len(attend_list) > 1:
                                        for i in attend_list[1:]: # starting from 2nd one
                                            refund_list.append((
                                                i['user_id'], i['bid_coin'], SERVER_BOT, i['bid_amount'], int(time.time())
                                            ))
                                            list_key_update.append(i['user_id'] + "_" + i['bid_coin'] + "_" + SERVER_BOT)
                                            payment_logs.append((
                                                "REFUND", each_bid['message_id'], i['user_id'],
                                                each_bid['guild_id'], each_bid['channel_id'], int(time.time()),
                                                num_format_coin(i['bid_amount'])
                                            ))
                                    # check if there is winner or no one join
                                    view = ClearButton(
                                        self.bot.coin_list, self.bot,
                                        channel.id, int(each_bid['user_id']), int(attend_list[0]['user_id']),
                                        attend_list[0]['bid_amount'], each_bid,
                                        False, True, True, True
                                    )
                                    view.message = _msg
                                    view.channel_interact = channel.id
                                    await _msg.edit(content=None, embed=embed, view=view)
                                    # update winner and status
                                    await self.utils.update_bid_with_winner(
                                        each_bid['message_id'], attend_list[0]['user_id'], attend_list[0]['bid_amount'],
                                        refund_list, payment_logs
                                    )
                                    msg_owner = "One of your bidding is completed! "\
                                        "User <@{}> is the winner for bidding __{}__ in guild __{}__.\n{}".format(
                                            attend_list[0]['user_id'], each_bid['message_id'], each_bid['guild_name'], link_bid
                                    )
                                    msg_winner = "Congratulation! You won a bid __{}__ in guild {}/{}. "\
                                        "Kindly check the new button and input necessary information and tap on Complete once's done.\n{}".format(
                                        each_bid['message_id'], each_bid['guild_name'], each_bid['guild_id'], link_bid
                                    )
                                    await log_to_channel(
                                        "bid",
                                        f"[BIDDING CLOSED]: {each_bid['guild_name']} / {each_bid['guild_id']} closed a bid {each_bid['message_id']}. "\
                                        f"Winner <@{attend_list[0]['user_id']}>, amount {attend_list[0]['bid_amount']} {each_bid['token_name']}",
                                        self.bot.config['discord']['bid_webhook']
                                    )
                                # notify bid owner
                                try:
                                    get_owner = self.bot.get_user(int(each_bid['user_id']))
                                    if get_owner is not None and len(msg_owner) > 0:
                                        await get_owner.send(msg_owner)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                    await log_to_channel(
                                        "bid",
                                        f"[BIDDING FAILED MSG]: failed to DM owner user <@{each_bid['user_id']}>. "\
                                        f"Bid __{each_bid['message_id']}__ at Guild {each_bid['guild_name']}/{each_bid['guild_id']}.",
                                        self.bot.config['discord']['bid_webhook']
                                    )
                                # notify bid winner
                                try:
                                    get_winner = self.bot.get_user(int(attend_list[0]['user_id']))
                                    if get_winner is not None and len(msg_winner) > 0:
                                        await get_winner.send(msg_winner)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                    await log_to_channel(
                                        "bid",
                                        f"[BIDDING FAILED MSG]: failed to DM winner user <@{attend_list[0]['user_id']}>. "\
                                        f"Bid __{each_bid['message_id']}__ at Guild {each_bid['guild_name']}/{each_bid['guild_id']}.",
                                        self.bot.config['discord']['bid_webhook']
                                    )
                                # DM refund
                                for i in refund_list:
                                    try:
                                        get_u = self.bot.get_user(int(i[0]))
                                        if get_u is not None:
                                            await get_u.send(f"You didn't win for bidding __{str(each_bid['message_id'])}__ in Guild "\
                                                             f"{each_bid['guild_name']}/{each_bid['guild_id']}!"\
                                                             " You get a refund of full amount "\
                                                             f"{num_format_coin(i[3])} {coin_name}.\n{link_bid}")
                                            await log_to_channel(
                                                "bid",
                                                f"[BIDDING REFUND]: sent refund DM to user <@{i[0]}>. "\
                                                f"Bid __{each_bid['message_id']}__ amount {num_format_coin(i[3])} {coin_name} "\
                                                f"at Guild {each_bid['guild_name']}/{each_bid['guild_id']}.",
                                                self.bot.config['discord']['bid_webhook']
                                            )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                        else:
                            try:
                                # not too rush to edit
                                if _msg is not None and _msg.edited_at and int(time.time()) - int(_msg.edited_at.timestamp()) > 60:
                                    # If we don't need to update view
                                    # await _msg.edit(content=None, embed=embed)
                                    # If we need to update view
                                    view = BidButton(
                                        duration, self.bot.coin_list, self.bot,
                                        int(each_bid['channel_id']), int(each_bid['user_id']), each_bid['token_name'],
                                        each_bid['minimum_amount'], each_bid['step_amount'], each_bid['title'], each_bid['description']
                                    )
                                    view.message = _msg
                                    view.channel_interact = int(each_bid['channel_id'])
                                    await _msg.edit(content=None, embed=embed, view=view)
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("bidding_check " +str(traceback.format_exc()))
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))

    @commands.guild_only()
    @commands.slash_command(
        name="bid",
        dm_permission=False,
        description="Various bid's commands."
    )
    async def bid(self, ctx):
        if self.bot.config['bidding']['enable'] == 0 and ctx.author.id != self.bot.config['discord']['owner_id']:
            await ctx.response.send_message(content=f"{ctx.author.mention}, this command is currently disable!")
            return
        if self.bot.config['bidding']['enable'] == 1 and self.bot.config['bidding']['is_private'] == 1 and ctx.author.id not in self.bot.config['bidding']['testers']:
            await ctx.response.send_message(content=f"{ctx.author.mention}, this command is still restricted! Try again later!")
            return

    @bid.sub_command(
        name="add",
        usage="bid add <title> <min_amount> <step_amount> <coin> <duration>", 
        options=[
            Option('title', 'title', OptionType.string, required=True),
            Option('min_amount', 'min amount', OptionType.string, required=True),
            Option('step_amount', 'step amount', OptionType.string, required=True),
            Option('coin', 'coin', OptionType.string, required=True),
            Option('duration', 'duration', OptionType.string, required=True, choices=[
                OptionChoice("1 Hour", "1H"),
                OptionChoice("2 Hours", "2H"),
                OptionChoice("6 Hours", "6H"),
                OptionChoice("12 Hours", "12H"),
                OptionChoice("1 Day", "24H"),
                OptionChoice("2 Days", "48H"),
                OptionChoice("3 Days", "72H"),
                OptionChoice("4 Days", "96H"),
                OptionChoice("5 Days", "120H"),
                OptionChoice("6 Days", "144H"),
                OptionChoice("7 Days", "168H")
            ]),
            Option('attachment', 'attachment', OptionType.attachment, required=True),
        ],
        description="Add a new item for bidding."
    )
    async def bidding_add_new(
        self, 
        ctx, 
        title: str,
        min_amount: str,
        step_amount: str,
        coin: str,
        duration: str,
        attachment: disnake.Attachment
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/bid add", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        serverinfo = self.bot.other_data['guild_list'].get((str(ctx.guild.id)))
        try:
            count_ongoing = await self.utils.discord_bid_ongoing(str(ctx.guild.id), "ONGOING")
            # Check max if set in guild
            if serverinfo and count_ongoing >= serverinfo['max_ongoing_bid'] and ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, there are still some ongoing bids in this guild. Please wait for them to complete first!'
                await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                return
            elif serverinfo is None and count_ongoing >= self.max_ongoing_by_guild and ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, there are still some ongoing bids in this guild. Please wait for them to complete first!'
                await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                await logchanbot(f"[BIDDING] server {str(ctx.guild.id)} has no data in discord_server.")
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # End of ongoing check

        coin_name = coin.upper()
        contract = None
        coin_decimal = 0
        try:
            get_perms = dict(ctx.guild.get_member(ctx.author.id).guild_permissions)
            if get_perms[self.bot.config['bidding']['perm_bid_add']] is False and ctx.author.id != self.bot.config['discord']['owner']:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you don't have permission here. At least __{self.bot.config['bidding']['perm_bid_add']}__ in this guild!"
                await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                return
            guild_id = str(ctx.guild.id)
            channel_id = (ctx.channel.id)
            file_saved = False
            saved_name = None
            original_name = str(attachment).split("/")[-1]
            random_string = str(uuid.uuid4())
            try:
                
                if not hasattr(self.bot.coin_list, coin_name):
                    msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
                    await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                    return
                bid_enable = getattr(getattr(self.bot.coin_list, coin_name), "bid_enable")
                if bid_enable != 1:
                    msg = f"{ctx.author.mention}, **{coin_name}** not enable with bidding. Contact TipBot dev"
                    await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                    return
                min_bid_start = getattr(getattr(self.bot.coin_list, coin_name), "min_bid_start")
                min_bid_lap = getattr(getattr(self.bot.coin_list, coin_name), "min_bid_lap")
                contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                # min_amount
                price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                if "$" in min_amount[-1] or "$" in min_amount[0]:  # last is $
                    # Check if conversion is allowed for this coin.
                    min_amount = min_amount.replace(",", "").replace("$", "")
                    if price_with is None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this __{coin_name}__."
                        await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                        return
                    else:
                        per_unit = await self.utils.get_coin_price(coin_name, price_with)
                        per_unit = await self.utils.get_coin_price(coin_name, price_with)
                        if per_unit and per_unit['price'] and per_unit['price'] > 0:
                            per_unit = per_unit['price']
                            min_amount = float(Decimal(min_amount) / Decimal(per_unit))
                        else:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. "\
                                "Try with different method."
                            await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                            return
                else:
                    min_amount = min_amount.replace(",", "")
                    min_amount = text_to_num(min_amount)
                    min_amount = truncate(float(min_amount), 12)
                    if min_amount is None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid given minimum amount."
                        await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                        return
                min_amount = float(min_amount)
                # step_amount
                if "$" in step_amount[-1] or "$" in step_amount[0]:  # last is $
                    # Check if conversion is allowed for this coin.
                    step_amount = step_amount.replace(",", "").replace("$", "")
                    price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                    if price_with is None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this __{coin_name}__."
                        await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                        return
                    else:
                        per_unit = await self.utils.get_coin_price(coin_name, price_with)
                        if per_unit and per_unit['price'] and per_unit['price'] > 0:
                            per_unit = per_unit['price']
                            step_amount = float(Decimal(step_amount) / Decimal(per_unit))
                        else:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. "\
                                "Try with different method."
                            await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                            return
                else:
                    step_amount = step_amount.replace(",", "")
                    step_amount = text_to_num(step_amount)
                    step_amount = truncate(float(step_amount), 12)
                    if step_amount is None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid given minimum amount."
                        await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                        return
                step_amount = float(step_amount)

                if min_amount < min_bid_start:
                    msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, you need to set minimum amount at least {num_format_coin(min_bid_start)} {coin_name}.'
                    await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                    return

                if step_amount < min_bid_lap:
                    msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, you need to set minimum step amount at least {num_format_coin(min_bid_lap)} {coin_name}.'
                    await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                    return

                if step_amount > min_amount:
                    msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, minimum amount must be bigger than step amount.'
                    await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                    return

                title = title.strip()
                if len(title) <= 3 or len(title) > 128:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, the title is too short or too long. "\
                        "You need more than 3 chars and less than 128 chars."
                    await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                    return
                duration = int(duration.replace("H", ""))*3600 # in seconds
                try:
                    # download attachment first
                    res_data = None
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(str(attachment), timeout=32) as response:
                                if response.status == 200:
                                    res_data = await response.read()
                                    hash_object = hashlib.sha256(res_data)
                                    hex_dig = str(hash_object.hexdigest())
                                    mime_type = magic.from_buffer(res_data, mime=True)
                                    if mime_type not in self.file_accept:
                                        msg = f"{ctx.author.mention}, the uploaded media is not a supported file."
                                        await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                                        return
                                    else:
                                        # Write the stuff
                                        saved_name = random_string + "_" + hex_dig + "." + mime_type.split("/")[1]
                                        with open(self.bid_storage + saved_name, "wb") as f:
                                            f.write(BytesIO(res_data).getbuffer())
                                            # web path: self.bid_web_path + saved_name
                                            file_saved = True
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            except Exception:
                traceback.print_exc(file=sys.stdout)
            if file_saved is True:
                bid_open_time = int(time.time()) + duration
                if bid_open_time <= int(time.time()):
                    return
                status = "ONGOING"
                owner_displayname = "{}#{}".format(ctx.author.name, ctx.author.discriminator)
                embed = disnake.Embed(
                    title="NEW BID",
                    description=title,
                    timestamp=datetime.fromtimestamp(bid_open_time)
                )
                embed.add_field(
                    name='Started amount',
                    value=num_format_coin(min_amount) + " " + coin_name,
                    inline=True
                )
                # step_amount
                embed.add_field(
                    name='Step amount',
                    value=num_format_coin(step_amount) + " " + coin_name,
                    inline=True
                )
                bid_note = self.bot.config['bidding']['bid_note']
                if self.bot.config['bidding']['bid_collecting_fee'] > 0:
                    bid_note += " There will be {:,.2f}{} charged for each successful bid.".format(
                        self.bot.config['bidding']['bid_collecting_fee']*100, "%"
                    )

                embed.add_field(
                    name='Note',
                    value=bid_note,
                    inline=False
                )
                time_left = seconds_str_days(duration)
                link = self.bot.config['bidding']['web_path'] + saved_name
                if ctx.guild.icon:
                    embed.set_thumbnail(url=str(ctx.guild.icon))
                embed.set_image(url=link)
                embed.set_footer(text=f"Created by {owner_displayname} | /bid add | Time left: {time_left}")
                # Add embed. If adding embed is failed, Turn discord_bidding_list to cancel
                view = BidButton(
                    duration, self.bot.coin_list, self.bot,
                    ctx.channel.id, ctx.author.id, coin_name, min_amount, step_amount,
                    title, None
                )
                msg = await ctx.channel.send(content=None, embed=embed, view=view)
                view.message = msg
                view.channel_interact = ctx.channel.id
                await self.utils.bid_add_new(
                    title, coin_name, contract, coin_decimal, str(ctx.author.id),
                    "{}#{}".format(ctx.author.name, ctx.author.discriminator), msg.id, channel_id,
                    guild_id, ctx.guild.name, min_amount, step_amount, int(time.time()), bid_open_time, status, original_name,
                    saved_name, mime_type, hex_dig
                )
                await ctx.edit_original_message(content="/bid add 👇")
                await log_to_channel(
                    "bid",
                    f"[NEW BID CREATED]: User {ctx.author.mention} created a new bid. Time <t:{bid_open_time}:R> (<t:{bid_open_time}:f>). "\
                    f"Started amount: {num_format_coin(min_amount)} {coin_name} and "\
                    f"step amount: {num_format_coin(step_amount)} {coin_name}"\
                    f" Ref: {str(view.message.id)} / Guild name: {ctx.guild.name}!",
                    self.bot.config['discord']['bid_webhook']
                )
            else:
                msg = f"{ctx.author.mention}, internal error."
                await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
                return
        except disnake.errors.Forbidden:
            await ctx.edit_original_message(content="Missing permission! Or failed to send embed message.", view=RowButtonRowCloseAnyMessage())
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @bidding_add_new.autocomplete("coin")
    async def pbid_add_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

    @bid.sub_command(
        name="view",
        usage="bid view <bid id>", 
        options=[
            Option('bid_id', 'bidding reference ID', OptionType.string, required=True),
        ],
        description="Show some information about bidding by ID."
    )
    async def bid_view(
        self, 
        ctx,
        bid_id: str
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, loading..."
        await ctx.response.send_message(msg, ephemeral=True)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/bid view", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if ctx.author.id != self.bot.config['discord']['owner_id']:
            await ctx.edit_original_message(content="Permission denied or currently unavailable!")
            return

        try:
            get_message = await self.utils.get_bid_id(bid_id)
            if get_message is None:
                await ctx.edit_original_message(content=f"I can't find bid message ID: {bid_id}")
                return
            get_message = await self.utils.get_bid_id(get_message['message_id'])
            attend_list = await self.utils.get_bid_attendant(get_message['message_id'])
            owner_displayname = get_message['username']
            coin_name = get_message['token_name']
            coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
            coin_emoji = coin_emoji + " " if coin_emoji else ""
            min_amount = get_message['minimum_amount']

            duration = get_message['bid_open_time'] - int(time.time())
            if get_message['bid_extended_time'] is not None:
                duration = get_message['bid_extended_time'] - int(time.time())
            if duration < 0:
                duration = 0

            time_left = seconds_str_days(duration)
            list_joined = []
            list_joined_key = []
            try:
                channel = self.bot.get_channel(int(get_message['channel_id']))
                if channel is None:
                    await ctx.edit_original_message(content="Currently unavailable!")
                    return
                else:
                    _msg: disnake.Message = await channel.fetch_message(int(get_message['message_id']))
                    embed = _msg.embeds[0] # embeds is list, we take 0
                    embed.clear_fields()
                    embed.add_field(
                        name='Started amount',
                        value=num_format_coin(min_amount) + " " + coin_name,
                        inline=True
                    )
                    # min_bid_lap
                    step_amount = get_message['step_amount']
                    if step_amount is None:
                        step_amount = getattr(getattr(self.bot.coin_list, coin_name), "min_bid_lap")
                    embed.add_field(
                        name='Step amount',
                        value=num_format_coin(step_amount) + " " + coin_name,
                        inline=True
                    )
                    link = self.bot.config['bidding']['web_path'] + get_message['saved_name']
                    embed.set_image(url=link)
                    embed.set_footer(text=f"Created by {owner_displayname} | /bid add | Time left: {time_left}")
                    if duration <= 0:
                        embed.set_footer(text=f"Created by {owner_displayname} | /bid add | Ended!")
                    if len(attend_list) > 0:
                        for i in attend_list:
                            if i['user_id'] not in list_joined_key:
                                list_joined_key.append(i['user_id'])
                                list_joined.append("<@{}>: {} {}".format(i['user_id'], num_format_coin(i['bid_amount']), coin_name))
                            if len(list_joined) > 0 and len(list_joined) % 15 == 0:
                                embed.add_field(name='Bidder(s)', value="\n".join(list_joined), inline=False)
                                list_joined = []
                        if len(list_joined) > 0:
                            embed.add_field(name='Bidder(s)', value="\n".join(list_joined), inline=False)
                    if get_message['number_extension'] > 0:
                        embed.add_field(name='Number of Extension', value="{}".format(get_message['number_extension']), inline=True)
                    bid_note = self.bot.config['bidding']['bid_note']
                    if self.bot.config['bidding']['bid_collecting_fee'] > 0:
                        bid_note += " There will be {:,.2f}{} charged for each successful bid.".format(
                            self.bot.config['bidding']['bid_collecting_fee']*100, "%"
                        )

                    status_msg = "ONGOING"
                    if get_message['status'] == "CANCELLED":
                        status_msg = "CANCELLED"
                    elif get_message['winner_user_id'] is not None and get_message['winner_instruction'] is None:
                        status_msg = "Waiting for winner's information."
                    elif get_message['winner_user_id'] is not None and get_message['owner_respond'] is None:
                        status_msg = "Waiting for owner's update."
                    elif get_message['winner_user_id'] is not None and get_message['winner_confirmation_date'] is None:
                        status_msg = "Waiting for winner's final confirmation."
                    elif get_message['winner_confirmation_date'] is not None:
                        status_msg = "COMPLETED"
                    elif get_message['winner_user_id'] is not None:
                        status_msg = "UNKNOWN"
                    embed.add_field(
                        name='Status',
                        value=status_msg + " and created <t:{}:f>".format(get_message['message_time']),
                        inline=False
                    )
                    embed.add_field(
                        name='Guild {}/{}'.format(get_message['guild_name'], get_message['guild_id']),
                        value="Bid created by <@{}>".format(get_message['user_id']),
                        inline=False
                    )
                    embed.add_field(
                        name='Note',
                        value=bid_note,
                        inline=False
                    )
                    await ctx.edit_original_message(content=None, embed=embed)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @bid.sub_command(
        name="clearwinmenu",
        usage="bid clearwinmenu", 
        options=[
            Option('msg_id', 'Admin check', OptionType.string, required=True),
        ],
        description="Admin to clear a bid where there is a bug with menu."
    )
    async def bid_clear_win_menu(
        self, 
        ctx,
        msg_id: str
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, loading..."
        await ctx.response.send_message(msg, ephemeral=True)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/bid clearwinmenu", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        
        if ctx.author.id != self.bot.config['discord']['owner_id']:
            await ctx.edit_original_message(content="Permission denied!")
            return
        try:
            get_message = await self.utils.get_bid_id(msg_id)
            if get_message is None:
                await ctx.edit_original_message(content=f"I can't find message ID: {msg_id}")
                return
            elif get_message['status'] == "ONGOING":
                await ctx.edit_original_message(content="That bidding is still ONGOING.")
                return
            elif get_message['status'] == "CANCELLED":
                await ctx.edit_original_message(content="That bidding is already CANCELLED.")
                return
            elif get_message['status'] == "COMPLETED" and get_message['owner_respond'] is not None and get_message['winner_confirmation_date'] is not None:
                await ctx.edit_original_message(content="That bidding is already SETTLE and paid.")
                return
            elif get_message['status'] == "COMPLETED" and get_message['winner_confirmation_date'] is None:
                get_guild = self.bot.get_guild(int(get_message['guild_id']))
                if get_guild is None:
                    await ctx.edit_original_message(content=f"I can't find guild {get_message['guild_id']}.")
                    return
                else:
                    channel = get_guild.get_channel(int(get_message['channel_id']))
                    if channel is None:
                        await ctx.edit_original_message(content=f"I can't find guild {get_message['channel_id']}.")
                    else:
                        _msg: disnake.Message = await channel.fetch_message(int(get_message['message_id']))
                        if _msg:
                            await _msg.edit(view=None)
                            await ctx.edit_original_message(content=f"Done. Removed win menu fo {get_message['message_id']}.")
                        else:
                            await ctx.edit_original_message(content=f"Failed to fetch message {get_message['channel_id']}.")
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @bid.sub_command(
        name="myrecents",
        usage="bid myrecents", 
        options=[
            Option('member_id', 'Admin check', OptionType.string, required=False),
        ],
        description="Check your recent bid placing."
    )
    async def bid_myrecents(
        self, 
        ctx,
        member_id: str=None
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, loading..."
        await ctx.response.send_message(msg, ephemeral=True)
        if member_id is None:
            member_id = str(ctx.author.id)

        others = ""
        if member_id != str(ctx.author.id):
            others = " (Other's)"
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/bid myrecents", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        
        if member_id != str(ctx.author.id) and ctx.author.id != self.bot.config['discord']['owner_id']:
            await ctx.edit_original_message(content="Permission denied!")
            return
        else:
            try:
                user_bids = await self.utils.bidding_joined_by_userid(member_id, limit=25)
                user_logs = await self.utils.bidding_logs_by_userid(member_id, limit=25)
                embed = disnake.Embed(
                    title="TipBot's Bidding System",
                    description="Please join our Discord for support and other request.",
                    timestamp=datetime.now(),
                )
                embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
                embed.set_thumbnail(url=self.bot.user.display_avatar)
                if len(user_bids):
                    list_bid_items = []
                    for i in user_bids:
                        list_bid_items.append("⚆ <t:{}:f>-{}/{}\namount {} {}".format(
                            i['bid_time'], i['message_id'], i['status'], num_format_coin(i['bid_amount']), i['bid_coin']
                        ))
                    embed.add_field(
                        name="Recent Bids {}{}".format(member_id, others),
                        value="{}".format(
                            "\n".join(list_bid_items)[:1000]
                        ),
                        inline=False
                    )
                if len(user_logs) > 0:
                    list_logs_items = []
                    for i in user_logs:
                        list_logs_items.append("⚆ <t:{}:f>\n{}/{}".format(
                            i['time'], i['message_id'] if i['message_id'] else "N/A", i['type']
                        ))
                    embed.add_field(
                        name="Recent Activities {}{}".format(member_id, others),
                        value="{}".format(
                            "\n".join(list_logs_items)[:1000]
                        ),
                        inline=False
                    )
                await ctx.edit_original_message(content=None, embed=embed)
            except Exception:
                traceback.print_exc(file=sys.stdout)

    @bid.sub_command(
        name="list",
        usage="bid list [guild id]", 
        options=[
            Option('guild_id', 'Filter by guild id', OptionType.string, required=False),
        ],
        description="Admin to see all the list."
    )
    async def bid_list(
        self, 
        ctx,
        guild_id: str=None
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, loading..."
        await ctx.response.send_message(msg, ephemeral=True)
        if guild_id is None:
            guild_id = str(ctx.guild.id)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/bid list", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            if ctx.author.id != self.bot.config['discord']['owner_id']:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, permission denied!")
                return
            list_bids = await self.utils.bidding_list_by_guildid(guild_id)
            if len(list_bids) > 0:
                list_bid_items = []
                for i in list_bids:
                    list_bid_items.append("⚆ <t:{}:f>-{}/{}\nMin. amount {} {}".format(
                        i['message_time'], i['message_id'], i['status'], num_format_coin(i['minimum_amount']), i['token_name']
                    ))
                await ctx.edit_original_message(content="\n".join(list_bid_items))
            else:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, there is not any listing!")
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @bid.sub_command(
        name="viewreport",
        usage="bid viewreport [report id]", 
        options=[
            Option('report_id', 'Select report ID', OptionType.number, required=False),
        ],
        description="Admin to check report"
    )
    async def bid_report_list(
        self, 
        ctx,
        report_id: int=None
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, loading..."
        await ctx.response.send_message(msg, ephemeral=True)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/bid viewreport", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            if ctx.author.id != self.bot.config['discord']['owner_id']:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, permission denied!")
                return
            list_reps = await self.utils.bid_get_report(report_id)
            if report_id is None and len(list_reps) > 0:
                list_items = []
                for i in list_reps:
                    list_items.append("⚆ rep: {}/ref: {} <t:{}:f>".format(
                        i['report_id'], i['list_message_id'], i['time']
                    ))
                await ctx.edit_original_message(content="\n".join(list_items))
            elif report_id is not None and len(list_reps) > 0:
                report = list_reps[0]
                await ctx.edit_original_message(
                    content="Rep ID: {}/ID: {}\nTime: <t:{}:f>\nContent:\n{}\n-----------\n"\
                        "Contact:\n{}\n-----------\nReporter: <@{}>\nGuild Name: {}/{}".format(
                            report['report_id'], report['list_message_id'], report['time'],
                            report['reported_content'], report['how_to_contact'], report['user_id'],
                            report['guild_name'], report['guild_id']
                    )
                )
            elif report_id is not None:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, there is no such report id!")
            else:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, no report found!")
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.Cog.listener()
    async def on_ready(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.bidding_check.is_running():
                self.bidding_check.start()

    async def cog_load(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.bidding_check.is_running():
                self.bidding_check.start()

    def cog_unload(self):
        # Ensure the task is stopped when the cog is unloaded.
        self.bidding_check.cancel()


def setup(bot):
    bot.add_cog(Bidding(bot))
