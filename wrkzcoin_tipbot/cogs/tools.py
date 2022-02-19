import asyncio
import re
import sys
import time
import traceback
from datetime import datetime
import random

import disnake
from disnake.ext import commands

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

import store
from Bot import *

from config import config

# TODO: copy from previous works

class Tool(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)


    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)


    @commands.slash_command(description="Various tool's commands.")
    async def tool(self, ctx):
        # This is just a parent for subcommands
        # It's not necessary to do anything here,
        # but if you do, it runs for any subcommand nested below
        pass


    # For each subcommand you can specify individual options and other parameters,
    # see the "Objects and methods" reference to learn more.
    @tool.sub_command(
        usage="tool avatar <member>", 
        options=[
            Option('member', 'member', OptionType.user, required=True)
        ],
        description="Get avatar of a user."
    )
    async def avatar(
        self,
        ctx,
        member: disnake.Member
    ):
        if member is None:
            member = ctx.author
        try:
            msg = await ctx.response.send_message(f'Avatar image for {member.mention}:\n{str(member.display_avatar)}')
        except Exception as e:
            await logchanbot(traceback.format_exc())


    @tool.sub_command(
        usage="tool prime <number>", 
        options=[
            Option('number', 'number', OptionType.string, required=True)
        ],
        description="Check a given number if it is a prime number."
    )
    async def prime(
        self, 
        ctx, 
        number: str
    ):
        # https://en.wikipedia.org/wiki/Primality_test
        def is_prime(n: int) -> bool:
            """Primality test using 6k+-1 optimization."""
            if n <= 3:
                return n > 1
            if n % 2 == 0 or n % 3 == 0:
                return False
            i = 5
            while i ** 2 <= n:
                if n % i == 0 or n % (i + 2) == 0:
                    return False
                i += 6
            return True

        number = number.replace(",", "")
        if len(number) >= 1900:
            await ctx.response.send_message(f'{ctx.author.mention} {EMOJI_ERROR} given number is too long.')
            return
        try:
            value = is_prime(int(number))
            if value:
                await ctx.response.send_message(f'{ctx.author.mention} {EMOJI_CHECKMARK} Given number is a prime number: ```{str(number)}```')
            else:
                await ctx.response.send_message(f'{ctx.author.mention} {EMOJI_ERROR} Given number is not a prime number: ```{str(number)}```')
        except ValueError:
            await ctx.response.send_message(f'{ctx.author.mention} {EMOJI_ERROR} Number error.')



def setup(bot):
    bot.add_cog(Tool(bot))
