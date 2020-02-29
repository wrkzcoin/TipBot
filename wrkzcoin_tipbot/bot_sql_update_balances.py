#!/usr/bin/python3.6
import sys
from config import config
import store
import time
import asyncio


ENABLE_COIN = config.Enable_Coin.split(",")
ENABLE_COIN_DOGE = config.Enable_Coin_Doge.split(",")
ENABLE_XMR = config.Enable_Coin_XMR.split(",")
INTERVAL_EACH = 10


# Let's run balance update by a separate process
async def update_balance():
    while True:
        print('sleep in second: '+str(INTERVAL_EACH))
        # do not update yet
        # DOGE family:
        for coinItem in ENABLE_COIN_DOGE:
            time.sleep(INTERVAL_EACH)
            print('Update balance: '+ coinItem)
            start = time.time()
            try:
                await store.sql_update_balances(coinItem.upper().strip())
            except Exception as e:
                print(e)
            end = time.time()
            time.sleep(INTERVAL_EACH)
            # End of DOGE family
        # XMR family:
        for coinItem in ENABLE_XMR:
            time.sleep(INTERVAL_EACH)
            print('Update balance: '+ coinItem)
            start = time.time()
            try:
                await store.sql_update_balances(coinItem.upper().strip())
            except Exception as e:
                print(e)
            end = time.time()
            print('Done update balance: '+ COIN_NAME+ ' duration (s): '+str(end - start))
            time.sleep(INTERVAL_EACH)
            # End of XMR family
        for coinItem in ENABLE_COIN:
            time.sleep(INTERVAL_EACH)
            print('Update balance: '+ coinItem.upper().strip())
            start = time.time()
            try:
                await store.sql_update_balances(coinItem.upper().strip())
            except Exception as e:
                print(e)
            end = time.time()
            print('Done update balance: '+ coinItem.upper().strip()+ ' duration (s): '+str(end - start))
            time.sleep(INTERVAL_EACH)
loop = asyncio.get_event_loop()  
loop.run_until_complete(update_balance())  
loop.close()