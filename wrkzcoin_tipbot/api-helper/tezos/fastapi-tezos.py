from fastapi import FastAPI
from typing import Any, List, Union, Dict
from pydantic import BaseModel
import uvicorn
import os, sys, traceback
import datetime, time
import aiohttp, asyncio
import argparse
import json
from decimal import Decimal
import math
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from mnemonic import Mnemonic
from pytezos.crypto.key import Key
from pytezos.crypto.encoding import is_address
from pytezos import pytezos

from cachetools import TTLCache

from config import load_config

config = load_config()
parser = argparse.ArgumentParser()
bind_port = config['api_helper']['port_tezos']

try:
    parser.add_argument('--port', dest='port', type=int, help='Set port (Ex. 7001)')
    args = parser.parse_args()
    if args and args.port and type(args.port) == int and 1024 < args.port < 60000:
        bind_port = int(args.port)
except Exception as e:
    traceback.print_exc(file=sys.stdout)

app = FastAPI(
    title="TipBotv2 FastAPI Tezos",
    version="0.1",
    docs_url="/dokument"
)
app.config = config
app.pending_cache_balance = TTLCache(maxsize=20000, ttl=5.0)

class Address(BaseModel):
    addr: str

class BalanceTzData(BaseModel):
    endpoint: str
    key: str

class BalanceTzToken(BaseModel):
    endpoint: str
    token_contract: str
    token_id: int
    address: List
    timeout: int=60

class BalanceTzTokenData(BaseModel):
    endpoint: str
    address: str
    timeout: int=60

class VerifyAsset(BaseModel):
    endpoint: str
    asset_name: str
    issuer: str
    address: str

class RevealAddress(BaseModel):
    endpoint: str
    key: str

class CheckRevealAddress(BaseModel):
    endpoint: str
    address: str

class EndpointData(BaseModel):
    endpoint: str
    timeout: int=30

class TxData(BaseModel):
    endpoint: str
    txhash: str
    timeout: int=30

class SendTxData(BaseModel):
    endpoint: str
    key: str
    to_address: str
    atomic_amount: int

class SendTxDataToken(BaseModel):
    endpoint: str
    key: str
    to_address: str
    atomic_amount: int
    contract: Any
    token_id: Any

@app.post("/validate_address")
async def validate_address(item: Address):
    try:
        valid = is_address(item.addr)
        return {
            "address": item.addr,
            "success": True,
            "valid": valid,
            "timestamp": int(time.time())
        }
    except AttributeError:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return {
        "address": item.addr,
        "success": True,
        "valid": False,
        "timestamp": int(time.time())
    }

@app.post("/check_reveal_address")
async def check_reveal_address(item: CheckRevealAddress):
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(item.endpoint + "accounts/" + item.address, headers=headers, timeout=30) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    if json_resp['type'] == "user" and 'revealed' in json_resp and json_resp['revealed'] is True:
                        return {
                            "result": True,
                            "timestamp": int(time.time())
                        }
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {
        "result": False,
        "timestamp": int(time.time())
    }

@app.post("/reveal_address")
async def reveal_address(item: RevealAddress):
    try:
        user_address = pytezos.using(shell=item.endpoint, key=item.key)
        tx = user_address.reveal().autofill().sign().inject()
        print("XTZ revealed new tx {}".format(tx))
        return {
            "success": True,
            "hash": tx,
            "timestamp": int(time.time())
        }
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Reveal address failed!",
        "timestamp": int(time.time())
    }

@app.post("/get_head")
async def get_head(item: EndpointData):
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(item.endpoint + "head/", headers=headers, timeout=item.timeout) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    if 'synced' in json_resp and json_resp['synced'] is True:
                        return {
                            "success": True,
                            "result": json_resp,
                            "timestamp": int(time.time())
                        }
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Get head failed!",
        "timestamp": int(time.time())
    }

@app.post("/get_tx")
async def get_tx(item: TxData):
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                item.endpoint + "operations/transactions/" + item.txhash,
                headers=headers,
                timeout=item.timeout
            ) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    if len(json_resp) == 1 and "status" in json_resp[0] and "level" in json_resp[0]:
                        return {
                            "success": True,
                            "result": json_resp[0],
                            "timestamp": int(time.time())
                        }
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Get tx {} failed!".format(item.txhash),
        "timestamp": int(time.time())
    }

@app.post("/send_tezos")
async def send_tezos(item: SendTxData):
    try:
        user_address = pytezos.using(shell=item.endpoint, key=item.key)
        tx = user_address.transaction(
            source=user_address.key.public_key_hash(),
            destination=item.to_address,
            amount=item.atomic_amount).send()
        return {
            "success": True,
            "hash": tx.hash(),
            "contents": json.dumps(tx.contents),
            "timestamp": int(time.time())
        }
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Send tezos failed!",
        "timestamp": int(time.time())
    }

