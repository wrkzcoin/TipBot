#!/usr/bin/python3.6
import sys
from config import config
import store
import time
import asyncio


ENABLE_COIN = config.Enable_Coin.split(",")
INTERVAL_EACH = 30


# Let's run balance update by a separate process
async def update_balance():
    while True:
        print('sleep in second: '+str(INTERVAL_EACH))
        # do not update yet
        # XTOR:
        COIN_NAME = "XTOR"
        asyncio.sleep(INTERVAL_EACH)
        print('Update balance: '+ COIN_NAME)
        start = time.time()
        try:
            await store.sql_update_balances(COIN_NAME)
        except Exception as e:
            print(e)
        end = time.time()
        # End of XTOR
        print('Done update balance: '+ COIN_NAME+ ' duration (s): '+str(end - start))
        # LOKI:
        COIN_NAME = "LOKI"
        asyncio.sleep(INTERVAL_EACH)
        print('Update balance: '+ COIN_NAME)
        start = time.time()
        try:
            await store.sql_update_balances(COIN_NAME)
        except Exception as e:
            print(e)
        end = time.time()
        # End of LOKI
        print('Done update balance: '+ COIN_NAME+ ' duration (s): '+str(end - start))
        # XMR:
        COIN_NAME = "XMR"
        asyncio.sleep(INTERVAL_EACH)
        print('Update balance: '+ COIN_NAME)
        start = time.time()
        try:
            await store.sql_update_balances(COIN_NAME)
        except Exception as e:
            print(e)
        end = time.time()
        # End of XMR
        print('Done update balance: '+ COIN_NAME+ ' duration (s): '+str(end - start))
        # XEQ:
        COIN_NAME = "XEQ"
        asyncio.sleep(INTERVAL_EACH)
        print('Update balance: '+ COIN_NAME)
        start = time.time()
        try:
            await store.sql_update_balances(COIN_NAME)
        except Exception as e:
            print(e)
        end = time.time()
        # End of XEQ
        # BLOG:
        COIN_NAME = "BLOG"
        asyncio.sleep(INTERVAL_EACH)
        print('Update balance: '+ COIN_NAME)
        start = time.time()
        try:
            await store.sql_update_balances(COIN_NAME)
        except Exception as e:
            print(e)
        end = time.time()
        # End of BLOG
        # ARQ:
        COIN_NAME = "ARQ"
        asyncio.sleep(INTERVAL_EACH)
        print('Update balance: '+ COIN_NAME)
        start = time.time()
        try:
            await store.sql_update_balances(COIN_NAME)
        except Exception as e:
            print(e)
        end = time.time()
        # End of ARQ
        # MSR:
        COIN_NAME = "MSR"
        asyncio.sleep(INTERVAL_EACH)
        print('Update balance: '+ COIN_NAME)
        start = time.time()
        try:
            await store.sql_update_balances(COIN_NAME)
        except Exception as e:
            print(e)
        end = time.time()
        # End of MSR
        print('Done update balance: '+ COIN_NAME+ ' duration (s): '+str(end - start))
        for coinItem in ENABLE_COIN:
            asyncio.sleep(INTERVAL_EACH)
            print('Update balance: '+ coinItem.upper().strip())
            start = time.time()
            try:
                await store.sql_update_balances(coinItem.upper().strip())
            except Exception as e:
                print(e)
            end = time.time()
            print('Done update balance: '+ coinItem.upper().strip()+ ' duration (s): '+str(end - start))

loop = asyncio.get_event_loop()  
loop.run_until_complete(update_balance())  
loop.close()