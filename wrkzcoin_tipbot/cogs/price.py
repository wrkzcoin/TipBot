import datetime
import time
import re
import sys
import traceback
import random

import disnake
from Bot import EMOJI_RED_NO, RowButtonRowCloseAnyMessage, text_to_num, EMOJI_HOURGLASS_NOT_DONE, SERVER_BOT
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands
from cogs.utils import Utils
from cogs.paprika import Paprika


class Price(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utils = Utils(self.bot)
        self.pap = Paprika(self.bot)

    async def async_price(self, ctx, amount: str = None, token: str = None):

        await ctx.response.send_message(f"{EMOJI_HOURGLASS_NOT_DONE} {ctx.author.mention}, checking price..")

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, f"/price", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if self.bot.coin_paprika_symbol_list is None:
            msg = f"{ctx.author.mention}, data is not available yet. Please try again soon!"
            await ctx.edit_original_message(content=msg)
            return

        token_name = None
        coin_paprika_symbol_list = [each.upper() for each in self.bot.coin_paprika_symbol_list.keys()]

        paprika_update_date = datetime.datetime.now()
        try:
            if coin_name not in self.bot.coin_price_dex:
                paprika_update_date = self.bot.coin_paprika_symbol_list[coin_name]['last_updated'].replace(
                    tzinfo=datetime.timezone.utc)
        except Exception:
            pass
        if amount is None and token is None:
            msg = f"{ctx.author.mention}, invalid command usage!"
            await ctx.edit_original_message(content=msg)
            return
        if amount is not None and amount.upper().endswith(tuple(coin_paprika_symbol_list)) and token is None:
            # amount is something like 10,0.0BTC [Possible]
            amount_tmp = re.findall(r'[\w\.\,]+[\d]', amount)  # If amount "111WRKZ 222WRKZ", take only the first one
            if len(amount_tmp) > 0:
                amount_tmp = amount_tmp[0]
                token_tmp = amount.replace(amount_tmp, "")
                if token_tmp.upper().strip() not in coin_paprika_symbol_list:
                    # Check dex 1st
                    if token_tmp.upper() in self.bot.coin_price_dex:
                        coin_name = token_tmp.upper()
                        token_name = coin_name
                        amount_old = amount
                        amount = amount_tmp[0]
                    elif hasattr(self.bot.coin_list, token_tmp.upper()):
                        native_token_name = getattr(getattr(self.bot.coin_list, token_tmp.upper()), "native_token_name")
                        if native_token_name:
                            coin_name = native_token_name
                            token_name = native_token_name
                            amount_old = amount
                            amount = amount_tmp[0]
                    else:
                        msg = f"I can not find price of `{token_tmp.upper()}`."
                        await ctx.edit_original_message(content=msg)
                        return
                else:
                    amount_old = amount
                    token_name = token_tmp.upper().strip()
                    coin_name = token_tmp.upper().strip()
                    amount = amount_tmp.replace(",", "")
                    amount = text_to_num(amount)
                    if amount is None:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                        await ctx.edit_original_message(content=msg)
                        return
            elif amount.upper() in self.bot.coin_price_dex or amount.upper() in coin_paprika_symbol_list:
                # token only
                coin_name = amount.upper()
                token_name = coin_name
                amount_old = 1
                amount = 1
            else:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given coin name or amount.'
                await ctx.edit_original_message(content=msg)
                return

        elif amount is not None and token is not None:
            # amount token
            amount_old = amount
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                await ctx.edit_original_message(content=msg)
                return
            coin_name = token.upper()
            token_name = coin_name
        elif amount and not amount.isdigit() and token is None:
            # token only
            coin_name = amount.upper()
            token_name = coin_name
            amount_old = 1
            amount = 1

        if token_name is not None and (coin_name in self.bot.coin_paprika_symbol_list or coin_name in self.bot.coin_price_dex):
            if coin_name in self.bot.token_hints:
                id = self.bot.token_hints[coin_name]['ticker_name']
                per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                try:
                    cache_pap_coin = await self.utils.async_get_cache_kv("paprika", id)
                    if cache_pap_coin is not None and cache_pap_coin['fetched_time'] + self.bot.config['kv_db']['paprika_ttl_coin_id'] > int(time.time()):
                        print(f"{datetime.datetime.now():%Y-%m-%d-%H-%M-%S} get paprika used cache for coin id [{id}]...")
                        per_unit = cache_pap_coin['price']
                        paprika_update_date = cache_pap_coin['timestamp']
                    elif cache_pap_coin is None:
                        get_pap_coin = await self.pap.fetch_coin_paprika(coin_name)
                        if get_pap_coin is not None:
                            per_unit = get_pap_coin['price']
                            paprika_update_date = get_pap_coin['timestamp']
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                name = self.bot.coin_paprika_id_list[id]['name']
            else:
                per_unit = self.bot.coin_paprika_symbol_list[coin_name]['price_usd']
                try:
                    cache_pap_coin = await self.utils.async_get_cache_kv("paprika", coin_name)
                    if cache_pap_coin is not None and cache_pap_coin['fetched_time'] + self.bot.config['kv_db']['paprika_ttl_coin_id'] > int(time.time()):
                        print(f"{datetime.datetime.now():%Y-%m-%d-%H-%M-%S} get paprika used cache for coin id [{coin_name}]...")
                        per_unit = cache_pap_coin['price']
                        paprika_update_date = cache_pap_coin['timestamp']
                    elif cache_pap_coin is None:
                        get_pap_coin = await self.pap.fetch_coin_paprika(coin_name)
                        if get_pap_coin is not None:
                            per_unit = get_pap_coin['price']
                            paprika_update_date = get_pap_coin['timestamp']
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                name = coin_name
                if 'name' in self.bot.coin_paprika_symbol_list[coin_name]:
                    name = self.bot.coin_paprika_symbol_list[coin_name]['name']
            try:
                total_price = float(amount) * per_unit
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
                embed = disnake.Embed(
                    title="PRICE CHECK",
                    description=f'**{coin_name}** | _{name}_',
                    timestamp=datetime.datetime.now()
                )
                embed.add_field(
                    name="Price (Coinpaprika)",
                    value="{} {} = {} {}\n{}".format(
                        amount_old.lower().replace(coin_name.lower(), "").strip() if type(amount_old) is str else amount_old,
                        coin_name,
                        total_price_str,
                        "USD",
                        "<t:{}:f>".format(int(paprika_update_date.timestamp()))
                    ),
                    inline=True
                )
                # Check coingecko
                if name.lower() in self.bot.other_data['gecko']:
                    try:
                        per_unit = self.bot.other_data['gecko'][name.lower()]['price_usd']
                        total_price = float(amount) * per_unit
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
                        if total_price > 0:
                            embed.add_field(
                                name="Price (CoinGecko)",
                                value="{} {} = {} {}\n{}".format(
                                    amount_old.lower().replace(coin_name.lower(), "").strip() if type(amount_old) is str else amount_old,
                                    coin_name,
                                    total_price_str,
                                    "USD",
                                    "<t:{}:f>".format(self.bot.other_data['gecko'][name.lower()]['price_time'])
                                ),
                                inline=True
                            )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                embed.set_footer(text="Credit: Coinpaprika | Coingecko")

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
        else:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} I could not find this information.'
            await ctx.edit_original_message(content=msg)

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
        token: str = None
    ):
        return await self.async_price(ctx, amount, token)


def setup(bot):
    bot.add_cog(Price(bot))