@app.post("/send_tezos_token_fa2")
async def send_tezos_token(item: SendTxDataToken):
    try:
        token = pytezos.using(shell=item.endpoint, key=item.key).contract(item.contract)
        acc = pytezos.using(shell=item.endpoint, key=item.key)
        tx_token = token.transfer(
            [dict(from_ = acc.key.public_key_hash(), txs = [ dict(to_ = item.to_address, amount = item.atomic_amount, token_id = int(item.token_id))])]
        ).send()
        return {
            "success": True,
            "hash": tx_token.hash(),
            "contents": json.dumps(tx_token.contents),
            "timestamp": int(time.time())
        }
    except Exception:
        traceback.print_exc(file=sys.stdout)
        print("[XTZ 2.0] failed to transfer url: {}, contract {} moving {} to {}".format(
            item.endpoint, item.contract, acc.key.public_key_hash(), item.to_address)
        )
    return {
        "error": "Send tezos failed!",
        "timestamp": int(time.time())
    }

@app.post("/send_tezos_token_fa12")
async def send_tezos_token_fa12(item: SendTxDataToken):
    try:
        token = pytezos.using(shell=item.endpoint, key=item.key).contract(item.contract)
        acc = pytezos.using(shell=item.endpoint, key=item.key)
        tx_token = token.transfer(**{'from': acc.key.public_key_hash(), 'to': item.to_address, 'value': item.atomic_amount}).inject()
        return {
            "success": True,
            "hash": tx_token['hash'],
            "contents": json.dumps(tx_token['contents']),
            "timestamp": int(time.time())
        }
    except Exception:
        traceback.print_exc(file=sys.stdout)
        print("[XTZ 1.2] failed to transfer url: {}, contract {} moving {} to {}".format(
            item.endpoint, item.contract, acc.key.public_key_hash(), item.to_address)
        )
    return {
        "error": "Send tezos failed!",
        "timestamp": int(time.time())
    }

@app.post("/get_address_token_balances")
async def get_address_token_balances(
    item: BalanceTzToken
):
    try:
        token = pytezos.using(shell=item.endpoint).contract(item.token_contract)
        addresses = []
        for each_address in item.address:
            addresses.append({'owner': each_address, 'token_id': item.token_id})
        token_balance = token.balance_of(requests=addresses, callback=None).view()
        if token_balance:
            result_balance = {}
            for each in token_balance:
                result_balance[each['request']['owner']] = int(each['balance'])
            return {
                "success": True,
                "result": result_balance, # dict of address => balance in float
                "timestamp": int(time.time())
            }
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {}

@app.post("/get_balances_token_tezos")
async def get_balance_token_tezos(
    item: BalanceTzTokenData
):
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                item.endpoint + "tokens/balances?account=" + item.address,
                headers=headers,
                timeout=item.timeout
            ) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    return {
                        "success": True,
                        "result": json_resp,
                        "timestamp": int(time.time())
                    }
                else:
                    print("tezos_check_token_balances: return {}".format(response.status))
    except asyncio.exceptions.TimeoutError:
        print("Tezos check balances timeout for url: {} / addr: {}. Time: {}".format(item.endpoint, item.address, item.timeout))
    except aiohttp.client_exceptions.ContentTypeError:
        print("Tezos Content type error: ", response)
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Error trying to get balance from endpoint for token address {}.".format(item.address),
        "timestamp": int(time.time())
    }

@app.post("/get_balance_tezos")
async def get_balance_tezos(
    item: BalanceTzData
):
    if app.pending_cache_balance.get(item.key):
        return app.pending_cache_balance[item.key]
    try:
        client = pytezos.using(shell=item.endpoint, key=item.key)
        if client is None:
            return {
                "error": "Error trying to get balance from endpoint.",
                "timestamp": int(time.time())
            }
        else:
            result = {
                "success": True,
                "result": {
                    "balance": float(client.balance())
                },
                "timestamp": int(time.time())
            }
            app.pending_cache_balance[item.key] = result
            return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

@app.get("/create_address")
async def create_address():
    mnemo = Mnemonic("english")
    words = str(mnemo.generate(strength=128))
    key = Key.from_mnemonic(mnemonic=words, passphrase="", email="")
    print("{} create a new address: {}".format(
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        key.public_key_hash()
    ))
    return {
        "success": True,
        "address": key.public_key_hash(),
        "seed": words,
        "secret_key_hex": key.secret_key(),
        "dump": {'address': key.public_key_hash(), 'seed': words, 'key': key.secret_key()},
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