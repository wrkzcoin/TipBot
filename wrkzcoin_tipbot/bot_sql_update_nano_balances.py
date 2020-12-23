#!/usr/bin/python3.6
from discord_webhook import DiscordWebhook
import discord

import sys, traceback
from config import config
import store
import time
import asyncio
import redis
import rpc_client

redis_pool = None
redis_conn = None
redis_expired = 120

ENABLE_COIN_NANO = config.Enable_Coin_Nano.split(",")
INTERVAL_EACH = 10


def init():
    global redis_pool
    print("PID %d: initializing redis pool..." % os.getpid())
    redis_pool = redis.ConnectionPool(host='localhost', port=6379, decode_responses=True, db=8)


def openRedis():
    global redis_pool, redis_conn
    if redis_conn is None:
        try:
            redis_conn = redis.Redis(connection_pool=redis_pool)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


async def logchanbot(content: str):
    filterword = config.discord.logfilterword.split(",")
    for each in filterword:
        content = content.replace(each, config.discord.filteredwith)
    try:
        webhook = DiscordWebhook(url=config.discord.botdbghook, content=f'```{discord.utils.escape_markdown(content)}```')
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


# Let's run balance update by a separate process
async def update_balance():
    global redis_conn
    while True:
        print('sleep in second: '+str(INTERVAL_EACH))
        # do not update yet
        # DOGE family:
        for coinItem in ENABLE_COIN_NANO:
            timeout = 12
            try:
                gettopblock = await rpc_client.call_nano(coinItem.upper().strip(), payload='{ "action": "block_count" }')
                if gettopblock and 'count' in gettopblock:
                    height = int(gettopblock['count'])
                    # store in redis
                    try:
                        openRedis()
                        if redis_conn: redis_conn.set(f'{config.redis_setting.prefix_daemon_height}{coinItem.upper().strip()}', str(height))
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                await logchanbot(traceback.format_exc())
            update = 0
            time.sleep(INTERVAL_EACH)
            print('Update balance: '+ coinItem)
            start = time.time()
            try:
                update = await store.sql_nano_update_balances(coinItem.upper().strip())
            except Exception as e:
                await logchanbot(traceback.format_exc())
            end = time.time()
            print('Done update balance: '+ coinItem.upper().strip()+ ' updated *'+str(update)+'* duration (s): '+str(end - start))
            time.sleep(INTERVAL_EACH)
            # End of DOGE family
loop = asyncio.get_event_loop()  
loop.run_until_complete(update_balance())  
loop.close()