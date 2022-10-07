import asyncio
import json
import sys
import time
import traceback
from decimal import Decimal

from Bot import logchanbot, truncate
import store
from disnake.ext import tasks, commands
from web3 import Web3
from web3.middleware import geth_poa_middleware
from cogs.utils import Utils


class DexScan(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.utils = Utils(self.bot)

    async def dex_get_list(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `dex_track_price_info` WHERE `enabled`=%s """
                    await cur.execute(sql, (1))
                    result = await cur.fetchall()
                    if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def getPrice_generic(
        self, rpc: str, contract: str, wrapped_main_token: str, usdt_contract: str, lp_usdt_with_main_token: str, lp_token_main_token: str
    ):
        erc20_abi = json.loads('[{"constant":true,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"_from","type":"address"},{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transferFrom","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"payable":true,"stateMutability":"payable","type":"fallback"},{"anonymous":false,"inputs":[{"indexed":true,"name":"owner","type":"address"},{"indexed":true,"name":"spender","type":"address"},{"indexed":false,"name":"value","type":"uint256"}],"name":"Approval","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"name":"from","type":"address"},{"indexed":true,"name":"to","type":"address"},{"indexed":false,"name":"value","type":"uint256"}],"name":"Transfer","type":"event"}]')

        web3 = Web3(Web3.HTTPProvider(rpc))

        # inject the poa compatibility middleware to the innermost layer
        web3.middleware_onion.inject(geth_poa_middleware, layer=0)
                                
        main_token = web3.eth.contract((Web3.toChecksumAddress(wrapped_main_token)), abi=erc20_abi) # Contract wrapped main_token
        usdt = web3.eth.contract((Web3.toChecksumAddress(usdt_contract)), abi=erc20_abi) # Contract usdt
        price_token = web3.eth.contract((Web3.toChecksumAddress(contract)), abi=erc20_abi) # Contract token
        try:
            # Get main_token price in usdt
            main_token_balance = main_token.functions.balanceOf(Web3.toChecksumAddress(lp_usdt_with_main_token)).call() # USDT-MAIN_TOKEN Pair
            usdc_balance = usdt.functions.balanceOf(Web3.toChecksumAddress(lp_usdt_with_main_token)).call() # USDT-MAIN_TOKEN Pair
            main_token_price = (usdc_balance / 10** 18) / (main_token_balance / 10**18)

            # Get liquid
            main_token_balance = main_token.functions.balanceOf(Web3.toChecksumAddress(lp_token_main_token)).call() # pair price_token-MAIN_TOKEN
            myToken_balance  = price_token.functions.balanceOf(Web3.toChecksumAddress(lp_token_main_token)).call() # pair price_token-MAIN_TOKEN
            token_price_in_usdt = (main_token_balance / 10**18) / (myToken_balance / 10**18)

            # Token price in usd
            my_token_price = token_price_in_usdt * main_token_price

            return f"{my_token_price:.18f}"
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def dex_insert_price(
        self, token_name: str, chain_id: str, net_name: str, contract: str, source_from: str, price
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO dex_track_price_info_data (`token_name`, `chain_id`, `net_name`, `contract`, `price`, `source_from`, `inserted_time`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (token_name, chain_id, net_name, contract, truncate(price, 18), source_from, int(time.time())))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("dexscan " +str(traceback.format_exc()))
        return False

    @tasks.loop(seconds=10.0)
    async def dex_price_loop(self):
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "dexscan_dex_price_loop"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        try:
            get_list = await self.dex_get_list()
            if get_list and len(get_list) > 0:
                for each_token in get_list:
                    coin_name = each_token['token_name']
                    get_price = await self.getPrice_generic(self.bot.erc_node_list["BSC"], each_token['contract'], each_token['wrapped_main_token'], each_token['usdt_contract'], each_token['lp_usdt_with_main_token'], each_token['lp_token_main_token'])
                    if get_price and Decimal(get_price) > 0:
                        get_price = Decimal(get_price)*Decimal(10**each_token['decimal'])/Decimal(10**18)
                        insert = await self.dex_insert_price(each_token['token_name'], each_token['chain_id'], each_token['net_name'], each_token['contract'], each_token['source_from'], Decimal(get_price))
                        if hasattr(self.bot.coin_list, coin_name): 
                            usd_equivalent_dex = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_dex")
                            if usd_equivalent_dex == 1:
                                if coin_name in self.bot.token_hints:
                                    id = self.bot.token_hints[coin_name]['ticker_name']
                                    if id not in self.bot.coin_paprika_id_list:
                                        self.bot.coin_paprika_id_list[id] = {}
                                    self.bot.coin_paprika_id_list[id]['name'] = self.bot.token_hints[coin_name]['name']
                                    self.bot.coin_paprika_id_list[id]['price_usd'] = float(get_price)
                                else:
                                    if coin_name not in self.bot.coin_paprika_symbol_list: self.bot.coin_paprika_symbol_list[coin_name] = {}
                                    self.bot.coin_paprika_symbol_list[coin_name]['price_usd'] = float(get_price)
                        else:
                            # coin_name is not in Bot
                            if coin_name in self.bot.token_hints:
                                self.bot.coin_paprika_id_list[id]['name'] = self.bot.token_hints[coin_name]['name']
                                self.bot.coin_paprika_id_list[id]['price_usd'] = float(get_price)
                            else:
                                if coin_name not in self.bot.coin_paprika_symbol_list: self.bot.coin_paprika_symbol_list[coin_name] = {}
                                self.bot.coin_paprika_symbol_list[coin_name]['price_usd'] = float(get_price)
                            if coin_name not in self.bot.coin_price_dex:
                                self.bot.coin_price_dex.append(coin_name)
                                self.bot.coin_price_dex_from[coin_name] = each_token['source_from']
                        await asyncio.sleep(each_token['sleep_after_fetched'])
            await asyncio.sleep(30.0)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))

    @commands.Cog.listener()
    async def on_ready(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.dex_price_loop.is_running():
                self.dex_price_loop.start()

    async def cog_load(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.dex_price_loop.is_running():
                self.dex_price_loop.start()

    def cog_unload(self):
        # Ensure the task is stopped when the cog is unloaded.
        self.dex_price_loop.cancel()


def setup(bot):
    bot.add_cog(DexScan(bot))
