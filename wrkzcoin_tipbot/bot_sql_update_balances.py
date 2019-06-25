#!/usr/bin/python3.6
import sys
from config import config
import store
import time

ENABLE_COIN = config.Enable_Coin.split(",")
INTERVAL_EACH = 10

### Let's run balance update by a separate process
while True:
    print('sleep in second: '+str(INTERVAL_EACH))
    ## do not update yet
    for coinItem in ENABLE_COIN:
        time.sleep(INTERVAL_EACH)
        print('Update balance: '+ coinItem.upper().strip())
        start = time.time()
        try:
            store.sql_update_balances(coinItem.upper().strip())
        except Exception as e:
            print(e)
        end = time.time()
        print('Done update balance: '+ coinItem.upper().strip()+ ' duration (s): '+str(end - start))