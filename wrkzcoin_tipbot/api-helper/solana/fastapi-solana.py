from fastapi import FastAPI
from typing import List
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
from spl.token.async_client import AsyncToken
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
        txn = Transaction().add(
            transfer(TransferParams(from_pubkey=sender.pubkey(), to_pubkey=Pubkey.from_string(to_address), lamports=atomic_amount))
        )
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

async def post_get_account_token(
    url: str, token_address: str, address: str, program_id: str, timeout: int=60
):
    try:
        async with AsyncClient(url, timeout=timeout) as client:            
            spl_client = AsyncToken(
                conn=client,
                pubkey=Pubkey.from_string(token_address),
                program_id=Pubkey.from_string(program_id),
                payer=None
            )
            token_account = await spl_client.get_account_info(
                account=Pubkey.from_string(address), commitment=None)
            return {
                "owner": str(token_account.owner),
                "balance": token_account.amount,
                "is_frozen": token_account.is_frozen
            }
    except (ValueError, AttributeError):
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def post_verify_account_token(
    url: str, token_address: str, address: str, program_id: str, timeout: int=60
):
    try:
        async with AsyncClient(url, timeout=timeout) as client:            
            spl_client = AsyncToken(
                conn=client,
                pubkey=Pubkey.from_string(token_address),
                program_id=Pubkey.from_string(program_id),
                payer=None
            )
            token_wallet_address_public_key = await spl_client.get_accounts_by_owner(
                owner=Pubkey.from_string(address), commitment=None, encoding='base64')
            if len(token_wallet_address_public_key.value) > 0:
                return token_wallet_address_public_key.value
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        return None
    return []

async def post_create_account_token(
    url: str, token_address: str, owner_address: str, program_id: str, from_key: str, timeout: int=60
):
    try:
        async with AsyncClient(url, timeout=timeout) as client:            
            spl_client = AsyncToken(
                conn=client,
                pubkey=Pubkey.from_string(token_address),
                program_id=Pubkey.from_string(program_id),
                payer=Keypair.from_bytes(bytes.fromhex(from_key))
            )
            token_wallet_address_public_key = await spl_client.create_associated_token_account(
                owner=Pubkey.from_string(owner_address), skip_confirmation=False, recent_blockhash=None)
            return token_wallet_address_public_key
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def post_transfer_token(
    url: str, token_address: str, owner_key: str,
    program_id: str, dest: str, atomic_amount: int, fee_payer_key: str,
    timeout: int=60
):
    try:
        async with AsyncClient(url, timeout=timeout) as client:            
            spl_client = AsyncToken(
                conn=client,
                pubkey=Pubkey.from_string(token_address),
                program_id=Pubkey.from_string(program_id),
                payer=Keypair.from_bytes(bytes.fromhex(fee_payer_key))
            )
            # check token account owner
            token_wallet_address_public_key = await spl_client.get_accounts_by_owner(
                owner=Keypair.from_bytes(bytes.fromhex(owner_key)).pubkey(), commitment=None, encoding='base64')
            if len(token_wallet_address_public_key.value) > 0:
                addr_sender = token_wallet_address_public_key.value[0].pubkey
                print("Owner {} has token address: {}".format(
                    Keypair.from_bytes(bytes.fromhex(owner_key)).pubkey(),
                    addr_sender
                ))
            else:
                error = "Owner {} has no token address!".format(Keypair.from_bytes(bytes.fromhex(owner_key)).pubkey())
                print(error)
                addr_sender = None
                return {"error": error}

            # check token account receiver
            # Check if given address is an account, 
            token_wallet_address_public_key = await spl_client.get_accounts_by_owner(
                owner=Pubkey.from_string(dest), commitment=None, encoding='base64')
            token_addr_owner = dest
            if len(token_wallet_address_public_key.value) > 0:
                addr_receiver = token_wallet_address_public_key.value[0].pubkey
                error = "Receiver {} has token address: {}".format(dest, addr_receiver)
            else:
                # If destination has no account token, there will be SOL fee to cover. Currently, 0.0021 SOL
                # Check if give address is a token address
                check_token = await post_get_account_token(
                    url,
                    token_address,
                    dest,
                    program_id,
                    timeout=timeout
                )
                if check_token is not None:
                    addr_receiver = Pubkey.from_string(dest)
                    token_addr_owner = check_token['owner']
                else:
                    error = "Receiver {} has no token address!".format(dest)
                    print(error)
                    addr_receiver = None
                    return {"error": error}

            if addr_sender and addr_receiver:
                print("{} Token {}/{} trying to send to {}, lamports={}".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    token_address, program_id,
                    dest,
                    atomic_amount
                ))
                blockhash = await client.get_latest_blockhash()
                txn = await spl_client.transfer(
                    source=addr_sender,
                    dest=addr_receiver,
                    owner=Keypair.from_bytes(bytes.fromhex(owner_key)).pubkey(),
                    amount=atomic_amount,
                    multi_signers=[Keypair.from_bytes(bytes.fromhex(owner_key)), Keypair.from_bytes(bytes.fromhex(fee_payer_key))],
                    recent_blockhash=blockhash.value.blockhash
                )
                print("{} Token {}/{} trying to send to {}, lamports={}. Hash: {}".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    token_address, program_id,
                    dest,
                    atomic_amount,
                    str(txn.value)
                ))
                return {"error": None, "hash": str(txn.value), "owner": token_addr_owner}
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

