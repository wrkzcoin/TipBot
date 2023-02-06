from fastapi import FastAPI, Response, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
import asyncio
from hashlib import sha256

import time
import traceback, sys
import uvicorn
import os
from typing import Union
from decimal import Decimal
from string import ascii_uppercase
import random
from attrdict import AttrDict

from config import load_config
from cogs.cexswap import cexswap_get_pools, cexswap_get_all_lp_pools, cexswap_get_pool_details, \
cexswap_get_poolshare, get_cexswap_get_sell_logs, get_cexswap_get_coin_sell_logs, \
cexswap_get_list_enable_pair_list, cexswap_get_coin_setting, cexswap_route_trade, \
cexswap_find_possible_trade, cexswap_estimate, find_user_by_apikey, \
cexswap_count_api_usage

from Bot import truncate, text_to_num, logchanbot
import store
from cogs.utils import num_format_coin


app = FastAPI(
    title="TipBot CEXSwap API",
    version="0.0.1",
    contact={
        "name": "Pluton",
        "url": "http://chat.wrkz.work/",
        "email": "team@bot.tips",
    },
    docs_url="/manual"
)
config = load_config()

# start of background
class BackgroundRunner:
    def __init__(self, app_main):
        self.app_main = app_main

    async def fetch_paprika_price(
        self
    ):
        config = load_config()
        while True:
            try:
                await store.openConnection()
                async with store.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """
                        SELECT * FROM `coin_paprika_list` 
                        WHERE `enable`=1
                        """
                        await cur.execute(sql, ())
                        result = await cur.fetchall()
                        if result and len(result) > 0:
                            id_list = {}
                            symbol_list = {}
                            for each_item in result:
                                id_list[each_item['id']] = each_item  # key example: btc-bitcoin
                                symbol_list[each_item['symbol'].upper()] = each_item  # key example: BTC
                            self.app_main.coin_paprika_id_list = id_list
                            self.app_main.coin_paprika_symbol_list = symbol_list
                        # Alias price
                        sql = """
                        SELECT * FROM `coin_alias_price`
                        """
                        await cur.execute(sql, ())
                        result = await cur.fetchall()
                        if result and len(result) > 0:
                            hints = {}
                            hint_names = {}
                            for each_item in result:
                                hints[each_item['ticker']] = each_item
                                hint_names[each_item['name'].upper()] = each_item
                            self.app_main.token_hints = hints
                            self.app_main.token_hint_names = hint_names
            except Exception:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(60.0)

    async def paprika_price_token(self, token_name: str, by_id: bool=False):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `coin_paprika_list`
                    WHERE `symbol`=%s
                    """
                    if by_id is True:
                        sql = """
                        SELECT * FROM `coin_paprika_list`
                        WHERE `id`=%s
                        """
                    await cur.execute(sql, (token_name))
                    result = await cur.fetchall()
                    if result:
                        price_list = []
                        for i in result:
                            price_list.append({
                                "id": i['id'],
                                "symbol": i['symbol'],
                                "name": i['name'],
                                "price_usd": i['price_usd'],
                                "price_date": i['last_updated']
                            })
                        return price_list
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []
    
    async def coingecko_price_token(self, token_name: str, by_id: bool=False):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `coin_coingecko_list`
                    WHERE `symbol`=%s
                    """
                    if by_id is True:
                        sql = """
                        SELECT * FROM `coin_coingecko_list`
                        WHERE `id`=%s
                        """
                    await cur.execute(sql, (token_name))
                    result = await cur.fetchall()
                    if result:
                        price_list = []
                        for i in result:
                            price_list.append({
                                "id": i['id'],
                                "symbol": i['symbol'],
                                "name": i['name'],
                                "price_usd": i['price_usd'],
                                "price_date": i['price_date']
                            })
                        return price_list
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

runner = BackgroundRunner(app)

@app.on_event('startup')
async def app_startup():
    asyncio.create_task(runner.fetch_paprika_price())
# End of background

async def get_coin_setting():
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                coin_list = {}
                sql = """ SELECT * FROM `coin_settings` 
                WHERE `enable`=1
                """
                await cur.execute(sql, ())
                result = await cur.fetchall()
                if result and len(result) > 0:
                    for each in result:
                        coin_list[each['coin_name']] = each
                    return AttrDict(coin_list)
    except Exception:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None

class SellToken(BaseModel):
    amount: str
    sell_token: str
    for_token: str

class BuyToken(BaseModel):
    amount: str
    buy_token: str
    sell_token: str

