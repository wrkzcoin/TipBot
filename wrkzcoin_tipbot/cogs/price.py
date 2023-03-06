from datetime import datetime, timedelta
import time
import sys, os
import os.path
import traceback
import random
import functools
import disnake
from Bot import EMOJI_RED_NO, RowButtonRowCloseAnyMessage, text_to_num, \
    EMOJI_HOURGLASS_NOT_DONE, EMOJI_INFORMATION, SERVER_BOT
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands
from cogs.utils import Utils, makechart


def round_dt(dt, delta):
    return datetime.min + round((dt - datetime.min) / delta) * delta

class Price(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utils = Utils(self.bot)

    @commands.slash_command(
        name="price",
        usage="price <token>",
        options=[
            Option('token', 'token', OptionType.string, required=True)
        ],
        description="Display Token price."
    )
    async def cmd_price(
        self,
        ctx,
        token: str
    ):
        await ctx.response.send_message(f"{EMOJI_HOURGLASS_NOT_DONE} {ctx.author.mention}, checking price..")

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/price", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        if token is None:
            await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, missing coin/token name.")
            return

        get_gecko = await self.utils.gecko_get_coin_db(token)
        if len(get_gecko) == 0:
            await ctx.edit_original_message(
                content=f"{EMOJI_RED_NO} {ctx.author.mention}, there's no result of such coin/token name.",
                view=RowButtonRowCloseAnyMessage()
            )
            return
        elif len(get_gecko) > 1:
            ids = ", ".join([i['id'] for i in get_gecko])
            names = ", ".join([i['name'] for i in get_gecko])
            await ctx.edit_original_message(
                content=f"{EMOJI_RED_NO} {ctx.author.mention}, there are more than one result. "\
                    f"Please re-try by specifying with coin/token's id (`{ids}`) or names (`{names}`).",
                view=RowButtonRowCloseAnyMessage()
            )
            return
        else:
            # == 1
            coin_info = get_gecko[0]
            embed = disnake.Embed(
                title="CoinGecko",
                description=f"**{coin_info['symbol'].upper()}** | _{coin_info['name']}_",
                timestamp=datetime.now()
            )
            unit_price = coin_info['price_usd']
            if coin_info['price_usd'] >= 0.01:
                unit_price = "{:,.2f} USD".format(coin_info['price_usd'])
            elif coin_info['price_usd'] >= 0.0001:
                unit_price = "{:,.5f} USD".format(coin_info['price_usd'])
            
            if coin_info['usd_market_cap'] and coin_info['usd_market_cap'] > 1:
                embed.add_field(
                    name="MarketCap (USD)",
                    value="{:,.2f}".format(coin_info['usd_market_cap']),
                    inline=True
                )
            embed.add_field(
                name="Price (USD)",
                value="{}\n{}".format(
                    unit_price,
                    "<t:{}:f>".format(coin_info['price_time'])
                ),
                inline=True
            )
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            embed.set_footer(text="Credit: CoinGecko")
            # Edit first before running graph
            await ctx.edit_original_message(content=None, embed=embed)
            try:
                get_marketdata = await self.utils.gecko_fetch_marketdata_coin(coin_info['id'])
                get_marketchart = await self.utils.gecko_fetch_marketchart_coin(coin_info['id'])
                if get_marketdata is not None and get_marketchart is not None:
                    marketdata = get_marketdata['market_data']
                    list_key = [
                        'price_change_24h', 'price_change_percentage_24h',
                        'price_change_percentage_7d', 'price_change_percentage_14d',
                        'price_change_percentage_30d'
                    ]
                    checkin =  all(elem in marketdata  for elem in list_key)
                    if checkin:
                        if abs(marketdata['price_change_24h']) > 0.01:
                            embed.add_field(
                                name="Change 24H",
                                value="{:,.2f} USD".format(marketdata['price_change_24h']),
                                inline=True
                            )
                        if abs(marketdata['price_change_percentage_24h']) > 0.01:
                            embed.add_field(
                                name="Change 24H",
                                value="{:,.2f}{}".format(marketdata['price_change_percentage_24h'], "%"),
                                inline=True
                            )
                        if abs(marketdata['price_change_percentage_7d']) > 0.01:
                            embed.add_field(
                                name="Change 7d",
                                value="{:,.2f}{}".format(marketdata['price_change_percentage_7d'], "%"),
                                inline=True
                            )
                        if abs(marketdata['price_change_percentage_14d']) > 0.01:
                            embed.add_field(
                                name="Change 14d",
                                value="{:,.2f}{}".format(marketdata['price_change_percentage_14d'], "%"),
                                inline=True
                            )
                        if abs(marketdata['price_change_percentage_30d']) > 0.01:
                            embed.add_field(
                                name="Change 30d",
                                value="{:,.2f}{}".format(marketdata['price_change_percentage_30d'], "%"),
                                inline=True
                            )
                        if len(get_marketchart['prices']) > 30 and len(get_marketchart['total_volumes']) > 30:
                            # make chart
                            delta = timedelta(minutes=5)
                            chart_name = round_dt(datetime.now(), delta).strftime("%Y-%m-%d-%H_%M") + "_coingecko_" + coin_info['id'].lower() + ".png"
                            saved_path = self.bot.config['cg_marketchart']['static_image_path'] + chart_name
                            has_chart = False
                            if os.path.exists(saved_path):
                                has_chart = True
                            else:
                                create_chart = functools.partial(makechart, get_marketchart, saved_path)
                                making_chart = await self.bot.loop.run_in_executor(None, create_chart)
                                if making_chart is not None and os.path.exists(saved_path):
                                    has_chart = True
                            if has_chart is True:
                                embed.set_image(url=self.bot.config['cg_marketchart']['static_image_link'] + chart_name)
                    # if advert enable
                    if self.bot.config['discord']['enable_advert'] == 1 and len(self.bot.advert_list) > 0:
                        try:
                            random.shuffle(self.bot.advert_list)
                            embed.add_field(
                                name="{}".format(self.bot.advert_list[0]['title']),
                                value="```{}```👉 <{}>".format(self.bot.advert_list[0]['content'], self.bot.advert_list[0]['link']),
                                inline=False
                            )
                            await self.utils.advert_impress(
                                self.bot.advert_list[0]['id'], str(ctx.author.id),
                                str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM"
                            )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    # end advert
                    await ctx.edit_original_message(content=None, embed=embed, view=RowButtonRowCloseAnyMessage())
            except Exception:
                traceback.print_exc(file=sys.stdout)


def setup(bot):
    bot.add_cog(Price(bot))
