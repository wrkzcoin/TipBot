import sys
import traceback
import time

import aiohttp, asyncio
from aiohttp import TCPConnector

import json
from disnake.ext import tasks, commands
import functools

import store
from Bot import get_token_list, logchanbot, hex_to_base58, base58_to_hex
from cogs.utils import Utils


class EthScan(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.utils = Utils(self.bot)
        self.blockTime = {}
        self.allow_start_ethscan = False

    @tasks.loop(seconds=10.0)
    async def fetch_trx_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_trx_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            if "local_node_trx" in bot_settings and bot_settings['local_node_trx'] is not None:
                self.bot.erc_node_list['TRX'] = bot_settings['local_node_trx']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_trx'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # trx needs to fetch best node from their public
                            self.bot.erc_node_list['TRX'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for TRX.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_arb1eth_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_arb1eth_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            if "local_node_arb1eth" in bot_settings and bot_settings['local_node_arb1eth'] is not None:
                self.bot.erc_node_list['ARB1ETH'] = bot_settings['local_node_arb1eth']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_arb1eth'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # ARB1ETH needs to fetch best node from their public
                            self.bot.erc_node_list['ARB1ETH'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for ARB1ETH.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_opeth_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_opeth_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            # Use withdraw node differently
            if bot_settings.get('local_node_opeth_withdraw'):
                self.bot.erc_node_list['OPETH_WITHDRAW'] = bot_settings['local_node_opeth_withdraw']
            if "local_node_opeth" in bot_settings and bot_settings['local_node_opeth'] is not None:
                self.bot.erc_node_list['OPETH'] = bot_settings['local_node_opeth']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_opeth'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # OPETH needs to fetch best node from their public
                            self.bot.erc_node_list['OPETH'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for OPETH.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_bsc_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_bsc_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            # Use withdraw node differently
            if bot_settings.get('local_node_bnb_withdraw'):
                self.bot.erc_node_list['BNB_WITHDRAW'] = bot_settings['local_node_bnb_withdraw']
            if "local_node_bnb" in bot_settings and bot_settings['local_node_bnb'] is not None:
                self.bot.erc_node_list['BNB'] = bot_settings['local_node_bnb']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_bsc'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # BSC needs to fetch best node from their public
                            self.bot.erc_node_list['BSC'] = res_data.replace('"', '')
                            self.bot.erc_node_list['BNB'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for BSC.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_sol_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_sol_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            # Use withdraw node differently
            if bot_settings.get('local_node_sol_withdraw'):
                self.bot.erc_node_list['SOL_WITHDRAW'] = bot_settings['local_node_sol_withdraw']
            if "local_node_sol" in bot_settings and bot_settings['local_node_sol'] is not None:
                self.bot.erc_node_list['SOL'] = bot_settings['local_node_sol']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_sol'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # SOL needs to fetch best node from their public
                            self.bot.erc_node_list['SOL'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for SOL.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_matic_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_matic_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            # Use withdraw node differently
            if bot_settings.get('local_node_matic_withdraw'):
                self.bot.erc_node_list['MATIC_WITHDRAW'] = bot_settings['local_node_matic_withdraw']
            if "local_node_matic" in bot_settings and bot_settings['local_node_matic'] is not None:
                self.bot.erc_node_list['MATIC'] = bot_settings['local_node_matic']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_matic'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # MATIC needs to fetch best node from their public
                            self.bot.erc_node_list['MATIC'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for MATIC.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_celo_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_celo_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            # Use withdraw node differently
            if bot_settings.get('local_node_celo_withdraw'):
                self.bot.erc_node_list['CELO_WITHDRAW'] = bot_settings['local_node_celo_withdraw']
            if "local_node_celo" in bot_settings and bot_settings['local_node_celo'] is not None:
                self.bot.erc_node_list['CELO'] = bot_settings['local_node_celo']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_celo'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # CELO needs to fetch best node from their public
                            self.bot.erc_node_list['CELO'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for CELO.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_ftm_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_ftm_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            # Use withdraw node differently
            if bot_settings.get('local_node_ftm_withdraw'):
                self.bot.erc_node_list['FTM_WITHDRAW'] = bot_settings['local_node_ftm_withdraw']
            if "local_node_ftm" in bot_settings and bot_settings['local_node_ftm'] is not None:
                self.bot.erc_node_list['FTM'] = bot_settings['local_node_ftm']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_ftm'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # FTM needs to fetch best node from their public
                            self.bot.erc_node_list['FTM'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for FTM.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_avax_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_avax_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            # Use withdraw node differently
            if bot_settings.get('local_node_avax_withdraw'):
                self.bot.erc_node_list['AVAX_WITHDRAW'] = bot_settings['local_node_avax_withdraw']
            if "local_node_avax" in bot_settings and bot_settings['local_node_avax'] is not None:
                self.bot.erc_node_list['AVAX'] = bot_settings['local_node_avax']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_avax'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # AVAX needs to fetch best node from their public
                            self.bot.erc_node_list['AVAX'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for AVAX.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_xdai_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_xdai_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            # Use withdraw node differently
            if bot_settings.get('local_node_xdai_withdraw'):
                self.bot.erc_node_list['XDAI_WITHDRAW'] = bot_settings['local_node_xdai_withdraw']
                self.bot.erc_node_list['xDai_WITHDRAW'] = bot_settings['local_node_xdai_withdraw']
            if "local_node_xdai" in bot_settings and bot_settings['local_node_xdai'] is not None:
                self.bot.erc_node_list['XDAI'] = bot_settings['local_node_xdai']
                self.bot.erc_node_list['xDai'] = bot_settings['local_node_xdai']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_xdai'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # XDAI needs to fetch best node from their public
                            self.bot.erc_node_list['XDAI'] = res_data.replace('"', '')
                            self.bot.erc_node_list['xDai'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for XDAI.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_one_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_one_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        async with aiohttp.ClientSession() as session:
            async with session.get(
                bot_settings['api_best_node_one'],
                headers={'Content-Type': 'application/json'},
                timeout=5.0
            ) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    # ONE needs to fetch best node from their public
                    self.bot.erc_node_list['ONE'] = res_data.replace('"', '')
                else:
                    await logchanbot(f"Can not fetch best node for ONE.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_tezos_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_tezos_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            # Use withdraw node differently
            if bot_settings.get('local_node_xtz_withdraw'):
                self.bot.erc_node_list['XTZ_WITHDRAW'] = bot_settings['local_node_xtz_withdraw']
            if "local_node_xtz" in bot_settings and bot_settings['local_node_xtz'] is not None:
                self.bot.erc_node_list['XTZ'] = bot_settings['local_node_xtz']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_xtz'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # XTZ needs to fetch best node from their public
                            self.bot.erc_node_list['XTZ'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for XTZ.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_near_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_near_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            # Use withdraw node differently
            if bot_settings.get('local_node_near_withdraw'):
                self.bot.erc_node_list['NEAR_WITHDRAW'] = bot_settings['local_node_near_withdraw']
            if "local_node_near" in bot_settings and bot_settings['local_node_near'] is not None:
                self.bot.erc_node_list['NEAR'] = bot_settings['local_node_near']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_near'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # NEAR needs to fetch best node from their public
                            self.bot.erc_node_list['NEAR'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for NEAR.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_xrp_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_xrp_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            # Use withdraw node differently
            if bot_settings.get('local_node_xrp_withdraw'):
                self.bot.erc_node_list['XRP_WITHDRAW'] = bot_settings['local_node_xrp_withdraw']
            if "local_node_xrp" in bot_settings and bot_settings['local_node_xrp'] is not None:
                self.bot.erc_node_list['XRP'] = bot_settings['local_node_xrp']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_xrp'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # XRP needs to fetch best node from their public
                            self.bot.erc_node_list['XRP'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for XRP.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_zil_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_zil_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        async with aiohttp.ClientSession() as session:
            async with session.get(
                bot_settings['api_best_node_zil'],
                headers={'Content-Type': 'application/json'},
                timeout=5.0
            ) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    # ZIL needs to fetch best node from their public
                    self.bot.erc_node_list['ZIL'] = res_data.replace('"', '')
                else:
                    await logchanbot(f"Can not fetch best node for ZIL.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_vet_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_vet_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            if "local_node_vet" in bot_settings and bot_settings['local_node_vet'] is not None:
                self.bot.erc_node_list['VET'] = bot_settings['local_node_vet']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_vet'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # VET needs to fetch best node from their public
                            self.bot.erc_node_list['VET'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for VET.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_nova_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_nova_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            # Use withdraw node differently
            if bot_settings.get('local_node_nova_withdraw'):
                self.bot.erc_node_list['NOVA_WITHDRAW'] = bot_settings['local_node_nova_withdraw']
            if "local_node_nova" in bot_settings and bot_settings['local_node_nova'] is not None:
                self.bot.erc_node_list['NOVA'] = bot_settings['local_node_nova']
                self.bot.erc_node_list['NOVAETH'] = bot_settings['local_node_nova']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_nova'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # NOVA needs to fetch best node from their public
                            self.bot.erc_node_list['NOVA'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for NOVA.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=10.0)
    async def fetch_eth_node(self):
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_fetch_eth_node"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        bot_settings = await self.utils.get_bot_settings()
        if bot_settings is None:
            return
        else:
            # Use withdraw node differently
            if bot_settings.get('local_node_eth_withdraw'):
                self.bot.erc_node_list['ETH_WITHDRAW'] = bot_settings['local_node_eth_withdraw']
            if "local_node_eth" in bot_settings and bot_settings['local_node_eth'] is not None:
                self.bot.erc_node_list['ETH'] = bot_settings['local_node_eth']
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        bot_settings['api_best_node_eth'],
                        headers={'Content-Type': 'application/json'},
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            # ETH needs to fetch best node from their public
                            self.bot.erc_node_list['ETH'] = res_data.replace('"', '')
                        else:
                            await logchanbot(f"Can not fetch best node for ETH.")
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(10.0)

    @tasks.loop(seconds=60.0)
    async def remove_all_tx_ethscan(self):
        await asyncio.sleep(5.0)
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_remove_all_tx_ethscan"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        try:
            remove_old_tx_erc20 = await store.contract_tx_remove_after(
                "ERC-20", 48 * 3600
            )  # 48hrs , any type will remove from erc20 table
            remove_old_tx_trc20 = await store.contract_tx_remove_after(
                "TRC-20", 48 * 3600
            )  # 48hrs
        except Exception:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(5.0)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))

    # Token contract only, not user's address
    @tasks.loop(seconds=60.0)
    async def pull_trc20_scanning(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(2.0)
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_pull_trc20_scanning"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
        # Get all contracts of ETH type and update to coin_ethscan_setting
        trc_contracts = await self.get_all_contracts("TRC-20")
        if len(trc_contracts) > 0:
            # Update height
            local_height = await store.trx_get_block_number(self.bot.erc_node_list['TRX'], 16)
            if local_height == 0:
                await asyncio.sleep(5.0)
                return
            else:
                try:
                    net_name = "TRX"
                    await self.utils.async_set_cache_kv(
                        "block",
                        f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{net_name}",
                        local_height
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("ethscan pull_trc20_scanning " + str(traceback.format_exc()))

            for each_contract in trc_contracts:
                try:
                    pass
                    # TODO, blocked IO
                    # await self.fetch_txes_trc(each_contract['coin_name'], each_contract['contract'])
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(10.0)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))

    # Token contract only, not user's address
    @tasks.loop(seconds=60.0)
    async def pull_erc20_scanning(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(2.0)
        # Check if task recently run @bot_task_logs
        task_name = "ethscan_pull_erc20_scanning"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15:
            # not running if less than 15s
            return
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
                        # Update height
                        local_height = await store.erc_get_block_number(self.bot.erc_node_list[k])
                        try:
                            if local_height and local_height > 0:
                                #print("{} new height: {}".format(k, local_height))
                                await self.utils.async_set_cache_kv(
                                    "block",
                                    f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{k}",
                                    local_height
                                )
                            else:
                                return
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("ethscan pull_erc20_scanning " + str(traceback.format_exc()))

                        # TODO: this blocked IO
                        # await self.fetch_txes(self.bot.erc_node_list[k], k, v, net_names[k]['scanned_from_height'])
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(10.0)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))

    async def get_all_contracts(self, type_token: str):
        # type_token: ERC-20, TRC-20
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_settings` 
                    WHERE `type`=%s AND `contract` IS NOT NULL AND `net_name` IS NOT NULL """
                    await cur.execute(sql, (type_token,))
                    result = await cur.fetchall()
                    if result and len(result) > 0: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("ethscan get_all_contracts " + str(traceback.format_exc()))
        return []

    async def get_all_net_names(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_ethscan_setting` 
                    WHERE `enable`=%s """
                    await cur.execute(sql, (1,))
                    result = await cur.fetchall()
                    net_names = {}
                    if result and len(result) > 0:
                        for each in result:
                            net_names[each['net_name']] = each
                        return net_names
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("ethscan get_all_net_names " + str(traceback.format_exc()))
        return {}

    async def update_scan_setting(self, net_name: str, contracts):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `coin_ethscan_setting` 
                    SET `contracts`=%s WHERE `net_name`=%s LIMIT 1 """
                    await cur.execute(sql, (",".join(contracts), net_name))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("ethscan update_scan_setting " + str(traceback.format_exc()))
        return None

    async def fetch_txes(self, url: str, net_name: str, contracts, scanned_from_height: int, timeout: int = 64):
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
                if local_height is None:
                    return
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("ethscan fetch_txes " + str(traceback.format_exc()))

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
                data = '{"jsonrpc":"2.0","method":"eth_getLogs","params":[{"fromBlock": "' + fromHeight + '", "toBlock": "' + to_bloc_str + '", "address": ' + contract + '}],"id":0}'
                if net_name == "xDai":
                    # xDai need camel case
                    data = '{"jsonrpc":"2.0","method":"eth_getLogs","params":[{"FromBlock": "' + fromHeight + '", "ToBlock": "' + to_bloc_str + '", "Address": ' + contract + '}],"id":0}'
                try:
                    async with aiohttp.ClientSession(connector=TCPConnector(ssl=False)) as session:
                        async with session.post(url, headers={'Content-Type': 'application/json'},
                                                json=json.loads(data), timeout=timeout) as response:
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                if decoded_data and 'error' in decoded_data:
                                    return []
                                elif decoded_data and 'result' in decoded_data:
                                    records = decoded_data['result']
                                    if len(records) > 0:
                                        # print("{} Got {} record(s).".format(net_name, len(records))) 
                                        # For later debug
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
                                                        get_blockinfo = await store.erc_get_block_info(url, int(
                                                            each['blockNumber'], 16))
                                                        if get_blockinfo:
                                                            blockTime = int(get_blockinfo['timestamp'], 16)
                                                            self.blockTime[
                                                                str(int(each['blockNumber'], 16))] = blockTime
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                                key = "{}_{}_{}_{}".format(
                                                    each['address'], int(each['blockNumber'], 16),
                                                    each['transactionHash'], from_addr, to_addr
                                                )

                                                def lower_txes(txHash_unique):
                                                    return [x.lower() for x in txHash_unique]

                                                uniq_txes = functools.partial(lower_txes, txHash_unique)
                                                txHash_unique = await self.bot.loop.run_in_executor(None, uniq_txes)

                                                if key.lower() not in txHash_unique:
                                                    txHash_unique.append(key)
                                                    try:
                                                        rows.append((net_name, each['address'],
                                                                     json.dumps(each['topics']), from_addr, to_addr,
                                                                     int(each['blockNumber'], 16), blockTime,
                                                                     each['transactionHash'], key))
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                                    # print("{} Append row {}".format(net_name, len(rows)))
                                        # print("{} Got {} row(s)".format(net_name, len(rows)))
                                        if len(rows) > 0:
                                            # insert data
                                            # print(rows[-1])
                                            insert_data = await store.get_monit_contract_tx_insert_erc(rows)
                                            # if insert_data == 0:
                                            # print(f"Failed to insert minting to `erc_contract_scan` for net_name {net_name}")
                                            # else:
                                            # print(f"Insert {insert_data} minting to `erc_contract_scan` for net_name {net_name}")
                                            update_height = await store.get_monit_scanning_net_name_update_height(
                                                net_name, to_block)
                                            if update_height is None:
                                                print(f"to_block {str(to_block)} No tx for `erc_contract_scan` for net_name {net_name}")
                                        elif len(rows) == 0:
                                            # Update height to DB
                                            update_height = await store.get_monit_scanning_net_name_update_height(
                                                net_name, to_block)
                                            if update_height is None:
                                                print(f"to_block {str(to_block)} No tx for `erc_contract_scan` for net_name {net_name}")
                                        ##return records
                                    elif len(records) == 0:
                                        # Update height to DB
                                        update_height = await store.get_monit_scanning_net_name_update_height(
                                            net_name, to_block
                                        )
                                        if update_height is None:
                                            print(f"to_block {str(to_block)} No tx for `erc_contract_scan` for net_name {net_name}")
                            elif response.status == 400:
                                await asyncio.sleep(3.0)
                                return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def fetch_txes_trc(self, coin: str, contract: str, timeout: int = 64):
        coin_name = coin.upper()
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
            local_height = await store.trx_get_block_number(self.bot.erc_node_list['TRX'], timeout)
            if local_height == 0:
                await asyncio.sleep(5.0)
                return

            try:
                url = "https://api.trongrid.io/v1/contracts/" + contract + "/events?event_name=Transfer&only_confirmed=true&order_by=block_timestamp,desc&limit=200"
                if last_timestamp:
                    url = "https://api.trongrid.io/v1/contracts/" + contract + "/events?event_name=Transfer&only_confirmed=true&order_by=block_timestamp,desc&limit=200&min_block_timestamp=" + str(
                        last_timestamp * 1000)
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers={'Content-Type': 'application/json',
                                                             'TRON-PRO-API-KEY': self.bot.config['Tron_Node']['trongrid_api']},
                                               timeout=timeout) as response:
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                if decoded_data and 'success' in decoded_data and decoded_data['success'] is True:
                                    records = decoded_data['data']
                                    if len(records) > 0:
                                        # print("{} / {} Got {} record(s).".format(net_name, coin_name, len(records))) # For later debug
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
                                                            get_blockinfo = await store.trx_get_block_info(
                                                                self.bot.erc_node_list['TRX'], each['block_number'])
                                                            if get_blockinfo:
                                                                blockTime = int(get_blockinfo['timestamp'] / 1000)
                                                                self.blockTime[str(each['block_number'])] = blockTime
                                                        except Exception:
                                                            traceback.print_exc(file=sys.stdout)
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                                    continue
                                                key = "{}_{}_{}_{}".format(
                                                    each['contract_address'],
                                                    each['block_number'], each['transaction_id'],
                                                    from_addr, to_addr
                                                )

                                                def lower_txes(txHash_unique):
                                                    return [x.lower() for x in txHash_unique]

                                                uniq_txes = functools.partial(lower_txes, txHash_unique)
                                                txHash_unique = await self.bot.loop.run_in_executor(None, uniq_txes)

                                                if key.lower() not in txHash_unique:
                                                    txHash_unique.append(key)
                                                    try:
                                                        rows.append((net_name, each['contract_address'], from_addr,
                                                                     to_addr, each['block_number'], blockTime,
                                                                     each['transaction_id'], key))
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                                    # print("{} Append row {}".format(net_name, len(rows)))
                                        # print("{} / {} Got {} row(s)".format(net_name, coin_name, len(rows)))
                                        if len(rows) > 0:
                                            # insert data
                                            # print(rows[-1])
                                            insert_data = await store.get_monit_contract_tx_insert_trc(rows)
                                            # if insert_data == 0:
                                            # print(f"Failed to insert minting to `erc_contract_scan` for net_name {net_name}")
                                            # else:
                                            # print(f"Insert {insert_data} minting to `erc_contract_scan` for net_name {net_name}")
                                            update_height = await store.get_monit_scanning_net_name_update_height(
                                                net_name, to_block, coin_name)
                                            if update_height is None:
                                                print(
                                                    f"to_block {str(to_block)} No tx for `erc_contract_scan` for net_name {net_name}")
                                        elif len(rows) == 0:
                                            # Update height to DB
                                            update_height = await store.get_monit_scanning_net_name_update_height(
                                                net_name, to_block, coin_name)
                                            if update_height is None:
                                                print(f"to_block {str(to_block)} No tx for `erc_contract_scan` for net_name {net_name}")
                                        ##return records
                                    elif len(records) == 0:
                                        # Update height to DB
                                        update_height = await store.get_monit_scanning_net_name_update_height(
                                            net_name,  to_block, coin_name
                                        )
                                        if update_height is None:
                                            print(f"to_block {str(to_block)} No tx for `erc_contract_scan` for net_name {net_name}")
                            elif response.status == 400:
                                await asyncio.sleep(5.0)
                                return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.Cog.listener()
    async def on_ready(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.fetch_arb1eth_node.is_running():
                self.fetch_arb1eth_node.start()
            if not self.fetch_opeth_node.is_running():
                self.fetch_opeth_node.start()
            if not self.fetch_bsc_node.is_running():
                self.fetch_bsc_node.start()
            if not self.fetch_sol_node.is_running():
                self.fetch_sol_node.start()
            if not self.fetch_trx_node.is_running():
                self.fetch_trx_node.start()
            if not self.fetch_matic_node.is_running():
                self.fetch_matic_node.start()
            if not self.fetch_celo_node.is_running():
                self.fetch_celo_node.start()
            if not self.fetch_ftm_node.is_running():
                self.fetch_ftm_node.start()
            if not self.fetch_avax_node.is_running():
                self.fetch_avax_node.start()
            if not self.fetch_xdai_node.is_running():
                self.fetch_xdai_node.start()
            if not self.fetch_one_node.is_running():
                self.fetch_one_node.start()
            if not self.fetch_tezos_node.is_running():
                self.fetch_tezos_node.start()
            if not self.fetch_near_node.is_running():
                self.fetch_near_node.start()
            if not self.fetch_xrp_node.is_running():
                self.fetch_xrp_node.start()
            if not self.fetch_zil_node.is_running():
                self.fetch_zil_node.start()
            if not self.fetch_vet_node.is_running():
                self.fetch_vet_node.start()
            if not self.fetch_nova_node.is_running():
                self.fetch_nova_node.start()
            if not self.fetch_eth_node.is_running():
                self.fetch_eth_node.start()

            # scan
            if not self.pull_trc20_scanning.is_running():
                self.pull_trc20_scanning.start()

            # temporary, blocking IO
            if not self.pull_erc20_scanning.is_running():
                self.pull_erc20_scanning.start()
            if not self.remove_all_tx_ethscan.is_running():
                self.remove_all_tx_ethscan.start()

    async def cog_load(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.fetch_arb1eth_node.is_running():
                self.fetch_arb1eth_node.start()
            if not self.fetch_opeth_node.is_running():
                self.fetch_opeth_node.start()
            if not self.fetch_bsc_node.is_running():
                self.fetch_bsc_node.start()
            if not self.fetch_sol_node.is_running():
                self.fetch_sol_node.start()
            if not self.fetch_trx_node.is_running():
                self.fetch_trx_node.start()
            if not self.fetch_matic_node.is_running():
                self.fetch_matic_node.start()
            if not self.fetch_celo_node.is_running():
                self.fetch_celo_node.start()
            if not self.fetch_ftm_node.is_running():
                self.fetch_ftm_node.start()
            if not self.fetch_avax_node.is_running():
                self.fetch_avax_node.start()
            if not self.fetch_xdai_node.is_running():
                self.fetch_xdai_node.start()
            if not self.fetch_one_node.is_running():
                self.fetch_one_node.start()
            if not self.fetch_tezos_node.is_running():
                self.fetch_tezos_node.start()
            if not self.fetch_near_node.is_running():
                self.fetch_near_node.start()
            if not self.fetch_xrp_node.is_running():
                self.fetch_xrp_node.start()
            if not self.fetch_zil_node.is_running():
                self.fetch_zil_node.start()
            if not self.fetch_vet_node.is_running():
                self.fetch_vet_node.start()
            if not self.fetch_nova_node.is_running():
                self.fetch_nova_node.start()
            if not self.fetch_eth_node.is_running():
                self.fetch_eth_node.start()

            # scan
            # Temporary disable
            if not self.pull_trc20_scanning.is_running():
                self.pull_trc20_scanning.start()
            if not self.pull_erc20_scanning.is_running():
                self.pull_erc20_scanning.start()
            if not self.remove_all_tx_ethscan.is_running():
                self.remove_all_tx_ethscan.start()

    def cog_unload(self):
        # Ensure the task is stopped when the cog is unloaded.
        self.fetch_arb1eth_node.cancel()
        self.fetch_opeth_node.cancel()
        self.fetch_bsc_node.cancel()
        self.fetch_sol_node.cancel()
        self.fetch_trx_node.cancel()
        self.fetch_matic_node.cancel()
        self.fetch_celo_node.cancel()
        self.fetch_ftm_node.cancel()
        self.fetch_avax_node.cancel()
        self.fetch_xdai_node.cancel()
        self.fetch_one_node.cancel()
        self.fetch_tezos_node.cancel()
        self.fetch_near_node.cancel()
        self.fetch_xrp_node.cancel()
        self.fetch_zil_node.cancel()
        self.fetch_vet_node.cancel()
        self.fetch_nova_node.cancel()
        self.fetch_eth_node.cancel()

        self.pull_trc20_scanning.cancel()
        self.pull_erc20_scanning.cancel()
        self.remove_all_tx_ethscan.cancel()


def setup(bot):
    bot.add_cog(EthScan(bot))
