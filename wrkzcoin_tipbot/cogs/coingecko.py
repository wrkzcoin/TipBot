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
from cogs.utils import Utils
# https://www.coingecko.com/en/api/documentation


# https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

class CoinGecko(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)
        self.utils = Utils(self.bot)


    # This token hints is priority
    async def get_coingecko_list_db(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_coingecko_list` 
                    ORDER BY `price_date` ASC
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        return [each['id'].lower() for each in result]
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("coingecko " + str(traceback.format_exc()))
        return []

    async def coingecko_to_bot_price(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_coingecko_list`
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        self.bot.other_data['gecko'] = {}
                        for each in result:
                            self.bot.other_data['gecko'][each['id']] = each
                        print("Gecko price reloaded...")
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("coingecko " + str(traceback.format_exc()))
        return False

    @tasks.loop(seconds=1800.0)
    async def fetch_gecko_coinlist(self):
        time_lap = 30 # seconds
        # Check if task recently run @bot_task_logs
        task_name = "fetch_gecko_coinlist"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        url = "https://api.coingecko.com/api/v3/coins/list"
        try:
            async with aiohttp.ClientSession() as cs:
                async with cs.get(url, timeout=30) as r:
                    res_data = await r.read()
                    res_data = res_data.decode('utf-8')
                    decoded_data = json.loads(res_data)
                    if len(decoded_data) > 0:
                        # existing_coinlist = await self.get_coingecko_list_db()
                        insert_list = []
                        id_list_inserting = []
                        for each_item in decoded_data:
                            if type(each_item) == str and each_item == "status":
                                continue
                            if each_item['id'].lower().strip() in id_list_inserting:
                                continue
                            try:
                                if len(each_item['id']) > 0 and len(each_item['symbol']) > 0 and len(each_item['name']) > 0 \
                                    and each_item['id'].lower().strip() not in id_list_inserting:
                                    insert_list.append((each_item['id'].lower().strip(), each_item['symbol'], each_item['name']))
                                    id_list_inserting.append(each_item['id'].lower().strip())
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                print("coingecko error id: {}".format(str(each_item)))
                        if len(insert_list) > 0:
                            try:
                                await store.openConnection()
                                async with store.pool.acquire() as conn:
                                    async with conn.cursor() as cur:
                                        sql = """
                                        INSERT INTO coin_coingecko_list (`id`, `symbol`, `name`) 
                                        VALUES (%s, %s, %s)
                                        ON DUPLICATE KEY
                                          UPDATE `symbol`=VALUES(`symbol`), `name`=VALUES(`name`)
                                        """
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
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=300.0)
    async def fetch_gecko_pricelist(self):
        time_lap = 300 # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "fetch_gecko_pricelist"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(30.0)
        try:
            existing_coinlist = await self.get_coingecko_list_db()
            if len(existing_coinlist) > 0:
                start_time = int(time.time())
                coin_chunk_list = chunks(existing_coinlist, 500)
                for each_list in coin_chunk_list:
                    # Process
                    key_list = ",".join(each_list)
                    url = "https://api.coingecko.com/api/v3/simple/price?ids="+key_list+"&vs_currencies=usd&include_market_cap=true&include_24hr_vol=true&include_24hr_change=true&include_last_updated_at=true"
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
                                    price_dict = {}
                                    for k, v in decoded_data.items():
                                        if 'usd' in v:
                                            update_list.append((
                                                v['usd'], update_time, update_date.strftime('%Y-%m-%d %H:%M:%S'),
                                                v['usd_market_cap'], v['usd_24h_vol'], v['usd_24h_change'], v['last_updated_at'],
                                                k
                                            ))
                                            price_dict[k.upper()] = {
                                                "id": k.upper(),
                                                "price": v['usd'],
                                                "time": v['last_updated_at'],
                                                "fetched_time": int(time.time()),
                                                "vol_24h": v['usd_24h_vol'],
                                                "mcap": v['usd_market_cap']
                                            }
                                    try:
                                        await store.openConnection()
                                        async with store.pool.acquire() as conn:
                                            async with conn.cursor() as cur:
                                                sql = """
                                                UPDATE coin_coingecko_list 
                                                SET `price_usd`=%s, `price_time`=%s, `price_date`=%s,
                                                `usd_market_cap`=%s, `usd_24h_vol`=%s, `usd_24h_change`=%s, `last_updated_at`=%s 
                                                WHERE `id`=%s """
                                                await cur.executemany(sql, update_list)
                                                await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    # Update cache price list
                                    for k, v in price_dict.items():
                                        try:
                                            await self.utils.async_set_cache_kv(
                                                self.bot.config['kv_db']['prefix_gecko'],
                                                "PRICE:" + k.upper(),
                                                v
                                            )
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                    except asyncio.TimeoutError:
                        print('TIMEOUT: Fetching from coingecko price')
                    except Exception:
                        #traceback.print_exc(file=sys.stdout)
                        await asyncio.sleep(30.0)
                    await asyncio.sleep(5.0)
                print("Coingecko completed: {}, time taken {}s".format(len(existing_coinlist), int(time.time()) - start_time))
                await self.coingecko_to_bot_price()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    @commands.Cog.listener()
    async def on_ready(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.fetch_gecko_coinlist.is_running():
                self.fetch_gecko_coinlist.start()
            if not self.fetch_gecko_pricelist.is_running():
                self.fetch_gecko_pricelist.start()

    async def cog_load(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.fetch_gecko_coinlist.is_running():
                self.fetch_gecko_coinlist.start()
            if not self.fetch_gecko_pricelist.is_running():
                self.fetch_gecko_pricelist.start()
            await self.coingecko_to_bot_price()

    def cog_unload(self):
        # Ensure the task is stopped when the cog is unloaded.
        self.fetch_gecko_coinlist.cancel()
        self.fetch_gecko_pricelist.cancel()


def setup(bot):
    bot.add_cog(CoinGecko(bot))
