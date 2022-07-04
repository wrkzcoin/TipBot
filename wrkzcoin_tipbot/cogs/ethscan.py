import sys
import traceback

import aiohttp, asyncio
from aiohttp import TCPConnector

import json
from disnake.ext import tasks, commands
import functools
import redis_utils

from config import config
import store
from Bot import get_token_list, logchanbot, hex_to_base58, base58_to_hex


class EthScan(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        redis_utils.openRedis()

        self.blockTime = {}

        self.allow_start_ethscan = False

        # BSC best node
        self.fetch_bsc_node.start()
        # SOL best node
        self.fetch_sol_node.start()
        # TRX best node
        self.fetch_trx_node.start()
        # MATIC best node
        self.fetch_matic_node.start()
        # CELO best node
        self.fetch_celo_node.start()
        # FTM best node
        self.fetch_ftm_node.start()
        # AVAX best node
        self.fetch_avax_node.start()
        # XDAI best node
        self.fetch_xdai_node.start()
        # ONE best node
        self.fetch_one_node.start()

        self.pull_trc20_scanning.start()
        self.pull_erc20_scanning.start()
        self.remove_all_tx_ethscan.start()

    @tasks.loop(seconds=10.0)
    async def fetch_trx_node(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(config.api_best_node.trx, headers={'Content-Type': 'application/json'}, timeout=5.0) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    # trx needs to fetch best node from their public
                    self.bot.erc_node_list['TRX'] = res_data.replace('"', '')
                else:
                    await logchanbot(f"Can not fetch best node for TRX.")
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_bsc_node(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(config.api_best_node.bsc, headers={'Content-Type': 'application/json'}, timeout=5.0) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    # BSC needs to fetch best node from their public
                    self.bot.erc_node_list['BSC'] = res_data.replace('"', '')
                else:
                    await logchanbot(f"Can not fetch best node for BSC.")
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_sol_node(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(config.api_best_node.sol, headers={'Content-Type': 'application/json'}, timeout=5.0) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    # SOL needs to fetch best node from their public
                    self.bot.erc_node_list['SOL'] = res_data.replace('"', '')
                else:
                    await logchanbot(f"Can not fetch best node for SOL.")
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_matic_node(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(config.api_best_node.matic, headers={'Content-Type': 'application/json'}, timeout=5.0) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    # MATIC needs to fetch best node from their public
                    self.bot.erc_node_list['MATIC'] = res_data.replace('"', '')
                else:
                    await logchanbot(f"Can not fetch best node for MATIC.")
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_celo_node(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(config.api_best_node.celo, headers={'Content-Type': 'application/json'}, timeout=5.0) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    # CELO needs to fetch best node from their public
                    self.bot.erc_node_list['CELO'] = res_data.replace('"', '')
                else:
                    await logchanbot(f"Can not fetch best node for CELO.")
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_ftm_node(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(config.api_best_node.ftm, headers={'Content-Type': 'application/json'}, timeout=5.0) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    # FTM needs to fetch best node from their public
                    self.bot.erc_node_list['FTM'] = res_data.replace('"', '')
                else:
                    await logchanbot(f"Can not fetch best node for FTM.")
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_avax_node(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(config.api_best_node.avax, headers={'Content-Type': 'application/json'}, timeout=5.0) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    # AVAX needs to fetch best node from their public
                    self.bot.erc_node_list['AVAX'] = res_data.replace('"', '')
                else:
                    await logchanbot(f"Can not fetch best node for AVAX.")
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_xdai_node(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(config.api_best_node.xdai, headers={'Content-Type': 'application/json'}, timeout=5.0) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    # XDAI needs to fetch best node from their public
                    self.bot.erc_node_list['XDAI'] = res_data.replace('"', '')
                else:
                    await logchanbot(f"Can not fetch best node for XDAI.")
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_one_node(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(config.api_best_node.one, headers={'Content-Type': 'application/json'}, timeout=5.0) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    # ONE needs to fetch best node from their public
                    self.bot.erc_node_list['ONE'] = res_data.replace('"', '')
                else:
                    await logchanbot(f"Can not fetch best node for ONE.")
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=60.0)
    async def remove_all_tx_ethscan(self):
        await asyncio.sleep(5.0)
        try:
            remove_old_tx_erc20 = await store.contract_tx_remove_after("ERC-20", 48*3600) # 48hrs , any type will remove from erc20 table
            remove_old_tx_trc20 = await store.contract_tx_remove_after("TRC-20", 48*3600) # 48hrs
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(5.0)


    # Token contract only, not user's address
    @tasks.loop(seconds=20.0)
    async def pull_trc20_scanning(self):
        await asyncio.sleep(2.0)
        # Get all contracts of ETH type and update to coin_ethscan_setting
        trc_contracts = await self.get_all_contracts("TRC-20")
        if len(trc_contracts) > 0:
            for each_contract in trc_contracts:
                try:
                    await self.fetch_txes_trc(each_contract['coin_name'], each_contract['contract'])
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)


    # Token contract only, not user's address
    @tasks.loop(seconds=20.0)
    async def pull_erc20_scanning(self):
        await asyncio.sleep(2.0)
        # Get all contracts of ETH type and update to coin_ethscan_setting
        erc_contracts = await self.get_all_contracts("ERC-20")
        net_names = await self.get_all_net_names()
        if len(erc_contracts) > 0:
            contracts = {}
            for each_c in erc_contracts:
                if each_c['net_name'] not in contracts:
                    contracts[each_c['net_name']] = []
                    if each_c['contract']:
                        contracts[each_c['net_name']].append(each_c['contract'])
                else:
                    if each_c['contract']:
                        contracts[each_c['net_name']].append(each_c['contract'])
            
            # Update contract list setting
            for k, v in contracts.items():
                try:
                    if k in net_names and net_names[k]['enable'] == 1:
                        await self.update_scan_setting(k, v)
                        await self.fetch_txes(self.bot.erc_node_list[k], k, v, net_names[k]['scanned_from_height'])
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(10.0)


    async def get_all_contracts(self, type_token: str):
        # type_token: ERC-20, TRC-20
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_settings` WHERE `type`=%s AND `contract` IS NOT NULL AND `net_name` IS NOT NULL """
                    await cur.execute(sql, (type_token,))
                    result = await cur.fetchall()
                    if result and len(result) > 0: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []


    async def get_all_net_names(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_ethscan_setting` WHERE `enable`=%s """
                    await cur.execute(sql, (1,))
                    result = await cur.fetchall()
                    net_names = {}
                    if result and len(result) > 0:
                        for each in result:
                            net_names[each['net_name']] = each
                        return net_names
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return {}


    async def update_scan_setting(self, net_name: str, contracts):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `coin_ethscan_setting` SET `contracts`=%s WHERE `net_name`=%s LIMIT 1 """
                    await cur.execute(sql, (",".join(contracts), net_name))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    async def fetch_txes(self, url: str, net_name: str, contracts, scanned_from_height: int, timeout: int=64):
        # contracts: List
        try:
            # get all addresses in DB
            all_addresses_in_db = await store.get_all_coin_token_addresses()

            reddit_blocks = 1000
            limit_notification = 0
            contract = json.dumps(contracts)
            txHash_unique = []
            list_tx = await store.get_txscan_stored_list_erc(net_name)
            if len(list_tx['txHash_unique']) > 0:
                # Get the latest one with timestamp
                txHash_unique += list_tx['txHash_unique']
                txHash_unique = list(set(txHash_unique))
            # Get latest fetching
            height = await store.get_latest_stored_scanning_height_erc(net_name)
            local_height = await store.erc_get_block_number(url)
            try:
                if local_height and local_height > 0:
                    redis_utils.redis_conn.set(f'{config.redis.prefix+config.redis.daemon_height}{net_name}', str(local_height))
                else:
                    return
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())

            # Check height in DB
            height = max([height, scanned_from_height])

            # To height
            to_block = local_height
            to_bloc_str = None
            if local_height and local_height - reddit_blocks > height:
                to_block = height + reddit_blocks
                to_bloc_str = hex(to_block)
            else:
                to_block = local_height
                to_bloc_str = hex(to_block)

            # If to and from just only 1 different. Sleep 15s before call. To minimize the failed call
            if to_block - height < 10:
                # print("{} to_block - height = {} - {} Little gab, skip from {} to next".format(net_name, to_block, height, contract))
                await asyncio.sleep(3.0)
                return

            if limit_notification > 0 and limit_notification % 20 == 0:
                # print("{} Fetching from: {} to {}".format(net_name, height, to_block))
                limit_notification += 1
                await asyncio.sleep(3.0)
            try:
                fromHeight = hex(height)
                if to_block - height > reddit_blocks - 1:
                    # print("{} eth_getLogs {} from: {} to: {}".format(net_name, contract, height, to_block))
                    pass
                data = '{"jsonrpc":"2.0","method":"eth_getLogs","params":[{"fromBlock": "'+fromHeight+'", "toBlock": "'+to_bloc_str+'", "address": '+contract+'}],"id":0}'
                if net_name == "xDai":
                    # xDai need camel case
                    data = '{"jsonrpc":"2.0","method":"eth_getLogs","params":[{"FromBlock": "'+fromHeight+'", "ToBlock": "'+to_bloc_str+'", "Address": '+contract+'}],"id":0}'
                try:
                    async with aiohttp.ClientSession(connector=TCPConnector(ssl=False)) as session:
                        async with session.post(url, headers={'Content-Type': 'application/json'}, json=json.loads(data), timeout=timeout) as response:
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                if decoded_data and 'error' in decoded_data:
                                    return []
                                elif decoded_data and 'result' in decoded_data:
                                    records = decoded_data['result']
                                    if len(records) > 0:
                                        # print("{} Got {} record(s).".format(net_name, len(records))) # For later debug
                                        pass
                                    if len(records) > 0:
                                        rows = []
                                        for each in records:
                                            if each['topics'] and len(each['topics']) >= 3:
                                                from_addr = each['topics'][1]
                                                to_addr = each['topics'][2]
                                                to_addr_tmp = "0x" + each['topics'][2][26:]
                                                if to_addr_tmp not in all_addresses_in_db:
                                                    continue

                                                blockTime = 0
                                                if str(int(each['blockNumber'], 16)) in self.blockTime:
                                                    blockTime = self.blockTime[str(int(each['blockNumber'], 16))]
                                                else:
                                                    try:
                                                        get_blockinfo = await store.erc_get_block_info(url, int(each['blockNumber'], 16))
                                                        if get_blockinfo:
                                                            blockTime = int(get_blockinfo['timestamp'], 16)
                                                            self.blockTime[str(int(each['blockNumber'], 16))] = blockTime
                                                    except Exception as e:
                                                        traceback.print_exc(file=sys.stdout)
                                                key = "{}_{}_{}_{}".format(each['address'], int(each['blockNumber'], 16), each['transactionHash'], from_addr, to_addr)
                                                def lower_txes(txHash_unique):
                                                    return [x.lower() for x in txHash_unique]
                                                
                                                uniq_txes = functools.partial(lower_txes, txHash_unique)
                                                txHash_unique = await self.bot.loop.run_in_executor(None, uniq_txes)

                                                if key.lower() not in txHash_unique:
                                                    txHash_unique.append(key)
                                                    try:
                                                        rows.append((net_name, each['address'], json.dumps(each['topics']), from_addr, to_addr, int(each['blockNumber'], 16), blockTime,  each['transactionHash'], key))
                                                    except Exception as e:
                                                        traceback.print_exc(file=sys.stdout)
                                                    # print("{} Append row {}".format(net_name, len(rows)))
                                        # print("{} Got {} row(s)".format(net_name, len(rows)))
                                        if len(rows) > 0:
                                            # insert data
                                            #print(rows[-1])
                                            insert_data = await store.get_monit_contract_tx_insert_erc(rows)
                                            # if insert_data == 0:
                                                # print(f"Failed to insert minting to `erc_contract_scan` for net_name {net_name}")
                                            # else:
                                                # print(f"Insert {insert_data} minting to `erc_contract_scan` for net_name {net_name}")
                                            update_height = await store.get_monit_scanning_net_name_update_height(net_name, to_block)
                                            if update_height is None:
                                                print(f"to_block {str(to_block)} No tx for `erc_contract_scan` for net_name {net_name}")
                                        elif len(rows) == 0:
                                            # Update height to DB
                                            update_height = await store.get_monit_scanning_net_name_update_height(net_name, to_block)
                                            if update_height is None:
                                                print(f"to_block {str(to_block)} No tx for `erc_contract_scan` for net_name {net_name}")
                                        ##return records
                                    elif len(records) == 0:
                                        # Update height to DB
                                        update_height = await store.get_monit_scanning_net_name_update_height(net_name, to_block)
                                        if update_height is None:
                                            print(f"to_block {str(to_block)} No tx for `erc_contract_scan` for net_name {net_name}")
                            elif response.status == 400:
                                await asyncio.sleep(3.0)
                                return
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    async def fetch_txes_trc(self, coin: str, contract: str, timeout: int=64):
        COIN_NAME = coin.upper()
        net_name = "TRX"
        try:
            # get all addresses in DB
            all_addresses_in_db = await store.get_all_coin_token_addresses()
            
            txHash_unique = []
            list_tx = await store.get_txscan_stored_list_erc(net_name)
            if len(list_tx['txHash_unique']) > 0:
                # Get the latest one with timestamp
                txHash_unique += list_tx['txHash_unique']
                txHash_unique = list(set(txHash_unique))

            # Get latest fetching
            last_timestamp = await store.get_latest_stored_scanning_height_erc(net_name, contract)

            local_height = await store.trx_get_block_number(timeout)
            try:
                redis_utils.redis_conn.set(f'{config.redis.prefix+config.redis.daemon_height}{net_name}', str(local_height))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
            try:
                url = "https://api.trongrid.io/v1/contracts/"+contract+"/events?event_name=Transfer&only_confirmed=true&order_by=block_timestamp,desc&limit=200"
                if last_timestamp:
                    url = "https://api.trongrid.io/v1/contracts/"+contract+"/events?event_name=Transfer&only_confirmed=true&order_by=block_timestamp,desc&limit=200&min_block_timestamp="+str(last_timestamp*1000)
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers={'Content-Type': 'application/json', 'TRON-PRO-API-KEY': config.Tron_Node.trongrid_api}, timeout=timeout) as response:
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                if decoded_data and 'success' in decoded_data and decoded_data['success'] == True:
                                    records = decoded_data['data']
                                    if len(records) > 0:
                                        # print("{} / {} Got {} record(s).".format(net_name, COIN_NAME, len(records))) # For later debug
                                        pass
                                    if len(records) > 0:
                                        to_block = int(records[0]['block_timestamp'] / 1000)
                                        rows = []
                                        for each in records:
                                            if each['result'] and len(each['result']) >= 6:
                                                try:
                                                    from_addr = hex_to_base58(each['result']['0'])
                                                    to_addr = hex_to_base58(each['result']['1'])
                                                    if to_addr not in all_addresses_in_db:
                                                        continue
                                                    blockTime = 0
                                                    if str(each['block_number']) in self.blockTime:
                                                        blockTime = self.blockTime[str(each['block_number'])]
                                                    else:
                                                        try:
                                                            get_blockinfo = await store.trx_get_block_info(self.bot.erc_node_list['TRX'], each['block_number'])
                                                            if get_blockinfo:
                                                                blockTime = int(get_blockinfo['timestamp'] / 1000)
                                                                self.blockTime[str(each['block_number'])] = blockTime
                                                        except Exception as e:
                                                            traceback.print_exc(file=sys.stdout)
                                                except Exception as e:
                                                    traceback.print_exc(file=sys.stdout)
                                                    continue
                                                key = "{}_{}_{}_{}".format(each['contract_address'], each['block_number'], each['transaction_id'], from_addr, to_addr)
                                                def lower_txes(txHash_unique):
                                                    return [x.lower() for x in txHash_unique]
                                                
                                                uniq_txes = functools.partial(lower_txes, txHash_unique)
                                                txHash_unique = await self.bot.loop.run_in_executor(None, uniq_txes)

                                                if key.lower() not in txHash_unique:
                                                    txHash_unique.append(key)
                                                    try:
                                                        rows.append((net_name, each['contract_address'], from_addr, to_addr, each['block_number'], blockTime,  each['transaction_id'], key))
                                                    except Exception as e:
                                                        traceback.print_exc(file=sys.stdout)
                                                    # print("{} Append row {}".format(net_name, len(rows)))
                                        # print("{} / {} Got {} row(s)".format(net_name, COIN_NAME, len(rows)))
                                        if len(rows) > 0:
                                            # insert data
                                            #print(rows[-1])
                                            insert_data = await store.get_monit_contract_tx_insert_trc(rows)
                                            # if insert_data == 0:
                                                # print(f"Failed to insert minting to `erc_contract_scan` for net_name {net_name}")
                                            # else:
                                                # print(f"Insert {insert_data} minting to `erc_contract_scan` for net_name {net_name}")
                                            update_height = await store.get_monit_scanning_net_name_update_height(net_name, to_block, COIN_NAME)
                                            if update_height is None:
                                                print(f"to_block {str(to_block)} No tx for `erc_contract_scan` for net_name {net_name}")
                                        elif len(rows) == 0:
                                            # Update height to DB
                                            update_height = await store.get_monit_scanning_net_name_update_height(net_name, to_block, COIN_NAME)
                                            if update_height is None:
                                                print(f"to_block {str(to_block)} No tx for `erc_contract_scan` for net_name {net_name}")
                                        ##return records
                                    elif len(records) == 0:
                                        # Update height to DB
                                        update_height = await store.get_monit_scanning_net_name_update_height(net_name, to_block, COIN_NAME)
                                        if update_height is None:
                                            print(f"to_block {str(to_block)} No tx for `erc_contract_scan` for net_name {net_name}")
                            elif response.status == 400:
                                await asyncio.sleep(3.0)
                                return
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

def setup(bot):
    bot.add_cog(EthScan(bot))
