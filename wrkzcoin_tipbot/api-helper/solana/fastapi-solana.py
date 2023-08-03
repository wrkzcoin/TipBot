from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import os, sys, traceback
import datetime, time
import argparse

from solders.keypair import Keypair
from solders.system_program import TransferParams, transfer
from solana.transaction import Transaction
from solders.pubkey import Pubkey
from solders.signature import Signature
from solana.rpc.async_api import AsyncClient
from cachetools import TTLCache

from config import load_config

config = load_config()
parser = argparse.ArgumentParser()
bind_port = config['api_helper']['port_solana']

try:
    parser.add_argument('--port', dest='port', type=int, help='Set port (Ex. 7001)')
    args = parser.parse_args()
    if args and args.port and type(args.port) == int and 1024 < args.port < 60000:
        bind_port = int(args.port)
except Exception as e:
    traceback.print_exc(file=sys.stdout)

async def fetch_wallet_balance(url: str, address: str, timeout: int=60):
    try:
        async with AsyncClient(url, timeout=timeout) as client:
            balance = await client.get_balance(Pubkey.from_string(address))
            if hasattr(balance, 'value') and hasattr(balance, 'context') and hasattr(balance.context, 'slot'):
                await client.close()
                return balance
            else:
                print("{} Error fetch_wallet_balance: {}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), balance))
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def send_solana(url: str, from_key: str, to_address: str, atomic_amount: int, timeout: int=60):
    try:
        sender = Keypair.from_bytes(bytes.fromhex(from_key))
        print("{} SOL trying to send from {} to {}, lamports={}".format(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sender.pubkey(), to_address, atomic_amount

        ))
        txn = Transaction().add(transfer(TransferParams(from_pubkey=sender.pubkey(), to_pubkey=Pubkey.from_string(to_address), lamports=atomic_amount)))
        solana_client = AsyncClient(url, timeout=timeout)
        sending = await solana_client.send_transaction(txn, sender)
        print("{} SOL successfully sent from {} to {}, lamports={}, {}".format(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sender.pubkey(), to_address, atomic_amount, sending.value

        ))
        return sending.value
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def get_sig(url: str, sig: str, timeout: int=60):
    try:
        solana_client = AsyncClient(url, timeout=timeout)
        signature = await solana_client.get_transaction(Signature.from_string(sig))
        return signature
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

def check_address(address: str):
    key = Pubkey.from_string(address) # Valid public key
    return key.is_on_curve() and key.LENGTH == 32

class Address(BaseModel):
    addr: str

class TxData(BaseModel):
    endpoint: str
    from_key: str
    to_addr: str
    atomic_amount: int

class SigData(BaseModel):
    endpoint: str
    sig: str

class BalanceSolData(BaseModel):
    endpoint: str
    address: str

app = FastAPI(
    title="TipBotv2 FastAPI Solana",
    version="0.1",
    docs_url="/dokument"
)
app.config = config
app.pending_cache_balance = TTLCache(maxsize=20000, ttl=60.0)

@app.get("/create_address")
async def create_address():
    kp = Keypair()
    public_key = str(kp.pubkey())
    print("{} create a new address: {}".format(
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        public_key
    ))
    return {
        "success": True,
        "address": public_key,
        "secret_key_hex": kp.secret().hex(),
        "timestamp": int(time.time())
    }

@app.get("/reset_cache/{address}")
async def reset_balance_cache(address: str):
    if app.pending_cache_balance.get(address):
        print("{} X Delete balance cache for {}".format(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), address
        ))
        del app.pending_cache_balance[address]
        return {
            "success": True,
            "timestamp": int(time.time())
        }
    else:
        return {
            "error": "Cache not exist for: {}".format(address),
            "timestamp": int(time.time())
        }

@app.post("/get_balance_solana")
async def get_balance_solana(
    item: BalanceSolData
):
    if app.pending_cache_balance.get(item.address):
        print("{} use balance cache for {}".format(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), item.address
        ))
        return app.pending_cache_balance[item.address]

    balance = await fetch_wallet_balance(item.endpoint, item.address, timeout=60)
    if balance is None:
        return {
            "error": "Error trying to get balance from endpoint with addr: ".format(item.address),
            "timestamp": int(time.time())
        }
    else:
        result = {
            "success": True,
            "result": {
                "balance": balance.value,
                "slot": balance.context.slot
            },
            "timestamp": int(time.time())
        }
        app.pending_cache_balance[item.address] = result
        return result

@app.post("/get_sig")
async def get_signature(
    item: SigData
):
    signature = await get_sig(item.endpoint, item.sig, timeout=60)
    return {
        "success": True,
        "timestamp": int(time.time())
    }

@app.post("/send_transaction")
async def send_transaction(item: TxData):
    try:
        valid = check_address(item.to_addr)
        if valid is False:
            return {
                "error": "Invalid address {}!".format(item.to_addr),
                "timestamp": int(time.time())
            }
        else:
            sending = await send_solana(item.endpoint, item.from_key, item.to_addr, item.atomic_amount)
            return {
                "success": True,
                "hash": str(sending),
                "timestamp": int(time.time())
            }
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Internal error!",
        "timestamp": int(time.time())
    }

@app.post("/validate_address")
async def validate_address(item: Address):
    try:
        valid = check_address(item.addr)
        return {
            "address": item.addr,
            "success": True,
            "valid": valid,
            "timestamp": int(time.time())
        }
    except ValueError:
        return {
            "address": item.addr,
            "success": True,
            "valid": False,
            "timestamp": int(time.time())
        }
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return {
        "address": item.addr,
        "error": "Internal error!",
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