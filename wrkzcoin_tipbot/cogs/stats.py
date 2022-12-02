import sys
import traceback
from datetime import datetime
import time

import disnake
from Bot import EMOJI_INFORMATION, logchanbot, SERVER_BOT
from cogs.wallet import WalletAPI
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands
import store
from cogs.utils import Utils

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

    async def get_coin_tipping_stats(self, coin: str):
        coin_name = coin.upper()
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT COUNT(*) AS numb_tip, 
                    SUM(real_amount) AS amount_tip, 
                    (SELECT `date` FROM `user_balance_mv` 
                    WHERE `token_name`=%s ORDER BY `id` DESC LIMIT 1) AS last_tip 
                    FROM `user_balance_mv` 
                    WHERE token_name=%s
                    """
                    await cur.execute(sql, (coin_name, coin_name))
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            await logchanbot("stats " +str(traceback.format_exc()))
        return None

    async def async_stats(self, ctx, coin: str = None):
        def simple_number(amount):
            amount = float(amount)
            if amount is None: return "0.0"
            amount_test = '{:,f}'.format(float(('%f' % (amount)).rstrip('0').rstrip('.')))
            if '.' in amount_test and len(amount_test.split('.')[1]) > 8:
                amount_str = '{:,.8f}'.format(amount)
            else:
                amount_str = amount_test
            return amount_str.rstrip('0').rstrip('.') if '.' in amount_str else amount_str

        embed = disnake.Embed(
            title='STATS',
            description='Servers: {:,.0f}'.format(len(self.bot.guilds)),
            timestamp=datetime.now()
        )
        try:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, checking `/stats`...'
            await ctx.response.send_message(msg)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(
                f"{EMOJI_INFORMATION} {ctx.author.mention}, failed to execute /stats message...", ephemeral=True)
            return
        if coin:
            coin_name = coin.upper()
            if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                coin_name = self.bot.coin_alias_names[coin_name]
            if not hasattr(self.bot.coin_list, coin_name):
                await ctx.edit_original_message(
                    content=f'{ctx.author.mention}, **{coin_name}** does not exist with us.')
                return
            else:
                balance = await self.wallet_api.get_coin_balance(coin_name)
                type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                explorer_link = getattr(getattr(self.bot.coin_list, coin_name), "explorer_link")
                display_name = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                embed.add_field(
                    name="WALLET **{}**".format(display_name),
                    value="`{} {}`".format(simple_number(balance), coin_name),
                    inline=True
                )
                try:
                    get_tip_stats = await self.get_coin_tipping_stats(coin_name)
                    if get_tip_stats is not None:
                        embed.add_field(
                            name="Tip/DB Records: {:,.0f}".format(get_tip_stats['numb_tip']),
                            value="`{}`".format(simple_number(get_tip_stats['amount_tip'])),
                            inline=True
                        )
                        embed.add_field(
                            name="Last Tip",
                            value=disnake.utils.format_dt(get_tip_stats['last_tip'], style='R'),
                            inline=True
                        )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                try:
                    height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                    if height:
                        embed.add_field(
                            name="blockNumber",
                            value="`{:,.0f}` | [Explorer Link]({})".format(height, explorer_link),
                            inline=False
                        )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        else:
            embed.add_field(
                name='Creator\'s Discord Name:',
                value='pluton#8888',
                inline=False
            )
            embed.add_field(
                name="Online",
                value='{:,.0f}'.format(
                    sum(1 for m in self.bot.get_all_members() if m.status == disnake.Status.online)),
                inline=True
            )
            embed.add_field(
                name="Users",
                value='{:,.0f}'.format(sum(1 for m in self.bot.get_all_members() if m.bot == False)),
                inline=True
            )
            embed.add_field(
                name="Bots",
                value='{:,.0f}'.format(sum(1 for m in self.bot.get_all_members() if m.bot == True)),
                inline=True
            )
            embed.add_field(name='Note:', value='Use `/stats coin` to check each coin\'s stats.', inline=False)
            embed.set_footer(
                text='Made in Python!',
                icon_url='http://findicons.com/files/icons/2804/plex/512/python.png'
            )
            embed.set_author(
                name=self.bot.user.name,
                icon_url=self.bot.user.display_avatar
            )
            embed.set_thumbnail(url=self.bot.user.display_avatar)
        await ctx.edit_original_message(content=None, embed=embed)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, f"/stats", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.slash_command(
        usage='stats',
        options=[
            Option("token", "Enter a coin/ticker name", OptionType.string, required=False)
        ],
        description='Get some statistic and information.'
    )
    async def stats(
            self,
            inter: disnake.AppCmdInter,
            token: str = None
    ) -> None:
        try:
            await self.async_stats(inter, token)
        except Exception:
            traceback.print_exc(file=sys.stdout)

def setup(bot):
    bot.add_cog(Stats(bot))
