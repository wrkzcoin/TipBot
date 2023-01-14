import sys
import traceback

import store
from Bot import logchanbot
from attrdict import AttrDict
from disnake.ext import commands


class CoinSetting(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def get_coin_setting(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    coin_list = {}
                    sql = """ SELECT * FROM `coin_settings` 
                    WHERE `enable`=1
                    """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each in result:
                            coin_list[each['coin_name']] = each
                        return AttrDict(coin_list)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_coin_list_name(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    coin_list_name = []
                    sql = """ SELECT `coin_name` 
                    FROM `coin_settings` 
                    WHERE `enable`=1 """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each in result:
                            coin_list_name.append(each['coin_name'])
                        return coin_list_name
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    # This token hints is priority
    async def get_token_hints(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_alias_price` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        hints = {}
                        hint_names = {}
                        for each_item in result:
                            hints[each_item['ticker']] = each_item
                            hint_names[each_item['name'].upper()] = each_item
                        self.bot.token_hints = hints
                        self.bot.token_hint_names = hint_names
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_advert_list(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `bot_advert_list` WHERE `enable`=1 """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        self.bot.advert_list = result
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_coin_alias_name(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_alias_name` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        alias_names = {}
                        for each_item in result:
                            alias_names[each_item['alt_name'].upper()] = each_item['coin_name']
                        self.bot.coin_alias_names = alias_names
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_faucet_coin_list(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT `coin_name` FROM `coin_settings` 
                    WHERE `enable`=1 AND `enable_faucet`=%s
                    """
                    await cur.execute(sql, (1))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        return [each['coin_name'] for each in result]
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    @commands.command(
        hidden=True,
        usage="config",
        description="Reload coin setting"
    )
    async def config(self, ctx, cmd: str = None):
        if self.bot.config['discord']['owner_id'] != ctx.author.id:
            await ctx.reply(f"{ctx.author.mention}, permission denied...")
            await logchanbot(f"{ctx.author.name}#{ctx.author.discriminator} tried to use `{ctx.command}`.")
            return

        try:
            if cmd is None:
                await ctx.reply(f"{ctx.author.mention}, available for reload `coinlist`")
            elif cmd.lower() == "coinlist":
                coin_list = await self.get_coin_setting()
                if coin_list:
                    self.bot.coin_list = coin_list
                coin_list_name = await self.get_coin_list_name()
                if coin_list_name:
                    self.bot.coin_name_list = coin_list_name

                faucet_coins = await self.get_faucet_coin_list()
                if faucet_coins:
                    self.bot.faucet_coins = faucet_coins

                await ctx.reply(f"{ctx.author.mention}, coin list, name reloaded...")
                await logchanbot(f"{ctx.author.name}#{ctx.author.discriminator} reloaded `{cmd}`.")
            elif cmd.lower() == "coinalias":
                await self.get_token_hints()
                await self.get_coin_alias_name()
                await ctx.reply(f"{ctx.author.mention}, coin aliases reloaded...")
                await logchanbot(f"{ctx.author.name}#{ctx.author.discriminator} reloaded `{cmd}`.")
            elif cmd.lower() == "advertlist":
                await self.get_advert_list()
                await ctx.reply(f"{ctx.author.mention}, advert list reloaded...")
                await logchanbot(f"{ctx.author.name}#{ctx.author.discriminator} reloaded `{cmd}`.")
            else:
                await ctx.reply(f"{ctx.author.mention}, unknown command. Available for reload `coinlist`")
        except Exception:
            traceback.print_exc(file=sys.stdout)

def setup(bot):
    bot.add_cog(CoinSetting(bot))
