import sys
import traceback
from datetime import datetime
import time
import disnake
import timeago
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands

import store
from Bot import SERVER_BOT
from cogs.utils import Utils


class Userinfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utils = Utils(self.bot)

    async def sql_user_get_tipstat(self, user_id: str, user_server: str = 'DISCORD'):
        user_server = user_server.upper()
        user_stat = {'tx_out': 0, 'tx_in': 0, 'ex_tip_usd': 0.0, 'in_tip_usd': 0.0, 'faucet_claimed': 0}
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT (SELECT COUNT(*) FROM user_balance_mv WHERE `from_userid`=%s AND `user_server`=%s) AS ex_tip,
                             (SELECT COUNT(*) FROM user_balance_mv WHERE `to_userid`=%s AND `user_server`=%s) AS in_tip,
                             (SELECT SUM(real_amount_usd) FROM user_balance_mv WHERE `from_userid`=%s AND `user_server`=%s) AS ex_tip_usd,
                             (SELECT SUM(real_amount_usd) FROM user_balance_mv WHERE `to_userid`=%s AND `user_server`=%s) AS in_tip_usd,
                             (SELECT COUNT(*) FROM discord_faucet WHERE `claimed_user`=%s) AS faucet_claimed """
                    await cur.execute(sql, (
                    user_id, user_server, user_id, user_server, user_id, user_server, user_id, user_server, user_id))
                    result = await cur.fetchone()
                    if result: user_stat = {'tx_out': result['ex_tip'], 'tx_in': result['in_tip'],
                                            'ex_tip_usd': float(result['ex_tip_usd']) if result['ex_tip_usd'] else 0.0,
                                            'in_tip_usd': float(result['in_tip_usd']) if result['in_tip_usd'] else 0.0,
                                            'faucet_claimed': result['faucet_claimed']}
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return user_stat

    async def get_userinfo(self, ctx, member):
        tip_text = "N/A"
        tipstat = await self.sql_user_get_tipstat(str(member.id), SERVER_BOT)
        if tipstat['tx_in'] > 0 and tipstat['tx_out'] > 0:
            ratio_tip = float("%.3f" % float(tipstat['tx_out'] / tipstat['tx_in']))
            if tipstat['tx_in'] + tipstat['tx_out'] < 50:
                tip_text = "CryptoTip Beginner"
            else:
                if ratio_tip < 0.1:
                    tip_text = "CryptoTip Rig"
                elif 0.5 > ratio_tip >= 0.1:
                    tip_text = "CryptoTip Excavator"
                elif 1 > ratio_tip >= 0.5:
                    tip_text = "CryptoTip Farmer"
                elif 5 > ratio_tip >= 1:
                    tip_text = "CryptoTip Seeder"
                elif ratio_tip >= 5:
                    tip_text = "CryptoTip AirDropper"

        embed = disnake.Embed(title="{}'s info".format(member.name),
                              description="Total faucet claim {}".format(tipstat['faucet_claimed']),
                              timestamp=datetime.now())
        embed.add_field(name="Name", value="{}#{}".format(member.name, member.discriminator), inline=True)
        embed.add_field(name="Display Name", value=member.display_name, inline=True)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Status", value=member.status, inline=True)
        embed.add_field(name="Highest role", value=member.top_role)
        embed.add_field(name="Tip In/Out",
                        value="{}/{} - {}".format('{:,}'.format(tipstat['tx_in']), '{:,}'.format(tipstat['tx_out']),
                                                  tip_text), inline=False)
        embed.add_field(name="$ In/Out", value="{}/{}".format('{:,.2f}'.format(tipstat['in_tip_usd']),
                                                              '{:,.2f}'.format(tipstat['ex_tip_usd']), tip_text),
                        inline=False)
        embed.add_field(name="Joined", value=str(
            member.joined_at.strftime("%d-%b-%Y") + ': ' + timeago.format(member.joined_at,
                                                                          datetime.utcnow().astimezone())))
        embed.add_field(name="Created", value=str(
            member.created_at.strftime("%d-%b-%Y") + ': ' + timeago.format(member.created_at,
                                                                           datetime.utcnow().astimezone())))
        embed.set_thumbnail(url=member.display_avatar)
        embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
        await ctx.response.send_message(embed=embed)

    @commands.user_command(name="UserInfo")  # optional
    async def user_info(self, ctx: disnake.ApplicationCommandInteraction, user: disnake.User):
        tip_text = "N/A"
        tipstat = await self.sql_user_get_tipstat(str(user.id), SERVER_BOT)
        if tipstat['tx_in'] > 0 and tipstat['tx_out'] > 0:
            ratio_tip = float("%.3f" % float(tipstat['tx_out'] / tipstat['tx_in']))
            if tipstat['tx_in'] + tipstat['tx_out'] < 50:
                tip_text = "CryptoTip Beginner"
            else:
                if ratio_tip < 0.1:
                    tip_text = "CryptoTip Rig"
                elif 0.5 > ratio_tip >= 0.1:
                    tip_text = "CryptoTip Excavator"
                elif 1 > ratio_tip >= 0.5:
                    tip_text = "CryptoTip Farmer"
                elif 5 > ratio_tip >= 1:
                    tip_text = "CryptoTip Seeder"
                elif ratio_tip >= 5:
                    tip_text = "CryptoTip AirDropper"

        embed = disnake.Embed(title="{}'s info".format(user.name),
                              description="Total faucet claim {}".format(tipstat['faucet_claimed']),
                              timestamp=datetime.now())
        embed.add_field(name="Name", value="{}#{}".format(user.name, user.discriminator), inline=True)
        embed.add_field(name="Display Name", value=user.display_name, inline=True)
        embed.add_field(name="ID", value=user.id, inline=True)
        embed.add_field(name="Tip In/Out",
                        value="{}/{} - {}".format('{:,}'.format(tipstat['tx_in']), '{:,}'.format(tipstat['tx_out']),
                                                  tip_text), inline=False)
        embed.add_field(name="$ In/Out", value="{}/{}".format('{:,.2f}'.format(tipstat['in_tip_usd']),
                                                              '{:,.2f}'.format(tipstat['ex_tip_usd']), tip_text),
                        inline=False)
        if hasattr(user, "joined_at"):
            embed.add_field(name="Joined", value=str(
                user.joined_at.strftime("%d-%b-%Y") + ': ' + timeago.format(user.joined_at,
                                                                            datetime.utcnow().astimezone())))
        embed.add_field(name="Created", value=str(
            user.created_at.strftime("%d-%b-%Y") + ': ' + timeago.format(user.created_at,
                                                                         datetime.utcnow().astimezone())))
        embed.set_thumbnail(url=user.display_avatar)
        embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
        await ctx.response.send_message(embed=embed)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/userinfo", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.guild_only()
    @commands.slash_command(
        usage="userinfo <member>",
        options=[
            Option("user", "Enter user", OptionType.user, required=False)
        ],
        description="Get user information."
    )
    async def userinfo(
        self,
        ctx,
        user: disnake.Member = None
    ):
        if user is None: user = ctx.author
        await self.get_userinfo(ctx, user)


def setup(bot):
    bot.add_cog(Userinfo(bot))
