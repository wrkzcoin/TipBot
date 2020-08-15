#!/usr/bin/python3.6
import sys, traceback
from config import config
import store
import time
import asyncio

ENABLE_COIN_NANO = config.Enable_Coin_Nano.split(",")
INTERVAL_EACH = 5

# Let's run balance update by a separate process
async def update_balance():
    while True:
        print('sleep in second: '+str(INTERVAL_EACH))
        # do not update yet
        # DOGE family:
        for coinItem in ENABLE_COIN_NANO:
            update = 0
            time.sleep(INTERVAL_EACH)
            print('Update balance: '+ coinItem)
            start = time.time()
            try:
                update = await store.sql_nano_update_balances(coinItem.upper().strip())
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            end = time.time()
            print('Done update balance: '+ coinItem.upper().strip()+ ' updated *'+str(update)+'* duration (s): '+str(end - start))
            time.sleep(INTERVAL_EACH)
            # End of DOGE family
loop = asyncio.get_event_loop()  
loop.run_until_complete(update_balance())  
loop.close()