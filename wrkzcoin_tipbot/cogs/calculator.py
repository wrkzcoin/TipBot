import numexpr
from Bot import EMOJI_INFORMATION, EMOJI_ERROR
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands


class Calculator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def async_calc(self, ctx, eval_string: str = None):
        if eval_string is None:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, Example: `cal 2+3+4/2`'
            await ctx.response.send_message(msg)
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
                    msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, result of `{eval_string_original}`:```{result}```'
                    await ctx.response.send_message(msg)
                except Exception:
                    msg = f'{EMOJI_ERROR} {ctx.author.mention}, I can not find the result for `{eval_string_original}`.'
                    await ctx.response.send_message(msg)
            else:
                msg = f'{EMOJI_ERROR} {ctx.author.mention}, unsupported usage for `{eval_string_original}`.'
                await ctx.response.send_message(msg)

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


def setup(bot):
    bot.add_cog(Calculator(bot))
