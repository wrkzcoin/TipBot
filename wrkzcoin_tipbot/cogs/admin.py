import sys
import traceback
from datetime import datetime

import disnake
from disnake.ext import commands
import time

# For eval
import contextlib
import io

import Bot
import store
from Bot import get_token_list, num_format_coin, EMOJI_ERROR, SERVER_BOT, logchanbot, encrypt_string, decrypt_string
from config import config


class Admin(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return commands.is_owner()


    @commands.is_owner()
    @commands.group(
        usage="admin <subcommand>", 
        hidden = True, 
        description="Various admin commands."
    )
    async def admin(self, ctx):
        if ctx.invoked_subcommand is None: await ctx.reply(f'{ctx.author.mention} Invalid admin command')
        return


    @commands.is_owner()
    @admin.command(hidden=True, usage='pending', description='Check pending things')
    async def pending(self, ctx):
        ts = datetime.utcnow()
        embed = disnake.Embed(title='Pending Actions', timestamp=ts)
        embed.add_field(name="Pending Tx", value=str(len(self.bot.TX_IN_PROCESS)), inline=True)
        if len(self.bot.TX_IN_PROCESS) > 0:
            string_ints = [str(num) for num in self.bot.TX_IN_PROCESS]
            list_pending = '{' + ', '.join(string_ints) + '}'
            embed.add_field(name="List Pending By", value=list_pending, inline=True)
        embed.set_footer(text=f"Pending requested by {ctx.author.name}#{ctx.author.discriminator}")
        try:
            await ctx.reply(embed=embed)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return


    @commands.is_owner()
    @commands.command(hidden=True, usage='cleartx', description='Clear TX_IN_PROCESS')
    async def cleartx(self, ctx):
        if len(self.bot.TX_IN_PROCESS) == 0:
            await ctx.reply(f'{ctx.author.mention} Nothing in tx pending to clear.')
        else:
            try:
                string_ints = [str(num) for num in self.bot.TX_IN_PROCESS]
                list_pending = '{' + ', '.join(string_ints) + '}'
                await ctx.reply(f'Clearing {str(len(self.bot.TX_IN_PROCESS))} {list_pending} in pending...')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            self.bot.TX_IN_PROCESS = []
        return


    @commands.is_owner()
    @admin.command(
        usage="eval <expression>", 
        description="Do some eval."
    )
    async def eval(
        self, 
        ctx, 
        *, 
        code
    ):
        if config.discord.enable_eval != 1:
            return

        str_obj = io.StringIO() #Retrieves a stream of data
        try:
            with contextlib.redirect_stdout(str_obj):
                exec(code)
        except Exception as e:
            return await ctx.reply(f"```{e.__class__.__name__}: {e}```")
        await ctx.reply(f'```{str_obj.getvalue()}```')


    @commands.is_owner()
    @admin.command(
        usage="encrypt <expression>", 
        description="Encrypt text."
    )
    async def encrypt(
        self, 
        ctx, 
        *, 
        text
    ):
        encrypt = encrypt_string(text)
        if encrypt: return await ctx.reply(f"```{encrypt}```")


    @commands.is_owner()
    @admin.command(
        usage="decrypt <expression>", 
        description="Decrypt text."
    )
    async def decrypt(
        self, 
        ctx, 
        *, 
        text
    ):
        decrypt = decrypt_string(text)
        if decrypt: return await ctx.reply(f"```{decrypt}```")


def setup(bot):
    bot.add_cog(Admin(bot))
