from fastapi import FastAPI
from typing import Any, List, Union, Dict
from pydantic import BaseModel
import uvicorn
import os, sys, traceback
import datetime, time
import aiohttp
import argparse
import json
from decimal import Decimal
import math
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import base64

from stellar_sdk.exceptions import Ed25519PublicKeyInvalidError
from stellar_sdk import (
    Account,
    AiohttpClient,
    Asset,
    Keypair,
    Network,
    ServerAsync,
    TransactionBuilder,
    parse_transaction_envelope_from_xdr
)

from cachetools import TTLCache

from config import load_config

config = load_config()
parser = argparse.ArgumentParser()
bind_port = config['api_helper']['port_stellar']

try:
    parser.add_argument('--port', dest='port', type=int, help='Set port (Ex. 7001)')
    args = parser.parse_args()
    if args and args.port and type(args.port) == int and 1024 < args.port < 60000:
        bind_port = int(args.port)
except Exception as e:
    traceback.print_exc(file=sys.stdout)

def truncate(number, digits) -> float:
    stepper = Decimal(pow(10.0, digits))
    return math.trunc(stepper * Decimal(number)) / stepper

def check_stellar_address(address):
    try:
        Account(account=address, sequence=0)
        return True
    except (Ed25519PublicKeyInvalidError, ValueError):
        return False

async def get_xlm_transactions(endpoint: str, account_addr: str):
    async with ServerAsync(
        horizon_url=endpoint, client=AiohttpClient()
    ) as server:
        # get a list of transactions submitted by a particular account
        transactions = await server.transactions().for_account(account_addr).order(
            desc=True).limit(50).call()
        if len(transactions["_embedded"]["records"]) > 0:
            return transactions["_embedded"]["records"]
        return []

async def check_xlm_asset(
    url: str, asset_name: str, issuer: str, to_address: str
):
    found = False
    try:
        async with ServerAsync(
            horizon_url=url, client=AiohttpClient()
        ) as server:
            account = await server.accounts().account_id(to_address).call()
            if 'balances' in account and len(account['balances']) > 0:
                for each_balance in account['balances']:
                    if 'asset_code' in each_balance and 'asset_issuer' in each_balance and \
                        each_balance['asset_code'] == asset_name and issuer == each_balance['asset_issuer']:
                        found = True
                        break
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return found

async def send_token(
    url: str, withdraw_keypair: str, amount: float, to_address: str,
    coin: str, asset_ticker: str = None, asset_issuer: str = None, memo=None,
    base_fee: int=50000
):
    coin_name = coin.upper()
    asset_sending = Asset.native()
    if coin_name != "XLM":
        asset_sending = Asset(asset_ticker, asset_issuer)
    kp = Keypair.from_secret(withdraw_keypair)
    async with ServerAsync(
        horizon_url=url, client=AiohttpClient()
    ) as server:
        try:
            src_account = await server.load_account(kp.public_key)
            print("{} {} trying to send from {} to {}, amount={}".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), coin_name, src_account, to_address, amount

            ))
            if memo is not None:
                transaction = (
                    TransactionBuilder(
                        source_account=src_account,
                        network_passphrase=Network.PUBLIC_NETWORK_PASSPHRASE,
                        base_fee=base_fee,
                    )
                    .add_text_memo(memo)
                    .append_payment_op(to_address, asset_sending, str(truncate(amount, 6)))
                    .set_timeout(30)
                    .build()
                )
            else:
                transaction = (
                    TransactionBuilder(
                        source_account=src_account,
                        network_passphrase=Network.PUBLIC_NETWORK_PASSPHRASE,
                        base_fee=base_fee,
                    )
                    .append_payment_op(to_address, asset_sending, str(truncate(amount, 6)))
                    .set_timeout(30)
                    .build()
                )
            transaction.sign(kp)
            response = await server.submit_transaction(transaction)
            print("{} {} successfully sent from {} to {}, amount={}. {}".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), coin_name, src_account, to_address, amount,
                response['hash']
            ))
            return {"hash": response['hash'], "fee": float(response['fee_charged']) / 10000000}
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

app = FastAPI(
    title="TipBotv2 FastAPI Solana",
    version="0.1",
    docs_url="/dokument"
)
app.config = config
app.pending_cache_balance = TTLCache(maxsize=20000, ttl=60.0)

class Address(BaseModel):
    addr: str

class AddressData(BaseModel):
    endpoint: str
    address: str

class EndpointData(BaseModel):
    endpoint: str
    timeout: int=30

class ParseTxData(BaseModel):
    envelope_xdr: Any
    coin_name_list: List
    coin_list: Dict
    main_address: str

class SendToken(BaseModel):
    endpoint: str
    kp: str
    amount: float
    to_address: str
    coin_name: str
    asset_ticker: Union[str, None] = None
    asset_issuer: Union[str, None] = None
    memo: Union[str, None] = None
    base_fee: int=50000

class VerifyAsset(BaseModel):
    endpoint: str
    asset_name: str
    issuer: str
    address: str

class BalanceXLMData(BaseModel):
    endpoint: str
    address: str
    coin_name: str

@app.post("/verify_asset")
async def verify_asset(
    item: VerifyAsset
):
    try:
        checking = await check_xlm_asset(
            item.endpoint, item.asset_name, item.issuer, item.address
        )
        return {
            "result": checking,
            "timestamp": int(time.time())
        }
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Error!",
        "timestamp": int(time.time())
    }

