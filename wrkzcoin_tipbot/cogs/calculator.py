import sys, traceback

import disnake
from disnake.ext import commands
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
import numexpr

from config import config
from Bot import EMOJI_INFORMATION, EMOJI_ERROR


class Calculator(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    async def async_calc(self, ctx, eval_string: str=None):
        if eval_string is None:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, Example: `cal 2+3+4/2`'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
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
                    msg = f'{EMOJI_INFORMATION} {ctx.author.mention} result of `{eval_string_original}`:```{result}```'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                except Exception as e:
                    msg = f'{EMOJI_ERROR} {ctx.author.mention} I can not find the result for `{eval_string_original}`.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
            else:
                msg = f'{EMOJI_ERROR} {ctx.author.mention} Unsupported usage for `{eval_string_original}`.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)


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
        await self.async_calc(ctx, eval_string)


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
        await self.async_calc(ctx, eval_string)


def setup(bot):
    bot.add_cog(Calculator(bot))
