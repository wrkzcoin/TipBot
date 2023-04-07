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
from cogs.utils import Utils, num_format_coin, chunks, stellar_get_tx_info, btc_get_tx_info, erc20_get_tx_info, erc20_get_block_number


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
    amountFrom: float, amountTo: float, nanswap_id: str,
    height: int=None, memo: str=None, fee: float=None,
    confirmations: int=None, blockhash: str=None, blocktime: int=None, category: str=None,
    contract: str=None, network: str=None, status: str=None
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
                elif coin_family == "ERC-20":
                    sql += """
                    INSERT INTO `erc20_move_deposit` (`token_name`, `contract`, 
                    `user_id`, `balance_wallet_address`, `to_main_address`, `real_amount`,
                    `real_deposit_fee`, `token_decimal`, `txn`, `time_insert`, 
                    `user_server`, `network`, `status`, `blockNumber`, `confirmed_depth`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    data_rows += [
                        coin_name, contract,
                        user_id, from_address, to_address, amount,
                        0.0, decimal, tx_hash, int(time.time()),
                        user_server, network, status, height, confirmations
                    ]
                elif coin_family == "XLM":
                    sql += """
                    INSERT INTO `xlm_get_transfers` 
                    (`coin_name`, `user_id`, `txid`, `height`, `amount`, `fee`, 
                    `decimal`, `address`, `memo`, `time_insert`, `user_server`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    data_rows += [
                        coin_name, user_id, tx_hash, height, amount, fee,
                        decimal, to_address, memo, int(time.time()), user_server
                    ]
                elif coin_family == "BTC":
                    # We have function get transfer already
                    pass
                elif coin_family == "XMR":
                    # We have function get transfer already
                    pass
                await cur.execute(sql, tuple(data_rows))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def nanswap_failed_tx(
    nanswap_id: str, user_id: str, user_server: str, json_order: str, amountFrom: float, coin_name: str
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                INSERT INTO `nanswap_trades_failed_tx`
                (`nanswap_id`, `user_id`, `user_server`, `json_order`, `amountFrom`, `from_coin`, `create_time`)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                data_rows = [
                    nanswap_id, user_id, user_server, json_order, amountFrom, coin_name, int(time.time())
                ]
                await cur.execute(sql, tuple(data_rows))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def nanswap_create_order(
    coin_name: str, coin_family: str, user_id: str, user_server: str, from_amount: float, from_decimal: int, to_address: str, tx_hash: str,
    nanswap_id: str, expectedAmountFrom: float, expectedAmountTo: float, amountFrom: float, amountTo: float,
    payinAddress: str, payoutAddress: str, from_coin: str, to_coin: str, json_order: str, fee: float, tx_key: str=None,
    contract: str=None, network: str=None
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
                    if coin_family == "NANO":
                        # add to nano_external_tx
                        sql += """
                        INSERT INTO `nano_external_tx` 
                        (`coin_name`, `user_id`, user_server, `amount`, `decimal`, `to_address`, `date`, `tx_hash`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                        """
                        data_rows += [
                            coin_name, user_id, user_server, from_amount, from_decimal, to_address, int(time.time()), tx_hash
                        ]
                    elif coin_family == "ERC-20":
                        sql += """
                        INSERT INTO `erc20_external_tx` 
                        (`token_name`, `contract`, `user_id`, `real_amount`, 
                        `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, 
                        `user_server`, `network`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """
                        data_rows += [
                            coin_name, contract, user_id, from_amount,
                            fee, from_decimal, to_address, int(time.time()), tx_hash,
                            user_server, network
                        ]
                    elif coin_family == "XLM":
                        sql += """
                        INSERT INTO `xlm_external_tx` 
                        (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, 
                        `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """
                        data_rows += [
                            coin_name, user_id, from_amount, fee, fee,
                            from_decimal, to_address, int(time.time()), tx_hash, user_server
                        ]
                    elif coin_family == "BTC":
                        sql += """
                        INSERT INTO `doge_external_tx` (`coin_name`, `user_id`, `amount`, `tx_fee`, 
                        `withdraw_fee`, `to_address`, `date`, `tx_hash`, `user_server`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """
                        data_rows += [
                            coin_name, user_id, from_amount, fee, fee,
                            to_address, int(time.time()), tx_hash, user_server
                        ]
                    elif coin_family == "XMR":
                        sql += """
                        INSERT INTO `cn_external_tx` 
                        (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, 
                        `to_address`, `paymentid`, `date`, `tx_hash`, `tx_key`, `user_server`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """
                        data_rows += [
                            coin_name, user_id, from_amount, fee, fee, from_decimal,
                            to_address, None, int(time.time()), tx_hash, tx_key, user_server
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
        url = "https://api.nanswap.com/v1/get-limits?from="+from_coin+"&to="+to_coin
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.json()
                    return res_data
    except asyncio.TimeoutError:
        await logchanbot(
            "nanswap_get_limit timeout: {}".format(url)
        )
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def nanswap_check_id_partner(id_str: str, timeout: int=30):
    try:
        url = "https://api.nanswap.com/get-order-partner?id="+id_str
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.json()
                    return res_data
    except asyncio.TimeoutError:
        await logchanbot(
            "nanswap_check_id_partner timeout: {}".format(url)
        )
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def nanswap_check_id(id_str: str, timeout: int=30):
    try:
        url = "https://api.nanswap.com/v1/get-order?id="+id_str
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.json()
                    return res_data
    except asyncio.TimeoutError:
        await logchanbot(
            "nanswap_check_id timeout: {}".format(url)
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
        nanswap_coin_list = ", ".join(self.bot.config['nanswap']['coin_list'])
        if sell_token not in self.bot.config['nanswap']['coin_list']:
            msg = f"{EMOJI_ERROR}, {ctx.author.mention}, __{sell_token}__ is not available in our /nanswap right now. "\
                f"Available __{nanswap_coin_list}__. Alternatively, please check with __/cexswap__."
            await ctx.edit_original_message(content=msg)
            return
        if for_token not in self.bot.config['nanswap']['coin_list']:
            msg = f"{EMOJI_ERROR}, {ctx.author.mention}, __{for_token}__ is not available in our /nanswap right now. "\
                f"Available __{nanswap_coin_list}__. Alternatively, please check with __/cexswap__."
            await ctx.edit_original_message(content=msg)
            return

        # check if the selling coin is disable with withdraw
        if getattr(getattr(self.bot.coin_list, sell_token), "enable_withdraw") != 1:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, **{sell_token}** withdraw is currently disable. "\
                "Hence, you can not sell this coin with /nanswap. Check again later!"
            await ctx.edit_original_message(content=msg)
            return        

        # check if deposit is disable for_token
        if getattr(getattr(self.bot.coin_list, for_token), "enable_deposit") != 1:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, **{for_token}** deposit is currently disable. "\
                "Hence, you can not sell a token/coin for this coin with /nanswap. Check again later!"
            await ctx.edit_original_message(content=msg)
            return      

        sell_coin_emoji = getattr(getattr(self.bot.coin_list, sell_token), "coin_emoji_discord")
        for_coin_emoji = getattr(getattr(self.bot.coin_list, for_token), "coin_emoji_discord")

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
            sell_net_fee = getattr(getattr(self.bot.coin_list, sell_token), "real_withdraw_fee")

            amount = Decimal(amount)
            if amount <= 0:
                await ctx.edit_original_message(content=f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.')
                return

            from_token_json = sell_token
            to_token_json = for_token
            if sell_token in self.bot.config['nanswap_network'].keys():
                from_token_json = self.bot.config['nanswap_network'][sell_token]
            if for_token in self.bot.config['nanswap_network'].keys():
                to_token_json = self.bot.config['nanswap_network'][for_token]

            get_limit = await nanswap_get_limit(from_token_json, to_token_json, timeout=30)
            max_sell_tx = getattr(getattr(self.bot.coin_list, sell_token), "real_max_tx")
            if get_limit is None:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, fetching limit error. Try again later!"
                await ctx.edit_original_message(content=msg)
                return
            elif truncate(amount, 12) < truncate(Decimal(get_limit['min']), 12) or \
                (get_limit['max'] is not None and truncate(amount, 12) > truncate(Decimal(get_limit['max']), 12)):
                max_limit = str(get_limit['max'])
                if get_limit['max'] is None:
                    max_limit = "unlimited"
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, your order amount in Nanswap is not in limit range "\
                    f"{str(get_limit['min'])} - {max_limit} {sell_token}!"
                await ctx.edit_original_message(content=msg)
                return
            elif truncate(Decimal(amount), 12) > truncate(Decimal(max_sell_tx), 12):
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, the sell amount {num_format_coin(amount)} {sell_token}"\
                    f" is more than tx limit {num_format_coin(max_sell_tx)} {sell_token}."
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
                userdata_balance = await self.wallet_api.user_balance(
                    str(ctx.author.id), sell_token, wallet_address, 
                    type_coin, height, deposit_confirm_depth, SERVER_BOT
                )
                actual_balance = Decimal(userdata_balance['adjust'])
                incl_fee = ""
                if sell_net_fee > 0:
                    incl_fee = " (+ network fee: {} {})".format(num_format_coin(sell_net_fee), sell_token)
                if truncate(actual_balance, 12) < truncate(amount + Decimal(sell_net_fee), 12):
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you don't have sufficient balance to do such swap! "\
                        f"Needed __{num_format_coin(amount)} {sell_token}__{incl_fee} but "\
                        f"having __{num_format_coin(actual_balance)} {sell_token}__."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    from_token_json = sell_token
                    to_token_json = for_token
                    if sell_token in self.bot.config['nanswap_network'].keys():
                        from_token_json = self.bot.config['nanswap_network'][sell_token]
                    if for_token in self.bot.config['nanswap_network'].keys():
                        to_token_json = self.bot.config['nanswap_network'][for_token]
                    get_estimate = await nanswap_get_estimate(from_coin=from_token_json, to_coin=to_token_json, amount=truncate(amount, 12), timeout=30)
                    if get_estimate is None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, error during estimation, try again later!"
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        # check minimum receive
                        real_min_deposit = getattr(getattr(self.bot.coin_list, for_token), "real_min_deposit")
                        if Decimal(get_estimate['amountTo']) < Decimal(real_min_deposit):
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, the receiving amount is less "\
                                f"than minimum deposit __{str(get_estimate['amountTo'])} < {str(real_min_deposit)}__ {for_token}!"
                            await ctx.edit_original_message(content=msg)
                            return
                        # always check main_address for new coin
                        main_address = getattr(getattr(self.bot.coin_list, for_token), "MainAddress")
                        for_type_coin = getattr(getattr(self.bot.coin_list, for_token), "type")
                        if main_address is None and for_type_coin not in ["BTC"]:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, there is no address to exchange. Please report!"
                            await ctx.edit_original_message(content=msg)
                            await log_to_channel(
                                "nanswap",
                                f"🔴 User {ctx.author.mention} try to sell "\
                                f" {sell_token} to {for_token} but no main address to exchange!",
                                self.bot.config['discord']['nanswap']
                            )
                            return
                        NetFee = getattr(getattr(self.bot.coin_list, sell_token), "real_withdraw_fee")
                        incl_fee = ""
                        if NetFee > 0:
                            incl_fee = " (+ network fee: {} {})".format(num_format_coin(NetFee), sell_token)
                        text = "{} {}, you should get __{} {}__ from selling __{} {}__{}.".format(
                            EMOJI_INFORMATION, ctx.author.mention,
                            num_format_coin(get_estimate['amountTo']),
                            for_token,
                            str(get_estimate['amountFrom']),
                            sell_token,
                            incl_fee
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
                            f"{str(get_estimate['amountFrom'])} {sell_token} to "\
                            f"{str(get_estimate['amountTo'])} {for_token} ",
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
                            # Disable button view first
                            await ctx.edit_original_message(view=None)
                            sell_coin_family = getattr(getattr(self.bot.coin_list, sell_token), "type")
                            memo_tag = ""
                            for_type_coin = getattr(getattr(self.bot.coin_list, for_token), "type")
                            for_net_name = getattr(getattr(self.bot.coin_list, for_token), "net_name")
                            for_type_coin = getattr(getattr(self.bot.coin_list, for_token), "type")
                            get_deposit = await self.wallet_api.sql_get_userwallet(
                                str(ctx.author.id), for_token, for_net_name, for_type_coin, SERVER_BOT, 0
                            )
                            if get_deposit is None:
                                get_deposit = await self.wallet_api.sql_register_user(
                                    str(ctx.author.id), for_token, for_net_name, for_type_coin, SERVER_BOT, 0, 0
                                )
                            if for_type_coin in ["XLM", "VITE", "COSMOS"]:
                                # get for token
                                address_memo = get_deposit['balance_wallet_address'].split()
                                memo_tag = address_memo[2]
                            elif for_type_coin in ["BTC", "XMR"]:
                                # change main address to user deposit
                                main_address = get_deposit['balance_wallet_address']
                            elif for_type_coin in ["ERC-20"]:
                                main_address = self.bot.config['eth']['MainAddress']
                            # execute trade
                            # insert to data
                            from_token_json = sell_token
                            to_token_json = for_token
                            if sell_token in self.bot.config['nanswap_network'].keys():
                                from_token_json = self.bot.config['nanswap_network'][sell_token]
                            if for_token in self.bot.config['nanswap_network'].keys():
                                to_token_json = self.bot.config['nanswap_network'][for_token]
                                
                            data_json = {
                                "from": from_token_json,
                                "to": to_token_json,
                                "itemName": "",
                                "extraId": memo_tag,
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
                                fee = 0.0
                                tx_key = None
                                if sell_coin_family == "NANO":
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
                                        # add to failed tx table
                                        try:
                                            await nanswap_failed_tx(
                                                trade['id'], str(ctx.author.id), SERVER_BOT, json.dumps(trade),
                                                trade['expectedAmountFrom'], sell_token
                                            )
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        try:
                                            del self.bot.tipping_in_progress[str(ctx.author.id)]
                                        except Exception:
                                            pass
                                        return
                                    else:
                                        tx_hash = send_tx['block']
                                        await ctx.edit_original_message(
                                            content=f"{ctx.author.mention}, successfully created an order from "\
                                                f"{sell_coin_emoji} __{str(amount)} {sell_token}__ "\
                                                f"to {for_coin_emoji} __{for_token}__. You shall be credited very soon! Nanswap ID: {trade['id']}.", view=None)
                                        await log_to_channel(
                                            "nanswap",
                                            f"[NANSWAP] User {ctx.author.mention} successfully created an order "\
                                            f"{str(amount)} {sell_token} to {for_token}!",
                                            self.bot.config['discord']['nanswap']
                                        )
                                elif sell_coin_family == "ERC-20":
                                    NetFee = getattr(getattr(self.bot.coin_list, sell_token), "real_withdraw_fee")
                                    fee = NetFee
                                    sell_coin_decimal = getattr(getattr(self.bot.coin_list, sell_token), "decimal")
                                    network = getattr(getattr(self.bot.coin_list, sell_token), "net_name")
                                    url = self.bot.erc_node_list[network]
                                    chain_id = getattr(getattr(self.bot.coin_list, sell_token), "chain_id")
                                    sender_addr = self.bot.config['eth']['MainAddress']
                                    send_tx = await self.wallet_api.send_external_erc20_nostore(
                                        url, network, sender_addr, self.bot.config['eth']['MainAddress_key'],
                                        trade['payinAddress'], truncate(amount, 8), sell_coin_decimal,
                                        chain_id, contract
                                    )
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
                                        # add to failed tx table
                                        try:
                                            await nanswap_failed_tx(
                                                trade['id'], str(ctx.author.id), SERVER_BOT, json.dumps(trade),
                                                trade['expectedAmountFrom'], sell_token
                                            )
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        try:
                                            del self.bot.tipping_in_progress[str(ctx.author.id)]
                                        except Exception:
                                            pass
                                        return
                                    else:
                                        tx_hash = send_tx
                                        await ctx.edit_original_message(
                                            content=f"{ctx.author.mention}, successfully created an order from "\
                                                f"{sell_coin_emoji} __{str(amount)} {sell_token}__ "\
                                                f"to {for_coin_emoji} __{for_token}__. You shall be credited very soon! Nanswap ID: {trade['id']}.", view=None)
                                        await log_to_channel(
                                            "nanswap",
                                            f"[NANSWAP] User {ctx.author.mention} successfully created an order "\
                                            f"{str(amount)} {sell_token} to {for_token}!",
                                            self.bot.config['discord']['nanswap']
                                        )
                                elif sell_coin_family == "XMR":
                                    NetFee = getattr(getattr(self.bot.coin_list, sell_token), "real_withdraw_fee")
                                    fee = NetFee
                                    sell_coin_decimal = getattr(getattr(self.bot.coin_list, sell_token), "decimal")
                                    send_tx = await self.wallet_api.send_external_xmr_nostore(
                                        truncate(amount, 8), trade['payinAddress'], sell_token, sell_coin_decimal, 120
                                    )
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
                                        # add to failed tx table
                                        try:
                                            await nanswap_failed_tx(
                                                trade['id'], str(ctx.author.id), SERVER_BOT, json.dumps(trade),
                                                trade['expectedAmountFrom'], sell_token
                                            )
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        try:
                                            del self.bot.tipping_in_progress[str(ctx.author.id)]
                                        except Exception:
                                            pass
                                        return
                                    else:
                                        tx_hash = send_tx['tx_hash']
                                        tx_key = send_tx['tx_key']
                                        await ctx.edit_original_message(
                                            content=f"{ctx.author.mention}, successfully created an order from "\
                                                f"{sell_coin_emoji} __{str(amount)} {sell_token}__ "\
                                                f"to {for_coin_emoji} __{for_token}__. You shall be credited very soon! Nanswap ID: {trade['id']}.", view=None)
                                        await log_to_channel(
                                            "nanswap",
                                            f"[NANSWAP] User {ctx.author.mention} successfully created an order "\
                                            f"{str(amount)} {sell_token} to {for_token}!",
                                            self.bot.config['discord']['nanswap']
                                        )
                                elif sell_coin_family == "BTC":
                                    NetFee = getattr(getattr(self.bot.coin_list, sell_token), "real_withdraw_fee")
                                    fee = NetFee
                                    send_tx = await self.wallet_api.send_external_doge_nostore(
                                        "nanswap", truncate(amount, 8), trade['payinAddress'], sell_token
                                    )
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
                                        # add to failed tx table
                                        try:
                                            await nanswap_failed_tx(
                                                trade['id'], str(ctx.author.id), SERVER_BOT, json.dumps(trade),
                                                trade['expectedAmountFrom'], sell_token
                                            )
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        try:
                                            del self.bot.tipping_in_progress[str(ctx.author.id)]
                                        except Exception:
                                            pass
                                        return
                                    else:
                                        tx_hash = send_tx
                                        await ctx.edit_original_message(
                                            content=f"{ctx.author.mention}, successfully created an order from "\
                                                f"{sell_coin_emoji} __{str(amount)} {sell_token}__ "\
                                                f"to {for_coin_emoji} __{for_token}__. You shall be credited very soon! Nanswap ID: {trade['id']}.", view=None)
                                        await log_to_channel(
                                            "nanswap",
                                            f"[NANSWAP] User {ctx.author.mention} successfully created an order "\
                                            f"{str(amount)} {sell_token} to {for_token}!",
                                            self.bot.config['discord']['nanswap']
                                        )
                                elif sell_coin_family == "XLM":
                                    # fetch the order
                                    check_id = await nanswap_check_id_partner(trade['id'])
                                    if "error" in check_id:
                                        await ctx.edit_original_message(
                                            content=f"{EMOJI_ERROR} {ctx.author.mention}, error checking ID __{trade['id']}__.",
                                            view=None
                                        )
                                        await log_to_channel(
                                            "nanswap",
                                            f"[NANSWAP] 🔴 User {ctx.author.mention} failed to get ID __{trade['id']}__ "\
                                            f"when selling {sell_token} to {for_token}!",
                                            self.bot.config['discord']['nanswap']
                                        )
                                        try:
                                            del self.bot.tipping_in_progress[str(ctx.author.id)]
                                        except Exception:
                                            pass
                                        return
                                    url = getattr(getattr(self.bot.coin_list, sell_token), "http_address")
                                    withdraw_keypair = decrypt_string(getattr(getattr(self.bot.coin_list, sell_token), "walletkey"))
                                    NetFee = getattr(getattr(self.bot.coin_list, sell_token), "real_withdraw_fee")
                                    fee = NetFee
                                    asset_ticker = getattr(getattr(self.bot.coin_list, sell_token), "header")
                                    asset_issuer = getattr(getattr(self.bot.coin_list, sell_token), "contract")
                                    send_tx = await self.wallet_api.send_external_xlm_nostore(
                                        url, withdraw_keypair, str(ctx.author.id),
                                        amount, trade['payinAddress'], coin_decimal, SERVER_BOT,
                                        sell_token, NetFee, asset_ticker, asset_issuer,
                                        30, check_id['payinExtraId']
                                    )
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
                                        # add to failed tx table
                                        try:
                                            await nanswap_failed_tx(
                                                trade['id'], str(ctx.author.id), SERVER_BOT, json.dumps(trade),
                                                trade['expectedAmountFrom'], sell_token
                                            )
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        try:
                                            del self.bot.tipping_in_progress[str(ctx.author.id)]
                                        except Exception:
                                            pass
                                        return
                                    else:
                                        tx_hash = send_tx
                                        await ctx.edit_original_message(
                                            content=f"{ctx.author.mention}, successfully created an order from "\
                                                f"{sell_coin_emoji} __{str(amount)} {sell_token}__ "\
                                                f"to {for_coin_emoji} __{for_token}__. You shall be credited very soon! Nanswap ID: {trade['id']}.", view=None)
                                        await log_to_channel(
                                            "nanswap",
                                            f"[NANSWAP] User {ctx.author.mention} successfully created an order "\
                                            f"{str(amount)} {sell_token} to {for_token}!",
                                            self.bot.config['discord']['nanswap']
                                        )
                                # insert to database
                                sell_contract = getattr(getattr(self.bot.coin_list, sell_token), "contract")
                                sell_network = getattr(getattr(self.bot.coin_list, sell_token), "net_name")
                                inserting = await nanswap_create_order(
                                    sell_token, sell_coin_family, str(ctx.author.id), SERVER_BOT, truncate(amount, 12), coin_decimal,
                                    trade['payinAddress'], tx_hash, trade['id'], trade['expectedAmountFrom'],
                                    trade['expectedAmountTo'], None, None,
                                    trade['payinAddress'], trade['payoutAddress'], sell_token, for_token, json.dumps(trade),
                                    fee, tx_key, sell_contract, sell_network
                                )
                                if inserting is True:
                                    sold_text = "{} {}, you should be credited (expectedly) {} __{} {}__ from selling {} __{} {}__. "\
                                        "Bot should notify the deposit soon! Nanswap ID: `{}`.".format(
                                        EMOJI_INFORMATION, ctx.author.mention,
                                        for_coin_emoji,
                                        num_format_coin(trade['expectedAmountTo']),
                                        for_token,
                                        sell_coin_emoji,
                                        str(trade['expectedAmountFrom']),
                                        sell_token,
                                        trade['id']
                                    )
                                    await ctx.edit_original_message(content=sold_text, view=None)
                                    await log_to_channel(
                                        "nanswap",
                                        f"[NANSWAP SOLD]: User {ctx.author.mention} successfully created an order "\
                                        f"{str(trade['expectedAmountFrom'])} {sell_token} for "\
                                        f"{str(trade['expectedAmountTo'])} {for_token}. Nanswap ID: `{trade['id']}`.",
                                        self.bot.config['discord']['nanswap']
                                    )
                                else:
                                    await ctx.edit_original_message(
                                        content=f"{EMOJI_ERROR} {ctx.author.mention}, failed to close an order from "\
                                            f"__{str(amount)} {sell_token}__ to __{for_token}__."
                                    )
                                    await log_to_channel(
                                        "nanswap",
                                        f"[NANSWAP] 🔴🔴🔴 User {ctx.author.mention} successfully created order "\
                                        f"{str(amount)} {sell_token} to {for_token} but failed to insert to database!",
                                        self.bot.config['discord']['nanswap']
                                    )
                                try:
                                    del self.bot.tipping_in_progress[str(ctx.author.id)]
                                except Exception:
                                    pass
                        else:
                            await ctx.edit_original_message(
                                content=text + "\n**🛑 Cancelled!**",
                                view=None
                            )
                            try:
                                del self.bot.tipping_in_progress[str(ctx.author.id)]
                            except Exception:
                                pass
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
        nanswap_coin_list = ", ".join(self.bot.config['nanswap']['coin_list'])
        if sell_token not in self.bot.config['nanswap']['coin_list']:
            msg = f"{EMOJI_ERROR}, {ctx.author.mention}, __{sell_token}__ is not available in our /nanswap right now. "\
                f"Available __{nanswap_coin_list}__. Alternatively, please check with __/cexswap__."
            await ctx.edit_original_message(content=msg)
            return
        if for_token not in self.bot.config['nanswap']['coin_list']:
            msg = f"{EMOJI_ERROR}, {ctx.author.mention}, __{for_token}__ is not available in our /nanswap right now. "\
                f"Available __{nanswap_coin_list}__. Alternatively, please check with __/cexswap__."
            await ctx.edit_original_message(content=msg)
            return
        # only some support this reversed
        if sell_token not in self.bot.config['nanswap']['reverse_list'] or for_token not in self.bot.config['nanswap']['reverse_list']:
            msg = f"{EMOJI_ERROR}, {ctx.author.mention}, this pair doesn't support buy command. Please use __/nanswap sell__ instead."
            await ctx.edit_original_message(content=msg)
            return

        # check if the selling coin is disable with withdraw
        if getattr(getattr(self.bot.coin_list, sell_token), "enable_withdraw") != 1:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, **{sell_token}** withdraw is currently disable. "\
                "Hence, you can not sell this coin with /nanswap. Check again later!"
            await ctx.edit_original_message(content=msg)
            return

        # check if deposit is disable for_token
        if getattr(getattr(self.bot.coin_list, for_token), "enable_deposit") != 1:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, **{for_token}** deposit is currently disable. "\
                "Hence, you can not sell a token/coin for this coin with /nanswap. Check again later!"
            await ctx.edit_original_message(content=msg)
            return

        sell_coin_emoji = getattr(getattr(self.bot.coin_list, sell_token), "coin_emoji_discord")
        for_coin_emoji = getattr(getattr(self.bot.coin_list, for_token), "coin_emoji_discord")

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

            if amount <= 0:
                await ctx.edit_original_message(content=f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.')
                return

            net_name = getattr(getattr(self.bot.coin_list, sell_token), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, sell_token), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, sell_token), "deposit_confirm_depth")
            contract = getattr(getattr(self.bot.coin_list, sell_token), "contract")

            amount = Decimal(amount)
            # check minimum receive
            real_min_deposit = getattr(getattr(self.bot.coin_list, for_token), "real_min_deposit")
            sell_net_fee = getattr(getattr(self.bot.coin_list, sell_token), "real_withdraw_fee")
            if amount < Decimal(real_min_deposit):
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, the receiving amount is less "\
                    f"than minimum deposit __{str(amount)} < {str(real_min_deposit)}__ {for_token}!"
                await ctx.edit_original_message(content=msg)
                return
            # get reverse order first
            get_estimate = await nanswap_get_estimate_rev(from_coin=sell_token, to_coin=for_token, amount=truncate(amount, 12), timeout=30)
            if get_estimate is None:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, error fetching estimation. Try again later!"
                await ctx.edit_original_message(content=msg)
                return
            else:
                amount_sell = get_estimate['amountFrom']
                max_sell_tx = getattr(getattr(self.bot.coin_list, sell_token), "real_max_tx")
                get_limit = await nanswap_get_limit(sell_token, for_token, timeout=30)
                if get_limit is None:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, fetching limit error. Try again later!"
                    await ctx.edit_original_message(content=msg)
                    return
                elif truncate(amount_sell, 12) < truncate(Decimal(get_limit['min']), 12) or \
                    truncate(amount_sell, 12) > truncate(Decimal(get_limit['max']), 12):
                    max_limit = str(get_limit['max'])
                    if get_limit['max'] is None:
                        max_limit = "unlimited"
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, your order amount in Nanswap is not in limit range "\
                        f"{str(get_limit['min'])} - {max_limit} {sell_token}. Estimation got {str(amount_sell)} {sell_token}!"
                    await ctx.edit_original_message(content=msg)
                    return
                elif truncate(Decimal(amount_sell), 12) > truncate(Decimal(max_sell_tx), 12):
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, the sell amount {num_format_coin(amount_sell)} {sell_token}"\
                        f" is more than tx limit {num_format_coin(max_sell_tx)} {sell_token}."
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
                    if truncate(actual_balance, 12) < truncate(amount_sell + Decimal(sell_net_fee), 12):
                        incl_fee = ""
                        if sell_net_fee > 0:
                            incl_fee = " (+ network fee: {} {})".format(num_format_coin(sell_net_fee), sell_token)
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you don't have sufficient balance to do such swap! "\
                            f"Needed __{num_format_coin(amount_sell)} {sell_token}__{incl_fee} "\
                            f"but having __{num_format_coin(actual_balance)} {sell_token}__."
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        # always check main_address for new coin
                        main_address = getattr(getattr(self.bot.coin_list, for_token), "MainAddress")
                        for_type_coin = getattr(getattr(self.bot.coin_list, for_token), "type")
                        if main_address is None and for_type_coin not in ["BTC"]:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, there is no address to exchange. Please report!"
                            await ctx.edit_original_message(content=msg)
                            await log_to_channel(
                                "nanswap",
                                f"🔴 User {ctx.author.mention} try to sell "\
                                f" {sell_token} to {for_token} but no main address to exchange!",
                                self.bot.config['discord']['nanswap']
                            )
                            return
                        NetFee = getattr(getattr(self.bot.coin_list, sell_token), "real_withdraw_fee")
                        incl_fee = ""
                        if NetFee > 0:
                            incl_fee = " (+ network fee: {} {})".format(num_format_coin(NetFee), sell_token)
                        text = "{} {}, you should get __{} {}__ from selling __{} {}__{}.".format(
                            EMOJI_INFORMATION, ctx.author.mention,
                            num_format_coin(get_estimate['amountTo']),
                            for_token,
                            str(get_estimate['amountFrom']),
                            sell_token,
                            incl_fee
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
                            f"{str(get_estimate['amountFrom'])} {sell_token} to "\
                            f"{str(get_estimate['amountTo'])} {for_token} ",
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
                            await asyncio.sleep(5.0)
                            await ctx.delete_original_message()
                            return
                        elif view.value:
                            # Disable button view first
                            await ctx.edit_original_message(view=None)
                            sell_coin_family = getattr(getattr(self.bot.coin_list, sell_token), "type")
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
                                fee = 0.0
                                tx_key = None
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
                                        # add to failed tx table
                                        try:
                                            await nanswap_failed_tx(
                                                trade['id'], str(ctx.author.id), SERVER_BOT, json.dumps(trade),
                                                trade['expectedAmountFrom'], sell_token
                                            )
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        try:
                                            del self.bot.tipping_in_progress[str(ctx.author.id)]
                                        except Exception:
                                            pass
                                        return
                                    else:
                                        tx_hash = send_tx['block']
                                        await ctx.edit_original_message(
                                            content=f"{ctx.author.mention}, successfully created an order from "\
                                                f"__{str(amount_sell)} {sell_token}__ to __{for_token}__. You shall be credited very soon! Nanswap ID: {trade['id']}.", view=None)
                                        await log_to_channel(
                                            "nanswap",
                                            f"[NANSWAP] User {ctx.author.mention} successfully created an order "\
                                            f"{str(amount_sell)} {sell_token} to {for_token}!",
                                            self.bot.config['discord']['nanswap']
                                        )                                
                                # insert to database
                                sell_contract = getattr(getattr(self.bot.coin_list, sell_token), "contract")
                                sell_network = getattr(getattr(self.bot.coin_list, sell_token), "net_name")
                                inserting = await nanswap_create_order(
                                    sell_token, sell_coin_family, str(ctx.author.id), SERVER_BOT, truncate(amount_sell, 12), coin_decimal,
                                    trade['payinAddress'], tx_hash, trade['id'], trade['expectedAmountFrom'],
                                    trade['expectedAmountTo'], None, None,
                                    trade['payinAddress'], trade['payoutAddress'], sell_token, for_token, json.dumps(trade),
                                    fee, tx_key,
                                    sell_contract, sell_network
                                )
                                if inserting is True:
                                    sold_text = "{} {}, you should be credited (expectedly) {} __{} {}__ from selling {} __{} {}__. Bot should notify the deposit soon!".format(
                                        EMOJI_INFORMATION, ctx.author.mention,
                                        for_coin_emoji,
                                        num_format_coin(trade['expectedAmountTo']),
                                        for_token,
                                        sell_coin_emoji,
                                        trade['expectedAmountFrom'],
                                        sell_token
                                    )
                                    await ctx.edit_original_message(content=sold_text, view=None)
                                    await log_to_channel(
                                        "nanswap",
                                        f"[NANSWAP SOLD]: User {ctx.author.mention} successfully sold "\
                                        f"{str(trade['expectedAmountFrom'])} {sell_token} for "\
                                        f"{str(trade['expectedAmountTo'])} {for_token}.",
                                        self.bot.config['discord']['nanswap']
                                    )
                                else:
                                    await ctx.edit_original_message(
                                        content=f"{EMOJI_ERROR} {ctx.author.mention}, failed to close an order from "\
                                            f"__{str(amount_sell)} {sell_token}__ to __{for_token}__."
                                    )
                                    await log_to_channel(
                                        "nanswap",
                                        f"[NANSWAP] 🔴🔴🔴 User {ctx.author.mention} successfully created order "\
                                        f"{str(amount_sell)} {sell_token} to {for_token} but failed to insert to database!",
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
        name="coinlist",
        usage="nanswap coinlist",
        description="List all coin supported by TipBot's Nanswap."
    )
    async def nanswap_coin_list(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /nanswap loading..."
        await ctx.response.send_message(msg)
        try:
            list_coins = ", ".join(self.bot.config['nanswap']['coin_list'])
            await ctx.edit_original_message(
                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, list supported coin for /nanswap: __{list_coins}__."
            )
        except Exception:
            traceback.print_exc(file=sys.stdout)

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
                check_id = await nanswap_check_id_partner(id, timeout=20)
                if check_id is None or "error" in check_id:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, there is no such Nanswap ID: __{id}__."
                    )
                    return

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
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @tasks.loop(seconds=15.0)
    async def check_pending(self):
        get_pending = await nanswap_get_pendings(status="ONGOING")
        if len(get_pending) > 0:
            get_guilds = await self.utils.get_trade_channel_list()
            list_guild_ids = [i.id for i in self.bot.guilds]
            for i in get_pending:
                try:
                    if i['to_coin'] in self.bot.config['nanswap']['partner_list'] or i['from_coin'] in self.bot.config['nanswap']['partner_list']:
                        check_id = await nanswap_check_id_partner(i['nanswap_id'], timeout=10)
                    else:
                        check_id = await nanswap_check_id(i['nanswap_id'], timeout=10)
                    if check_id and check_id['status'] == "completed":
                        # credit user
                        main_address = getattr(getattr(self.bot.coin_list, i['to_coin']), "MainAddress")
                        coin_family = getattr(getattr(self.bot.coin_list, i['to_coin']), "type")
                        coin_decimal = getattr(getattr(self.bot.coin_list, i['to_coin']), "decimal")
                        contract = getattr(getattr(self.bot.coin_list, i['to_coin']), "contract")
                        network = getattr(getattr(self.bot.coin_list, i['to_coin']), "net_name")
                        height = None
                        memo = None
                        fee = None
                        confirmations = None
                        blockhash = None
                        blocktime = None
                        category = None
                        status_tx = "FAILED"
                        if coin_family == "XLM":
                            try:
                                # Fetch transaction
                                get_tx = await stellar_get_tx_info(check_id['payoutHash'])
                                if get_tx is None:
                                    continue
                                else:
                                    height = get_tx['ledger']
                                    memo = get_tx['memo'] if 'memo' in get_tx else None
                                    fee = int(get_tx['fee_charged']) / (10 ** coin_decimal)
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                continue
                        elif coin_family == "BTC":
                            try:
                                url = getattr(getattr(self.bot.coin_list, i['to_coin']), "daemon_address")
                                get_tx = await btc_get_tx_info(url, check_id['payoutHash'])
                                if get_tx and "confirmations" in get_tx:
                                    confirmations = get_tx['confirmations']
                                    blockhash = get_tx['blockhash']
                                    blocktime = get_tx['blocktime']
                                    category = get_tx['details']['category']
                                    if category != "receive":
                                        continue
                                    if main_address != get_tx['details']['address']:
                                        continue
                                    if blockhash is None or confirmations == 0:
                                        continue
                                    get_confirm_depth = getattr(getattr(self.bot.coin_list, i['to_coin']), "deposit_confirm_depth")
                                    if get_confirm_depth > confirmations:
                                        continue
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                continue
                        elif coin_family == "XMR":
                            # We only update credit table but no notification
                            continue
                        elif coin_family == "ERC-20":
                            # check tx status
                            confirmation_depth = getattr(getattr(self.bot.coin_list, i['to_coin']), "deposit_confirm_depth")
                            # change main address
                            main_address = self.bot.config['eth']['MainAddress']
                            url = self.bot.erc_node_list[network]
                            get_tx = await erc20_get_tx_info(url, check_id['payoutHash'])
                            if get_tx is None:
                                print("Nanswap fetches erc20 tx received None for hash: {}, url: {}".format(check_id['payoutHash'], url))
                                continue
                            else:
                                if 'status' in get_tx and int(get_tx['status'], 16) == 0:
                                    # they sent to us but tx failed
                                    await log_to_channel(
                                        "nanswap",
                                        f"[NANSWAP] 🔴🔴🔴🔴🔴 Nanswap received status failed tx: {check_id['payoutHash']}. "\
                                        f"Nanswap ID: {i['nanswap_id']} from {num_format_coin(check_id['amountTo'])} {i['from_coin']}"\
                                        f" to {i['to_coin']}.",
                                        self.bot.config['discord']['nanswap']
                                    )
                                    continue
                                else:
                                    tx_block_number = int(get_tx['blockNumber'], 16)
                                    top_block = await erc20_get_block_number(url, timeout=30)
                                    if top_block - confirmation_depth > tx_block_number:
                                        status_tx = "CONFIRMED"
                                        confirmations = top_block - tx_block_number
                                        height = tx_block_number
                                    else:
                                        continue
                        if 'senderAddress' in check_id:
                            sender = check_id['senderAddress']
                        else:
                            sender = check_id['payoutHash']
                        crediting = await nanswap_credit(
                            coin_family, i['to_coin'], i['user_id'], SERVER_BOT,
                            sender, main_address, check_id['amountTo'], coin_decimal,
                            check_id['payoutHash'], json.dumps(check_id),
                            check_id['amountFrom'], check_id['amountTo'], i['nanswap_id'],
                            height=height, memo=memo, fee=fee,
                            confirmations=confirmations, blockhash=blockhash,
                            blocktime=blocktime, category=category,
                            contract=contract, network=network, status=status_tx
                        )
                        sell_coin_emoji = getattr(getattr(self.bot.coin_list, i['from_coin']), "coin_emoji_discord")
                        for_coin_emoji = getattr(getattr(self.bot.coin_list, i['to_coin']), "coin_emoji_discord")
                        if crediting is True and i['user_id'].isdigit and i['user_server'] == SERVER_BOT:
                            completed_text = "{} <@{}>, you are credited {} __{} {}__ from selling {} __{} {}__. Nanswap ID: {}. It could take a few seconds to be in.".format(
                                EMOJI_INFORMATION, i['user_id'],
                                for_coin_emoji,
                                num_format_coin(check_id['amountTo']),
                                i['to_coin'],
                                sell_coin_emoji,
                                check_id['amountFrom'],
                                i['from_coin'],
                                i['nanswap_id']
                            )
                            try:
                                member = self.bot.get_user(int(i['user_id']))
                                if member is not None:
                                    await member.send(completed_text)
                                    await log_to_channel(
                                        "nanswap",
                                        f"[NANSWAP] User <@{i['user_id']}> completed an order "\
                                        f"selling {str(check_id['amountFrom'])} {i['from_coin']} to "\
                                        f"{str(check_id['amountTo'])} {i['to_coin']}. Nanswap ID: {i['nanswap_id']}!",
                                        self.bot.config['discord']['nanswap']
                                    )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            if self.bot.config['nanswap']['enable_trade_ann'] == 1:
                                ann_nanswap_msg = "[NANSWAP] A user sold {} {} for {} {}.".format(
                                    num_format_coin(check_id['amountFrom']),
                                    i['from_coin'],
                                    num_format_coin(check_id['amountTo']),
                                    i['to_coin']
                                )
                                for item in get_guilds:
                                    if int(item['serverid']) not in list_guild_ids:
                                        continue
                                    try:
                                        get_guild = self.bot.get_guild(int(item['serverid']))
                                        if get_guild:
                                            channel = get_guild.get_channel(int(item['trade_channel']))
                                            if channel is None:
                                                continue
                                            else:
                                                await channel.send(ann_nanswap_msg)
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
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
    nanswap = Nanswap(bot)
    bot.add_cog(nanswap)

