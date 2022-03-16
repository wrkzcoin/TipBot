import sys
import traceback
import datetime

import asyncio
from decimal import Decimal

import disnake
from disnake.ext import tasks, commands
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
import re

import store
import utils
from Bot import num_format_coin, logchanbot, EMOJI_ERROR, EMOJI_RED_NO, SERVER_BOT, RowButton_close_message, RowButton_row_close_any_message, human_format, text_to_num
from config import config


class Price(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    async def async_price(self, ctx, amount: str=None, token: str=None):
        if self.bot.coin_paprika_symbol_list is None:
            msg = f"{ctx.author.mention}, data is not available yet. Please try again soon!"
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        token_list = []
        invalid_token_list = []
        coin_paprika_symbol_list = [each.upper() for each in self.bot.coin_paprika_symbol_list.keys()]

        if amount is None and token is None:
            msg = f"{ctx.author.mention}, invalid command usage!"
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        if amount is not None and amount.upper().endswith(tuple(coin_paprika_symbol_list)):
            # amount is something like 10,0.0BTC [Possible]
            amount_tmp = re.findall(r'[\w\.\,]+[\d]', amount) # If amount "111WRKZ 222WRKZ", take only the first one
            if len(amount_tmp) > 0:
                amount_tmp = amount_tmp[0]
                token_tmp = amount.replace(amount_tmp, "")
                if token_tmp.upper() not in coin_paprika_symbol_list:
                    msg = f"I can not find price of `{token_tmp.upper()}`."
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
                else:
                    amount_old = amount
                    token_list = [token_tmp.upper()]
                    COIN_NAME = token_tmp.upper()
                    amount = amount_tmp.replace(",", "")
                    amount = text_to_num(amount)
                    if amount is None:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return
                
        elif amount is not None and token is not None:
            # amount token
            amount_old = amount
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
            COIN_NAME = token.upper()
            token_list = [COIN_NAME]
        elif amount and not amount.isdigit() and token is None:
            if "," in amount:
                # several token
                tokens = amount.split(",")
                for each in tokens:
                    if each.upper().strip() in self.bot.coin_paprika_symbol_list:
                        token_list.append(each.upper().strip())
                    else:
                        invalid_token_list.append(each.upper().strip())
                if len(token_list) == 1:
                    COIN_NAME = token_list[0].upper()
                    amount_old = 1
                    amount = 1
            elif " " in amount:
                # several token
                tokens = amount.split(" ")
                for each in tokens:
                    if each.upper() in self.bot.coin_paprika_symbol_list:
                        token_list.append(each.upper())
                    else:
                        if each.upper().strip() != "":
                            invalid_token_list.append(each.upper().strip())
                if len(token_list) == 1:
                    COIN_NAME = token_list[0].upper()
                    amount_old = 1
                    amount = 1
            else:
                # token only
                COIN_NAME = amount.upper()
                token_list = [COIN_NAME]
                amount_old = 1
                amount = 1

        if len(token_list) == 1 and COIN_NAME in self.bot.coin_paprika_symbol_list:
            if COIN_NAME in self.bot.token_hints:
                id = self.bot.token_hints[COIN_NAME]['ticker_name']
                per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                name = self.bot.coin_paprika_id_list[id]['name']
            else:
                per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME]['price_usd']
                name = self.bot.coin_paprika_symbol_list[COIN_NAME]['name']
            try:
                total_price = float(amount)*per_unit
                total_price_str = ""
                if total_price > 1000:
                    total_price_str = "{:,.2f}".format(total_price)
                elif total_price > 100:
                    total_price_str = "{:.2f}".format(total_price)
                elif total_price > 1:
                    total_price_str = "{:.3f}".format(total_price)
                elif total_price > 0.01:
                    total_price_str = "{:.4f}".format(total_price)
                else:
                    total_price_str = "{:.8f}".format(total_price)

                update_date = self.bot.coin_paprika_symbol_list[COIN_NAME]['last_updated'].replace(tzinfo=datetime.timezone.utc)
                embed = disnake.Embed(title="PRICE CHECK", description=f'**{COIN_NAME}** | _{name}_', timestamp=update_date)
                embed.add_field(name="Price", value="```{} {} = {} {}```".format(amount_old, COIN_NAME, total_price_str, "USD"), inline=False)
                embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                embed.set_footer(text="Credit: https://api.coinpaprika.com/")
                try:
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(embed=embed, view=RowButton_row_close_any_message())
                    else:
                        await ctx.reply(embed=embed, view=RowButton_row_close_any_message())
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        elif len(token_list) > 1:
            token_list = list(set(token_list))
            coin_price = []
            for each_coin in token_list:
                if each_coin in self.bot.token_hints:
                    id = self.bot.token_hints[each_coin]['ticker_name']
                    per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                else:
                    per_unit = self.bot.coin_paprika_symbol_list[each_coin]['price_usd']
                per_unit_str = ""
                if per_unit > 1000:
                    per_unit_str = "{:,.2f}".format(per_unit)
                elif per_unit > 100:
                    per_unit_str = "{:.2f}".format(per_unit)
                elif per_unit > 1:
                    per_unit_str = "{:.3f}".format(per_unit)
                elif per_unit > 0.01:
                    per_unit_str = "{:.4f}".format(per_unit)
                else:
                    per_unit_str = "{:.8f}".format(per_unit)
                coin_price.append("{} {} = {} {}".format(1, each_coin, per_unit_str, "USD"))
            embed = disnake.Embed(title="PRICE CHECK", description='```{}```'.format(", ".join(token_list)), timestamp=datetime.datetime.utcnow())
            embed.add_field(name="Price List", value="```{}```".format("\n".join(coin_price)), inline=False)
            if len(invalid_token_list) > 0:
                invalid_token_list = list(set(invalid_token_list))
                embed.add_field(name="Invalid Coin/Token", value="```{}```".format(", ".join(invalid_token_list).strip()), inline=False)
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            embed.set_footer(text="Credit: https://api.coinpaprika.com/")
            try:
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(embed=embed, view=RowButton_row_close_any_message())
                else:
                    await ctx.reply(embed=embed, view=RowButton_row_close_any_message())
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        else:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} I could not find this information.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)


    @commands.slash_command(
        usage="price <amount> <token>",
        options=[
            Option('amount', 'amount or token', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=False)
        ],
        description="Display Token price list."
    )
    async def price(
        self, 
        ctx, 
        amount: str, 
        token: str=None
    ):
        return await self.async_price(ctx, amount, token)



def setup(bot):
    bot.add_cog(Price(bot))
