from fastapi import FastAPI, Response, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
import sys, traceback
import uvicorn
import asyncio, aiohttp
import os, signal, subprocess
import time, datetime

sys.path.append("../")
import store
from config import load_config

app = FastAPI()
config = load_config()

@app.on_event("shutdown")
async def shutdown_event():
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                INSERT INTO `vaults_process_spawn_archive` SELECT * FROM `vaults_process_spawn`;
                DELETE FROM `vaults_process_spawn`;
                """
                await cur.execute(sql,)
                await conn.commit()
    except Exception:
        traceback.print_exc(file=sys.stdout)

class BackgroundRunner:
    def __init__(self, app):
        self.app = app
        self.config = load_config()

    async def add_process_db(
        self, coin_name: str, pid: int, started_time: int,
        exec: str, port: int, rpc_address: str, ringdb: str, walletdir: str
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `vaults_process_spawn`
                    (`coin_name`, `pid`, `started_time`, `exec`, `rpc_address`, `port`, `ringdb_dir`, `wallet_dir`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (
                        coin_name, pid, started_time, exec,
                        rpc_address, port, ringdb, walletdir
                    ))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def wallet_xmr_tasks(
        self
    ):
        for i in ["xmr", "wow"]:
            for c in range(0, self.config['vault'][i+'_max_proc']):
                # spawn process
                try:
                    ringdb = " --shared-ringdb-dir "+ self.config['vault'][i+'_ringdb_dir']
                    if i == "wow":
                        ringdb = " --wow-shared-ringdb-dir "+ self.config['vault'][i+'_ringdb_dir']
                    walletdir = self.config['vault'][i+'_wallet_dir']
                    logfile = self.config['vault'][i+'_log_dir'] + datetime.datetime.now().strftime("%Y-%m-%d") + "_"+ str(self.config['vault'][i+'_wallet_port_range']+c) + ".log"
                    rpc_address = "http://{}:{}".format(self.config['vault'][i+'_bind_ip'], self.config['vault'][i+'_wallet_port_range']+c)
                    exec_params = self.config['vault'][i+'_wallet_rpc'] + " --daemon-address " + self.config['vault'][i+'_daemon_addr'] + \
                        " --rpc-bind-ip " + self.config['vault'][i+'_bind_ip'] + \
                        " --rpc-bind-port " + str(self.config['vault'][i+'_wallet_port_range']+c) + \
                        " --wallet-dir " + walletdir + \
                        " --disable-rpc-login --log-level=1 " + ringdb + " --trusted-daemon --confirm-external-bind" + \
                        " --log-file="+ logfile
                    exec_params_list = exec_params.split()
                    p = subprocess.Popen(
                        exec_params_list
                    ) # Call subprocess
                    print("Spawn {} process id {}".format(i, p.pid))
                    # insert to db
                    await self.add_process_db(
                        i.upper(), p.pid, int(time.time()), exec_params,
                        self.config['vault'][i+'_wallet_port_range']+c, rpc_address,
                        ringdb, walletdir
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)

runner = BackgroundRunner(app)

class CreateWallet(BaseModel):
    filename: str
    password: str

@app.post("/create_wallet/{coin_name}")
async def xmr_create_wallet(
    request: Request, coin_name: str, item: CreateWallet
):
    try:
        coin_name = coin_name.upper()
        filename = item.filename.strip()
        password = item.password.strip()

    except Exception:
        traceback.print_exc(file=sys.stdout)
    
@app.on_event('startup')
async def app_startup():
    asyncio.create_task(runner.wallet_xmr_tasks())

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", headers=[("server", "fastapi_wallet_helper")], port=config['vault']['helper_fastapi_port'])
