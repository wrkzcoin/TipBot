import sys
import traceback
from datetime import datetime
from decimal import Decimal
from attrdict import AttrDict

import disnake
from disnake.ext import commands
from Bot import RowButton_row_close_any_message, num_format_coin, logchanbot
import store
from config import config


class CoinSetting(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    async def get_coin_setting(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    coin_list = {}
                    sql = """ SELECT * FROM `coin_settings` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each in result:
                            coin_list[each['coin_name']] = each
                        return AttrDict(coin_list)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    @commands.command(hidden=True, usage="config", description="Reload coin setting")
    async def config(self, ctx, cmd: str=None):
        if config.discord.owner != ctx.author.id:
            await ctx.reply(f"{ctx.author.mention}, permission denied...")
            await logchanbot(f"{ctx.author.name}#{ctx.author.discriminator} tried to use `{ctx.command}`.")
            return

        try:
            if cmd is None:
                await ctx.reply(f"{ctx.author.mention}, available for reload `coinlist`")
            elif cmd.lower() == "coinlist":
                coin_list = await self.get_coin_setting()
                if coin_list:
                    self.bot.coin_list = coin_list
                await ctx.reply(f"{ctx.author.mention}, coin list reloaded...")
                await logchanbot(f"{ctx.author.name}#{ctx.author.discriminator} reloaded `{cmd}`.")
            else:
                await ctx.reply(f"{ctx.author.mention}, unknown command. Available for reload `coinlist`")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


def setup(bot):
    bot.add_cog(CoinSetting(bot))
