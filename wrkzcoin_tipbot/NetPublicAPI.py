#!/usr/bin/python3.8
from typing import List, Dict
import asyncio, aiohttp
from aiohttp import web
import time, json
import store
import sys, traceback
from config import config
from wallet import *

ENABLE_TRADE_COIN = config.trade.enable_coin.split(",")

CF = True

async def handle_get_all(request):
    global CF, ENABLE_TRADE_COIN
    client_ip = request.headers.get('X-Real-IP', None)
    if CF:
        # if cloudflare
        client_ip = request.headers.get('X-Forwarded-For', None)
        try:
            print('Client ip: {} / {} / Browser: {} requested {}'.format(client_ip, request.headers.get('cf-ipcountry', None), request.headers.get('User-Agent', None), request.rel_url))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    uri = str(request.rel_url).lower()
    if uri.startswith("/orders/"):
        # catch order book market.
        market_pair = uri.replace("/orders/", "").upper()
        market_pairs = market_pair.split("-")
        if len(market_pairs) != 2:
            return await respond_bad_request_404()
        else:
            sell_coin = market_pairs[0]
            buy_coin = market_pairs[1]
            get_market_buy_list = await store.sql_get_open_order_by_alluser_by_coins(sell_coin, buy_coin, "OPEN", "ASC", 1000)
            get_market_sell_list = await store.sql_get_open_order_by_alluser_by_coins(buy_coin, sell_coin, "OPEN", "DESC", 1000)
            buy_list = {}
            sell_list = {}
            if get_market_buy_list and len(get_market_buy_list) > 0:
                for each_buy in get_market_buy_list:
                    rate = "{:.8f}".format( (each_buy['amount_sell']/each_buy['coin_sell_decimal']) / (each_buy['amount_get']/each_buy['coin_get_decimal']) )
                    amount = "{:.8f}".format(each_buy['amount_sell']/each_buy['coin_sell_decimal'])
                    buy_list[rate] = amount
            if get_market_sell_list and len(get_market_sell_list) > 0:
                for each_sell in get_market_sell_list:
                    rate = "{:.8f}".format((each_sell['amount_sell']/each_sell['coin_sell_decimal']) / (each_sell['amount_get']/each_sell['coin_get_decimal']))
                    amount = "{:.8f}".format(each_sell['amount_get']/each_sell['coin_get_decimal'])
                    sell_list[rate] = amount
            result = {"success": False, "order_book": "{}-{}".format(sell_coin, buy_coin)}
            if len(buy_list) > 0 or len(sell_list) > 0:
                result = {"success": True, "order_book": "{}-{}".format(sell_coin, buy_coin), "buy": buy_list, "sell": sell_list, "timestamp": int(time.time())}
            return web.Response(text=json.dumps(result).replace("\\", ""), status=200)
    elif uri.startswith("/markets/list"):
        # TODO: disable if there are a lot of orders
        market_list = {}
        pairs = []
        for each_coin in ENABLE_TRADE_COIN:
            each_market_coin = await store.sql_get_markets_by_coin(each_coin, 'OPEN')
            if each_market_coin and len(each_market_coin) > 0:
                for each_item in each_market_coin:
                    sell_coin = each_item['coin_sell']
                    buy_coin = each_item['coin_get']
                    pair_items = "{}-{}".format(sell_coin, buy_coin)
                    if pair_items not in pairs:
                        pairs.append(pair_items)
                        get_market_buy_list = await store.sql_get_open_order_by_alluser_by_coins(sell_coin, buy_coin, "OPEN", "ASC", 1000)
                        get_market_sell_list = await store.sql_get_open_order_by_alluser_by_coins(buy_coin, sell_coin, "OPEN", "DESC", 1000)
                        buy_list = {}
                        sell_list = {}
                        if get_market_buy_list and len(get_market_buy_list) > 0:
                            for each_buy in get_market_buy_list:
                                rate = "{:.8f}".format( (each_buy['amount_sell']/each_buy['coin_sell_decimal']) / (each_buy['amount_get']/each_buy['coin_get_decimal']) )
                                amount = "{:.8f}".format(each_buy['amount_sell']/each_buy['coin_sell_decimal'])
                                buy_list[rate] = amount
                        if get_market_sell_list and len(get_market_sell_list) > 0:
                            for each_sell in get_market_sell_list:
                                rate = "{:.8f}".format((each_sell['amount_sell']/each_sell['coin_sell_decimal']) / (each_sell['amount_get']/each_sell['coin_get_decimal']))
                                amount = "{:.8f}".format(each_sell['amount_get']/each_sell['coin_get_decimal'])
                                sell_list[rate] = amount
                        if len(buy_list) > 0 or len(sell_list) > 0:
                            market_list[pair_items] = {"buy": buy_list, "sell": sell_list}
        result = {"success": True, "market_list": market_list, "timestamp": int(time.time())}
        return web.Response(text=json.dumps(result).replace("\\", ""), status=200)
    elif uri.startswith("/markets"):
        # list all open markets
        market_list = []
        for each_coin in ENABLE_TRADE_COIN:
            each_market_coin = await store.sql_get_markets_by_coin(each_coin, 'OPEN')
            if each_market_coin and len(each_market_coin) > 0:
                market_list += ['{}-{}'.format(each_item['coin_sell'], each_item['coin_get']) for each_item in each_market_coin]
        result = {"success": True, "market_list": sorted(set(market_list)), "timestamp": int(time.time())}
        return web.Response(text=json.dumps(result).replace("\\", ""), status=200)
    elif uri.startswith("/ticker/"):
        COIN_NAME = uri.replace("/ticker/", "").upper()
        if COIN_NAME not in ENABLE_TRADE_COIN:
            return await respond_bad_request_404()
        else:
            get_trade = await store.sql_get_coin_trade_stat(COIN_NAME)
            markets = await store.sql_get_markets_by_coin(COIN_NAME, 'OPEN')
            market_list = []
            if markets and len(markets) > 0:
                market_list = ['{}-{}'.format(each_item['coin_sell'], each_item['coin_get']) for each_item in markets]
            result = {"success": True, "volume_24h": num_format_coin(get_trade['trade_24h'], COIN_NAME), "volume_7d": num_format_coin(get_trade['trade_7d'], COIN_NAME), "volume_30d": num_format_coin(get_trade['trade_30d'], COIN_NAME), "markets": sorted(set(market_list)), "timestamp": int(time.time())}
            return web.Response(text=json.dumps(result).replace("\\", ""), status=200)
    else:
        return await respond_bad_request_404()


# some bg1
async def bg_1(app):
    while True:
        # DO nothing
        pass


async def respond_bad_request():
    text = "Bad Request"
    return web.Response(text=text, status=400)


async def respond_bad_request_404():
    text = "Bad Request"
    return web.Response(text=text, status=404)


async def respond_internal_error():
    text = 'Internal Server Error'
    return web.Response(text=text, status=500)


#async def start_background_tasks(app):
#    app['market_live'] = asyncio.create_task(bg_1(app))


async def cleanup_background_tasks(app):
    app['market_live'].cancel()
    await app['market_live']


app = web.Application()
#app.on_startup.append(start_background_tasks)
#app.on_cleanup.append(cleanup_background_tasks)

app.router.add_route('GET', '/{tail:.*}', handle_get_all)

web.run_app(app, host='127.0.0.1', port=2022)