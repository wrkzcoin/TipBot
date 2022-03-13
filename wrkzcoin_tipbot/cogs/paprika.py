import sys
import traceback

import json
import aiohttp, asyncio
import disnake
from disnake.ext import commands

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

from Bot import EMOJI_CHART_DOWN, EMOJI_ERROR, EMOJI_RED_NO, logchanbot
import redis_utils
import store

from config import config


class Paprika(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)
        redis_utils.openRedis()


    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)


    async def paprika_coin(
        self, 
        coin: str
    ):
        COIN_NAME = coin.upper()
        key = config.redis.prefix_paprika + coin.upper()
        # Get from redis
        try:
            if redis_utils.redis_conn.exists(key):
                response_text = redis_utils.redis_conn.get(key).decode()
                return {"result": response_text, "cache": True}
        except Exception as e:
            traceback.format_exc()
            await logchanbot(traceback.format_exc())
            return {"error": "Internal error from cache."}

        if COIN_NAME in self.bot.token_hints:
            id = self.bot.token_hints[COIN_NAME]['ticker_name']
        elif COIN_NAME in self.bot.token_hint_names:
            id = self.bot.token_hint_names[COIN_NAME]['ticker_name']
        else:
            if redis_utils.redis_conn.exists(config.redis.prefix_paprika + "COINSLIST"):
                j = json.loads(redis_utils.redis_conn.get(config.redis.prefix_paprika + "COINSLIST").decode())
            else:
                link = 'https://api.coinpaprika.com/v1/coins'
                async with aiohttp.ClientSession() as session:
                    async with session.get(link) as resp:
                        if resp.status == 200:
                            j = await resp.json()
                            # add to redis coins list
                            try:
                                redis_utils.redis_conn.set(config.redis.prefix_paprika + "COINSLIST", json.dumps(j), ex=config.redis.default_time_coinlist)
                            except Exception as e:
                                traceback.format_exc()
                            # end add to redis
            if COIN_NAME.isdigit():
                for i in j:
                    if int(COIN_NAME) == int(i['rank']):
                        id = i['id']
            else:
                for i in j:
                    if COIN_NAME.lower() == i['name'].lower() or COIN_NAME.lower() == i['symbol'].lower():
                        id = i['id'] #i['name']
        try:
            async with aiohttp.ClientSession() as session:
                url = 'https://api.coinpaprika.com/v1/tickers/{}'.format(id)
                async with session.get(url) as resp:
                    if resp.status == 200:
                        j = await resp.json()
                        if 'error' in j and j['error'] == 'id not found':
                            return {"error": f"Can not get data **{coin.upper()}** from paprika."}
                        if float(j['quotes']['USD']['price']) > 100:
                            trading_at = "${:.2f}".format(float(j['quotes']['USD']['price']))
                        elif float(j['quotes']['USD']['price']) > 1:
                            trading_at = "${:.3f}".format(float(j['quotes']['USD']['price']))
                        elif float(j['quotes']['USD']['price']) > 0.01:
                            trading_at = "${:.4f}".format(float(j['quotes']['USD']['price']))
                        else:
                            trading_at = "${:.8f}".format(float(j['quotes']['USD']['price']))
                        response_text = "{} ({}) is #{} by marketcap (${:,.2f}), trading at {} with a 24h vol of ${:,.2f}. It's changed {}% over 24h, {}% over 7d, {}% over 30d, and {}% over 1y with an ath of ${} on {}.".format(j['name'], j['symbol'], j['rank'], float(j['quotes']['USD']['market_cap']), trading_at, float(j['quotes']['USD']['volume_24h']), j['quotes']['USD']['percent_change_24h'], j['quotes']['USD']['percent_change_7d'], j['quotes']['USD']['percent_change_30d'], j['quotes']['USD']['percent_change_1y'], j['quotes']['USD']['ath_price'], j['quotes']['USD']['ath_date'])
                        try:
                            redis_utils.redis_conn.set(key, response_text, ex=config.redis.default_time_paprika)
                        except Exception as e:
                            traceback.format_exc()
                            await logchanbot(traceback.format_exc())
                        return {"result": response_text}
                    else:
                        return {"error": f"Can not get data **{coin.upper()}** from paprika."}
                    return
        except Exception as e:
            traceback.format_exc()
        return {"error": "No paprika only salt."}


    @commands.slash_command(usage="paprika [coin]",
                            options=[
                                Option("coin", "Enter coin ticker/name", OptionType.string, required=True)
                            ],
                            description="Check coin at Paprika.")
    async def paprika(
        self, 
        ctx, 
        coin: str
    ):
        get_pap = await self.paprika_coin(coin)
        if 'result' in get_pap:
            resp = get_pap['result']
            await ctx.response.send_message(f"{ctx.author.name}#{ctx.author.discriminator}, {resp}", ephemeral=False)
        elif 'error' in get_pap:
            resp = get_pap['error']
            await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.name}#{ctx.author.discriminator}, {resp}", ephemeral=False)


    @commands.command(
        usage="pap <coin>", 
        description="Check coin at Paprika."
    )
    async def pap(
        self, 
        ctx, 
        coin: str=None
    ):
        await self.bot_log()
        if coin is None:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} Missing coin name.')
            return
        else:
            get_pap = await self.paprika_coin(coin)
            if 'result' in get_pap:
                resp = get_pap['result']
                msg = await ctx.reply(f"{ctx.author.name}#{ctx.author.discriminator}, {resp}")
                if 'cache' in get_pap:
                    await ctx.message.add_reaction(EMOJI_FLOPPY)
            elif 'error' in get_pap:
                resp = get_pap['error']
                msg = await ctx.reply(f"{EMOJI_RED_NO} {ctx.author.name}#{ctx.author.discriminator}, {resp}")


def setup(bot):
    bot.add_cog(Paprika(bot))
