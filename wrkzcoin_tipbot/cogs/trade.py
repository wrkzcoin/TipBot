import sys, traceback

import disnake
from disnake.ext import commands
from decimal import Decimal
from datetime import datetime
import time

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

# ascii table
from terminaltables import AsciiTable
import store
from Bot import get_token_list, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, \
    EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, RowButtonCloseMessage, RowButtonRowCloseAnyMessage, human_format, \
    text_to_num, truncate, seconds_str, EMOJI_HOURGLASS_NOT_DONE, EMOJI_INFORMATION

from cogs.utils import MenuPage
from cogs.wallet import WalletAPI
from cogs.utils import Utils, num_format_coin


class Trade(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.min_ratio = 0.0000000001
        self.message_cexswap = "Try our TipBot's feature with /cexswap for more advanced trading!"

        self.botLogChan = None
        self.enable_logchan = True

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    async def sql_get_markets_by_coin(self, status: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT DISTINCT `coin_sell`, `coin_get` 
                    FROM `open_order` WHERE `status`=%s """
                    await cur.execute(sql, status)
                    result = await cur.fetchall()
                    return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_open_orders(
            self,
            ctx,
            option: str,
            coin1: str,
            coin2: str = None
    ):
        await self.bot_log()
        table_list = []
        item_selling_list = []
        per_page = 8
        get_markets = None
        title = "**MARKET**"
        no_trading_msg = "Currently, no opening selling or buying market."
        if coin2 is None:
            get_markets = await store.sql_get_open_order_by_alluser(coin1.upper(), 'OPEN', option.upper(), 200)
            title = "**MARKET {}**".format(coin1.upper())
            no_trading_msg = f"Currently, no opening selling or buying market for {coin1.upper()}. "\
                f"Please make some open order for others."
        else:
            get_markets = await store.sql_get_open_order_by_alluser_by_coins(
                coin1.upper(), coin2.upper(), "OPEN", option
            )
            title = "**MARKET {}/{}**".format(coin1.upper(), coin2.upper())
            no_trading_msg = f"Currently, no opening selling market pair for {coin1.upper()} with {coin2.upper()}. "\
                f"Please make some open order for others."

        if get_markets and len(get_markets) > 0:
            list_numb = 0
            table_data = [
                ['PAIR', 'Selling', 'For', 'Rate', 'Order #']
            ]
            for order_item in get_markets:
                rate = 0.0
                if order_item['amount_sell'] / order_item['amount_get'] < 0.000001:
                    rate = '{:.8f}'.format(round(order_item['amount_sell'] / order_item['amount_get'], 8))
                elif order_item['amount_sell'] / order_item['amount_get'] < 0.001:
                    rate = '{:.4f}'.format(round(order_item['amount_sell'] / order_item['amount_get'], 4))
                else:
                    rate = '{:.2f}'.format(round(order_item['amount_sell'] / order_item['amount_get'], 2))
                table_data.append([order_item['pair_name'],
                                   num_format_coin(order_item['amount_sell_after_fee']) + order_item['coin_sell'],
                                   num_format_coin(order_item['amount_get']) + order_item['coin_get'],
                                   '{:.8f}'.format(round(order_item['amount_sell'] / order_item['amount_get'], 8)),
                                   order_item['order_id']])
                item_selling_list.append({
                    "pair": order_item['pair_name'],
                    "selling": num_format_coin(order_item['amount_sell_after_fee']) + " " + order_item['coin_sell'],
                    "for": num_format_coin(order_item['amount_get']) + " " + order_item['coin_get'],
                    "rate": rate,
                    "order_number": order_item['order_id']
                })
                if list_numb > 0 and list_numb % per_page == 0:
                    table = AsciiTable(table_data)
                    # table.inner_column_border = False
                    # table.outer_border = False
                    table.padding_left = 0
                    table.padding_right = 0
                    table_list.append(table.table)
                    # reset table
                    table_data = [
                        ['PAIR', 'Selling', 'For', 'Rate', 'Order #']
                    ]
                list_numb += 1
            # IF table_data len > 1, append more
            if len(table_data) > 1:
                table = AsciiTable(table_data)
                table.padding_left = 0
                table.padding_right = 0
                table_list.append(table.table)
            return {
                "result": item_selling_list,
                "table": table_list,
                "title": title
            }
        else:
            return {"error": no_trading_msg}

    async def make_open_order(
            self,
            ctx,
            sell_amount: str,
            sell_ticker: str,
            buy_amount: str,
            buy_ticker: str
    ):
        await self.bot_log()
        sell_ticker = sell_ticker.upper()
        buy_ticker = buy_ticker.upper()
        sell_amount = str(sell_amount).replace(",", "")
        buy_amount = str(buy_amount).replace(",", "")
        try:
            sell_amount = text_to_num(sell_amount)
            buy_amount = text_to_num(buy_amount)
            sell_amount = Decimal(sell_amount)
            buy_amount = Decimal(buy_amount)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            msg = f"{ctx.author.mention}, invalid sell/buy amount."
            await ctx.edit_original_message(content=msg)
            return

        if sell_amount <= 0 or buy_amount <= 0:
            msg = f'{ctx.author.mention}, amount can not be negative.'
            await ctx.edit_original_message(content=msg)
            return

        if len(self.bot.coin_alias_names) > 0 and sell_ticker in self.bot.coin_alias_names:
            sell_ticker = self.bot.coin_alias_names[sell_ticker]
        if len(self.bot.coin_alias_names) > 0 and buy_ticker in self.bot.coin_alias_names:
            buy_ticker = self.bot.coin_alias_names[buy_ticker]
        # Check if both coin with TipBot
        if not hasattr(self.bot.coin_list, sell_ticker):
            msg = f'{ctx.author.mention}, **{sell_ticker}** does not exist with us.'
            await ctx.edit_original_message(content=msg)
            return
        elif not hasattr(self.bot.coin_list, buy_ticker):
            msg = f'{ctx.author.mention}, **{buy_ticker}** does not exist with us.'
            await ctx.edit_original_message(content=msg)
            return
        # Check if both coin has trade enable
        if getattr(getattr(self.bot.coin_list, sell_ticker), "enable_trade") != 1:
            msg = f"{ctx.author.mention}, invalid trade ticker `{sell_ticker}`. They may not be enable for trade. "\
                "Check with TipBot dev team."
            await ctx.edit_original_message(content=msg)
            return
        if getattr(getattr(self.bot.coin_list, buy_ticker), "enable_trade") != 1:
            msg = f"{ctx.author.mention}, invalid trade ticker `{buy_ticker}`. They may not be enable for trade. "\
                "Check with TipBot dev team."
            await ctx.edit_original_message(content=msg)
            return

        if buy_ticker == sell_ticker:
            msg = f"{ctx.author.mention}, **{buy_ticker}** you cannot trade the same coins."
            await ctx.edit_original_message(content=msg)
            return

        # get opened order:
        user_count_order = await store.sql_count_open_order_by_sellerid(str(ctx.author.id), SERVER_BOT)
        if user_count_order >= self.bot.config['trade']['Max_Open_Order']:
            msg = f"{ctx.author.mention}, you have maximum opened selling **{self.bot.config['trade']['Max_Open_Order']}**. "\
                f"Please cancel some or wait."
            await ctx.edit_original_message(content=msg)
            return

        sell_amount = float(sell_amount)
        buy_amount = float(buy_amount)
        # sell_ticker
        coin_name = sell_ticker
        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        coin_decimal_sell = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        min_tx = getattr(getattr(self.bot.coin_list, coin_name), "real_min_buysell")
        max_tx = getattr(getattr(self.bot.coin_list, coin_name), "real_max_buysell")
        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
        if sell_amount < min_tx or sell_amount > max_tx:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, trade for {coin_name} cannot be smaller than "\
                f"{num_format_coin(min_tx)} {token_display} or bigger than "\
                f"{num_format_coin(max_tx)} {token_display}."
            await ctx.edit_original_message(content=msg)
            return
        # Get balance user
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

        height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        userdata_balance = await store.sql_user_balance_single(
            str(ctx.author.id), coin_name, wallet_address, type_coin,
            height, deposit_confirm_depth, SERVER_BOT
        )
        actual_balance = float(userdata_balance['adjust'])
        if sell_amount > actual_balance:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance of {coin_name} to trade. "\
                f"Having {num_format_coin(actual_balance)} {coin_name} and needed {num_format_coin(sell_amount)} {coin_name}."
            await ctx.edit_original_message(content=msg)
            return

        # buy_ticker
        coin_name = buy_ticker
        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        coin_decimal_buy = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        min_tx = getattr(getattr(self.bot.coin_list, coin_name), "real_min_buysell")
        max_tx = getattr(getattr(self.bot.coin_list, coin_name), "real_max_buysell")
        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
        if buy_amount < min_tx or buy_amount > max_tx:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, trade for {coin_name} cannot be smaller than "\
                f"{num_format_coin(min_tx)} {token_display} or bigger than "\
                f"{num_format_coin(max_tx)} {token_display}."
            await ctx.edit_original_message(content=msg)
            return

        if sell_amount / buy_amount < self.min_ratio or buy_amount / sell_amount < self.min_ratio:
            msg = f"{ctx.author.mention}, ratio buy/sell rate is so low."
            await ctx.edit_original_message(content=msg)
        else:
            sell_div_get = round(sell_amount / buy_amount, 12)
            fee_sell = round(self.bot.config['trade']['Trade_Margin'] * sell_amount, 8)
            fee_buy = round(self.bot.config['trade']['Trade_Margin'] * buy_amount, 8)
            if fee_sell == 0: fee_sell = 0.00000010
            if fee_buy == 0: fee_buy = 0.00000010
            if str(ctx.author.id) in self.bot.tipping_in_progress and \
                int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 30:
                msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
                await ctx.edit_original_message(content=msg)
                return
            else:
                self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())
            order_add = await store.sql_store_openorder(
                sell_ticker, coin_decimal_sell, sell_amount,
                sell_amount - fee_sell, str(ctx.author.id), buy_ticker,
                coin_decimal_buy, buy_amount, buy_amount - fee_buy,
                sell_div_get, SERVER_BOT
            )
            if order_add:
                try:
                    key_coin = str(ctx.author.id) + "_" + sell_ticker+ "_" + SERVER_BOT
                    if key_coin in self.bot.user_balance_cache:
                        del self.bot.user_balance_cache[key_coin]
                    key_coin = str(ctx.author.id) + "_" + buy_ticker + "_" + SERVER_BOT
                    if key_coin in self.bot.user_balance_cache:
                        del self.bot.user_balance_cache[key_coin]
                except Exception:
                    pass
                try:
                    del self.bot.tipping_in_progress[str(self.ctx.author.id)]
                except Exception:
                    pass
                buy_msg = "You can buy with `/market buy ref_number:{}`.".format(order_add)
                additional_message = " You will sell {} {} and you can get {} {}.".format(
                    num_format_coin(buy_amount), buy_ticker,
                    num_format_coin(sell_amount-fee_sell), sell_ticker,
                )
                get_message = "[P2P] New order created: #**{}**```Selling: {} {}\nFor: {} {}\nFee: {} {}```".format(
                    order_add,
                    num_format_coin(sell_amount), sell_ticker,
                    num_format_coin(buy_amount), buy_ticker,
                    num_format_coin(fee_sell), sell_ticker
                )
                await ctx.edit_original_message(content="{}{}".format(get_message, self.message_cexswap))
                # Find guild where there is trade channel assign
                get_guilds = await self.utils.get_trade_channel_list()
                if len(get_guilds) > 0:
                    for item in get_guilds:
                        try:
                            get_guild = self.bot.get_guild(int(item['serverid']))
                            if get_guild:
                                channel = self.bot.get_channel(int(item['trade_channel']))
                                if channel:
                                    await channel.send(get_message+buy_msg+additional_message)
                                    if channel.id == ctx.channel.id:
                                        await ctx.edit_original_message(content=f"{ctx.author.mention}, sell order posted!")
                        except Exception:
                            traceback.print_exc(file=sys.stdout)

    @commands.slash_command(
        description="Various crypto p2p trading commands."
    )
    async def market(self, ctx):
        await self.bot_log()
        try:
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                if serverinfo and 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "NO":
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, trade function is not ENABLE yet in this guild. "\
                        "Please request Guild owner to enable by `/SETTING TRADE`'
                    await ctx.response.send_message(msg)
                    if self.enable_logchan:
                        await self.botLogChan.send(
                            f"{ctx.author.name} / {ctx.author.id} tried **trade/market command** in "\
                            f"{ctx.guild.name} / {ctx.guild.id} which is not ENABLE."
                        )
                    return
                elif serverinfo and serverinfo['trade_channel'] is not None and \
                    int(serverinfo['trade_channel']) != ctx.channel.id:
                    channel = ctx.guild.get_channel(int(serverinfo['trade_channel']))
                    if channel is not None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, trade channel was assigned to {channel.mention}."
                        await ctx.response.send_message(msg)
        except Exception:
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                return

    @market.sub_command(
        usage="market sell <sell_amount> <sell_ticker> <buy_amount> <buy_ticker>",
        options=[
            Option('sell_amount', 'Enter amount of coin to sell', OptionType.string, required=True),
            Option('sell_ticker', 'Enter coin ticker/name to sell', OptionType.string, required=True),
            Option('buy_amount', 'Enter amount of coin to buy', OptionType.string, required=True),
            Option('buy_ticker', 'Enter coin ticker/name to buy', OptionType.string, required=True)
        ],
        description="Make an opened sell of a coin for another coin."
    )
    async def sell(
        self,
        ctx,
        sell_amount: str,
        sell_ticker: str,
        buy_amount: str,
        buy_ticker: str
    ):

        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, market loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/market sell", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # check lock
        try:
            is_user_locked = self.utils.is_locked_user(str(ctx.author.id), SERVER_BOT)
            if is_user_locked is True:
                await ctx.edit_original_message(content=f"{EMOJI_RED_NO} {ctx.author.mention}, your account is locked for using the Bot. "\
                    "Please contact bot dev by /about link."
                )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # end check lock

        await self.bot_log()
        await self.make_open_order(ctx, sell_amount, sell_ticker, buy_amount, buy_ticker)

    @sell.autocomplete("sell_ticker")
    async def sell_sell_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        list_trade = []
        for each in self.bot.coin_name_list:
            if getattr(getattr(self.bot.coin_list, each), "enable_trade") == 1:
                list_trade.append(each)
        return [name for name in list_trade if string in name.lower()][:10]

    @sell.autocomplete("buy_ticker")
    async def sell_buy_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        list_trade = []
        for each in self.bot.coin_name_list:
            if getattr(getattr(self.bot.coin_list, each), "enable_trade") == 1:
                list_trade.append(each)
        return [name for name in list_trade if string in name.lower()][:10]

    @market.sub_command(
        usage="market myorder [coin]",
        options=[
            Option('ticker', 'ticker', OptionType.string, required=False)
        ],
        description="Check your opened orders."
    )
    async def myorder(
        self,
        ctx,
        ticker: str = None
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, market loading..."
        await ctx.response.send_message(msg)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/market myorder", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        await self.bot_log()

        if ticker:
            if len(ticker) < 6:
                # assume it is a coin
                coin_name = ticker.upper()
                # Check if coin with TipBot
                if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                    coin_name = self.bot.coin_alias_names[coin_name]
                if not hasattr(self.bot.coin_list, coin_name):
                    msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
                    await ctx.edit_original_message(content=msg)
                    return
                if coin_name not in self.bot.coin_name_list:
                    msg = f'{EMOJI_ERROR}, {ctx.author.mention}, **{coin_name}** is not in our supported list.'
                    await ctx.edit_original_message(content=msg)
                    return
                elif getattr(getattr(self.bot.coin_list, coin_name), "enable_trade") != 1:
                    msg = f'{EMOJI_ERROR}, {ctx.author.mention}, **{coin_name}** is not in our trade list.'
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    get_open_order = await store.sql_get_open_order_by_sellerid(str(ctx.author.id), coin_name, 'OPEN')
                    if get_open_order and len(get_open_order) > 0:
                        table_data = [
                            ['PAIR', 'Selling', 'For', 'Order #']
                        ]
                        for order_item in get_open_order:
                            table_data.append([
                                order_item['pair_name'], num_format_coin(order_item['amount_sell']) + order_item['coin_sell'],
                                num_format_coin(order_item['amount_get_after_fee']) + order_item['coin_get'],
                                order_item['order_id']
                            ])
                        table = AsciiTable(table_data)
                        # table.inner_column_border = False
                        # table.outer_border = False
                        table.padding_left = 0
                        table.padding_right = 0
                        msg = f'**[ OPEN SELLING LIST {coin_name}]**\n```{table.table}```'
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        msg = f'{ctx.author.mention}, you do not have any active selling of **{coin_name}**.'
                        await ctx.edit_original_message(content=msg)
                        return
            else:
                # assume this is reference number
                try:
                    ref_number = int(ticker)
                    ref_number = str(ref_number)
                except ValueError:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid # number.'
                    await ctx.edit_original_message(content=msg)
                    return
                get_order_num = await store.sql_get_order_numb(ref_number)
                if get_order_num:
                    # check if own order
                    response_text = "```"
                    response_text += "Order #: " + ref_number + "\n"
                    response_text += "Sell (After Fee): " + num_format_coin(get_order_num['amount_sell_after_fee']) + get_order_num['coin_sell'] + "\n"
                    response_text += "For (After Fee): " + num_format_coin(get_order_num['amount_get_after_fee']) + get_order_num['coin_get'] + "\n"
                    if get_order_num['status'] == "COMPLETE":
                        response_text = response_text.replace("Sell", "Sold")
                        response_text += "Status: COMPLETED"
                    elif get_order_num['status'] == "OPEN":
                        response_text += "Status: OPENED"
                    elif get_order_num['status'] == "CANCEL":
                        response_text += "Status: CANCELLED"
                    response_text += "```"

                    if get_order_num['sell_user_server'] == SERVER_BOT and ctx.author.id == int(
                            get_order_num['userid_sell']):
                        # if he is the seller
                        response_text = response_text.replace("Sell", "You sell")
                        response_text = response_text.replace("Sold", "You sold")
                    if get_order_num['sell_user_server'] and get_order_num['sell_user_server'] == SERVER_BOT and \
                            'userid_get' in get_order_num and (
                            ctx.author.id == int(get_order_num['userid_get'] if get_order_num['userid_get'] else 0)):
                        # if he bought this
                        response_text = response_text.replace("Sold", "You bought: ")
                        response_text = response_text.replace("For (After Fee):", "From selling (After Fee): ")
                    msg = f'{ctx.author.mention} {response_text}'
                    await ctx.edit_original_message(content=msg)
                else:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, I could not find #**{ref_number}**.'
                    await ctx.edit_original_message(content=msg)
                return
        else:
            get_open_order = await store.sql_get_open_order_by_sellerid_all(str(ctx.author.id), 'OPEN')
            if get_open_order and len(get_open_order) > 0:
                table_data = [
                    ['PAIR', 'Selling', 'For', 'Order #']
                ]
                for order_item in get_open_order:
                    table_data.append([
                        order_item['pair_name'],
                        num_format_coin(order_item['amount_sell']) + order_item['coin_sell'],
                        num_format_coin(order_item['amount_get_after_fee']) + order_item['coin_get'],
                        order_item['order_id']
                    ])
                table = AsciiTable(table_data)
                # table.inner_column_border = False
                # table.outer_border = False
                table.padding_left = 0
                table.padding_right = 0
                msg = f'**[ OPEN SELLING LIST ]**\n```{table.table}```'
                await ctx.edit_original_message(content=msg, view=RowButtonRowCloseAnyMessage())
            else:
                msg = f'{ctx.author.mention}, you do not have any active selling.'
                await ctx.edit_original_message(content=msg)

    @myorder.autocomplete("ticker")
    async def myorder_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        list_trade = []
        for each in self.bot.coin_name_list:
            if getattr(getattr(self.bot.coin_list, each), "enable_trade") == 1:
                list_trade.append(each)
        return [name for name in list_trade if string in name.lower()][:10]

    @market.sub_command(
        usage="market cancel <ref_number|all>",
        options=[
            Option('order_num', 'order_num', OptionType.string, required=True)
        ],
        description="Cancel your opened order or all."
    )
    async def cancel(
        self,
        ctx,
        order_num: str = 'ALL'
    ):

        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, market loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/market cancel", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        await self.bot_log()

        if order_num.upper() == 'ALL':
            get_open_order = await store.sql_get_open_order_by_sellerid_all(str(ctx.author.id), 'OPEN')
            if len(get_open_order) == 0:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you do not have any open order.'
                await ctx.edit_original_message(content=msg)
                return
            else:
                cancel_order = await store.sql_cancel_open_order_by_sellerid(str(ctx.author.id), 'ALL')
                msg = f'{ctx.author.mention}, you have cancelled all opened order(s).'
                await ctx.edit_original_message(content=msg)
                return
        else:
            if len(order_num) < 6:
                # use coin name
                coin_name = order_num.upper()
                # Check if coin with TipBot
                if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                    coin_name = self.bot.coin_alias_names[coin_name]
                if not hasattr(self.bot.coin_list, coin_name):
                    msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
                    await ctx.edit_original_message(content=msg)
                    return
                if coin_name not in self.bot.coin_name_list:
                    msg = f'{EMOJI_ERROR}, {ctx.author.mention}, **{coin_name}** is not in our supported list.'
                    await ctx.edit_original_message(content=msg)
                    return
                elif getattr(getattr(self.bot.coin_list, coin_name), "enable_trade") != 1:
                    msg = f'{EMOJI_ERROR}, {ctx.author.mention}, **{coin_name}** is not in our trade list.'
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    get_open_order = await store.sql_get_open_order_by_sellerid(str(ctx.author.id), coin_name, 'OPEN')
                    if len(get_open_order) == 0:
                        msg = f'{ctx.author.mention}, you do not have any open order for **{coin_name}**.'
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        cancel_order = await store.sql_cancel_open_order_by_sellerid(str(ctx.author.id), coin_name)
                        msg = f'{ctx.author.mention}, you have cancelled all opened sell(s) for **{coin_name}**.'
                        await ctx.edit_original_message(content=msg)
                        return
            else:
                # open order number
                get_open_order = await store.sql_get_open_order_by_sellerid_all(str(ctx.author.id), 'OPEN')
                if len(get_open_order) == 0:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you do not have any open order.'
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    cancelled = False
                    for open_order_list in get_open_order:
                        if order_num == str(open_order_list['order_id']):
                            cancel_order = await store.sql_cancel_open_order_by_sellerid(str(ctx.author.id), order_num)
                            if cancel_order: cancelled = True
                    if cancelled is False:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you do not have sell #**{order_num}**. "\
                            "Please check command `/myorder`."
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        msg = f'{ctx.author.mention}, you cancelled #**{order_num}**.'
                        await ctx.edit_original_message(content=msg)

    @market.sub_command(
        usage="market buy <ref_number>",
        options=[
            Option('ref_number', 'ref_number', OptionType.string, required=True)
        ],
        description="Trade from a referenced number."
    )
    async def buy(
        self,
        ctx,
        ref_number: str
    ):

        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, market loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/market buy", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # check lock
        try:
            is_user_locked = self.utils.is_locked_user(str(ctx.author.id), SERVER_BOT)
            if is_user_locked is True:
                await ctx.edit_original_message(content=f"{EMOJI_RED_NO} {ctx.author.mention}, your account is locked for using the Bot. "\
                    "Please contact bot dev by /about link."
                )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # end check lock

        await self.bot_log()
        # check if the argument is ref or ticker by length
        if len(ref_number) < 6:
            # assume it is ticker
            # ,buy trtl (example)
            coin_name = ref_number.upper()
            # Check if coin with TipBot
            if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                coin_name = self.bot.coin_alias_names[coin_name]
            if not hasattr(self.bot.coin_list, coin_name):
                msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
                await ctx.edit_original_message(content=msg)
                return
            if coin_name not in self.bot.coin_name_list:
                msg = f'{EMOJI_ERROR}, {ctx.author.mention}, **{coin_name}** is not in our supported list.'
                await ctx.edit_original_message(content=msg)
                return
            if getattr(getattr(self.bot.coin_list, coin_name), "enable_trade") != 1:
                msg = f'{EMOJI_ERROR}, {ctx.author.mention}, **{coin_name}** is not in our trade list.'
                await ctx.edit_original_message(content=msg)
                return

            # get list of all coin where they sell XXX
            get_markets = await store.sql_get_open_order_by_alluser_by_coins(coin_name, "ALL", "OPEN", "ASC")
            if get_markets and len(get_markets) > 0:
                list_numb = 0
                table_data = [
                    ['PAIR', 'Selling', 'For', 'Rate', 'Order #']
                ]
                for order_item in get_markets:
                    rate = 0.0
                    if order_item['amount_sell'] / order_item['amount_get'] < 0.000001:
                        rate = '{:.8f}'.format(round(order_item['amount_sell'] / order_item['amount_get'], 8))
                    elif order_item['amount_sell'] / order_item['amount_get'] < 0.001:
                        rate = '{:.4f}'.format(round(order_item['amount_sell'] / order_item['amount_get'], 4))
                    else:
                        rate = '{:.2f}'.format(round(order_item['amount_sell'] / order_item['amount_get'], 2))
                    table_data.append([
                        order_item['pair_name'],
                        num_format_coin(order_item['amount_sell_after_fee']) + order_item['coin_sell'],
                        num_format_coin(order_item['amount_get_after_fee']) + order_item['coin_get'], rate,
                        order_item['order_id']
                    ])
                    list_numb += 1
                    if list_numb > 20:
                        break
                table = AsciiTable(table_data)
                # table.inner_column_border = False
                # table.outer_border = False
                table.padding_left = 0
                table.padding_right = 0
                title = "MARKET SELLING **{}**".format(coin_name)
                msg = f'[ {title} ]\n```{table.table}```'
                await ctx.edit_original_message(content=msg)
                return
            else:
                msg = f"{ctx.author.mention}, no opening selling **{coin_name}**. Please make some open order for others."
                await ctx.edit_original_message(content=msg)
                return
        else:
            # assume reference number
            get_order_num = await store.sql_get_order_numb(ref_number)
            if get_order_num:
                # check if own order
                if get_order_num['sell_user_server'] == SERVER_BOT and ctx.author.id == int(
                        get_order_num['userid_sell']):
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention} #**{ref_number}** is your own selling order.'
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    # check if sufficient balance
                    coin_name = get_order_num['coin_get']
                    net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                    type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                    deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
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

                    height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                    userdata_balance = await store.sql_user_balance_single(
                        str(ctx.author.id), coin_name, wallet_address, type_coin, height,
                        deposit_confirm_depth, SERVER_BOT
                    )
                    actual_balance = float(userdata_balance['adjust'])

                    if actual_balance < get_order_num['amount_get_after_fee']:
                        msg = '{} {} You do not have sufficient balance. ```Needed: {} {}\nHave:   {} {}```'.format(
                            EMOJI_RED_NO, ctx.author.mention,
                            num_format_coin(get_order_num['amount_get']),
                            get_order_num['coin_get'], num_format_coin(actual_balance),
                            get_order_num['coin_get']
                        )
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        try:
                            key_coin = str(ctx.author.id) + "_" + get_order_num['coin_get'] + "_" + SERVER_BOT
                            if key_coin in self.bot.user_balance_cache:
                                del self.bot.user_balance_cache[key_coin]

                            key_coin = get_order_num['userid_sell'] + "_" + get_order_num['coin_get'] + "_" + SERVER_BOT
                            if key_coin in self.bot.user_balance_cache:
                                del self.bot.user_balance_cache[key_coin]

                            key_coin = str(ctx.author.id) + "_" + get_order_num['coin_sell'] + "_" + SERVER_BOT
                            if key_coin in self.bot.user_balance_cache:
                                del self.bot.user_balance_cache[key_coin]

                            key_coin = get_order_num['userid_sell'] + "_" + get_order_num['coin_sell'] + "_" + SERVER_BOT
                            if key_coin in self.bot.user_balance_cache:
                                del self.bot.user_balance_cache[key_coin]
                        except Exception:
                            pass
                        if str(ctx.author.id) in self.bot.tipping_in_progress and \
                            int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 30:
                            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
                            await ctx.edit_original_message(content=msg)
                            return
                        else:
                            self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())
                        # let's make order update
                        match_order = await store.sql_match_order_by_sellerid(
                            str(ctx.author.id), ref_number,
                            SERVER_BOT,
                            get_order_num['sell_user_server'],
                            get_order_num['userid_sell'], True
                        )
                        if match_order:
                            try:
                                del self.bot.tipping_in_progress[str(self.ctx.author.id)]
                            except Exception:
                                pass
                            try:
                                got_amount = num_format_coin(
                                    get_order_num['amount_sell_after_fee']
                                )
                                from_selling = num_format_coin(
                                    get_order_num['amount_get']
                                )
                                msg = "[P2P] Order num.: **{}** completed! ```Get: {} {}\nFrom selling: {} {}```".format(
                                    ref_number,
                                    got_amount,
                                    get_order_num['coin_sell'],
                                    from_selling,
                                    get_order_num['coin_get']
                                )
                                # Find guild where there is trade channel assign
                                await ctx.edit_original_message(content=msg)
                                get_guilds = await self.utils.get_trade_channel_list()
                                if len(get_guilds) > 0:
                                    for item in get_guilds:
                                        try:
                                            get_guild = self.bot.get_guild(int(item['serverid']))
                                            if get_guild:
                                                channel = self.bot.get_channel(int(item['trade_channel']))
                                                if channel and ctx.channel.id != channel.id:
                                                    await channel.send(msg)
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                try:
                                    sold = num_format_coin(get_order_num['amount_sell']) + get_order_num['coin_sell']
                                    bought = num_format_coin(get_order_num['amount_get_after_fee']) + get_order_num['coin_get']
                                    fee = num_format_coin(
                                        get_order_num['amount_get'] - get_order_num['amount_get_after_fee']
                                    )
                                    fee += get_order_num['coin_get']
                                    if get_order_num['sell_user_server'] == SERVER_BOT:
                                        member = self.bot.get_user(int(get_order_num['userid_sell']))
                                        if member:
                                            try:
                                                await member.send(
                                                    f'A user has bought #**{ref_number}**\n```Sold: {sold}\nGet: {bought}```')
                                            except (disnake.Forbidden, disnake.errors.Forbidden,
                                                    disnake.errors.HTTPException) as e:
                                                pass
                                    # add message to trade channel as well.
                                    if self.enable_logchan:
                                        await self.botLogChan.send(
                                            f'A user has bought #**{ref_number}**\n```Sold: {sold}\nGet: {bought}\nFee: {fee}```')
                                except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
                                    pass
                            except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
                                pass
                            return
                        else:
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention} **{ref_number}** internal error, please report.'
                            await ctx.edit_original_message(content=msg)
                            return
            else:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention} #**{ref_number}** does not exist or already completed."
                await ctx.edit_original_message(content=msg)

    @market.sub_command(
        usage="market list <coin/pair> <desc|asc>",
        options=[
            Option('coin', 'coin or pair', OptionType.string, required=True),
            Option('option_order', 'desc or asc', OptionType.string, required=False, choices=[
                OptionChoice("desc", "desc"),
                OptionChoice("asc", "asc")]
            )
        ],
        description="Make an opened sell of a coin for another coin.")
    async def list(
        self,
        ctx,
        coin: str,
        option_order: str = 'desc'
    ):

        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, market loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/market list", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        await self.bot_log()

        if option_order is None:
            option_order = "DESC"  # ascending
        elif option_order and (option_order.upper() not in ["DESC", "ASC"]):
            option_order = "DESC"  # ascending
        elif option_order:
            option_order = option_order.upper()

        # check if there is / or -
        coin_pair = None
        coin_name = None
        get_markets = None
        coin = coin.upper()
        if "/" in coin:
            coin_pair = coin.split("/")
        elif "." in coin:
            coin_pair = coin.split(".")
        elif "-" in coin:
            coin_pair = coin.split("-")
        get_list_orders = None
        if coin_pair is None:
            coin_name = coin.upper()
            if coin_name != "ALL":
                # Check if coin with TipBot
                if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                    coin_name = self.bot.coin_alias_names[coin_name]
                if not hasattr(self.bot.coin_list, coin_name):
                    msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
                    await ctx.edit_original_message(content=msg)
                    return

                if getattr(getattr(self.bot.coin_list, coin_name), "enable_trade") != 1:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, {coin_name} in not in our list of trade.'
                    await ctx.edit_original_message(content=msg)
                    return

            await ctx.edit_original_message(content=f"{ctx.author.mention}, Bot's checking trading..")
            get_list_orders = await self.get_open_orders(ctx, option_order, coin_name, None)
        elif coin_pair and len(coin_pair) == 2:
            if getattr(getattr(self.bot.coin_list, coin_pair[0]), "enable_trade") != 1:
                msg = f'{EMOJI_ERROR} {ctx.author.mention}, **{coin_pair[0]}** is not in our list of trade.'
                await ctx.edit_original_message(content=msg)
                return
            elif getattr(getattr(self.bot.coin_list, coin_pair[1]), "enable_trade") != 1:
                msg = f'{EMOJI_ERROR} {ctx.author.mention}, **{coin_pair[1]}** is not in our list.'
                await ctx.edit_original_message(content=msg)
                return
            else:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, Bot's checking trading..")
                get_list_orders = await self.get_open_orders(ctx, option_order, coin_pair[0], coin_pair[1])
        if 'result' in get_list_orders and len(get_list_orders['result']) > 0:
            all_pages = []
            item_nos = 0
            per_page = 6
            empty_page = False
            for each_page in get_list_orders['result']:
                if item_nos == 0 or (item_nos > 0 and item_nos % per_page == 0):
                    if item_nos > 0 and item_nos % per_page == 0:
                        all_pages.append(page)
                    page = disnake.Embed(
                        title=get_list_orders['title'],
                        description="Thank you for trading with TipBot!",
                        color=disnake.Color.blue(),
                        timestamp=datetime.now(),
                    )
                    page.set_thumbnail(url=ctx.author.display_avatar)
                    page.set_footer(text="Use the reactions to flip pages.")
                    empty_page = True
                page.add_field(
                    name="{}: **# {}** (Ratio: {})".format(each_page['pair'], each_page['order_number'], each_page['rate']),
                    value="Selling {} for {}".format(each_page['selling'], each_page['for']),
                    inline=False)
                empty_page = False
                item_nos += 1
            if empty_page is False:
                all_pages.append(page)
            if len(all_pages) == 1:
                all_pages[0].set_footer(text="Please create more opened orders with /market sell")
                await ctx.edit_original_message(
                    content=None,
                    embed=all_pages[0],
                    view=RowButtonRowCloseAnyMessage()
                )
            elif len(all_pages) > 1:
                await ctx.edit_original_message(
                    content=None,
                    embed=all_pages[0],
                    view=MenuPage(ctx, all_pages, timeout=30, disable_remove=False)
                )
        else:
            no_open = ""
            if coin_pair and len(coin_pair) == 2:
                no_open = " for {}/{}".format(coin_pair[0], coin_pair[1])
            msg = f"{ctx.author.mention}, there is no result{no_open}. Please create opened order with /market sell command."
            await ctx.edit_original_message(content=msg)
            return

    @list.autocomplete("coin")
    async def marketlist_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        string = string.lower()
        list_trade = []
        for each in self.bot.coin_name_list:
            if getattr(getattr(self.bot.coin_list, each), "enable_trade") == 1:
                list_trade.append(each)
        return [name for name in list_trade if string in name.lower()][:10]

    @market.sub_command(
        usage="market listcoins",
        description="List coins/tokens supported /market"
    )
    async def listcoins(
        self,
        ctx
    ):

        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, market loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/market listcoins", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        await self.bot_log()
        if self.bot.coin_name_list and len(self.bot.coin_name_list) > 0:
            trade_coins = []
            for coin_name in self.bot.coin_name_list:
                if getattr(getattr(self.bot.coin_list, coin_name), "enable_trade") == 1:
                    trade_coins.append(coin_name)
            coin_list_names = ", ".join(trade_coins)
            if len(trade_coins) > 0:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, list of supported coins/tokens for /market:```{coin_list_names}```")
            else:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, please check again later. I got none now.")
        else:
            await ctx.edit_original_message(content=f"{ctx.author.mention}, please check again later. I got none now.")

    @market.sub_command(
        usage="market listpairs",
        description="List opened or traded pairs"
    )
    async def listpairs(
        self,
        ctx
    ):

        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, market loading..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/market listpairs", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        await self.bot_log()
        get_pairs = await self.sql_get_markets_by_coin('OPEN')

        if len(get_pairs) > 0:
            trade_pairs = []
            for each in get_pairs:
                trade_pairs.append("{}-{}".format(each['coin_sell'], each['coin_get']))
            coin_pairs = ", ".join(trade_pairs)
            if len(trade_pairs) > 0:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, list of available opened pairs:```{coin_pairs}```"
                )
            else:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, please check again later. I got none now.")
        else:
            await ctx.edit_original_message(content=f"{ctx.author.mention}, please check again later. I got none now.")

def setup(bot):
    bot.add_cog(Trade(bot))
