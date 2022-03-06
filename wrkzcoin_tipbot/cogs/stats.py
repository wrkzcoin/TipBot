import sys
import traceback
from datetime import datetime
from decimal import Decimal

import disnake
from disnake.ext import commands
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

from Bot import RowButton_row_close_any_message, num_format_coin
import store
from config import config
import redis_utils


class Stats(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        redis_utils.openRedis()


    async def async_stats(self, ctx, coin: str=None):
        embed = disnake.Embed(title='STATS', description='Nothing much', timestamp=datetime.utcnow())
        embed.add_field(name='Bot ID:', value=str(self.bot.user.id), inline=False)
        if coin:
            COIN_NAME = coin.upper()
            if not hasattr(self.bot.coin_list, COIN_NAME):
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
                else:
                    await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
                return
            else:
                type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                explorer_link = getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")
                net_name = None
                if type_coin == "ERC-20":
                    net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                    contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    display_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
                    if contract is None or (contract and len(contract) < 1):
                        contract = None
                    main_balance = await store.http_wallet_getbalance(self.bot.erc_node_list[net_name], config.eth.MainAddress, COIN_NAME, contract)
                    if main_balance:
                        main_balance_balance = num_format_coin(float(main_balance / 10** coin_decimal), COIN_NAME, coin_decimal, False)
                        embed.add_field(name="WALLET **{}**".format(display_name), value=main_balance_balance, inline=False)
                elif type_coin in ["TRC-20", "TRC-10"]:
                    type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                    explorer_link = getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")
                    net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                    contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    display_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
                    if contract is None or (contract and len(contract) < 1):
                        contract = None
                    main_balance = await store.trx_wallet_getbalance(config.trc.MainAddress, COIN_NAME, coin_decimal, type_coin, contract)
                    if main_balance:
                        # already divided decimal
                        main_balance_balance = num_format_coin(float(main_balance), COIN_NAME, coin_decimal, False)
                        embed.add_field(name="WALLET **{}**".format(display_name), value=main_balance_balance, inline=False)
                elif type_coin == "TRTL-API":
                    print("TODO")
                elif type_coin == "TRTL-SERVICE":
                    print("TODO")
                elif type_coin == "XMR":
                    print("TODO")
                elif type_coin == "BTC":
                    print("TODO")
                elif type_coin == "CHIA":
                    print("TODO")
                elif type_coin == "NANO":
                    print("TODO")
                try:
                    height = None
                    if net_name is None:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                    else:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                    if height:
                        embed.add_field(name="blockNumber", value="`{:,.0f}` | [Explorer Link]({})".format(height, explorer_link), inline=False)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        else:
            embed.add_field(name='Creator\'s Discord Name:', value='pluton#8888', inline=True)
            embed.set_footer(text='Made in Python3.8+!', icon_url='http://findicons.com/files/icons/2804/plex/512/python.png')
            embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
            embed.set_thumbnail(url=self.bot.user.display_avatar)

        if type(ctx) == disnake.ApplicationCommandInteraction:
            await ctx.response.send_message(embed=embed)
        else:
            await ctx.reply(embed=embed)
        return



    @commands.slash_command(
        usage='stats', 
        options=[
                    Option("token", "Enter a coin/ticker name", OptionType.string, required=False)
                ],
        description='Get some statistic and information.'
    )
    async def stats(
        self, 
        inter: disnake.AppCmdInter,
        token: str=None
    ) -> None:
        try:
            await self.async_stats(inter, token)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.command(
        usage="stats [token]",
        aliases=["stats"],
        description="Get some statistic and information."
    )
    async def _stats(
        self, 
        ctx,
        token: str=None
    ):
        try:
            await self.async_stats(ctx, token)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


def setup(bot):
    bot.add_cog(Stats(bot))
