import datetime
import json
import sys
import time
import traceback

import aiohttp
import asyncio
import store
from Bot import logchanbot
from disnake.ext import commands, tasks


# https://www.coingecko.com/en/api/documentation


class CoinGecko(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

        self.fetch_gecko_coinlist.start()
        self.fetch_gecko_pricelist.start()

    # This token hints is priority
    async def get_coingecko_list_db(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_coingecko_list` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        return [each['id'] for each in result]
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []

    @tasks.loop(seconds=60.0)
    async def fetch_gecko_coinlist(self):
        time_lap = 600 # seconds
        await self.bot.wait_until_ready()
        await asyncio.sleep(time_lap)
        url = "https://api.coingecko.com/api/v3/coins/list"
        try:
            async with aiohttp.ClientSession() as cs:
                async with cs.get(url, timeout=30) as r:
                    res_data = await r.read()
                    res_data = res_data.decode('utf-8')
                    decoded_data = json.loads(res_data)
                    update_time = int(time.time())
                    if len(decoded_data) > 0:
                        existing_coinlist = await self.get_coingecko_list_db()
                        insert_list = []
                        for each_item in decoded_data:
                            if len(each_item['id']) > 0 and len(each_item['symbol']) > 0 and len(each_item['name']) > 0 and each_item['id'] not in existing_coinlist:
                                insert_list.append((each_item['id'], each_item['symbol'], each_item['name']))
                        if len(insert_list) > 0:
                            try:
                                await store.openConnection()
                                async with store.pool.acquire() as conn:
                                    async with conn.cursor() as cur:
                                        sql = """ INSERT INTO coin_coingecko_list (`id`, `symbol`, `name`) 
                                                  VALUES (%s, %s, %s) """
                                        await cur.executemany(sql, insert_list)
                                        await conn.commit()
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                        else:
                            await asyncio.sleep(60.0)
        except asyncio.TimeoutError:
            print('TIMEOUT: Fetching from coingecko price')
        except Exception:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=1200.0)
    async def fetch_gecko_pricelist(self):
        time_lap = 600 # seconds
        await self.bot.wait_until_ready()
        await asyncio.sleep(time_lap)
        try:
            existing_coinlist = await self.get_coingecko_list_db()
            if len(existing_coinlist) > 0:
                chunk = []
                chunk_str = ""
                for each_coin in existing_coinlist:
                    if len(chunk_str) < 1000:
                        chunk.append(each_coin)
                        chunk_str = ",".join(chunk)
                    else:
                        # Process
                        key_list = ",".join(chunk)
                        url = "https://api.coingecko.com/api/v3/simple/price?ids="+key_list+"&vs_currencies=usd"
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
                                        for k, v in decoded_data.items():
                                            if 'usd' in v:
                                                update_list.append((v['usd'], update_time, update_date.strftime('%Y-%m-%d %H:%M:%S'), k))
                                        try:
                                            await store.openConnection()
                                            async with store.pool.acquire() as conn:
                                                async with conn.cursor() as cur:
                                                    sql = """ UPDATE coin_coingecko_list SET `price_usd`=%s, `price_time`=%s, `price_date`=%s WHERE `id`=%s """
                                                    await cur.executemany(sql, update_list)
                                                    await conn.commit()

                                                    chunk = []
                                                    chunk_str = ""
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                        except asyncio.TimeoutError:
                            print('TIMEOUT: Fetching from coingecko price')
                        except Exception:
                            #traceback.print_exc(file=sys.stdout)
                            await asyncio.sleep(30.0)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)


    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

def setup(bot):
    bot.add_cog(CoinGecko(bot))
