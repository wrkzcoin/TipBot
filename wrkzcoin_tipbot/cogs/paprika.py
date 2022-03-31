import sys
import traceback

import json
import aiohttp, asyncio
import disnake
from disnake.ext import commands, tasks
import time
import datetime

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

from Bot import EMOJI_CHART_DOWN, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_FLOPPY, logchanbot
import redis_utils
import store

from config import config


# https://api.coinpaprika.com/#tag/Tags/paths/~1tags~1{tag_id}/get


class Paprika(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)
        redis_utils.openRedis()
        self.fetch_paprika_pricelist.start()


    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)


    @tasks.loop(seconds=3600)
    async def fetch_paprika_pricelist(self):
        await asyncio.sleep(3.0)
        url = "https://api.coinpaprika.com/v1/tickers"
        try:
            async with aiohttp.ClientSession() as cs:
                async with cs.get(url, timeout=30) as r:
                    res_data = await r.read()
                    res_data = res_data.decode('utf-8')
                    decoded_data = json.loads(res_data)
                    update_time = int(time.time())
                    update_date = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
                    if len(decoded_data) > 0:
                        update_list = []
                        insert_list = []
                        for each_coin in decoded_data:
                            try:
                                quote_usd = each_coin['quotes']['USD']
                                ath_date = None

                                if quote_usd['ath_date'] and "." in quote_usd['ath_date']:
                                    ath_date = datetime.datetime.strptime(quote_usd['ath_date'], '%Y-%m-%dT%H:%M:%S.%fZ')
                                elif quote_usd['ath_date'] and "." not in quote_usd['ath_date']:
                                    ath_date = datetime.datetime.strptime(quote_usd['ath_date'], '%Y-%m-%dT%H:%M:%SZ')

                                if "." in each_coin['last_updated']:
                                    last_updated = datetime.datetime.strptime(each_coin['last_updated'], '%Y-%m-%dT%H:%M:%S.%fZ')
                                else:
                                    last_updated = datetime.datetime.strptime(each_coin['last_updated'], '%Y-%m-%dT%H:%M:%SZ')
                                update_list.append((each_coin['id'], each_coin['symbol'], each_coin['name'], each_coin['rank'], each_coin['circulating_supply'], each_coin['total_supply'], each_coin['max_supply'], quote_usd['price'], update_time, last_updated, quote_usd['price'], quote_usd['volume_24h'], quote_usd['volume_24h_change_24h'], quote_usd['market_cap'], quote_usd['market_cap_change_24h'], quote_usd['percent_change_15m'], quote_usd['percent_change_30m'], quote_usd['percent_change_1h'], quote_usd['percent_change_6h'], quote_usd['percent_change_12h'], quote_usd['percent_change_24h'], quote_usd['percent_change_7d'], quote_usd['percent_change_30d'], quote_usd['percent_change_1y'], quote_usd['ath_price'], ath_date, quote_usd['percent_from_price_ath']))

                                insert_list.append((each_coin['id'], each_coin['rank'], each_coin['circulating_supply'], each_coin['total_supply'], each_coin['max_supply'], quote_usd['price'], update_time, last_updated, quote_usd['price'], quote_usd['volume_24h'], quote_usd['volume_24h_change_24h'], quote_usd['market_cap'], quote_usd['market_cap_change_24h'], quote_usd['percent_change_15m'], quote_usd['percent_change_30m'], quote_usd['percent_change_1h'], quote_usd['percent_change_6h'], quote_usd['percent_change_12h'], quote_usd['percent_change_24h'], quote_usd['percent_change_7d'], quote_usd['percent_change_30d'], quote_usd['percent_change_1y'], quote_usd['ath_price'], ath_date, quote_usd['percent_from_price_ath'],  update_time))
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                        if len(update_list) or len(insert_list) > 0:
                            try:
                                await store.openConnection()
                                async with store.pool.acquire() as conn:
                                    async with conn.cursor() as cur:
                                        sql = """ INSERT INTO coin_paprika_list (`id`, `symbol`, `name`, `rank`, `circulating_supply`, `total_supply`, `max_supply`, `price_usd`, `price_time`, `last_updated`, `quotes_USD_price`, `quotes_USD_volume_24h`, `quotes_USD_volume_24h_change_24h`, `quotes_USD_market_cap`, `quotes_USD_market_cap_change_24h`, `quotes_USD_percent_change_15m`, `quotes_USD_percent_change_30m`, `quotes_USD_percent_change_1h`, `quotes_USD_percent_change_6h`, `quotes_USD_percent_change_12h`, `quotes_USD_percent_change_24h`, `quotes_USD_percent_change_7d`, `quotes_USD_percent_change_30d`, `quotes_USD_percent_change_1y`, `quotes_USD_ath_price`, `quotes_USD_ath_date`, `quotes_USD_percent_from_price_ath`) 
                                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY 
                                                  UPDATE 
                                                  `rank`=VALUES(`rank`), 
                                                  `circulating_supply`=VALUES(`circulating_supply`), 
                                                  `total_supply`=VALUES(`total_supply`), 
                                                  `max_supply`=VALUES(`max_supply`), 
                                                  `price_usd`=VALUES(`price_usd`), 
                                                  `price_time`=VALUES(`price_time`), 
                                                  `last_updated`=VALUES(`last_updated`), 
                                                  `quotes_USD_price`=VALUES(`quotes_USD_price`), 
                                                  `quotes_USD_volume_24h`=VALUES(`quotes_USD_volume_24h`), 
                                                  `quotes_USD_volume_24h_change_24h`=VALUES(`quotes_USD_volume_24h_change_24h`), 
                                                  `quotes_USD_market_cap`=VALUES(`quotes_USD_market_cap`), 
                                                  `quotes_USD_market_cap_change_24h`=VALUES(`quotes_USD_market_cap_change_24h`), 
                                                  `quotes_USD_percent_change_15m`=VALUES(`quotes_USD_percent_change_15m`), 
                                                  `quotes_USD_percent_change_30m`=VALUES(`quotes_USD_percent_change_30m`), 
                                                  `quotes_USD_percent_change_1h`=VALUES(`quotes_USD_percent_change_1h`), 
                                                  `quotes_USD_percent_change_6h`=VALUES(`quotes_USD_percent_change_6h`), 
                                                  `quotes_USD_percent_change_12h`=VALUES(`quotes_USD_percent_change_12h`), 
                                                  `quotes_USD_percent_change_24h`=VALUES(`quotes_USD_percent_change_24h`), 
                                                  `quotes_USD_percent_change_7d`=VALUES(`quotes_USD_percent_change_7d`), 
                                                  `quotes_USD_percent_change_30d`=VALUES(`quotes_USD_percent_change_30d`), 
                                                  `quotes_USD_percent_change_1y`=VALUES(`quotes_USD_percent_change_1y`), 
                                                  `quotes_USD_ath_price`=VALUES(`quotes_USD_ath_price`), 
                                                  `quotes_USD_ath_date`=VALUES(`quotes_USD_ath_date`), 
                                                  `quotes_USD_percent_from_price_ath`=VALUES(`quotes_USD_percent_from_price_ath`)
                                               """
                                        await cur.executemany(sql, update_list)
                                        await conn.commit()
                                        update_list = []

                                        sql = """ INSERT INTO coin_paprika_list_history (`id`, `rank`, `circulating_supply`, `total_supply`, `max_supply`, `price_usd`, `price_time`, `price_date`, `quotes_USD_price`, `quotes_USD_volume_24h`, `quotes_USD_volume_24h_change_24h`, `quotes_USD_market_cap`, `quotes_USD_market_cap_change_24h`, `quotes_USD_percent_change_15m`, `quotes_USD_percent_change_30m`, `quotes_USD_percent_change_1h`, `quotes_USD_percent_change_6h`, `quotes_USD_percent_change_12h`, `quotes_USD_percent_change_24h`, `quotes_USD_percent_change_7d`, `quotes_USD_percent_change_30d`, `quotes_USD_percent_change_1y`, `quotes_USD_ath_price`, `quotes_USD_ath_date`, `quotes_USD_percent_from_price_ath`, `inserted_date`) 
                                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                        await cur.executemany(sql, insert_list)
                                        await conn.commit()
                                        insert_list = []
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                                # print(insert_list[-1])
        except asyncio.TimeoutError:
            print('TIMEOUT: Fetching from coingecko price')
        except Exception:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(3.0)


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