@app.post("/send_transaction")
async def send_transaction(
    item: SendToken
):
    try:
        sending = await send_token(
            item.endpoint, item.kp, item.amount, item.to_address,
            item.coin_name, item.asset_ticker, item.asset_issuer, item.memo,
            item.base_fee
        )
        if sending:
            return {
                "result": sending,
                "timestamp": int(time.time())
            }
        else:
            return {
                "error": "Failed to send tx to {}".format(item.to_address),
                "timestamp": int(time.time())
            }
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Error!",
        "timestamp": int(time.time())
    }

@app.post("/validate_address")
async def validate_address(item: Address):
    try:
        valid = check_stellar_address(item.addr)
        return {
            "address": item.addr,
            "success": True,
            "valid": valid,
            "timestamp": int(time.time())
        }
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return {
        "address": item.addr,
        "error": "Internal error!",
        "timestamp": int(time.time())
    }

@app.get("/create_address")
async def create_address():
    kp = Keypair.random()

    public_key = kp.public_key
    secret_seed = kp.secret

    print("{} create a new address: {}".format(
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        public_key
    ))
    return {
        "success": True,
        "address": public_key,
        "secret_key_hex": secret_seed,
        "timestamp": int(time.time())
    }

@app.post("/get_balance_xlm")
async def get_balance_xlm(
    item: BalanceXLMData
):
    balance = 0.0
    try:
        async with ServerAsync(
            horizon_url=item.endpoint, client=AiohttpClient()
        ) as server:
            account = await server.accounts().account_id(item.address).call()
            if 'balances' in account and len(account['balances']) > 0:
                for each_balance in account['balances']:
                    if item.coin_name == "XLM" and each_balance['asset_type'] == "native":
                        balance = float(each_balance['balance'])
                        break
                    elif 'asset_code' in each_balance and 'asset_issuer' in each_balance and \
                        each_balance['asset_code'] == asset_code and issuer == each_balance['asset_issuer']:
                        balance = float(each_balance['balance'])
                        break
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {
        "balance": balance,
        "timestamp": int(time.time())
    }

@app.post("/get_transactions")
async def get_transactions(
    item: AddressData
):    
    try:
        list_tx = await get_xlm_transactions(item.endpoint, item.address)
        return {
            "result": list_tx,
            "timestamp": int(time.time())
        }
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Error!",
        "timestamp": int(time.time())
    }

@app.post("/get_status")
async def get_status(
    item: EndpointData
):
    try:
        headers = {
            'Content-Type': 'application/json'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                item.endpoint,
                headers=headers,
                timeout=item.timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    return json.loads(res_data)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Error!",
        "timestamp": int(time.time())
    }

@app.post("/parse_transaction")
async def parse_transaction(
    item: ParseTxData
):
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                parse_transaction_envelope_from_xdr,
                item.envelope_xdr,
                Network.PUBLIC_NETWORK_PASSPHRASE
            )
            transaction_envelope = future.result()
            if hasattr(transaction_envelope, "transaction"):
                coin_name = None
                for Payment in transaction_envelope.transaction.operations:
                    try:
                        destination = Payment.destination.account_id
                        asset_type = Payment.asset.type
                        asset_code = Payment.asset.code
                        asset_issuer = None
                        if asset_type == "native":
                            coin_name = "XLM"
                        else:
                            if hasattr(Payment.asset, "code") and hasattr(Payment.asset, "issuer"):
                                asset_issuer = Payment.asset.issuer
                                for each_coin in item.coin_name_list:
                                    if item.coin_list.get(each_coin):
                                       asset_code = item.coin_list[each_coin]['header']
                                    if asset_code == item.coin_list[each_coin]['header'] \
                                        and asset_issuer == item.coin_list[each_coin]['contract']:
                                        coin_name = item.coin_list[each_coin]['coin_name']
                                        break
                        if item.coin_list.get(coin_name) is None:
                            continue
                        amount = float(Payment.amount)
                        if destination != item.main_address:
                            continue
                        # if asset_type not in ["native", "credit_alphanum4", "credit_alphanum12"]:
                        # Check all atrribute
                        all_xlm_coins = []
                        if item.coin_name_list and len(item.coin_name_list) > 0:
                            for each_coin in item.coin_name_list:
                                ticker = item.coin_list[each_coin]['header']
                                if item.coin_list[each_coin]['enable'] == 1:
                                    all_xlm_coins.append(ticker)
                        if asset_code not in all_xlm_coins:
                            continue
                    except:
                        continue
                if coin_name:
                    result = {
                        "coin_name": coin_name,
                        "fee": float(transaction_envelope.transaction.fee) / 10000000,  # atomic,
                        "amount": amount
                    }
                    return {
                        "result": result,
                        "timestamp": int(time.time())
                    }
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Error!",
        "timestamp": int(time.time())
    }

if __name__ == "__main__":
    print("{} running with IP: {} and port {}".format(
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        config['api_helper']['bind_ip'],
        bind_port
    ))
    uvicorn.run(
        app,
        host=config['api_helper']['bind_ip'],
        headers=[("server", "TipBot v2")],
        port=bind_port,
        access_log=False
    )