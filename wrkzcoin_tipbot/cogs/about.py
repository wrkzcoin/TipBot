import sys
import traceback

import disnake
import store
from Bot import RowButtonRowCloseAnyMessage, logchanbot
from cogs.utils import Utils
from config import config
from disnake.ext import commands


class About(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.utils = Utils(self.bot)

    async def get_tipping_count(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT (SELECT COUNT(*) FROM user_balance_mv) AS nos_tipping,
                              (SELECT COUNT(*) FROM user_balance_mv_data) AS nos_user """
                    await cur.execute(sql, ())
                    result = await cur.fetchone()
                    return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def async_about(self, ctx):
        try:
            await ctx.response.send_message(embed=await self.about_embed(), view=RowButtonRowCloseAnyMessage())
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def about_embed(self):
        botdetails = disnake.Embed(title='About Me', description='')
        botdetails.add_field(name='Creator\'s Discord Name:', value='pluton#8888', inline=True)
        botdetails.add_field(name='My Github:', value="[TipBot Github](https://github.com/wrkzcoin/TipBot)",
                             inline=True)
        botdetails.add_field(name='Invite Me:', value=config.discord.invite_link, inline=True)
        botdetails.add_field(name='Servers:', value=len(self.bot.guilds), inline=True)
        try:
            botdetails.add_field(name="Online", value='{:,.0f}'.format(
                sum(1 for m in self.bot.get_all_members() if m.status == disnake.Status.online)), inline=True)
            botdetails.add_field(name="Users",
                                 value='{:,.0f}'.format(sum(1 for m in self.bot.get_all_members() if m.bot is False)),
                                 inline=True)
            botdetails.add_field(name="Bots",
                                 value='{:,.0f}'.format(sum(1 for m in self.bot.get_all_members() if m.bot is True)),
                                 inline=True)
            get_tipping_count = await self.get_tipping_count()
            if get_tipping_count:
                botdetails.add_field(name="Tips", value='{:,.0f}'.format(get_tipping_count['nos_tipping']), inline=True)
                botdetails.add_field(name="Wallets", value='{:,.0f}'.format(get_tipping_count['nos_user']), inline=True)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            bot_settings = await self.utils.get_bot_settings()
            botdetails.add_field(name='Add Coin/Token', value=bot_settings['link_listing_form'], inline=False)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        botdetails.set_footer(text='Made in Python',
                              icon_url='http://findicons.com/files/icons/2804/plex/512/python.png')
        botdetails.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
        return botdetails

    @commands.slash_command(
        usage="about",
        description="Get information about me."
    )
    async def about(
            self,
            ctx
    ):
        await self.async_about(ctx)

    @commands.user_command(name="About")
    async def about_me(self, ctx):
        await self.async_about(ctx)


def setup(bot):
    bot.add_cog(About(bot))
