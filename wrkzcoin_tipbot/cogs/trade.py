import sys, traceback
import time, timeago
import disnake
from disnake.ext import commands
from decimal import getcontext, Decimal
from datetime import datetime

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

# ascii table
from terminaltables import AsciiTable

from config import config
import store
from Bot import get_token_list, num_format_coin, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, RowButton_close_message, RowButton_row_close_any_message, human_format, text_to_num, truncate, seconds_str, EMOJI_HOURGLASS_NOT_DONE

from utils import MenuPage
import redis_utils
from cogs.wallet import WalletAPI


class Trade(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.botLogChan = None
        self.enable_logchan = True
        redis_utils.openRedis()


    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)


    async def get_open_orders(
        self,
        ctx,
        option: str,
        coin1: str,
        coin2: str=None
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
            no_trading_msg = f"Currently, no opening selling or buying market for {coin1.upper()}. Please make some open order for others."
        else:
            get_markets = await store.sql_get_open_order_by_alluser_by_coins(coin1.upper(), coin2.upper(), "OPEN", option)
            title = "**MARKET {}/{}**".format(coin1.upper(), coin2.upper())
            no_trading_msg = f"Currently, no opening selling market pair for {coin1.upper()} with {coin2.upper()}. Please make some open order for others."

        if get_markets and len(get_markets) > 0:
            list_numb = 0
            table_data = [
                ['PAIR', 'Selling', 'For', 'Rate', 'Order #']
                ]
            for order_item in get_markets:
                rate = 0.0
                if order_item['amount_sell']/order_item['amount_get'] < 0.000001:
                    rate = '{:.8f}'.format(round(order_item['amount_sell']/order_item['amount_get'], 8))
                elif order_item['amount_sell']/order_item['amount_get'] < 0.001:
                    rate = '{:.4f}'.format(round(order_item['amount_sell']/order_item['amount_get'], 4))
                else:
                    rate = '{:.2f}'.format(round(order_item['amount_sell']/order_item['amount_get'], 2))
                table_data.append([order_item['pair_name'], num_format_coin(order_item['amount_sell_after_fee'], order_item['coin_sell'], getattr(getattr(self.bot.coin_list, order_item['coin_sell']), "decimal"), False)+order_item['coin_sell'], num_format_coin(order_item['amount_get'], order_item['coin_get'], getattr(getattr(self.bot.coin_list, order_item['coin_get']), "decimal"), False)+order_item['coin_get'], '{:.8f}'.format(round(order_item['amount_sell']/order_item['amount_get'], 8)), order_item['order_id']])
                item_selling_list.append({
                    "pair": order_item['pair_name'], 
                    "selling": num_format_coin(order_item['amount_sell_after_fee'], order_item['coin_sell'], getattr(getattr(self.bot.coin_list, order_item['coin_sell']), "decimal"), False)+" "+order_item['coin_sell'],
                    "for": num_format_coin(order_item['amount_get'], order_item['coin_get'], getattr(getattr(self.bot.coin_list, order_item['coin_get']), "decimal"), False)+" "+order_item['coin_get'],
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
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            msg = f"{ctx.author.mention}, invalid sell/buy amount."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        if sell_amount <= 0 or buy_amount <= 0:
            if type(ctx) == disnake.ApplicationCommandInteraction:
                msg = f'{ctx.author.mention}, amount can not be negative.'
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        # Check if both coin with TipBot
        if not hasattr(self.bot.coin_list, sell_ticker):
            if type(ctx) == disnake.ApplicationCommandInteraction:
                msg = f'{ctx.author.mention}, **{sell_ticker}** does not exist with us.'
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        elif not hasattr(self.bot.coin_list, buy_ticker):
            if type(ctx) == disnake.ApplicationCommandInteraction:
                msg = f'{ctx.author.mention}, **{buy_ticker}** does not exist with us.'
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        # Check if both coin has trade enable
        if getattr(getattr(self.bot.coin_list, sell_ticker), "enable_trade") != 1:
            msg = f"{ctx.author.mention}, invalid trade ticker `{sell_ticker}`. They may not be enable for trade. Check with TipBot dev team."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        if getattr(getattr(self.bot.coin_list, buy_ticker), "enable_trade") != 1:
            msg = f"{ctx.author.mention}, invalid trade ticker `{buy_ticker}`. They may not be enable for trade. Check with TipBot dev team."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        if buy_ticker == sell_ticker:
            msg = f"{ctx.author.mention}, **{buy_ticker}** you cannot trade the same coins."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        # get opened order:
        user_count_order = await store.sql_count_open_order_by_sellerid(str(ctx.author.id), SERVER_BOT)
        if user_count_order >= config.trade.Max_Open_Order:
            msg = f"{ctx.author.mention}, you have maximum opened selling **{config.trade.Max_Open_Order}**. Please cancel some or wait."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        sell_amount = float(sell_amount)
        buy_amount = float(buy_amount)
        # sell_ticker
        COIN_NAME = sell_ticker
        net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
        coin_decimal_sell = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
        MinTx = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_buysell")
        MaxTx = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_buysell")
        token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
        if sell_amount < MinTx or sell_amount >  MaxTx:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, trade for {COIN_NAME} cannot be smaller than {num_format_coin(MinTx, COIN_NAME, coin_decimal_sell, False)} {token_display} or bigger than {num_format_coin(MaxTx, COIN_NAME, coin_decimal_sell, False)} {token_display}.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        # Get balance user
        User_WalletAPI = WalletAPI(self.bot)
        get_deposit = await User_WalletAPI.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await User_WalletAPI.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

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

        userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])
        if sell_amount > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance of {COIN_NAME} to trade. Having {num_format_coin(actual_balance, COIN_NAME, coin_decimal_sell, False)} {COIN_NAME} and needed {num_format_coin(sell_amount, COIN_NAME, coin_decimal_sell, False)} {COIN_NAME}.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        # buy_ticker
        COIN_NAME = buy_ticker
        net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
        coin_decimal_buy = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
        MinTx = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_buysell")
        MaxTx = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_buysell")
        token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
        if buy_amount < MinTx or buy_amount >  MaxTx:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, trade for {COIN_NAME} cannot be smaller than {num_format_coin(MinTx, COIN_NAME, coin_decimal_buy, False)} {token_display} or bigger than {num_format_coin(MaxTx, COIN_NAME, coin_decimal_buy, False)} {token_display}.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        if sell_amount / buy_amount < config.trade.Min_Ratio or buy_amount / sell_amount < config.trade.Min_Ratio:
            msg = f"{ctx.author.mention}, ratio buy/sell rate is so low."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        else:
            sell_div_get = round(sell_amount / buy_amount, 12)
            fee_sell = round(config.trade.Trade_Margin * sell_amount, 8)
            fee_buy = round(config.trade.Trade_Margin * buy_amount, 8)
            if fee_sell == 0: fee_sell = 0.00000010
            if fee_buy == 0: fee_buy = 0.00000010
            order_add = await store.sql_store_openorder(sell_ticker, coin_decimal_sell, sell_amount, sell_amount-fee_sell, str(ctx.author.id), buy_ticker, coin_decimal_buy, buy_amount, buy_amount-fee_buy, sell_div_get, SERVER_BOT)
            if order_add:
                get_message = "New open order created: #**{}**```Selling: {} {}\nFor: {} {}\nFee: {} {}```".format(order_add, 
                            num_format_coin(sell_amount, sell_ticker, coin_decimal_sell, False), sell_ticker,
                            num_format_coin(buy_amount, buy_ticker, coin_decimal_buy, False), buy_ticker,
                            num_format_coin(fee_sell, sell_ticker, coin_decimal_sell, False), sell_ticker)
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(get_message)
            else:
                await ctx.reply(get_message)
            return


    @commands.slash_command(usage="sell <sell_amount> <sell_ticker> <buy_amount> <buy_ticker>",
                            options=[
                                Option('sell_amount', 'Enter amount of coin to sell', OptionType.string, required=True),
                                Option('sell_ticker', 'Enter coin ticker/name to sell', OptionType.string, required=True),
                                Option('buy_amount', 'Enter amount of coin to buy', OptionType.string, required=True),
                                Option('buy_ticker', 'Enter coin ticker/name to buy', OptionType.string, required=True)
                            ],
                            description="Make an opened sell of a coin for another coin.")
    async def sell(
        self, 
        ctx, 
        sell_amount: str, 
        sell_ticker: str, 
        buy_amount: str, 
        buy_ticker: str
    ):
        await self.bot_log()
        try:
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                if serverinfo and 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "NO":
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, trade function is not ENABLE yet in this guild. Please request Guild owner to enable by `/SETTING TRADE`'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    if self.enable_logchan:
                        await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **trade/market command** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
                    return
        except Exception as e:
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                return

        create_order = await self.make_open_order(ctx, sell_amount, sell_ticker, buy_amount, buy_ticker)


    @commands.slash_command(usage="buy <ref_number>", 
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
        await self.bot_log()
        try:
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                if serverinfo and 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "NO":
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, trade function is not ENABLE yet in this guild. Please request Guild owner to enable by `/SETTING TRADE`'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    if self.enable_logchan:
                        await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **trade/market command** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
                    return
        except Exception as e:
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                return

        # check if the argument is ref or ticker by length
        if len(ref_number) < 6:
            # assume it is ticker
            # ,buy trtl (example)
            COIN_NAME = ref_number.upper()
            # Check if coin with TipBot
            if not hasattr(self.bot.coin_list, COIN_NAME):
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
            if COIN_NAME not in self.bot.coin_name_list:
                msg = f'{EMOJI_ERROR}, {ctx.author.mention}, **{COIN_NAME}** is not in our supported list.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_trade") != 1:
                msg = f'{EMOJI_ERROR}, {ctx.author.mention}, **{COIN_NAME}** is not in our trade list.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return

            # get list of all coin where they sell XXX
            get_markets = await store.sql_get_open_order_by_alluser_by_coins(COIN_NAME, "ALL", "OPEN", "ASC")
            if get_markets and len(get_markets) > 0:
                list_numb = 0
                table_data = [
                    ['PAIR', 'Selling', 'For', 'Rate', 'Order #']
                    ]
                for order_item in get_markets:
                    rate = 0.0
                    if order_item['amount_sell']/order_item['amount_get'] < 0.000001:
                        rate = '{:.8f}'.format(round(order_item['amount_sell']/order_item['amount_get'], 8))
                    elif order_item['amount_sell']/order_item['amount_get'] < 0.001:
                        rate = '{:.4f}'.format(round(order_item['amount_sell']/order_item['amount_get'], 4))
                    else:
                        rate = '{:.2f}'.format(round(order_item['amount_sell']/order_item['amount_get'], 2))
                    table_data.append([order_item['pair_name'], num_format_coin(order_item['amount_sell_after_fee'], order_item['coin_sell'], getattr(getattr(self.bot.coin_list, order_item['coin_sell']), "decimal"), False)+order_item['coin_sell'], num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'], getattr(getattr(self.bot.coin_list, order_item['coin_get']), "decimal"), False)+order_item['coin_get'], rate, order_item['order_id']])
                    list_numb += 1
                    if list_numb > 20:
                        break
                table = AsciiTable(table_data)
                # table.inner_column_border = False
                # table.outer_border = False
                table.padding_left = 0
                table.padding_right = 0
                title = "MARKET SELLING **{}**".format(COIN_NAME)
                msg = f'[ {title} ]\n```{table.table}```'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
            else:
                msg = f'{ctx.author.mention}, no opening selling **{COIN_NAME}**. Please make some open order for others.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
        else:
            # assume reference number
            get_order_num = await store.sql_get_order_numb(ref_number)
            if get_order_num:
                # check if own order
                if get_order_num['sell_user_server'] == SERVER_BOT and ctx.author.id == int(get_order_num['userid_sell']):
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention} #**{ref_number}** is your own selling order.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
                else:
                    # check if sufficient balance
                    COIN_NAME = get_order_num['coin_get']
                    net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                    type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                    deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                    User_WalletAPI = WalletAPI(self.bot)
                    get_deposit = await User_WalletAPI.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                    if get_deposit is None:
                        get_deposit = await User_WalletAPI.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

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

                    userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                    actual_balance = float(userdata_balance['adjust'])

                    if actual_balance < get_order_num['amount_get_after_fee']:
                        msg = '{} {} You do not have sufficient balance. ```Needed: {}{}\nHave:   {}{}```'.format(EMOJI_RED_NO, ctx.author.mention, num_format_coin(get_order_num['amount_get'], get_order_num['coin_get'], getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal"), False), get_order_num['coin_get'], num_format_coin(actual_balance, get_order_num['coin_get'], getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal"), False), get_order_num['coin_get'])
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return
                    else:
                        # let's make order update
                        match_order = await store.sql_match_order_by_sellerid(str(ctx.author.id), ref_number, SERVER_BOT, get_order_num['sell_user_server'], get_order_num['userid_sell'], True)
                        if match_order:
                            try:
                                msg = '{} #**{}** Order completed! ```Get: {}{}\nFrom selling: {}{}\nFee: {}{}\n```'.format(ctx.author.mention, ref_number, num_format_coin(get_order_num['amount_sell_after_fee'], get_order_num['coin_sell'], getattr(getattr(self.bot.coin_list, get_order_num['coin_sell']), "decimal"), False), get_order_num['coin_sell'], num_format_coin(get_order_num['amount_get_after_fee'], get_order_num['coin_get'], getattr(getattr(self.bot.coin_list, get_order_num['coin_get']), "decimal"), False), get_order_num['coin_get'], num_format_coin(get_order_num['amount_get']-get_order_num['amount_get_after_fee'], get_order_num['coin_get'], getattr(getattr(self.bot.coin_list, get_order_num['coin_get']), "decimal"), False), get_order_num['coin_get'])
                                if type(ctx) == disnake.ApplicationCommandInteraction:
                                    await ctx.response.send_message(msg)
                                else:
                                    await ctx.reply(msg)
                                try:
                                    sold = num_format_coin(get_order_num['amount_sell'], get_order_num['coin_sell'], getattr(getattr(self.bot.coin_list, get_order_num['coin_sell']), "decimal"), False) + get_order_num['coin_sell']
                                    bought = num_format_coin(get_order_num['amount_get_after_fee'], get_order_num['coin_get'], getattr(getattr(self.bot.coin_list, get_order_num['coin_get']), "decimal"), False) + get_order_num['coin_get']
                                    fee = str(num_format_coin(get_order_num['amount_get']-get_order_num['amount_get_after_fee'], get_order_num['coin_get'], getattr(getattr(self.bot.coin_list, get_order_num['coin_get']), "decimal"), False))
                                    fee += get_order_num['coin_get']
                                    if get_order_num['sell_user_server'] == SERVER_BOT:
                                        member = self.bot.get_user(int(get_order_num['userid_sell']))
                                        if member:
                                            try:
                                                await member.send(f'A user has bought #**{ref_number}**\n```Sold: {sold}\nGet: {bought}```')
                                            except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
                                                pass
                                    # add message to trade channel as well.
                                    if self.enable_logchan:
                                        await self.botLogChan.send(f'A user has bought #**{ref_number}**\n```Sold: {sold}\nGet: {bought}\nFee: {fee}```')
                                except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
                                    pass
                            except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
                                pass
                            return
                        else:
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention} **{ref_number}** internal error, please report.'
                            if type(ctx) == disnake.ApplicationCommandInteraction:
                                await ctx.response.send_message(msg)
                            else:
                                await ctx.reply(msg)
                            return
            else:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} #**{ref_number}** does not exist or already completed.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return


    @commands.slash_command(usage="cancel <ref_number|all>",
                            options=[
                                Option('order_num', 'order_num', OptionType.string, required=True)
                            ],
                            description="Cancel your opened order or all.")
    async def cancel(
        self, 
        ctx, 
        order_num: str = 'ALL'
    ):
        await self.bot_log()
        try:
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                if serverinfo and 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "NO":
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, trade function is not ENABLE yet in this guild. Please request Guild owner to enable by `/SETTING TRADE`'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    if self.enable_logchan:
                        await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **trade/market command** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
                    return
        except Exception as e:
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                return

        if order_num.upper() == 'ALL':
            get_open_order = await store.sql_get_open_order_by_sellerid_all(str(ctx.author.id), 'OPEN')
            if len(get_open_order) == 0:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you do not have any open order.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
            else:
                cancel_order = await store.sql_cancel_open_order_by_sellerid(str(ctx.author.id), 'ALL')
                msg = f'{ctx.author.mention}, you have cancelled all opened order(s).'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
        else:
            if len(order_num) < 6:
                # use coin name
                COIN_NAME = order_num.upper()
                # Check if coin with TipBot
                if not hasattr(self.bot.coin_list, COIN_NAME):
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
                if COIN_NAME not in self.bot.coin_name_list:
                    msg = f'{EMOJI_ERROR}, {ctx.author.mention}, **{COIN_NAME}** is not in our supported list.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
                elif getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_trade") != 1:
                    msg = f'{EMOJI_ERROR}, {ctx.author.mention}, **{COIN_NAME}** is not in our trade list.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
                else:
                    get_open_order = await store.sql_get_open_order_by_sellerid(str(ctx.author.id), COIN_NAME, 'OPEN')
                    if len(get_open_order) == 0:
                        msg = f'{ctx.author.mention}, you do not have any open order for **{COIN_NAME}**.'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return
                    else:
                        cancel_order = await store.sql_cancel_open_order_by_sellerid(str(ctx.author.id), COIN_NAME)
                        msg = f'{ctx.author.mention}, you have cancelled all opened sell(s) for **{COIN_NAME}**.'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return
            else:
                # open order number
                get_open_order = await store.sql_get_open_order_by_sellerid_all(str(ctx.author.id), 'OPEN')
                if len(get_open_order) == 0:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you do not have any open order.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
                else:
                    cancelled = False
                    for open_order_list in get_open_order:
                        if order_num == str(open_order_list['order_id']):
                            cancel_order = await store.sql_cancel_open_order_by_sellerid(str(ctx.author.id), order_num) 
                            if cancel_order: cancelled = True
                    if cancelled == False:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you do not have sell #**{order_num}**. Please check command `/myorder`.'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return
                    else:
                        msg = f'{ctx.author.mention}, you cancelled #**{order_num}**.'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return


    @commands.slash_command(usage="myorder [coin]",
                            options=[
                                Option('ticker', 'ticker', OptionType.string, required=False)
                            ],
                            description="Check your opened orders.")
    async def myorder(
        self, 
        ctx, 
        ticker: str = None
    ):
        await self.bot_log()
        try:
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                if serverinfo and 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "NO":
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, trade function is not ENABLE yet in this guild. Please request Guild owner to enable by `/SETTING TRADE`'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    if self.enable_logchan:
                        await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **trade/market command** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
                    return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                return

        if ticker:
            if len(ticker) < 6:
                # assume it is a coin
                COIN_NAME = ticker.upper()
                # Check if coin with TipBot
                if not hasattr(self.bot.coin_list, COIN_NAME):
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
                if COIN_NAME not in self.bot.coin_name_list:
                    msg = f'{EMOJI_ERROR}, {ctx.author.mention}, **{COIN_NAME}** is not in our supported list.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
                elif getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_trade") != 1:
                    msg = f'{EMOJI_ERROR}, {ctx.author.mention}, **{COIN_NAME}** is not in our trade list.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
                else:
                    get_open_order = await store.sql_get_open_order_by_sellerid(str(ctx.author.id), COIN_NAME, 'OPEN')
                    if get_open_order and len(get_open_order) > 0:
                        table_data = [
                            ['PAIR', 'Selling', 'For', 'Order #']
                            ]
                        for order_item in get_open_order:
                            table_data.append([order_item['pair_name'], num_format_coin(order_item['amount_sell'], order_item['coin_sell'], getattr(getattr(self.bot.coin_list, order_item['coin_sell']), "decimal"), False)+order_item['coin_sell'], num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'], getattr(getattr(self.bot.coin_list, order_item['coin_get']), "decimal"), False)+order_item['coin_get'], rder_item['order_id']])
                        table = AsciiTable(table_data)
                        # table.inner_column_border = False
                        # table.outer_border = False
                        table.padding_left = 0
                        table.padding_right = 0
                        msg = f'**[ OPEN SELLING LIST {COIN_NAME}]**\n```{table.table}```'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return
                    else:
                        msg = f'{ctx.author.mention}, you do not have any active selling of **{COIN_NAME}**.'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return
            else:
                # assume this is reference number
                try:
                    ref_number = int(ticker)
                    ref_number = str(ref_number)
                except ValueError:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid # number.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
                get_order_num = await store.sql_get_order_numb(ref_number)
                if get_order_num:
                    # check if own order
                    response_text = "```"
                    response_text += "Order #: " + ref_number + "\n"
                    response_text += "Sell (After Fee): " + num_format_coin(get_order_num['amount_sell_after_fee'], get_order_num['coin_sell'], getattr(getattr(self.bot.coin_list, get_order_num['coin_sell']), "decimal"), False)+get_order_num['coin_sell'] + "\n"
                    response_text += "For (After Fee): " + num_format_coin(get_order_num['amount_get_after_fee'], get_order_num['coin_get'], getattr(getattr(self.bot.coin_list, get_order_num['coin_get']), "decimal"), False)+get_order_num['coin_get'] + "\n"
                    if get_order_num['status'] == "COMPLETE":
                        response_text = response_text.replace("Sell", "Sold")
                        response_text += "Status: COMPLETED"
                    elif get_order_num['status'] == "OPEN":
                        response_text += "Status: OPENED"
                    elif get_order_num['status'] == "CANCEL":
                        response_text += "Status: CANCELLED"
                    response_text += "```"

                    if get_order_num['sell_user_server'] == SERVER_BOT and ctx.author.id == int(get_order_num['userid_sell']):
                        # if he is the seller
                        response_text = response_text.replace("Sell", "You sell")
                        response_text = response_text.replace("Sold", "You sold")
                    if get_order_num['sell_user_server'] and get_order_num['sell_user_server'] == SERVER_BOT and \
                        'userid_get' in get_order_num and (ctx.author.id == int(get_order_num['userid_get'] if get_order_num['userid_get'] else 0)):
                        # if he bought this
                        response_text = response_text.replace("Sold", "You bought: ")
                        response_text = response_text.replace("For (After Fee):", "From selling (After Fee): ")
                    msg = f'{ctx.author.mention} {response_text}'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                else:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, I could not find #**{ref_number}**.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                return
        else:
            get_open_order = await store.sql_get_open_order_by_sellerid_all(str(ctx.author.id), 'OPEN')
            if get_open_order and len(get_open_order) > 0:
                table_data = [
                    ['PAIR', 'Selling', 'For', 'Order #']
                    ]
                for order_item in get_open_order:
                    table_data.append([order_item['pair_name'], num_format_coin(order_item['amount_sell'], order_item['coin_sell'], getattr(getattr(self.bot.coin_list, order_item['coin_sell']), "decimal"), False)+order_item['coin_sell'], num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'], getattr(getattr(self.bot.coin_list, order_item['coin_get']), "decimal"), False)+order_item['coin_get'], order_item['order_id']])
                table = AsciiTable(table_data)
                # table.inner_column_border = False
                # table.outer_border = False
                table.padding_left = 0
                table.padding_right = 0
                msg = f'**[ OPEN SELLING LIST ]**\n```{table.table}```'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg, view=RowButton_row_close_any_message())
                else:
                    await ctx.reply(msg)
            else:
                msg = f'{ctx.author.mention}, you do not have any active selling.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
            return


    @commands.slash_command(usage="trade <coin/pair> <desc|asc>",
                            options=[
                                Option('coin', 'coin or pair', OptionType.string, required=True),
                                Option('option_order', 'desc or asc', OptionType.string, required=False, choices=[
                                    OptionChoice("desc", "desc"),
                                    OptionChoice("asc", "asc")
                                ]
                                )
                            ],
                            description="Make an opened sell of a coin for another coin.")
    async def trade(
        self, 
        ctx, 
        coin: str, 
        option_order: str='desc'
    ):
        await self.bot_log()
        try:
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                if serverinfo and 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "NO":
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, trade function is not ENABLE yet in this guild. Please request Guild owner to enable by `/SETTING TRADE`'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    if self.enable_logchan:
                        await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **trade/market command** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
                    return
        except Exception as e:
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                return

        if option_order is None:
            option_order = "DESC" # ascending
        elif option_order and (option_order.upper() not in ["DESC", "ASC"]):
            option_order = "DESC" # ascending
        elif option_order:
            option_order = option_order.upper()

        # check if there is / or -
        coin_pair = None
        COIN_NAME = None
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
            COIN_NAME = coin.upper()
            # Check if coin with TipBot
            if not hasattr(self.bot.coin_list, COIN_NAME):
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
            
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_trade") != 1:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, {COIN_NAME} in not in our list of trade.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
            else:
                get_list_orders = await self.get_open_orders(ctx, option_order, COIN_NAME, None)
        elif coin_pair and len(coin_pair) == 2:
            if getattr(getattr(self.bot.coin_list, coin_pair[0]), "enable_trade") != 1:
                msg = f'{EMOJI_ERROR} {ctx.author.mention}, **{coin_pair[0]}** is not in our list of trade.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
            elif getattr(getattr(self.bot.coin_list, coin_pair[1]), "enable_trade") != 1:
                msg = f'{EMOJI_ERROR} {ctx.author.mention}, **{coin_pair[1]}** is not in our list.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
            else:
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
                    page = disnake.Embed(title=get_list_orders['title'],
                                         description="Thank you for trading with TipBot!",
                                         color=disnake.Color.blue(),
                                         timestamp=datetime.utcnow(), )
                    page.set_thumbnail(url=ctx.author.display_avatar)
                    page.set_footer(text="Use the reactions to flip pages.")
                    empty_page = True
                page.add_field(name="{}: **# {}** (Ratio: {})".format(each_page['pair'], each_page['order_number'], each_page['rate']), value="```Selling {} for {}```".format(each_page['selling'], each_page['for']), inline=False)
                empty_page = False
                item_nos += 1
            if empty_page == False:
                all_pages.append(page)
            if len(all_pages) == 1:
                all_pages[0].set_footer(text="Please create more opened orders with /sell")
                await ctx.response.send_message(embed=all_pages[0], view=RowButton_row_close_any_message())
            elif len(all_pages) > 1:
                await ctx.response.send_message(embed=all_pages[0], view=MenuPage(ctx, all_pages, timeout=30))
        else:
            no_open = ""
            if coin_pair and len(coin_pair) == 2:
                no_open = " for {}/{}".format(coin_pair[0], coin_pair[1])
            msg = f'{ctx.author.mention}, there is no result{no_open}. Please create opened order with /sell command.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return


def setup(bot):
    bot.add_cog(Trade(bot))