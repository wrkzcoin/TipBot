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

import disnake
import store
from Bot import logchanbot, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_INFORMATION, SERVER_BOT, text_to_num, \
    truncate, seconds_str_days, log_to_channel
from cogs.wallet import WalletAPI
from disnake.app_commands import Option
from disnake.enums import ButtonStyle
from disnake.enums import OptionType
from disnake import TextInputStyle
from disnake.app_commands import Option, OptionChoice

from disnake.ext import commands, tasks
from cogs.utils import Utils, num_format_coin


class EditBid(disnake.ui.Modal):
    def __init__(self, ctx, bot, message_id: str, owner_userid: str, title: str) -> None:
        self.ctx = ctx
        self.bot = bot
        self.utils = Utils(self.bot)
        self.message_id = message_id
        self.owner_userid = owner_userid
        self.caption_new = title

        components = [
            disnake.ui.TextInput(
                label="Description",
                placeholder="Describe about it.",
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
                except Exception:
                    traceback.print_exc(file=sys.stdout)
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

            # Check if tx in progress
            if str(interaction.author.id) in self.bot.tipping_in_progress and \
                int(time.time()) - self.bot.tipping_in_progress[str(interaction.author.id)] < 150:
                msg = f"{EMOJI_ERROR} {interaction.author.mention}, you have another transaction in progress."
                await interaction.edit_original_message(content=msg)
                return

            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
            userdata_balance = await store.sql_user_balance_single(
                str(interaction.author.id), coin_name, wallet_address,
                type_coin, height, deposit_confirm_depth, SERVER_BOT
            )
            actual_balance = float(userdata_balance['adjust'])
            if amount <= 0:
                msg = f"{EMOJI_RED_NO} {interaction.author.mention}, please get more {token_display}."
                await interaction.edit_original_message(content=msg)
                return
            elif amount > actual_balance:
                msg = f"{EMOJI_RED_NO} {self.ctx.author.mention}, insufficient balance to place a bid of "\
                    f"**{num_format_coin(amount)} {token_display}**."
                await interaction.edit_original_message(content=msg)
                return
            elif amount < current_max:
                msg = f"{EMOJI_RED_NO} {self.ctx.author.mention}, bid amount can't be smaller than "\
                    f"**{num_format_coin(current_max)} {token_display}**."
                await interaction.edit_original_message(content=msg)
                return

            try:
                # get his previous bid amount
                previous_bid = 0.0
                additional_bid_amount = amount
                try:
                    key = str(self.message_id) + "_" + str(interaction.author.id)
                    previous_bid = self.utils.get_cache_kv(
                        "bidding_amount",
                        key
                    )
                    if previous_bid and previous_bid > 0:
                        additional_bid_amount = amount - previous_bid
                    self.utils.set_cache_kv(
                        "bidding_amount",
                        key,
                        amount
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                if additional_bid_amount < 0:
                    msg = f"{EMOJI_INFORMATION} {self.ctx.author.mention}, internal error with a new amount {num_format_coin(amount)} {coin_name}!"
                    await interaction.edit_original_message(content=msg)
                    return
                adding_bid = await self.utils.bid_new_join(
                    str(self.message_id), str(interaction.author.id), "{}#{}".format(interaction.author.name, interaction.author.discriminator),
                    amount, coin_name, str(interaction.guild.id), str(interaction.channel.id), SERVER_BOT, additional_bid_amount
                )
                # remove cache
                try:
                    key = str(interaction.author.id) + "_" + coin_name + "_" + SERVER_BOT
                    if key in self.bot.user_balance_cache:
                        del self.bot.user_balance_cache[key]
                except Exception:
                    pass
                if adding_bid:
                    msg = f"{EMOJI_INFORMATION} {self.ctx.author.mention}, successfully placing a bid with a new amount {num_format_coin(amount)} {coin_name}!"
                    await interaction.edit_original_message(content=msg)
                    try:
                        get_message = await self.utils.get_bid_id(str(self.message_id))
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
                        await _msg.edit(content=None, embed=embed)
                        await log_to_channel(
                            "bid",
                            f"[NEW BID]: User {interaction.author.mention} joined/updated a bid in Guild ID: {interaction.guild.name} / {interaction.guild.id}. "\
                            f"Ref: {self.message_id} and new amount {num_format_coin(amount)} {coin_name}.",
                            self.bot.config['discord']['bid_webhook']
                        )
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
            if get_message['winner_instruction'] is None and self.method_for == "winner" and interaction.author.id != self.winner_user_id:
                await interaction.edit_original_message(f"{interaction.author.mention}, you clicked on wrong button!")
                return
            elif get_message['owner_respond'] is None and self.method_for == "owner" and interaction.author.id != self.owner_userid:
                await interaction.edit_original_message(f"{interaction.author.mention}, you clicked on wrong button!")
                return
            elif get_message['winner_instruction'] is not None and self.method_for == "winner" and interaction.author.id in [self.owner_userid, self.winner_user_id, self.bot.config['discord']['owner_id']]:
                await interaction.edit_original_message(f"{interaction.author.mention}, winner's input:\n\n{get_message['winner_instruction']}")
                return
            elif get_message['owner_respond'] is not None and self.method_for == "owner" and interaction.author.id in [self.owner_userid, self.winner_user_id, self.bot.config['discord']['owner_id']]:
                await interaction.edit_original_message(f"{interaction.author.mention}, owner's input:\n\n{get_message['owner_respond']}")
                return
            # check if input already
            get_message = await self.utils.get_bid_id(str(self.message_id))
            if get_message['winner_instruction'] is None and self.method_for == "owner":
                await interaction.edit_original_message(f"{interaction.author.mention}, please inform to winner to update his delivery method first!")
                return
            elif get_message['winner_instruction'] is None and self.method_for == "winner":
                await self.utils.update_bid_winner_instruction(
                    str(self.message_id), instruction, self.method_for, None, None
                )
                # find owner to message
                try:
                    owner_user = self.bot.get_user(self.owner_userid)
                    if owner_user is not None:
                        await owner_user.send(
                            f"One of your bidding winner for `{str(self.message_id)}` at guild `{get_message['guild_name']}` updated an "\
                            f"instruction/information as the following:\n\n{instruction}"
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
                    False, False, True
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
                await self.utils.update_bid_winner_instruction(
                    str(self.message_id), instruction, self.method_for, None, None
                )
                # find winner to message
                try:
                    winner_user = self.bot.get_user(self.winner_user_id)
                    if winner_user is not None:
                        await winner_user.send(
                            f"You win one of bidding id `{str(self.message_id)}` at guild `{get_message['guild_name']}`. Owner just updated "\
                            f"instruction/information as the following:\n\n{instruction}"
                        )
                        await interaction.edit_original_message(f"{interaction.author.mention}, we updated your input and notified the winner.")
                    else:
                        await interaction.edit_original_message(f"{interaction.author.mention}, we updated your input and but we failed to find the winner user!")
                except disnake.errors.Forbidden:
                    await interaction.edit_original_message(f"{interaction.author.mention}, we updated your input but we failed "\
                                                            f"to message to the winner. Please inform him/her.")
                view = ClearButton(
                    self.bot.coin_list, self.bot,
                    interaction.channel.id, int(self.bid_info['user_id']), int(self.winner_user_id),
                    self.winner_amount, self.bid_info,
                    False, False, False
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
        complete_btn: bool=True
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


    @disnake.ui.button(label="1️⃣ Winner Click", style=ButtonStyle.primary, custom_id="bidding_clearbtn_winner_input")
    async def winner_input(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        if interaction.author.id != self.winner_id:
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
        if interaction.author.id != self.owner_id:
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
                payment_list_msg.append(f"Processing deduct from winner (Done during bidding): {num_format_coin(self.winner_amount)} {self.bid_info['token_name']}")
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
                payment_list_msg.append(f"Processing to bid owner: {num_format_coin(remaining)} {self.bid_info['token_name']}")
                await self.utils.update_bid_winner_instruction(
                    str(self.bid_info['message_id']), "placeholder", "final",
                    payment_list, payment_logs
                )
                payment_list_msg = "\n".join(payment_list_msg)
                for i in [self.bid_info['user_id'], str(self.winner_id)]:
                    key = i + "_" + self.bid_info['token_name'] + "_" + SERVER_BOT
                    try:
                        if i in self.bot.user_balance_cache:
                            del self.bot.user_balance_cache[i]
                    except Exception:
                        pass
                await self.message.edit(view=self)
                await log_to_channel(
                    "bid",
                    f"[BID COMPLETED]: User {interaction.author.mention} marked the bid as completed. "\
                    f"Ref: {self.bid_info['message_id']} and at Guild name: {self.bid_info['guild_name']} / {self.bid_info['guild_id']}!\n{payment_list_msg}",
                    self.bot.config['discord']['bid_webhook']
                )
                await interaction.edit_original_message(f"{interaction.author.mention}, Completed!")
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
        self, ctx, timeout, coin_list, bot, channel_interact,
        owner_id: int, coin_name: str, min_amount: float, step_amount: float,
        title: str
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.coin_list = coin_list
        self.ctx = ctx
        self.channel_interact = channel_interact
        self.owner_id = owner_id
        self.coin_name = coin_name
        self.min_amount = min_amount
        self.step_amount = step_amount
        self.caption_new = title

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

    @disnake.ui.button(label="Place Bid", style=ButtonStyle.primary, custom_id="bidding_place_bid")
    async def bid_place(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        if interaction.author.id == self.owner_id and self.bot.config['bidding']['allow_own_bid'] != 1:
            await interaction.response.send_message(f"{interaction.author.mention}, you can't bid on your own!", delete_after=5.0)
        else:
            # set status to cancelled, log, refund to all bidders.
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
            # set status to cancelled, log, refund to all bidders.
            try:
                await interaction.response.send_modal(
                    modal=EditBid(interaction, self.bot, self.message.id, self.owner_id, self.caption_new))
            except disnake.errors.NotFound:
                await interaction.response.send_message(f"{interaction.author.mention}, failed to retreive bidding information! Try again later!", ephemeral=True)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    @disnake.ui.button(label="Cancel", style=ButtonStyle.danger, custom_id="bidding_cancel")
    async def bid_cancel(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not your listing!", ephemeral=True)
        else:
            await interaction.response.send_message(f"{interaction.author.mention}, checking cancellation!", ephemeral=True)
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
                    if len(list_key_update) > 0:
                        for i in list_key_update:
                            try:
                                if i in self.bot.user_balance_cache:
                                    del self.bot.user_balance_cache[i]
                            except Exception:
                                pass
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
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    await interaction.edit_original_message(f"{interaction.author.mention}, successfully cancelled!")
                else:
                    await interaction.edit_original_message(f"{interaction.author.mention}, internal error!")
            except disnake.errors.NotFound:
                await interaction.edit_original_message(f"{interaction.author.mention}, failed to retreive bidding information! Try again later!", ephemeral=True)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

class Bidding(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.max_ongoing_by_user = 3
        self.max_ongoing_by_guild = 5
        self.bidding_cache = TTLCache(maxsize=2000, ttl=60.0) # if previous value and new value the same, no need to edit
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

        self.file_accept = ["image/jpeg", "image/gif", "image/png"]
        self.bid_storage = "./discordtip_v2_bidding/"
        self.bid_web_path = self.bot.config['bidding']['web_path']
        self.bid_channel_upload = self.bot.config['bidding']['upload_channel_log']

    @tasks.loop(seconds=15.0)
    async def bidding_check(self):
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "bidding_check"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 5: # not running if less than 15s
            return
        try:
            get_list_bids = await self.utils.get_all_bids("ONGOING")
            if len(get_list_bids) > 0:
                for each_bid in get_list_bids:
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
                                        for i in list_key_update:
                                            try:
                                                if i in self.bot.user_balance_cache:
                                                    del self.bot.user_balance_cache[i]
                                            except Exception:
                                                pass
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
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                continue
                        except Exception:
                            traceback.print_exc(file=sys.stdout)

                        if each_bid['bid_open_time'] < int(time.time()):
                            try:
                                msg_owner = ""
                                if len(attend_list) == 0:
                                    await _msg.edit(content=None, embed=embed, view=None)
                                    await self.utils.update_bid_no_winning(each_bid['message_id'])
                                    # notify owner, no winner
                                    msg_owner = "One of your bidding is completed! "\
                                        "There is no winner for bidding `{}` in guild `{}`.".format(each_bid['message_id'], each_bid['guild_name'])
                                    await log_to_channel(
                                        "bid",
                                        f"[BIDDING CLOSED]: Guild {each_bid['guild_name']} / {each_bid['guild_id']} closed a bid {each_bid['message_id']} and no on bid.",
                                        self.bot.config['discord']['bid_webhook']
                                    )
                                else:
                                    refund_list = []
                                    list_key_update = []
                                    payment_logs = []
                                    if len(attend_list) > 1:
                                        for i in attend_list[:1]: # starting from 2nd one
                                            refund_list.append((
                                                i['user_id'], i['bid_coin'], SERVER_BOT, i['bid_amount'], int(time.time())
                                            ))
                                            list_key_update.append(i['user_id'] + "_" + i['bid_coin'] + "_" + SERVER_BOT)
                                            payment_logs.append((
                                                "REFUND", self.bid_info['message_id'], i['user_id'],
                                                self.bid_info['guild_id'], self.bid_info['channel_id'], int(time.time()),
                                                num_format_coin(i['bid_amount'])
                                            ))
                                    if len(list_key_update) > 0:
                                        for i in list_key_update:
                                            try:
                                                if i in self.bot.user_balance_cache:
                                                    del self.bot.user_balance_cache[i]
                                            except Exception:
                                                pass
                                    # check if there is winner or no one join
                                    view = ClearButton(
                                        self.bot.coin_list, self.bot,
                                        channel.id, int(each_bid['user_id']), int(attend_list[0]['user_id']),
                                        attend_list[0]['bid_amount'], each_bid,
                                        False, True, True
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
                                        "User `{}` is the winner for bidding `{}` in guild `{}`.".format(
                                        attend_list[0]['user_id'], each_bid['message_id'], each_bid['guild_name']
                                    )
                                    await log_to_channel(
                                        "bid",
                                        f"[BIDDING CLOSED]: {each_bid['guild_name']} / {each_bid['guild_id']} closed a bid {each_bid['message_id']}. "\
                                        f"Winner <@{attend_list[0]['user_id']}>, amount {attend_list[0]['bid_amount']} {each_bid['token_name']}",
                                        self.bot.config['discord']['bid_webhook']
                                    )
                                try:
                                    get_owner = self.bot.get_user(int(each_bid['user_id']))
                                    if get_owner is not None and len(msg_owner) > 0:
                                        await get_owner.send(msg_owner)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                        else:
                            try:
                                if _msg is not None:
                                    await _msg.edit(content=None, embed=embed)
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
        if self.bot.config['bidding']['enable'] == 0 and ctx.author.id not in self.bot.config['bidding']['testers']:
            await ctx.response.send_message(content=f"{ctx.author.mention}, create public bidding is not enable yet!")
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

        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        # Check if there is many airdrop/mathtip/triviatip/partydrop
        try:
            count_ongoing = await self.utils.discord_bid_ongoing(str(ctx.guild.id), "ONGOING")
            # Check max if set in guild
            if serverinfo and count_ongoing >= serverinfo['max_ongoing_bid'] and ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, there are still some ongoing bids in this guild. Please wait for them to complete first!'
                await ctx.edit_original_message(content=msg)
                return
            elif serverinfo is None and count_ongoing >= self.max_ongoing_by_guild and ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, there are still some ongoing bids in this guild. Please wait for them to complete first!'
                await ctx.edit_original_message(content=msg)
                await logchanbot(f"[BIDDING] server {str(ctx.guild.id)} has no data in discord_server.")
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # End of ongoing check

        coin_name = coin.upper()
        contract = None
        coin_decimal = 0
        try:
            guild_id = str(ctx.guild.id)
            channel_id = (ctx.channel.id)
            file_saved = False
            saved_name = None
            original_name = str(attachment).split("/")[-1]
            random_string = str(uuid.uuid4())
            try:
                
                if not hasattr(self.bot.coin_list, coin_name):
                    msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
                    await ctx.edit_original_message(content=msg)
                    return
                bid_enable = getattr(getattr(self.bot.coin_list, coin_name), "bid_enable")
                if bid_enable != 1:
                    msg = f"{ctx.author.mention}, **{coin_name}** not enable with bidding. Contact TipBot dev"
                    await ctx.edit_original_message(content=msg)
                    return
                min_bid_start = getattr(getattr(self.bot.coin_list, coin_name), "min_bid_start")
                min_bid_lap = getattr(getattr(self.bot.coin_list, coin_name), "min_bid_lap")
                usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")
                contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                # min_amount
                if "$" in min_amount[-1] or "$" in min_amount[0]:  # last is $
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
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. "\
                                "Try with different method."
                            await ctx.edit_original_message(content=msg)
                            return
                else:
                    min_amount = min_amount.replace(",", "")
                    min_amount = text_to_num(min_amount)
                    min_amount = truncate(float(min_amount), 12)
                    if min_amount is None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid given minimum amount."
                        await ctx.edit_original_message(content=msg)
                        return
                min_amount = float(min_amount)
                # step_amount
                if "$" in step_amount[-1] or "$" in step_amount[0]:  # last is $
                    # Check if conversion is allowed for this coin.
                    step_amount = step_amount.replace(",", "").replace("$", "")
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
                            step_amount = float(Decimal(step_amount) / Decimal(per_unit))
                        else:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. "\
                                "Try with different method."
                            await ctx.edit_original_message(content=msg)
                            return
                else:
                    step_amount = step_amount.replace(",", "")
                    step_amount = text_to_num(step_amount)
                    step_amount = truncate(float(step_amount), 12)
                    if step_amount is None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid given minimum amount."
                        await ctx.edit_original_message(content=msg)
                        return
                step_amount = float(step_amount)

                if min_amount < min_bid_start:
                    msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, you need to set minimum amount at least {num_format_coin(min_bid_start)} {coin_name}.'
                    await ctx.edit_original_message(content=msg)
                    return

                if step_amount < min_bid_lap:
                    msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, you need to set minimum step amount at least {num_format_coin(min_bid_lap)} {coin_name}.'
                    await ctx.edit_original_message(content=msg)
                    return

                if step_amount > min_amount:
                    msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, minimum amount must be bigger than step amount.'
                    await ctx.edit_original_message(content=msg)
                    return

                title = title.strip()
                if len(title) <= 3 or len(title) > 128:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, the title is too short or too long. "\
                        "You need more than 3 chars and less than 128 chars."
                    await ctx.edit_original_message(content=msg)
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
                                        await ctx.edit_original_message(content=msg)
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
                    ctx, duration, self.bot.coin_list, self.bot,
                    ctx.channel.id, ctx.author.id, coin_name, min_amount, step_amount,
                    title
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
                await ctx.edit_original_message(content=msg)
                return
        except disnake.errors.Forbidden:
            await ctx.edit_original_message(content="Missing permission! Or failed to send embed message.")
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
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/bid view", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            pass
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @bid.sub_command(
        name="myrecents",
        usage="bid myrecents", 
        description="Check your recent bid placing."
    )
    async def bid_myrecents(
        self, 
        ctx, 
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/bid myrecents", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            pass
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
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/bid list", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            if ctx.author.id != self.bot.config['discord']['owner_id']:
                await ctx.response.send_message(content=f"{ctx.author.mention}, permission denied!")
                return
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
