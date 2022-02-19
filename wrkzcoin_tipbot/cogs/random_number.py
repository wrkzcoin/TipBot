import sys, traceback
import random as rand

import disnake
from disnake.ext import commands

from disnake.enums import OptionType
from disnake.app_commands import Option

from config import config
from Bot import *


class RandomNumber(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    async def rand_number(
        self,
        ctx,
        number_string: str=None
    ):
        rand_numb = None
        respond = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid range given. Example, use: `rand 1-50`'
        if number_string is None:
            rand_numb = rand.randint(1, 100)
            respond = '{} Random number: **{:,}**'.format(ctx.author.mention, rand_numb)
        else:
            number_string = number_string.replace(",", "")
            rand_min_max = number_string.split("-")
            if len(rand_min_max) <= 1:
                respond = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid range given. Example, use: `rand 1-50`'
            else:
                try:
                    min_numb = int(rand_min_max[0])
                    max_numb = int(rand_min_max[1])
                    if max_numb - min_numb > 0:
                        rand_numb = rand.randint(min_numb, max_numb)
                        respond = '{} Random number: **{:,}**'.format(ctx.author.mention, rand_numb)
                except ValueError:
                    pass
        try:
            if type(ctx) == disnake.ApplicationCommandInteraction:
                msg = await ctx.response.send_message(respond)
            else:
                msg = await ctx.reply(respond)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.slash_command(
        usage="rand [1-100]",
        options=[
            Option("range_number", "Enter a range from to (ex. 1-100)", OptionType.string, required=False)
        ],
        description="Generate a random number with TipBot."
    )
    async def rand(
        self, 
        ctx, 
        range_number: str=None
    ):
        await self.rand_number(ctx, range_number)


    @commands.command(
        usage="random [1-100]", 
        aliases=['random', 'rand'], 
        description="Generate a random number with TipBot."
    )
    async def _rand(
        self, 
        ctx, 
        randstring: str = None
    ):
        await self.rand_number(ctx, randstring)


def setup(bot):
    bot.add_cog(RandomNumber(bot))