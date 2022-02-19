import sys
import traceback
from datetime import datetime
from decimal import Decimal

import disnake
from disnake.ext import commands
from Bot import RowButton_row_close_any_message, num_format_coin
import store
from config import config


class About(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    async def about_embed(self):
        botdetails = disnake.Embed(title='About Me', description='Nothing much', timestamp=datetime.utcnow())
        botdetails.add_field(name='Bot ID:', value=str(self.bot.user.id), inline=False)
        botdetails.add_field(name='Creator\'s Discord Name:', value='pluton#8888', inline=True)
        botdetails.set_footer(text='Made in Python3.8!', icon_url='http://findicons.com/files/icons/2804/plex/512/python.png')
        botdetails.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
        botdetails.set_thumbnail(url=self.bot.user.display_avatar)
        return botdetails


    @commands.command(usage="about", description="Get information about me.")
    async def about(self, ctx):
        try:
            msg = await ctx.reply(embed=await self.about_embed(), view=RowButton_row_close_any_message())
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


def setup(bot):
    bot.add_cog(About(bot))
