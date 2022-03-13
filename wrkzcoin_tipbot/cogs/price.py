import sys
import traceback
import datetime

import asyncio
from decimal import Decimal

import disnake
from disnake.ext import tasks, commands
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

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

        if amount is None and token is None:
            msg = f"{ctx.author.mention}, invalid command usage!"
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
        elif amount and not amount.isdigit() and token is None:
            # token only
            COIN_NAME = amount.upper()
            amount_old = 1
            amount = 1

        if COIN_NAME in self.bot.coin_paprika_symbol_list:
            try:
                per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME]['price_usd']
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
                name = self.bot.coin_paprika_symbol_list[COIN_NAME]['name']
                update_date = self.bot.coin_paprika_symbol_list[COIN_NAME]['last_updated'].replace(tzinfo=datetime.timezone.utc)
                embed = disnake.Embed(title="PRICE CHECK", description=f'**{COIN_NAME}** | _{name}_', timestamp=update_date)
                embed.add_field(name="Price", value="```{} {} = {} {}```".format(amount_old, COIN_NAME, total_price_str, "USD"), inline=False)
                embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                embed.set_footer(text="Credit: https://api.coinpaprika.com/".format(self.bot.coin_paprika_symbol_list[COIN_NAME]['last_updated']))
                try:
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(embed=embed, view=RowButton_row_close_any_message())
                    else:
                        await ctx.reply(embed=embed, view=RowButton_row_close_any_message())
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
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
