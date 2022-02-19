import sys, traceback

import disnake
from disnake.ext import commands
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
import numexpr

from config import config
from Bot import *


class Calculator(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    @commands.guild_only()
    @commands.slash_command(
        usage="cal <expression>",
        options=[
            Option("eval_string", "Math to evaluate", OptionType.string, required=True)
        ],
        description="Do some math."
    )
    async def cal(
        self, 
        ctx, 
        eval_string: str = None
    ):
        if eval_string is None:
            await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention}, Example: `cal 2+3+4/2`')
        else:
            eval_string_original = eval_string
            eval_string = eval_string.replace(",", "")
            supported_function = ['+', '-', '*', '/', '(', ')', '.', ',']
            additional_support = ['exp', 'sqrt', 'abs', 'log10', 'log', 'sinh', 'cosh', 'tanh', 'sin', 'cos', 'tan']
            test_string = eval_string
            for each in additional_support:
                test_string = test_string.replace(each, "")
            if all([c.isdigit() or c in supported_function for c in test_string]):
                try:
                    result = numexpr.evaluate(eval_string).item()
                    await ctx.response.send_message(f'{EMOJI_INFORMATION} {ctx.author.mention} result of `{eval_string_original}`:```{result}```')
                except Exception as e:
                    await ctx.response.send_message(f'{EMOJI_ERROR} {ctx.author.mention} I can not find the result for `{eval_string_original}`.')
            else:
                await ctx.response.send_message(f'{EMOJI_ERROR} {ctx.author.mention} Unsupported usage for `{eval_string_original}`.')


    @commands.guild_only()
    @commands.command(
        usage="cal <expression>", 
        aliases=['cal', 'calc', 'calculate'], 
        description="Do some math."
    )
    async def _cal(
        self, 
        ctx, 
        eval_string: str = None
    ):
        if eval_string is None:
            await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention}, Example: `cal 2+3+4/2`')
        else:
            eval_string_original = eval_string
            eval_string = eval_string.replace(",", "")
            supported_function = ['+', '-', '*', '/', '(', ')', '.', ',']
            additional_support = ['exp', 'sqrt', 'abs', 'log10', 'log', 'sinh', 'cosh', 'tanh', 'sin', 'cos', 'tan']
            test_string = eval_string
            for each in additional_support:
                test_string = test_string.replace(each, "")
            if all([c.isdigit() or c in supported_function for c in test_string]):
                try:
                    result = numexpr.evaluate(eval_string).item()
                    await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} result of `{eval_string_original}`:```{result}```')
                except Exception as e:
                    await ctx.reply(f'{EMOJI_ERROR} {ctx.author.mention} I can not find the result for `{eval_string_original}`.')
            else:
                await ctx.reply(f'{EMOJI_ERROR} {ctx.author.mention} Unsupported usage for `{eval_string_original}`.')


def setup(bot):
    bot.add_cog(Calculator(bot))
