import sys, traceback
from aiohttp import web
import aiohttp
import json
import asyncio
from cachetools import TTLCache

import disnake
from disnake.ext import commands, tasks
from typing import Optional
from decimal import Decimal
from datetime import datetime
import time
from string import ascii_uppercase
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

import store
from Bot import get_token_list, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, \
    EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, RowButtonCloseMessage, RowButtonRowCloseAnyMessage, human_format, \
    text_to_num, truncate, seconds_str, EMOJI_HOURGLASS_NOT_DONE, EMOJI_INFORMATION, log_to_channel, \
    encrypt_string, decrypt_string

from cogs.wallet import WalletAPI
from cogs.utils import Utils, num_format_coin, chunks


async def nanswap_get_pendings(status: str="ONGOING"):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `nanswap_trades`
                WHERE `status`=%s
                """
                await cur.execute(sql, status)
                result = await cur.fetchall()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def nanswap_credit(
    coin_family: str, coin_name: str, user_id: str, user_server: str,
    from_address: str, to_address: str, amount: float, decimal: int, tx_hash: str, json_data: str,
    amountFrom: float, amountTo: float, nanswap_id: str
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                UPDATE `nanswap_trades`
                SET `status`=%s, `json_complete`=%s, `amountFrom`=%s, `amountTo`=%s
                WHERE `nanswap_id`=%s LIMIT 1;
                """
                data_rows = [
                    "COMPLETED", json_data, amountFrom, amountTo, nanswap_id
                ]
                if coin_family == "NANO":
                    sql += """
                    INSERT INTO `nano_move_deposit` 
                    (`coin_name`, `user_id`, `balance_wallet_address`, 
                    `to_main_address`, `amount`, `decimal`, `block`, 
                    `time_insert`, `user_server`, `remark`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    data_rows += [
                        coin_name, user_id, from_address, to_address,
                        amount, decimal, tx_hash, int(time.time()), user_server,
                        "nanswap: {}".format(json_data)
                    ]
                await cur.execute(sql, tuple(data_rows))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def nanswap_create_order(
    coin_name: str, user_id: str, user_server: str, from_amount: float, from_decimal: int, to_address: str, tx_hash: str,
    nanswap_id: str, expectedAmountFrom: float, expectedAmountTo: float, amountFrom: float, amountTo: float,
    payinAddress: str, payoutAddress: str, from_coin: str, to_coin: str, json_order: str
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = ""
                data_rows = []
                status = "ONGOING"
                if tx_hash is None:
                    status = "FAILED"

                if tx_hash is not None:
                    if coin_name in ["BAN", "XDG", "XNO"]:
                        # add to nano_external_tx
                        sql += """
                        INSERT INTO nano_external_tx 
                        (`coin_name`, `user_id`, user_server, `amount`, `decimal`, `to_address`, `date`, `tx_hash`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                        """
                        data_rows += [
                            coin_name, user_id, user_server, from_amount, from_decimal, to_address, int(time.time()), tx_hash
                        ]
                sql += """
                INSERT INTO `nanswap_trades` 
                (`nanswap_id`, `expectedAmountFrom`, `expectedAmountTo`, `amountFrom`,
                `amountTo`, `payinAddress`, `payoutAddress`, `from_coin`,
                `to_coin`, `user_id`, `user_server`, `create_time`, `json_order`, `status`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                data_rows += [
                    nanswap_id, expectedAmountFrom, expectedAmountTo, amountFrom,
                    amountTo, payinAddress, payoutAddress, from_coin,
                    to_coin, user_id, user_server, int(time.time()), json_order, status
                ]
                await cur.execute(sql, tuple(data_rows))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def nanswap_get_create_order(data, api_key: str, timeout: int=30):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.nanswap.com/v1/create-order",
                json=data,
                headers={'nanswap-api-key': api_key, 'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.json()
                    return res_data
    except asyncio.TimeoutError:
        await logchanbot(
            "nanswap_get_create_order timeout: {}, data: {}".format(timeout, data)
        )
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def nanswap_get_estimate(from_coin: str, to_coin: str, amount: float, timeout: int=30):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.nanswap.com/v1/get-estimate?from="+from_coin+"&to="+to_coin+"&amount="+str(amount),
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.json()
                    return res_data
    except asyncio.TimeoutError:
        await logchanbot(
            "nanswap_get_estimate timeout: {}".format(timeout)
        )
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def nanswap_get_estimate_rev(from_coin: str, to_coin: str, amount: float, timeout: int=30):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.nanswap.com/v1/get-estimate-reverse?from="+from_coin+"&to="+to_coin+"&amount="+str(amount),
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.json()
                    return res_data
    except asyncio.TimeoutError:
        await logchanbot(
            "nanswap_get_estimate timeout: {}".format(timeout)
        )
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def nanswap_get_limit(from_coin: str, to_coin: str, timeout: int=30):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.nanswap.com/v1/get-limits?from="+from_coin+"&to="+to_coin,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.json()
                    return res_data
    except asyncio.TimeoutError:
        await logchanbot(
            "nanswap_get_limit timeout: {}".format(timeout)
        )
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def nanswap_check_id(id_str: str, timeout: int=30):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.nanswap.com/v1/get-order?id="+id_str,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.json()
                    return res_data
    except asyncio.TimeoutError:
        await logchanbot(
            "nanswap_check_id timeout: {}".format(timeout)
        )
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None



class ConfirmSell(disnake.ui.View):
    def __init__(self, bot, owner_id: int):
        super().__init__(timeout=30.0)
        self.value: Optional[bool] = None
        self.bot = bot
        self.owner_id = owner_id

    @disnake.ui.button(label="Confirm", emoji="✅", style=disnake.ButtonStyle.green)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.response.defer()
            return
        else:
            if str(inter.author.id) in self.bot.tipping_in_progress and \
                int(time.time()) - self.bot.tipping_in_progress[str(inter.author.id)] < 30:
                await inter.response.send_message(
                    content=f"{EMOJI_ERROR} {inter.author.mention}, you have another transaction in progress.",
                    ephemeral=True
                )
                return
            else:
                self.bot.tipping_in_progress[str(inter.author.id)] = int(time.time())
            self.value = True
            self.stop()
            await inter.response.defer()

    @disnake.ui.button(label="Cancel", emoji="❌", style=disnake.ButtonStyle.grey)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.response.defer()
            return
        else:
            self.value = False
            self.stop()
            await inter.response.defer()

class Nanswap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.botLogChan = None
        self.enable_logchan = True

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    @commands.slash_command(
        name="nanswap",
        description="Trading crypto with Nanswap."
    )
    async def nanswap(self, ctx):
        await self.bot_log()
        try:
            if self.bot.config['nanswap']['is_private'] == 1 and ctx.author.id not in self.bot.config['nanswap']['private_user_list']:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, this command is not public yet. "\
                    "Please try again later!"
                await ctx.response.send_message(msg)
                return
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                if serverinfo and 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "NO":
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, nanswap function is not ENABLE yet in this guild. "\
                        "Please request Guild owner to enable by `/SETTING TRADE`"
                    await ctx.response.send_message(msg)
                    if self.enable_logchan:
                        await self.botLogChan.send(
                            f"{ctx.author.name} / {ctx.author.id} tried /nanswap command** in "\
                            f"{ctx.guild.name} / {ctx.guild.id} which is not ENABLE."
                        )
                    return
                elif serverinfo and serverinfo['trade_channel'] is not None and \
                    int(serverinfo['trade_channel']) != ctx.channel.id and ctx.author.id != self.bot.config['discord']['owner']:
                    channel = ctx.guild.get_channel(int(serverinfo['trade_channel']))
                    if channel is not None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, nanswap/trade channel was assigned to {channel.mention}."
                        await ctx.response.send_message(msg)
            is_user_locked = self.utils.is_locked_user(str(ctx.author.id), SERVER_BOT)
            if is_user_locked is True:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, your account is locked for using the Bot. Please contact bot dev by /about link."
                await ctx.response.send_message(msg)
                return
            if self.bot.config['nanswap']['disable'] == 1 and ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, Nanswap is currently on maintenance. Be back soon!"
                await ctx.response.send_message(msg)
                return
        except Exception:
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                return

    @nanswap.sub_command(
        name="intro",
        usage="nanswap intro",
        description="Introduction of /nanswap."
    )
    async def nanswap_intro(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /nanswap loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/nanswap intro", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            embed = disnake.Embed(
                title="TipBot's 3rd party swap with Nanswap",
                description=f"{ctx.author.mention}, You can join our supported guild for #help.",
                timestamp=datetime.now(),
            )
            embed.add_field(
                name="BRIEF",
                value=self.bot.config['nanswap']['brief_msg'],
                inline=False
            )        
            embed.add_field(
                name="NOTE",
                value=self.bot.config['nanswap']['note_msg'],
                inline=False
            )
            embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
            embed.set_thumbnail(url=self.bot.user.display_avatar)
            await ctx.edit_original_message(content=None, embed=embed)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @nanswap.sub_command(
        name="sell",
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('sell_token', 'sell_token', OptionType.string, required=True),
            Option('for_token', 'for_token', OptionType.string, required=True),
        ],
        usage="nanswap sell <amount> <token> <for token>",
        description="Sell an amount of coins for another."
    )
    async def nanswap_sell(
        self,
        ctx,
        amount: str,
        sell_token: str,
        for_token: str
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /nanswap loading..."
        await ctx.response.send_message(msg)
        sell_amount_old = amount

        sell_token = sell_token.upper()
        for_token = for_token.upper()

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/nanswap sell", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if sell_token == for_token:
            msg = f"{EMOJI_ERROR}, {ctx.author.mention}, you cannot do /nanswap for the same token."
            await ctx.edit_original_message(content=msg)
            return

        # check if enable in Nanswap
        if sell_token not in self.bot.config['nanswap']['coin_list']:
            msg = f"{EMOJI_ERROR}, {ctx.author.mention}, __{sell_token}__ is not available in our /nanswap right now."
            await ctx.edit_original_message(content=msg)
            return
        if for_token not in self.bot.config['nanswap']['coin_list']:
            msg = f"{EMOJI_ERROR}, {ctx.author.mention}, __{for_token}__ is not available in our /nanswap right now."
            await ctx.edit_original_message(content=msg)
            return
        # Check min./max. through 3rd party of amount
        # Check user's balance
        # Execute trade
        # Store in database
        try:
            if "$" in amount[-1] or "$" in amount[0]:  # last is $
                # Check if conversion is allowed for this coin.
                amount = amount.replace(",", "").replace("$", "")
                price_with = getattr(getattr(self.bot.coin_list, sell_token), "price_with")
                if price_with is None:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this __{sell_token}__."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    per_unit = await self.utils.get_coin_price(sell_token, price_with)
                    if per_unit and per_unit['price'] and per_unit['price'] > 0:
                        per_unit = per_unit['price']
                        amount = Decimal(amount) / Decimal(per_unit)
                    else:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. "\
                            "Try with different method."
                        await ctx.edit_original_message(content=msg)
                        return
            else:
                amount = amount.replace(",", "")
                amount = text_to_num(amount)
                amount = truncate(Decimal(amount), 12)
                if amount is None:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                    await ctx.edit_original_message(content=msg)
                    return

            net_name = getattr(getattr(self.bot.coin_list, sell_token), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, sell_token), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, sell_token), "deposit_confirm_depth")
            contract = getattr(getattr(self.bot.coin_list, sell_token), "contract")

            amount = Decimal(amount)
            get_limit = await nanswap_get_limit(sell_token, for_token, timeout=30)
            if get_limit is None:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, fetching limit error. Try again later!"
                await ctx.edit_original_message(content=msg)
                return
            elif amount < Decimal(get_limit['min']) or amount > Decimal(get_limit['max']):
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, the order amount is not in limit range "\
                    f"{num_format_coin(get_limit['min'])} - {num_format_coin(get_limit['max'])}!"
                await ctx.edit_original_message(content=msg)
                return
            else:
                # pass limit
                # check balance
                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(ctx.author.id), sell_token, net_name, type_coin, SERVER_BOT, 0
                )
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(ctx.author.id), sell_token, net_name, type_coin, SERVER_BOT, 0, 0
                    )

                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                elif type_coin in ["XRP"]:
                    wallet_address = get_deposit['destination_tag']

                height = await self.wallet_api.get_block_height(type_coin, sell_token, net_name)
                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(ctx.author.id), sell_token, net_name, type_coin, SERVER_BOT, 0
                )
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(ctx.author.id), sell_token, net_name, type_coin, SERVER_BOT, 0, 0
                    )

                height = await self.wallet_api.get_block_height(type_coin, sell_token, net_name)
                userdata_balance = await self.wallet_api.user_balance(
                    str(ctx.author.id), sell_token, wallet_address, 
                    type_coin, height, deposit_confirm_depth, SERVER_BOT
                )
                actual_balance = Decimal(userdata_balance['adjust'])
                if truncate(actual_balance, 12) < truncate(amount, 12):
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you don't have sufficient balance to do such swap!"
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    get_estimate = await nanswap_get_estimate(from_coin=sell_token, to_coin=for_token, amount=truncate(amount, 12), timeout=30)
                    if get_estimate is None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, error during estimation, try again later!"
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        # always check main_address for new coin
                        main_address = getattr(getattr(self.bot.coin_list, for_token), "MainAddress")
                        if main_address is None:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, there is no address to exchange. Please report!"
                            await ctx.edit_original_message(content=msg)
                            await log_to_channel(
                                "nanswap",
                                f"🔴 User {ctx.author.mention} try to sell "\
                                f" {sell_token} to {for_token} but no main address to exchange!",
                                self.bot.config['discord']['nanswap']
                            )
                            return
                        text = "{} {}, you should get __{} {}__ from selling __{} {}__.".format(
                            EMOJI_INFORMATION, ctx.author.mention,
                            num_format_coin(get_estimate['amountTo']),
                            for_token,
                            num_format_coin(get_estimate['amountFrom']),
                            sell_token
                        )
                        # If there is progress
                        if str(ctx.author.id) in self.bot.tipping_in_progress and \
                            int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 30:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress.")
                            return

                        view = ConfirmSell(self.bot, ctx.author.id)
                        await ctx.edit_original_message(content=text, view=view)
                        await log_to_channel(
                            "nanswap",
                            f"[ESTIMATE]: User {ctx.author.mention} estimated selling "\
                            f"{num_format_coin(get_estimate['amountFrom'])} {sell_token} to "\
                            f"{num_format_coin(get_estimate['amountTo'])} {for_token} ",
                            self.bot.config['discord']['nanswap']
                        )
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        if view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\n🔴 Timeout!",
                                view=None
                            )
                            try:
                                del self.bot.tipping_in_progress[str(ctx.author.id)]
                            except Exception:
                                pass
                            return
                        elif view.value:
                            # execute trade
                            # insert to data
                            data_json = {
                                "from": sell_token,
                                "to": for_token,
                                "itemName": "",
                                "amount": float(truncate(amount, 12)),
                                "toAddress": main_address
                            }
                            trade = await nanswap_get_create_order(data_json, self.bot.config['nanswap']['api_key'], 30)
                            if trade is None:
                                await ctx.edit_original_message(
                                    content=f"{EMOJI_ERROR} {ctx.author.mention}, failed to created an order from __{sell_token}__ to __{for_token}__.",
                                    view=None
                                )
                                await log_to_channel(
                                    "nanswap",
                                    f"🔴 User {ctx.author.mention} failed to create an order "\
                                    f" {sell_token} to {for_token}!",
                                    self.bot.config['discord']['nanswap']
                                )
                                try:
                                    del self.bot.tipping_in_progress[str(ctx.author.id)]
                                except Exception:
                                    pass
                                return
                            else:
                                coin_decimal = getattr(getattr(self.bot.coin_list, sell_token), "decimal")
                                tx_hash = None
                                if sell_token in ["BAN", "XDG", "XNO"]:
                                    sender_addr = getattr(getattr(self.bot.coin_list, sell_token), "MainAddress")
                                    send_tx = await self.wallet_api.nano_sendtoaddress(
                                        sender_addr, trade['payinAddress'], int(amount * 10 ** coin_decimal), sell_token
                                    )  # atomic
                                    if send_tx is None:
                                        await ctx.edit_original_message(
                                            content=f"{EMOJI_ERROR} {ctx.author.mention}, failed to send tx after "\
                                                f"created an order from __{sell_token}__ to __{for_token}__.",
                                            view=None
                                        )
                                        await log_to_channel(
                                            "nanswap",
                                            f"[NANSWAP] 🔴 User {ctx.author.mention} failed to send tx after creating order "\
                                            f" {sell_token} to {for_token}!",
                                            self.bot.config['discord']['nanswap']
                                        )
                                    else:
                                        tx_hash = send_tx['block']
                                        await ctx.edit_original_message(
                                            content=f"{ctx.author.mention}, successfully created an order from "\
                                                f"__{num_format_coin(amount)} {sell_token}__ to __{for_token}__. You shall be credited very soon!", view=None)
                                        await log_to_channel(
                                            "nanswap",
                                            f"[NANSWAP] User {ctx.author.mention} successfully created an order "\
                                            f"{num_format_coin(amount)} {sell_token} to {for_token}!",
                                            self.bot.config['discord']['nanswap']
                                        )                                
                                # insert to database
                                inserting = await nanswap_create_order(
                                    sell_token, str(ctx.author.id), SERVER_BOT, truncate(amount, 12), coin_decimal,
                                    trade['payinAddress'], tx_hash, trade['id'], trade['expectedAmountFrom'],
                                    trade['expectedAmountTo'], None, None,
                                    trade['payinAddress'], trade['payoutAddress'], sell_token, for_token, json.dumps(trade)
                                )
                                if inserting is True:
                                    sold_text = "{} {}, you should credit (expected) __{} {}__ from selling __{} {}__. Bot should notify the deposit soon!".format(
                                        EMOJI_INFORMATION, ctx.author.mention,
                                        num_format_coin(trade['expectedAmountTo']),
                                        for_token,
                                        num_format_coin(trade['expectedAmountFrom']),
                                        sell_token
                                    )
                                    await ctx.edit_original_message(content=sold_text, view=None)
                                    await log_to_channel(
                                        "nanswap",
                                        f"[NANSWAP SOLD]: User {ctx.author.mention} successfully sold "\
                                        f"{num_format_coin(trade['expectedAmountFrom'])} {sell_token} for "\
                                        f"{num_format_coin(trade['expectedAmountTo'])} {for_token}.",
                                        self.bot.config['discord']['nanswap']
                                    )
                                else:
                                    await ctx.edit_original_message(
                                        content=f"{EMOJI_ERROR} {ctx.author.mention}, failed to close an order from "\
                                            f"__{num_format_coin(amount)} {sell_token}__ to __{for_token}__."
                                    )
                                    await log_to_channel(
                                        "nanswap",
                                        f"[NANSWAP] 🔴🔴🔴 User {ctx.author.mention} successfully created order "\
                                        f"{num_format_coin(amount)} {sell_token} to {for_token} but failed to insert to database!",
                                        self.bot.config['discord']['nanswap']
                                    )
                        else:
                            await ctx.edit_original_message(
                                content=text + "\n**🛑 Cancelled!**",
                                view=None
                            )
                            try:
                                del self.bot.tipping_in_progress[str(ctx.author.id)]
                            except Exception:
                                pass
                            return
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @nanswap_sell.autocomplete("sell_token")
    async def cexswap_addliquidity_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.config['nanswap']['coin_list'] if string in name.lower()][:12]

    @nanswap_sell.autocomplete("for_token")
    async def cexswap_addliquidity_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.config['nanswap']['coin_list'] if string in name.lower()][:12]

    @nanswap.sub_command(
        name="buy",
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option('sell_token', 'sell_token', OptionType.string, required=True),
        ],
        usage="nanswap buy <amount> <token> <sell_token>",
        description="Buy an amount of token from selling another token."
    )
    async def nanswap_buy(
        self,
        ctx,
        amount: str,
        token: str,
        sell_token: str
    ):
        for_token = token
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /nanswap loading..."
        await ctx.response.send_message(msg)
        buy_amount_old = amount

        sell_token = sell_token.upper()
        for_token = for_token.upper()

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/nanswap sell", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if sell_token == for_token:
            msg = f"{EMOJI_ERROR}, {ctx.author.mention}, you cannot do /nanswap for the same token."
            await ctx.edit_original_message(content=msg)
            return

        # check if enable in Nanswap
        if sell_token not in self.bot.config['nanswap']['coin_list']:
            msg = f"{EMOJI_ERROR}, {ctx.author.mention}, __{sell_token}__ is not available in our /nanswap right now."
            await ctx.edit_original_message(content=msg)
            return
        if for_token not in self.bot.config['nanswap']['coin_list']:
            msg = f"{EMOJI_ERROR}, {ctx.author.mention}, __{for_token}__ is not available in our /nanswap right now."
            await ctx.edit_original_message(content=msg)
            return

        try:
            if "$" in amount[-1] or "$" in amount[0]:  # last is $
                # Check if conversion is allowed for this coin.
                amount = amount.replace(",", "").replace("$", "")
                price_with = getattr(getattr(self.bot.coin_list, sell_token), "price_with")
                if price_with is None:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this __{sell_token}__."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    per_unit = await self.utils.get_coin_price(sell_token, price_with)
                    if per_unit and per_unit['price'] and per_unit['price'] > 0:
                        per_unit = per_unit['price']
                        amount = Decimal(amount) / Decimal(per_unit)
                    else:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. "\
                            "Try with different method."
                        await ctx.edit_original_message(content=msg)
                        return
            else:
                amount = amount.replace(",", "")
                amount = text_to_num(amount)
                amount = truncate(Decimal(amount), 12)
                if amount is None:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                    await ctx.edit_original_message(content=msg)
                    return

            net_name = getattr(getattr(self.bot.coin_list, sell_token), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, sell_token), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, sell_token), "deposit_confirm_depth")
            contract = getattr(getattr(self.bot.coin_list, sell_token), "contract")

            amount = Decimal(amount)
            # get reverse order first
            get_estimate = await nanswap_get_estimate_rev(from_coin=sell_token, to_coin=for_token, amount=truncate(amount, 12), timeout=30)
            if get_estimate is None:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, error fetching estimation. Try again later!"
                await ctx.edit_original_message(content=msg)
                return
            else:
                amount_sell = get_estimate['amountFrom']
                get_limit = await nanswap_get_limit(sell_token, for_token, timeout=30)
                if get_limit is None:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, fetching limit error. Try again later!"
                    await ctx.edit_original_message(content=msg)
                    return
                elif amount_sell < Decimal(get_limit['min']) or amount_sell > Decimal(get_limit['max']):
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, the order amount is not in limit range "\
                        f"{num_format_coin(get_limit['min'])} - {num_format_coin(get_limit['max'])}. Estimation got {num_format_coin(amount_sell)} {sell_token}!"
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    # pass limit
                    # check balance
                    get_deposit = await self.wallet_api.sql_get_userwallet(
                        str(ctx.author.id), sell_token, net_name, type_coin, SERVER_BOT, 0
                    )
                    if get_deposit is None:
                        get_deposit = await self.wallet_api.sql_register_user(
                            str(ctx.author.id), sell_token, net_name, type_coin, SERVER_BOT, 0, 0
                        )

                    wallet_address = get_deposit['balance_wallet_address']
                    if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        wallet_address = get_deposit['paymentid']
                    elif type_coin in ["XRP"]:
                        wallet_address = get_deposit['destination_tag']

                    height = await self.wallet_api.get_block_height(type_coin, sell_token, net_name)
                    get_deposit = await self.wallet_api.sql_get_userwallet(
                        str(ctx.author.id), sell_token, net_name, type_coin, SERVER_BOT, 0
                    )
                    if get_deposit is None:
                        get_deposit = await self.wallet_api.sql_register_user(
                            str(ctx.author.id), sell_token, net_name, type_coin, SERVER_BOT, 0, 0
                        )

                    height = await self.wallet_api.get_block_height(type_coin, sell_token, net_name)
                    userdata_balance = await self.wallet_api.user_balance(
                        str(ctx.author.id), sell_token, wallet_address, 
                        type_coin, height, deposit_confirm_depth, SERVER_BOT
                    )
                    actual_balance = Decimal(userdata_balance['adjust'])
                    if truncate(actual_balance, 12) < truncate(amount_sell, 12):
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you don't have sufficient balance to do such swap!"
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        # always check main_address for new coin
                        main_address = getattr(getattr(self.bot.coin_list, for_token), "MainAddress")
                        if main_address is None:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, there is no address to exchange. Please report!"
                            await ctx.edit_original_message(content=msg)
                            await log_to_channel(
                                "nanswap",
                                f"🔴 User {ctx.author.mention} try to sell "\
                                f" {sell_token} to {for_token} but no main address to exchange!",
                                self.bot.config['discord']['nanswap']
                            )
                            return
                        text = "{} {}, you should get __{} {}__ from selling __{} {}__.".format(
                            EMOJI_INFORMATION, ctx.author.mention,
                            num_format_coin(get_estimate['amountTo']),
                            for_token,
                            num_format_coin(get_estimate['amountFrom']),
                            sell_token
                        )
                        # If there is progress
                        if str(ctx.author.id) in self.bot.tipping_in_progress and \
                            int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 30:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress.")
                            return

                        view = ConfirmSell(self.bot, ctx.author.id)
                        await ctx.edit_original_message(content=text, view=view)
                        await log_to_channel(
                            "nanswap",
                            f"[ESTIMATE]: User {ctx.author.mention} estimated selling "\
                            f"{num_format_coin(get_estimate['amountFrom'])} {sell_token} to "\
                            f"{num_format_coin(get_estimate['amountTo'])} {for_token} ",
                            self.bot.config['discord']['nanswap']
                        )
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        if view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\n🔴 Timeout!",
                                view=None
                            )
                            try:
                                del self.bot.tipping_in_progress[str(ctx.author.id)]
                            except Exception:
                                pass
                            return
                        elif view.value:
                            # execute trade
                            # insert to data
                            data_json = {
                                "from": sell_token,
                                "to": for_token,
                                "itemName": "",
                                "amount": float(truncate(amount_sell, 12)),
                                "toAddress": main_address
                            }
                            trade = await nanswap_get_create_order(data_json, self.bot.config['nanswap']['api_key'], 30)
                            if trade is None:
                                await ctx.edit_original_message(
                                    content=f"{EMOJI_ERROR} {ctx.author.mention}, failed to created an order from __{sell_token}__ to __{for_token}__.",
                                    view=None
                                )
                                await log_to_channel(
                                    "nanswap",
                                    f"🔴 User {ctx.author.mention} failed to create an order "\
                                    f" {sell_token} to {for_token}!",
                                    self.bot.config['discord']['nanswap']
                                )
                                try:
                                    del self.bot.tipping_in_progress[str(ctx.author.id)]
                                except Exception:
                                    pass
                                return
                            else:
                                coin_decimal = getattr(getattr(self.bot.coin_list, sell_token), "decimal")
                                tx_hash = None
                                if sell_token in ["BAN", "XDG", "XNO"]:
                                    sender_addr = getattr(getattr(self.bot.coin_list, sell_token), "MainAddress")
                                    send_tx = await self.wallet_api.nano_sendtoaddress(
                                        sender_addr, trade['payinAddress'], int(amount_sell * 10 ** coin_decimal), sell_token
                                    )  # atomic
                                    if send_tx is None:
                                        await ctx.edit_original_message(
                                            content=f"{EMOJI_ERROR} {ctx.author.mention}, failed to send tx after "\
                                                f"created an order from __{sell_token}__ to __{for_token}__.",
                                            view=None
                                        )
                                        await log_to_channel(
                                            "nanswap",
                                            f"[NANSWAP] 🔴 User {ctx.author.mention} failed to send tx after creating order "\
                                            f" {sell_token} to {for_token}!",
                                            self.bot.config['discord']['nanswap']
                                        )
                                    else:
                                        tx_hash = send_tx['block']
                                        await ctx.edit_original_message(
                                            content=f"{ctx.author.mention}, successfully created an order from "\
                                                f"__{num_format_coin(amount_sell)} {sell_token}__ to __{for_token}__. You shall be credited very soon!", view=None)
                                        await log_to_channel(
                                            "nanswap",
                                            f"[NANSWAP] User {ctx.author.mention} successfully created an order "\
                                            f"{num_format_coin(amount_sell)} {sell_token} to {for_token}!",
                                            self.bot.config['discord']['nanswap']
                                        )                                
                                # insert to database
                                inserting = await nanswap_create_order(
                                    sell_token, str(ctx.author.id), SERVER_BOT, truncate(amount_sell, 12), coin_decimal,
                                    trade['payinAddress'], tx_hash, trade['id'], trade['expectedAmountFrom'],
                                    trade['expectedAmountTo'], None, None,
                                    trade['payinAddress'], trade['payoutAddress'], sell_token, for_token, json.dumps(trade)
                                )
                                if inserting is True:
                                    sold_text = "{} {}, you should credit (expected) __{} {}__ from selling __{} {}__. Bot should notify the deposit soon!".format(
                                        EMOJI_INFORMATION, ctx.author.mention,
                                        num_format_coin(trade['expectedAmountTo']),
                                        for_token,
                                        num_format_coin(trade['expectedAmountFrom']),
                                        sell_token
                                    )
                                    await ctx.edit_original_message(content=sold_text, view=None)
                                    await log_to_channel(
                                        "nanswap",
                                        f"[NANSWAP SOLD]: User {ctx.author.mention} successfully sold "\
                                        f"{num_format_coin(trade['expectedAmountFrom'])} {sell_token} for "\
                                        f"{num_format_coin(trade['expectedAmountTo'])} {for_token}.",
                                        self.bot.config['discord']['nanswap']
                                    )
                                else:
                                    await ctx.edit_original_message(
                                        content=f"{EMOJI_ERROR} {ctx.author.mention}, failed to close an order from "\
                                            f"__{num_format_coin(amount_sell)} {sell_token}__ to __{for_token}__."
                                    )
                                    await log_to_channel(
                                        "nanswap",
                                        f"[NANSWAP] 🔴🔴🔴 User {ctx.author.mention} successfully created order "\
                                        f"{num_format_coin(amount_sell)} {sell_token} to {for_token} but failed to insert to database!",
                                        self.bot.config['discord']['nanswap']
                                    )
                        else:
                            await ctx.edit_original_message(
                                content=text + "\n**🛑 Cancelled!**",
                                view=None
                            )
                            try:
                                del self.bot.tipping_in_progress[str(ctx.author.id)]
                            except Exception:
                                pass
                            return
        except Exception:
            traceback.print_exc(file=sys.stdout)


    @nanswap_buy.autocomplete("token")
    async def cexswap_addliquidity_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.config['nanswap']['coin_list'] if string in name.lower()][:12]

    @nanswap_buy.autocomplete("sell_token")
    async def cexswap_addliquidity_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.config['nanswap']['coin_list'] if string in name.lower()][:12]

    @nanswap.sub_command(
        name="check",
        options=[
            Option('id', 'id', OptionType.string, required=True)
        ],
        usage="nanswap check <id>",
        description="Check nanswap trade by ID."
    )
    async def nanswap_check(
        self,
        ctx,
        id: str
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /nanswap loading..."
        await ctx.response.send_message(msg)
        try:
            check_id = await nanswap_check_id(id, timeout=20)
            if check_id is None or "error" in check_id:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, there is no such Nanswap ID: __{id}__."
                )
                return
            else:
                content = """
Id: {}
status: {}
[expectedAmountFrom] from: {} {} to {} {}
[Amount]: {} {} to {} {}
payinAddress: {}
payoutAddress: {}
""".format(
                    id, check_id['status'], check_id['expectedAmountFrom'], check_id['from'],
                    check_id['expectedAmountTo'], check_id['to'],
                    check_id['amountFrom'], check_id['from'], check_id['amountTo'], check_id['to'],
                    check_id['payinAddress'], check_id['payoutAddress']
                )
                await ctx.edit_original_message(
                    content="```{}```".format(content)
                )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)


    @tasks.loop(seconds=10.0)
    async def check_pending(self):
        get_pending = await nanswap_get_pendings(status="ONGOING")
        if len(get_pending) > 0:
            for i in get_pending:
                try:
                    check_id = await nanswap_check_id(i['nanswap_id'], timeout=20)
                    if check_id and check_id['senderAddress'] is not None and check_id['status'] == "completed":
                        # credit user
                        main_address = getattr(getattr(self.bot.coin_list, i['to_coin']), "MainAddress")
                        coin_family = getattr(getattr(self.bot.coin_list, i['to_coin']), "type")
                        coin_decimal = getattr(getattr(self.bot.coin_list, i['to_coin']), "decimal")
                        crediting = await nanswap_credit(
                            coin_family, i['to_coin'], i['user_id'], SERVER_BOT,
                            check_id['senderAddress'], main_address, check_id['amountTo'], coin_decimal,
                            check_id['payoutHash'], json.dumps(check_id),
                            check_id['amountFrom'], check_id['amountTo'], i['nanswap_id']
                        )
                        if crediting is True and i['user_id'].isdigit and i['user_server'] == SERVER_BOT:
                            completed_text = "{} <@{}>, you are credited __{} {}__ from selling __{} {}__. Nanswap ID: {}. It could take a few seconds to be in.".format(
                                EMOJI_INFORMATION, i['user_id'],
                                num_format_coin(check_id['amountTo']),
                                i['to_coin'],
                                num_format_coin(check_id['amountFrom']),
                                i['from_coin'],
                                i['nanswap_id']
                            )
                            member = self.bot.get_user(int(i['user_id']))
                            if member is not None:
                                await member.send(completed_text)
                                await log_to_channel(
                                    "nanswap",
                                    f"[NANSWAP] User <@{i['user_id']}> completed an order "\
                                    f"selling {num_format_coin(check_id['amountFrom'])} {i['from_coin']} to "\
                                    f"{num_format_coin(check_id['amountTo'])} {i['to_coin']}. Nanswap ID: {i['nanswap_id']}!",
                                    self.bot.config['discord']['nanswap']
                                )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        else:
            await asyncio.sleep(5.0)    
        await asyncio.sleep(5.0)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_pending.is_running():
            self.check_pending.start()

    async def cog_load(self):
        if not self.check_pending.is_running():
            self.check_pending.start()

    def cog_unload(self):
        self.check_pending.cancel()

def setup(bot):
    cex = Nanswap(bot)
    bot.add_cog(cex)

