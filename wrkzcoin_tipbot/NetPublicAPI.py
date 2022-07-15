#!/usr/bin/python3.8
import asyncio
import json
import math
import sys
import time
import traceback
from decimal import Decimal

import aiomysql
from aiohttp import web
from aiomysql.cursors import DictCursor

import redis_utils
from config import config


class DBStore():
    def __init__(self):
        # DB
        self.pool = None
        self.enable_trade_coin = []

    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=2, maxsize=4,
                                                       user=config.mysql.user, password=config.mysql.password,
                                                       db=config.mysql.db, cursorclass=DictCursor, autocommit=True)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def get_all_coin(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_settings` """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_trading_coinlist(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM coin_settings WHERE `enable_trade`=%s """
                    await cur.execute(sql, 1)
                    result = await cur.fetchall()
                    return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    def truncate(self, number, digits) -> float:
        stepper = Decimal(pow(10.0, digits))
        return math.trunc(stepper * Decimal(number)) / stepper

    def num_format_coin(self, amount):
        if amount == 0:
            return "0.0"

        amount = self.truncate(amount, 8)
        amount_test = '{:,f}'.format(float(('%f' % (amount)).rstrip('0').rstrip('.')))
        if '.' in amount_test and len(amount_test.split('.')[1]) > 8:
            amount_str = '{:,.8f}'.format(amount)
        else:
            amount_str = amount_test
        return amount_str.rstrip('0').rstrip('.') if '.' in amount_str else amount_str

    async def sql_get_open_order_by_alluser_by_coins(self, coin1: str, coin2: str, status: str, option_order: str,
                                                     limit: int = 50):
        option_order = option_order.upper()
        if option_order not in ["DESC", "ASC"]:
            return False
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if coin2.upper() == "ALL":
                        sql = """ SELECT * FROM open_order WHERE `status`=%s AND `coin_sell`=%s 
                                  ORDER BY sell_div_get """ + option_order + """ LIMIT """ + str(limit)
                        await cur.execute(sql, (status, coin1.upper()))
                        result = await cur.fetchall()
                        return result
                    else:
                        sql = """ SELECT * FROM open_order WHERE `status`=%s AND `coin_sell`=%s AND `coin_get`=%s 
                                  ORDER BY sell_div_get """ + option_order + """ LIMIT """ + str(limit)
                        await cur.execute(sql, (status, coin1.upper(), coin2.upper()))
                        result = await cur.fetchall()
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def sql_get_markets_by_coin(self, coin: str, status: str):
        global pool
        coin_name = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT DISTINCT `coin_sell`, `coin_get` 
                              FROM `open_order` WHERE `status`=%s AND (`coin_sell`=%s OR `coin_get`=%s) """
                    await cur.execute(sql, (status, coin_name, coin_name))
                    result = await cur.fetchall()
                    return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def sql_get_order_numb(self, order_num: str, status: str = None):
        if status is None: status = 'OPEN'
        if status: status = status.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    result = None
                    if status == "ANY":
                        sql = """ SELECT * FROM `open_order` WHERE `order_id` = %s LIMIT 1 """
                        await cur.execute(sql, order_num)
                        result = await cur.fetchone()
                    else:
                        sql = """ SELECT * FROM `open_order` WHERE `order_id` = %s 
                                  AND `status`=%s LIMIT 1 """
                        await cur.execute(sql, (order_num, status))
                        result = await cur.fetchone()
                    return result
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def sql_get_coin_trade_stat(self, coin: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT (SELECT SUM(amount_sell) FROM open_order 
                              WHERE coin_sell=%s AND status='COMPLETE' AND order_completed_date > UNIX_TIMESTAMP()-3600*24) AS sell_24h, 
                              (SELECT SUM(amount_get) FROM open_order 
                              WHERE coin_get=%s AND status='COMPLETE' AND order_completed_date > UNIX_TIMESTAMP()-3600*24) AS get_24h,
                              (SELECT SUM(amount_sell) FROM open_order 
                              WHERE coin_sell=%s AND status='COMPLETE' AND order_completed_date > UNIX_TIMESTAMP()-3600*24*7) AS sell_7d, 
                              (SELECT SUM(amount_get) FROM open_order 
                              WHERE coin_get=%s AND status='COMPLETE' AND order_completed_date > UNIX_TIMESTAMP()-3600*24*7) AS get_7d,
                              (SELECT SUM(amount_sell) FROM open_order 
                              WHERE coin_sell=%s AND status='COMPLETE' AND order_completed_date > UNIX_TIMESTAMP()-3600*24*30) AS sell_30d, 
                              (SELECT SUM(amount_get) FROM open_order 
                              WHERE coin_get=%s AND status='COMPLETE' AND order_completed_date > UNIX_TIMESTAMP()-3600*24*30) AS get_30d
                              """
                    await cur.execute(sql, (
                    coin.upper(), coin.upper(), coin.upper(), coin.upper(), coin.upper(), coin.upper()))
                    result = await cur.fetchone()
                    if result:
                        result['sell_24h'] = result['sell_24h'] if result['sell_24h'] else 0
                        result['get_24h'] = result['get_24h'] if result['get_24h'] else 0
                        result['sell_7d'] = result['sell_7d'] if result['sell_7d'] else 0
                        result['get_7d'] = result['get_7d'] if result['get_7d'] else 0
                        result['sell_30d'] = result['sell_30d'] if result['sell_30d'] else 0
                        result['get_30d'] = result['get_30d'] if result['get_30d'] else 0
                        return {'trade_24h': result['sell_24h'] + result['get_24h'],
                                'trade_7d': result['sell_7d'] + result['get_7d'],
                                'trade_30d': result['sell_30d'] + result['get_30d']}
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def handle_get_all(self, request):
        list_trading_coins = await self.get_trading_coinlist()
        enabled_coin = [each['coin_name'] for each in list_trading_coins]

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
                get_market_buy_list = await self.sql_get_open_order_by_alluser_by_coins(sell_coin, buy_coin, "OPEN",
                                                                                        "ASC", 1000)
                get_market_sell_list = await self.sql_get_open_order_by_alluser_by_coins(buy_coin, sell_coin, "OPEN",
                                                                                         "DESC", 1000)
                buy_refs = []
                sell_refs = []
                if get_market_buy_list and len(get_market_buy_list) > 0:
                    for each_buy in get_market_buy_list:
                        rate = "{:.8f}".format(each_buy['amount_sell'] / each_buy['amount_get'])
                        amount = "{:.8f}".format(each_buy['amount_sell'])
                        buy_refs.append({str(each_buy["order_id"]): {"sell": {"coin_sell": each_buy['coin_sell'],
                                                                              "amount_sell": self.num_format_coin(
                                                                                  each_buy['amount_sell_after_fee']),
                                                                              "fee_sell": self.num_format_coin(
                                                                                  each_buy['amount_sell'] - each_buy[
                                                                                      'amount_sell_after_fee']),
                                                                              "total": self.num_format_coin(
                                                                                  each_buy['amount_sell'])},
                                                                     "for": {"coin_get": each_buy['coin_get'],
                                                                             "amount_get": self.num_format_coin(
                                                                                 each_buy['amount_get_after_fee']),
                                                                             "fee_get": self.num_format_coin(
                                                                                 each_buy['amount_get'] - each_buy[
                                                                                     'amount_get_after_fee']),
                                                                             "total": self.num_format_coin(
                                                                                 each_buy['amount_get'])}}})
                if get_market_sell_list and len(get_market_sell_list) > 0:
                    for each_sell in get_market_sell_list:
                        rate = "{:.8f}".format(each_sell['amount_sell'] / each_sell['amount_get'])
                        amount = "{:.8f}".format(each_sell['amount_get'])
                        sell_refs.append({str(each_sell["order_id"]): {"sell": {"coin_sell": each_sell['coin_sell'],
                                                                                "amount_sell": self.num_format_coin(
                                                                                    each_sell['amount_sell_after_fee']),
                                                                                "fee_sell": self.num_format_coin(
                                                                                    each_sell['amount_sell'] -
                                                                                    each_sell['amount_sell_after_fee']),
                                                                                "total": self.num_format_coin(
                                                                                    each_sell['amount_sell'])},
                                                                       "for": {"coin_get": each_sell['coin_get'],
                                                                               "amount_get": self.num_format_coin(
                                                                                   each_sell['amount_get_after_fee']),
                                                                               "fee_get": self.num_format_coin(
                                                                                   each_sell['amount_get'] - each_sell[
                                                                                       'amount_get_after_fee']),
                                                                               "total": self.num_format_coin(
                                                                                   each_sell['amount_get'])}}})
                result = {"success": False, "order_book": "{}-{}".format(sell_coin, buy_coin)}
                if len(buy_refs) > 0 or len(sell_refs) > 0:
                    result = {"success": True, "order_book": "{}-{}".format(sell_coin, buy_coin), "buys": buy_refs,
                              "sells": sell_refs, "timestamp": int(time.time())}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=200)
        elif uri.startswith("/order/"):
            # catch order book market.
            ref_number = uri.replace("/order/", "")
            if ref_number.isnumeric() is False:
                return await respond_bad_request_404()
            get_order_num = await self.sql_get_order_numb(ref_number, 'ANY')
            if get_order_num:
                result = {"success": True, "ref_number": "#{}".format(get_order_num['order_id']),
                          "sell": {"coin_sell": get_order_num['coin_sell'],
                                   "amount_sell": self.num_format_coin(get_order_num['amount_sell_after_fee']),
                                   "fee_sell": self.num_format_coin(
                                       get_order_num['amount_sell'] - get_order_num['amount_sell_after_fee']),
                                   "total": self.num_format_coin(get_order_num['amount_sell'])},
                          "for": {"coin_get": get_order_num['coin_get'],
                                  "amount_get": self.num_format_coin(get_order_num['amount_get_after_fee']),
                                  "fee_get": self.num_format_coin(
                                      get_order_num['amount_get'] - get_order_num['amount_get_after_fee']),
                                  "total": self.num_format_coin(get_order_num['amount_get'])},
                          "status": get_order_num['status'], "timestamp": int(time.time())}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=404)
            else:
                result = {"success": False, "error": "ref_number not found.", "timestamp": int(time.time())}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=404)
        elif uri.startswith("/markets/list"):
            # TODO: disable if there are a lot of orders
            market_list = {}
            pairs = []
            for each_coin in enabled_coin:
                each_market_coin = await self.sql_get_markets_by_coin(each_coin, 'OPEN')
                if each_market_coin and len(each_market_coin) > 0:
                    for each_item in each_market_coin:
                        sell_coin = each_item['coin_sell']
                        buy_coin = each_item['coin_get']
                        pair_items = "{}-{}".format(sell_coin, buy_coin)
                        if pair_items not in pairs:
                            pairs.append(pair_items)
                            get_market_buy_list = await self.sql_get_open_order_by_alluser_by_coins(sell_coin, buy_coin,
                                                                                                    "OPEN", "ASC", 1000)
                            get_market_sell_list = await self.sql_get_open_order_by_alluser_by_coins(buy_coin,
                                                                                                     sell_coin, "OPEN",
                                                                                                     "DESC", 1000)
                            buy_list = []
                            sell_list = []
                            if get_market_buy_list and len(get_market_buy_list) > 0:
                                for each_buy in get_market_buy_list:
                                    rate = "{:.8f}".format(each_buy['amount_sell'] / (each_buy['amount_get']))
                                    amount = "{:.8f}".format(each_buy['amount_sell'])
                                    buy_list.append({str(each_buy["order_id"]): {
                                        "sell": {"coin_sell": each_buy['coin_sell'],
                                                 "amount_sell": self.num_format_coin(each_buy['amount_sell_after_fee']),
                                                 "fee_sell": self.num_format_coin(
                                                     each_buy['amount_sell'] - each_buy['amount_sell_after_fee']),
                                                 "total": self.num_format_coin(each_buy['amount_sell'])},
                                        "for": {"coin_get": each_buy['coin_get'],
                                                "amount_get": self.num_format_coin(each_buy['amount_get_after_fee']),
                                                "fee_get": self.num_format_coin(
                                                    each_buy['amount_get'] - each_buy['amount_get_after_fee']),
                                                "total": self.num_format_coin(each_buy['amount_get'])}}})
                            if get_market_sell_list and len(get_market_sell_list) > 0:
                                for each_sell in get_market_sell_list:
                                    rate = "{:.8f}".format(each_sell['amount_sell'] / each_sell['amount_get'])
                                    amount = "{:.8f}".format(each_sell['amount_get'])
                                    sell_list.append({str(each_sell["order_id"]): {
                                        "sell": {"coin_sell": each_sell['coin_sell'],
                                                 "amount_sell": self.num_format_coin(
                                                     each_sell['amount_sell_after_fee']),
                                                 "fee_sell": self.num_format_coin(
                                                     each_sell['amount_sell'] - each_sell['amount_sell_after_fee']),
                                                 "total": self.num_format_coin(each_sell['amount_sell'])},
                                        "for": {"coin_get": each_sell['coin_get'],
                                                "amount_get": self.num_format_coin(each_sell['amount_get_after_fee']),
                                                "fee_get": self.num_format_coin(
                                                    each_sell['amount_get'] - each_sell['amount_get_after_fee']),
                                                "total": self.num_format_coin(each_sell['amount_get'])}}})
                            if len(buy_list) > 0 or len(sell_list) > 0:
                                market_list[pair_items] = {"buy": buy_list, "sell": sell_list}
            result = {"success": True, "market_list": market_list, "timestamp": int(time.time())}
            return web.Response(text=json.dumps(result).replace("\\", ""), status=200)
        elif uri.startswith("/markets"):
            # list all open markets
            market_list = []
            for each_coin in enabled_coin:
                each_market_coin = await self.sql_get_markets_by_coin(each_coin, 'OPEN')
                if each_market_coin and len(each_market_coin) > 0:
                    market_list += ['{}-{}'.format(each_item['coin_sell'], each_item['coin_get']) for each_item in
                                    each_market_coin]
            result = {"success": True, "market_list": sorted(set(market_list)), "timestamp": int(time.time())}
            return web.Response(text=json.dumps(result).replace("\\", ""), status=200)
        elif uri.startswith("/ticker/"):
            coin_name = uri.replace("/ticker/", "").upper()
            if coin_name not in enabled_coin:
                return await respond_bad_request_404()
            else:
                get_trade = await self.sql_get_coin_trade_stat(coin_name)
                markets = await self.sql_get_markets_by_coin(coin_name, 'OPEN')
                market_list = []
                if markets and len(markets) > 0:
                    market_list = ['{}-{}'.format(each_item['coin_sell'], each_item['coin_get']) for each_item in
                                   markets]
                result = {"success": True, "volume_24h": self.num_format_coin(get_trade['trade_24h']),
                          "volume_7d": self.num_format_coin(get_trade['trade_7d']),
                          "volume_30d": self.num_format_coin(get_trade['trade_30d']),
                          "markets": sorted(set(market_list)), "timestamp": int(time.time())}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=200)
        elif uri.startswith("/coininfo"):
            # show json all coin info
            get_all_coins = await self.get_all_coin()
            redis_utils.openRedis()
            if len(get_all_coins) > 0:
                all_coins = []
                for c in get_all_coins:
                    type_coin = c['type']
                    height = "N/A"
                    tip = "✅" if c['enable_tip'] == 1 else "❌"
                    deposit = "✅" if c['enable_deposit'] == 1 else "❌"
                    withdraw = "✅" if c['enable_withdraw'] == 1 else "❌"
                    twitter = "✅" if c['enable_twitter'] == 1 else "❌"
                    telegram = "✅" if c['enable_telegram'] == 1 else "❌"

                    explorer_link = c['explorer_link']
                    if explorer_link and explorer_link.startswith("http"):
                        explorer_link = "<a href=\"{}\" target=\"_blank\">Link</a>".format(explorer_link)
                    withdraw_info = "Min. {} / Max. {} {}".format(self.num_format_coin(c['real_min_tx']),
                                                                  self.num_format_coin(c['real_max_tx']),
                                                                  c['coin_name'])
                    tip_info = "Min. {} / Max. {} {}".format(self.num_format_coin(c['real_min_tip']),
                                                             self.num_format_coin(c['real_max_tip']), c['coin_name'])
                    net_name = c['net_name']
                    coin_name = c['coin_name']
                    try:
                        if type_coin in ["ERC-20", "TRC-20"]:
                            height = int(redis_utils.redis_conn.get(
                                f'{config.redis.prefix + config.redis.daemon_height}{net_name}').decode())
                        else:
                            height = int(redis_utils.redis_conn.get(
                                f'{config.redis.prefix + config.redis.daemon_height}{coin_name}').decode())
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    all_coins.append(
                        [c['coin_name'], height, c['deposit_confirm_depth'], tip, deposit, withdraw, twitter, telegram,
                         tip_info, withdraw_info, explorer_link])
                result = {'data': all_coins}
                return web.json_response(result, status=200)
        else:
            return await respond_bad_request_404()


# some bg1
async def bg_1(app):
    while True:
        # DO nothing
        await asyncio.sleep(10.0)
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


# async def start_background_tasks(app):
#    app['market_live'] = asyncio.create_task(bg_1(app))


async def cleanup_background_tasks(app):
    app['market_live'].cancel()
    await app['market_live']


app = web.Application()
# app.on_startup.append(start_background_tasks)
# app.on_cleanup.append(cleanup_background_tasks)

DB = DBStore()
app.router.add_route('GET', '/{tail:.*}', DB.handle_get_all)
web.run_app(app, host='127.0.0.1', port=2022)
