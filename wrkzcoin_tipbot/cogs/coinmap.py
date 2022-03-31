import sys, traceback

from disnake.ext import commands
import disnake
from coin360 import get_coin360
from config import config
from Bot import logchanbot, EMOJI_RED_NO

class CoinMap(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    @commands.guild_only()
    @commands.slash_command(
        usage="coinmap",
        description="Get view from coin360."
    )
    async def coinmap(self, ctx):
        try:
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(f'Loading...')
            map_image = await self.bot.loop.run_in_executor(None, get_coin360)
            if map_image:
                path_image = config.coin360.static_coin360_link + map_image
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    msg = await ctx.edit_original_message(content=path_image)
                else:
                    msg = await ctx.reply(path_image)
            else:
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    msg = await ctx.response.send_message(f'{EMOJI_RED_NO} {ctx.author.mention} Internal error during fetch image.')
                else:
                    await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} Internal error during fetch image.')
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.guild_only()
    @commands.command(
        usage="coinmap", 
        aliases=['coinmap', 'coin360', 'c360', 'cmap'], 
        description="Get view from coin360."
    )
    async def _coinmap(self, ctx):
        async with ctx.typing():
            try:
                map_image = await self.bot.loop.run_in_executor(None, get_coin360)
                if map_image:
                    msg = await ctx.reply(f'{config.coin360.static_coin360_link + map_image}')
                else:
                    msg = await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} Internal error during fetch image.')
                return
            except Exception as e:
                await logchanbot(traceback.format_exc())


def setup(bot):
    bot.add_cog(CoinMap(bot))