@app.post("/estimate_sell/")
async def estimate_amount_token_sell(
    request: Request, item: SellToken, Authorization: Union[str, None] = Header(default=None)
):
    if config['cexswap_api']['api_enable'] != 1:
        return {
            "success": False,
            "data": None,
            "error": "API is currently disable!",
            "time": int(time.time())
        }

    user_id = "PUBLIC"
    user_server = "PUBLIC"

    if config['cexswap_api']['is_estimation_pub'] != 1 and Authorization is not None:
        hash_key = sha256(Authorization.encode()).hexdigest()
        find_user = await find_user_by_apikey(hash_key)
        if find_user is None:
            return {
                "success": False,
                "data": None,
                "error": "Invalid given Authorization API Key!",
                "time": int(time.time())
            }
        else:
            user_id = find_user['user_id']
            user_server = find_user['user_server']

    # check usage of API by user_id and user_server
    if config['cexswap_api']['is_estimation_pub'] != 1:
        if user_id == "PUBLIC" and user_server == "PUBLIC":
            count = await cexswap_count_api_usage(user_id, user_server, 1, 3600)
            if count >= config['cexswap_api']['public_api_call_1h']:
                return {
                    "success": False,
                    "data": None,
                    "error": "Public usage reached limit for the last hour, please use with API key as 'Authorization'!",
                    "time": int(time.time())
                }

            count = await cexswap_count_api_usage(user_id, user_server, 1, 24*3600)
            if count >= config['cexswap_api']['public_api_call_24h']:
                return {
                    "success": False,
                    "data": None,
                    "error": "Public usage reached limit for the last 24 hours, please use with API key as 'Authorization'!",
                    "time": int(time.time())
                }
        else:
            count = await cexswap_count_api_usage(user_id, user_server, 1, 3600)
            if count >= config['cexswap_api']['private_api_estimate_1h']:
                return {
                    "success": False,
                    "data": None,
                    "error": "Your API usage reached limit for the last hour!",
                    "time": int(time.time())
                }

    sell_token = item.sell_token.upper()
    for_token = item.for_token.upper()
    amount = item.amount

    app.coin_list = await get_coin_setting()

    if sell_token == for_token:
        return {
            "success": False,
            "data": sell_token,
            "error": "<sell_token> can't be the same as <for_token>.",
            "time": int(time.time())
        }

    liq_pair = await cexswap_get_pool_details(sell_token, for_token, None)
    if liq_pair is None:
        return {
            "success": False,
            "data": None,
            "error": f"There is no liquidity pool for {sell_token}/{for_token}.",
            "time": int(time.time())
        }
    else:
        try:
            sell_amount_old = amount
            amount_liq_sell = liq_pair['pool']['amount_ticker_1']
            if sell_token == liq_pair['pool']['ticker_2_name']:
                amount_liq_sell = liq_pair['pool']['amount_ticker_2']
            cexswap_min = getattr(getattr(app.coin_list, sell_token), "cexswap_min")
            token_display = getattr(getattr(app.coin_list, sell_token), "display_name")
            usd_equivalent_enable = getattr(getattr(app.coin_list, sell_token), "usd_equivalent_enable")
            cexswap_max_swap_percent_sell = getattr(getattr(app.coin_list, sell_token), "cexswap_max_swap_percent")
            max_swap_sell_cap = cexswap_max_swap_percent_sell * float(amount_liq_sell)

            # Check amount
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                return {
                    "success": False,
                    "data": sell_amount_old,
                    "error": "invalid given amount.",
                    "time": int(time.time())
                }

            amount = truncate(float(amount), 12)
            if amount is None:
                return {
                    "success": False,
                    "data": sell_amount_old,
                    "error": "invalid given amount.",
                    "time": int(time.time())
                }
            amount = float(amount)

            # Check if amount is more than liquidity
            if truncate(float(amount), 8) > truncate(float(max_swap_sell_cap), 8):
                msg = f"The given amount {sell_amount_old}"\
                    f" is more than allowable 10% of liquidity {num_format_coin(max_swap_sell_cap)} {token_display}." \
                    f" Current LP: {num_format_coin(liq_pair['pool']['amount_ticker_1'])} "\
                    f"{liq_pair['pool']['ticker_1_name']} and "\
                    f"{num_format_coin(liq_pair['pool']['amount_ticker_2'])} "\
                    f"{liq_pair['pool']['ticker_2_name']} for LP {liq_pair['pool']['ticker_1_name']}/{liq_pair['pool']['ticker_2_name']}."
                return {
                    "success": False,
                    "data": num_format_coin(max_swap_sell_cap),
                    "error": msg,
                    "time": int(time.time())
                }
            # Check if too big rate gap
            try:
                rate_ratio = liq_pair['pool']['amount_ticker_1'] / liq_pair['pool']['amount_ticker_2']
                if rate_ratio > 10**12 or rate_ratio < 1/10**12:
                    msg = "Rate ratio is out of range. Try with other pairs."
                    return {
                        "success": False,
                        "data": rate_ratio,
                        "error": msg,
                        "time": int(time.time())
                    }
            except Exception:
                traceback.print_exc(file=sys.stdout)

            # check slippage first
            slippage = 1.0 - amount / float(liq_pair['pool']['amount_ticker_1']) - config['cexswap_slipage']['reserve']
            amount_get = amount * float(liq_pair['pool']['amount_ticker_2'] / liq_pair['pool']['amount_ticker_1'])

            amount_qty_1 = liq_pair['pool']['amount_ticker_2']
            amount_qty_2 = liq_pair['pool']['amount_ticker_1']

            if sell_token == liq_pair['pool']['ticker_2_name']:
                amount_get = amount * float(liq_pair['pool']['amount_ticker_1'] / liq_pair['pool']['amount_ticker_2'])
                slippage = 1.0 - amount / float(liq_pair['pool']['amount_ticker_2']) - config['cexswap_slipage']['reserve']

                amount_qty_1 = liq_pair['pool']['amount_ticker_1']
                amount_qty_2 = liq_pair['pool']['amount_ticker_2']

            # adjust slippage
            amount_get = slippage * amount_get
            if slippage > 1 or slippage < 0.88:
                msg = "Internal error with slippage. Try again later!"
                return {
                    "success": False,
                    "data": slippage,
                    "error": msg,
                    "time": int(time.time())
                }

            # price impact = unit price now / unit price after sold
            price_impact_text = ""
            new_impact_ratio = (float(amount_qty_2) + amount) / (float(amount_qty_1) - amount_get)
            old_impact_ratio = float(amount_qty_2) / float(amount_qty_1)
            impact_ratio = abs(old_impact_ratio - new_impact_ratio) / max(old_impact_ratio, new_impact_ratio)
            price_impact_percent = 0.0
            if 0.0001 < impact_ratio < 1:
                price_impact_text = "~{:,.2f}{}".format(impact_ratio * 100, "%")
                price_impact_percent = impact_ratio * 100

            # If the amount get is too small.
            if amount_get < config['cexswap']['minimum_receive_or_reject']:
                num_receive = num_format_coin(amount_get)
                msg = f"The received amount is too small {num_receive} {for_token}. Please increase your sell amount!"
                return {
                    "success": False,
                    "data": num_receive,
                    "error": msg,
                    "time": int(time.time())
                }
            elif truncate(amount, 8) < truncate(cexswap_min, 8):
                msg = f"The given amount {sell_amount_old} is below minimum {num_format_coin(cexswap_min)} {token_display}."
                return {
                    "success": False,
                    "data": num_format_coin(cexswap_min),
                    "error": msg,
                    "time": int(time.time())
                }
            else:
                # OK, show sell estimation
                got_fee_dev = amount_get * config['cexswap']['dev_fee'] / 100
                got_fee_liquidators = amount_get * config['cexswap']['liquidator_fee'] / 100
                got_fee_dev += amount_get * config['cexswap']['guild_fee'] / 100
                ref_log = ''.join(random.choice(ascii_uppercase) for i in range(16))
                liq_users = []
                if len(liq_pair['pool_share']) > 0:
                    for each_s in liq_pair['pool_share']:
                        distributed_amount = None
                        if for_token == each_s['ticker_1_name']:
                            distributed_amount = float(each_s['amount_ticker_1']) / float(liq_pair['pool']['amount_ticker_1']) * float(truncate(got_fee_liquidators, 12))
                        elif for_token == each_s['ticker_2_name']:
                            distributed_amount = float(each_s['amount_ticker_2']) / float(liq_pair['pool']['amount_ticker_2']) * float(truncate(got_fee_liquidators, 12))
                        if distributed_amount is not None:
                            liq_users.append([distributed_amount, each_s['user_id'], each_s['user_server']])

                fee = truncate(got_fee_dev, 12) + truncate(got_fee_liquidators, 12)
                user_amount_get = num_format_coin(truncate(amount_get - float(fee), 12))
                user_amount_sell = num_format_coin(amount)

                suggestion_msg = []
                if config['cexswap']['enable_better_price'] == 1:
                    try:
                        get_better_price = await cexswap_find_possible_trade(
                            sell_token, for_token, amount * slippage, amount_get - float(fee)
                        )
                        if len(get_better_price) > 0:
                            suggestion_msg = get_better_price
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                # add estimate
                try:
                    await cexswap_estimate(
                        ref_log, liq_pair['pool']['pool_id'], "{}->{}".format(sell_token, for_token),
                        truncate(amount, 12), sell_token, truncate(amount_get - float(fee), 12), for_token,
                        got_fee_dev, got_fee_liquidators, 0.0, price_impact_percent,
                        user_id, user_server, use_api=1
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                return {
                    "success": True,
                    "data": {
                        "sell_amount": user_amount_sell,
                        "sell_coin": sell_token,
                        "for_amount": user_amount_get,
                        "for_token": for_token,
                        "price_impact": price_impact_text,
                        "suggestion": suggestion_msg,
                        "ref": ref_log
                    },
                    "error": None,
                    "time": int(time.time())
                }
        except Exception:
            traceback.print_exc(file=sys.stdout)

@app.get("/paprika_price/{token}")
async def get_paprika_price(
    token: str, request: Request
):
    """
    token: coin name or token name. Example: BTC, LTC, DOGE, etc
    """
    if config['cexswap_api']['api_enable'] != 1:
        return {
            "success": False,
            "data": None,
            "error": "API is currently disable!",
            "time": int(time.time())
        }
    token = token.upper()
    app.coin_list = await get_coin_setting()
    note = None
    if token not in app.coin_list:
        note = f"Token {token} not in our CEXSwap!"
    price = await runner.paprika_price_token(token_name=token, by_id=False)
    return {
        "success": True,
        "unit": "USD",
        "data": price,
        "error": None,
        "note": note,
        "time": int(time.time())
    }

@app.get("/gecko_price/{token}")
async def get_coingecko_price(
    token: str, request: Request
):
    """
    token: coin name or token name. Example: BTC, LTC, DOGE, etc
    """
    if config['cexswap_api']['api_enable'] != 1:
        return {
            "success": False,
            "data": None,
            "error": "API is currently disable!",
            "time": int(time.time())
        }
    token = token.upper()
    app.coin_list = await get_coin_setting()
    note = None
    if token not in app.coin_list:
        note = f"Token {token} not in our CEXSwap!"
    price = await runner.coingecko_price_token(token_name=token, by_id=False)
    return {
        "success": True,
        "unit": "USD",
        "data": price,
        "error": None,
        "note": note,
        "time": int(time.time())
    }

@app.get("/summary/{slug}")
async def get_summary_detail(
    slug: str, request: Request
):
    """
    slug: coin name or pool pairs. Example: WRKZ, WRKZ-DEGO
    """
    if config['cexswap_api']['api_enable'] != 1:
        return {
            "success": False,
            "data": None,
            "error": "API is currently disable!",
            "time": int(time.time())
        }

    pool_name = slug.upper()
    get_coins_pairs = await cexswap_get_list_enable_pair_list()
    if "-" in pool_name:
        pool_name = sorted(pool_name.split("-"))
        pool_name = "{}/{}".format(pool_name[0], pool_name[1])
    if pool_name in get_coins_pairs['coins']:
        # single coin
        coin_name = pool_name
        coin_data = await cexswap_get_coin_setting(coin_name)
        if coin_data is None:
            return {
                "success": False,
                "data": None,
                "error": "could not find such coin or not enable!",
                "time": int(time.time())
            }
        else:
            find_other_lp = await cexswap_get_pools(coin_name)
            total_liq = Decimal(0)
            items = []
            if len(find_other_lp) > 0:
                items =[i['pairs'] for i in find_other_lp]
                # get L in LP
                for i in find_other_lp:
                    if coin_name == i['ticker_1_name']:
                        total_liq += i['amount_ticker_1']
                    elif coin_name == i['ticker_2_name']:
                        total_liq += i['amount_ticker_2']

            get_coin_vol = {}
            get_coin_vol['volume_1d'] = await get_cexswap_get_coin_sell_logs(
                coin_name=coin_name, user_id=None, from_time=int(time.time())-1*24*3600)
            get_coin_vol['volume_7d'] = await get_cexswap_get_coin_sell_logs(
                coin_name=coin_name, user_id=None, from_time=int(time.time())-7*24*3600)
            get_coin_vol['volume_30d'] = await get_cexswap_get_coin_sell_logs(
                coin_name=coin_name, user_id=None, from_time=int(time.time())-30*24*3600)
            volume = {}
            if len(get_coin_vol) > 0:
                for k, v in get_coin_vol.items():
                    if len(v) > 0:
                        sum_amount = Decimal(0)
                        for i in v:
                            if i['got_ticker'] == coin_name:
                                sum_amount += i['got']
                        if sum_amount > 0:
                            volume[k] = truncate(sum_amount, 8)
            return {
                "success": True,
                "result": {
                    "pairs": items,
                    "total_liquidity": truncate(total_liq, 8),
                    "volume_1d": volume['volume_1d'] if 'volume_1d' in volume else None,
                    "volume_7d": volume['volume_7d'] if 'volume_7d' in volume else None,
                    "volume_30d": volume['volume_30d'] if 'volume_30d' in volume else None,
                },
                "time": int(time.time())
            }
    elif pool_name in get_coins_pairs['pairs']:
        # available pairs
        tickers = pool_name.split("/")
        liq_pair = await cexswap_get_pool_details(tickers[0], tickers[1], None)
        if liq_pair is not None:
            return {
                "success": True,
                "result": {
                    "total_liquidity": {
                        liq_pair['pool']['ticker_1_name']: truncate(liq_pair['pool']['amount_ticker_1'], 8),
                        liq_pair['pool']['ticker_2_name']: truncate(liq_pair['pool']['amount_ticker_2'], 8),
                    },
                    "rate": {
                        liq_pair['pool']['ticker_1_name']: truncate(liq_pair['pool']['amount_ticker_2']/liq_pair['pool']['amount_ticker_1'], 10),
                        liq_pair['pool']['ticker_2_name']: truncate(liq_pair['pool']['amount_ticker_1']/liq_pair['pool']['amount_ticker_2'], 10),
                    }
                },
                "time": int(time.time())
            }
        else:
            return {
                "success": False,
                "result": None,
                "error": "there is no pool for that yet!",
                "time": int(time.time())
            }
    else:
        return {
            "success": False,
            "result": None,
            "error": "invalid coins or pairs!",
            "time": int(time.time())
        }


@app.get("/summary")
async def get_summary(
    request: Request
):
    if config['cexswap_api']['api_enable'] != 1:
        return {
            "success": False,
            "data": None,
            "error": "API is currently disable!",
            "time": int(time.time())
        }

    get_coins_pairs = await cexswap_get_list_enable_pair_list()
    get_pools = await cexswap_get_pools()

    get_coin_vol = await get_cexswap_get_coin_sell_logs(coin_name=None, user_id=None, from_time=int(time.time())-1*24*3600)
    list_volume_1d = {}
    if len(get_coin_vol) > 0:
        for v in get_coin_vol:
            list_volume_1d["{}/{}".format(v['sold_ticker'], v['got_ticker'])] = {
                v['sold_ticker']: truncate(v['sold'], 8), v['got_ticker']: truncate(v['got'], 8)
            }

    get_coin_vol = await get_cexswap_get_coin_sell_logs(coin_name=None, user_id=None, from_time=int(time.time())-7*24*3600)
    list_volume_7d = {}
    if len(get_coin_vol) > 0:
        for v in get_coin_vol:
            list_volume_7d["{}/{}".format(v['sold_ticker'], v['got_ticker'])] = {
                v['sold_ticker']: truncate(v['sold'], 8), v['got_ticker']: truncate(v['got'], 8)
            }


    list_markets = {}
    if len(get_pools) > 0:
        for i in get_pools:
            pairs = "{}/{}".format(i['amount_ticker_1'], i['amount_ticker_2'])
            list_markets[i['pairs']] = {
                "rate": {
                    i['ticker_1_name']: truncate(i['amount_ticker_2']/i['amount_ticker_1'], 10),
                    i['ticker_2_name']: truncate(i['amount_ticker_1']/i['amount_ticker_2'], 10),
                },
                "liquidity": {
                    i['ticker_1_name']: truncate(i['amount_ticker_1'], 8),
                    i['ticker_2_name']: truncate(i['amount_ticker_2'], 8),
                }
            }

    if len(get_pools) > 0:
        return {
            "success": True,
            "result": {
                "markets": list_markets,
                "enable_coins": get_coins_pairs['coins'],
                "enable_pairs": get_coins_pairs['pairs'],
                "active_pools": [i['pairs'] for i in get_pools],
            },
            "time": int(time.time())
        }

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        headers=[("server", config['cexswap_api']['api_name'])],
        port=config['cexswap_api']['api_port']
    )