class VerifyTokenAcc(BaseModel):
    endpoint: str
    token_address: str
    address: str
    program_id: str

class CreateTokenAcc(BaseModel):
    endpoint: str
    token_address: str
    owner_address: str
    program_id: str
    from_key: str
    
class SendTokenAcc(BaseModel):
    endpoint: str
    token_address: str
    owner_key: str
    program_id: str
    dest: str
    atomic_amount: int
    fee_payer_key: str

app = FastAPI(
    title="TipBotv2 FastAPI Solana",
    version="0.1",
    docs_url="/dokument"
)
app.config = config
app.pending_cache_balance = TTLCache(maxsize=20000, ttl=60.0)


@app.post("/send_token")
async def send_token_account(
    item: SendTokenAcc
):    
    try:
        sending = await post_transfer_token(
            item.endpoint,
            item.token_address,
            item.owner_key,
            item.program_id,
            item.dest,
            item.atomic_amount,
            item.fee_payer_key,
            timeout=60
        )
        if sending is None:
            return {
                "error": "Internal error when transfering token {}.".format(item.token_address),
                "timestamp": int(time.time())
            }
        else:
            if sending.get("error"):
                return {
                    "success": False,
                    "error": sending['error'],
                    "timestamp": int(time.time())
                }
            else:
                return {
                    "success": True,
                    "result": sending['hash'],
                    "dump": sending,
                    "timestamp": int(time.time())
                }
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Account failed to create!",
        "timestamp": int(time.time())
    }

@app.post("/create_token_account")
async def create_token_account(
    item: CreateTokenAcc
):    
    try:
        addr = await post_create_account_token(
            item.endpoint,
            item.token_address,
            item.owner_address,
            item.program_id,
            item.from_key,
            timeout=60
        )
        if addr is None:
            return {
                "error": "Internal error when creating Account address for {}.".format(item.owner_address),
                "timestamp": int(time.time())
            }
        else:
            return {
                "success": True,
                "result": str(addr),
                "timestamp": int(time.time())
            }
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Account failed to create!",
        "timestamp": int(time.time())
    }

@app.post("/token_account_info")
async def get_token_account_info(
    item: VerifyTokenAcc
):    
    try:
        # Try token info
        check_token = await post_get_account_token(
            item.endpoint,
            item.token_address,
            item.address,
            item.program_id,
            timeout=60
        )
        if check_token is not None:
            return {
                "success": True,
                "token_account": [item.address],
                "owner": check_token['owner'],
                "result": check_token,
                "timestamp": int(time.time())
            }
        else:
            # Try with verify
            check_account = await post_verify_account_token(
                item.endpoint,
                item.token_address,
                item.address,
                item.program_id,
                timeout=60
            )
            if check_account is None:
                return {
                    "error": "Internal error when checking Account address for {}.".format(item.address),
                    "timestamp": int(time.time())
                }
            elif len(check_account) > 0:
                return {
                    "success": True,
                    "token_account": [str(i.pubkey) for i in check_account],
                    "owner": item.address,
                    "timestamp": int(time.time())
                }
            else:
                return {
                    "error": "There's no Account address with {}.".format(item.address),
                    "timestamp": int(time.time())
                }
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Account not found!",
        "timestamp": int(time.time())
    }

@app.post("/verify_token_account")
async def verify_token_account(
    item: VerifyTokenAcc
):    
    try:
        # .value[0].pubkey
        check = await post_verify_account_token(
            item.endpoint,
            item.token_address,
            item.address,
            item.program_id,
            timeout=60
        )
        if check is None:
            return {
                "error": "Internal error when checking Account address for {}.".format(item.address),
                "timestamp": int(time.time())
            }
        elif len(check) > 0:
            return {
                "success": True,
                "result": [str(i.pubkey) for i in check],
                "timestamp": int(time.time())
            }
        else:
            return {
                "error": "There's no Account address with {}.".format(item.address),
                "timestamp": int(time.time())
            }
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": "Account not found!",
        "timestamp": int(time.time())
    }

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
            sending = await send_solana(item.endpoint, item.from_key, item.to_addr, item.atomic_amount, 60)
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