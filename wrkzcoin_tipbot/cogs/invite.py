import sys, traceback
import time, timeago
import disnake
from disnake.ext import commands

from config import config

class Invite(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    @commands.slash_command(description="Get TipBpt's invite link.")
    async def invite(self, ctx):
        await ctx.response.send_message(f"**[INVITE LINK]**: {config.discord.invite_link}", ephemeral=False)


    @commands.command(usage="invite", aliases = ['invite'], description="Get TipBpt's invite link.")
    async def _invite(self, ctx):
        await ctx.reply(f"**[INVITE LINK]**: {config.discord.invite_link}")


def setup(bot):
    bot.add_cog(Invite(bot))
