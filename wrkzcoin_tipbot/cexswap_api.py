from fastapi import FastAPI, Response, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

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
cexswap_find_possible_trade, cexswap_estimate

from Bot import truncate, text_to_num
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

@app.post("/estimate_sell/")
async def estimate_amount_token_sell(
    request: Request, item: SellToken
):
    if config['cexswap_api']['api_enable'] != 1:
        return {
            "success": False,
            "data": None,
            "error": "API is currently disable!",
            "time": int(time.time())
        }

    if config['cexswap_api']['is_estimation_pub'] != 1:
        return {
            "success": False,
            "data": None,
            "error": "Estimation is not public yet!",
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
                        got_fee_dev, got_fee_liquidators, 0.0, price_impact_percent
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
