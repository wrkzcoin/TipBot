import sys
import traceback
from datetime import datetime
import aiohttp
import json
import ssl
import uuid
import aiomysql
from aiomysql.cursors import DictCursor

from decimal import Decimal
import disnake
from disnake.ext import commands
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

from Bot import num_format_coin, EMOJI_INFORMATION
import store
from config import config
import redis_utils


class Stats(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        redis_utils.openRedis()
        # DB
        self.pool = None

    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=2, maxsize=4, 
                                                       user=config.mysql.user, password=config.mysql.password,
                                                       db=config.mysql.db, cursorclass=DictCursor, autocommit=True)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    async def get_coin_tipping_stats(self, coin: str):
        COIN_NAME = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT COUNT(*) AS numb_tip, SUM(real_amount) AS amount_tip FROM `user_balance_mv` WHERE token_name=%s """
                    await cur.execute(sql, (COIN_NAME))
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None

    async def async_stats(self, ctx, coin: str=None):
        def simple_number(amount):
            if amount is None: return "0.0"
            amount_test = '{:,f}'.format(float(('%f' % (amount)).rstrip('0').rstrip('.')))
            if '.' in amount_test and len(amount_test.split('.')[1]) > 8:
                amount_str = '{:,.8f}'.format(amount)
            else:
                amount_str =  amount_test
            return amount_str.rstrip('0').rstrip('.') if '.' in amount_str else amount_str

        embed = disnake.Embed(title='STATS', description='Servers: {:,.0f}'.format(len(self.bot.guilds)), timestamp=datetime.now())
        try:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, checking `/stats`...'
            await ctx.response.send_message(msg)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(f"{EMOJI_INFORMATION} {ctx.author.mention}, failed to execute /stats message...", ephemeral=True)
            return
        if coin:
            COIN_NAME = coin.upper()
            if not hasattr(self.bot.coin_list, COIN_NAME):
                await ctx.edit_original_message(content=f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
                return
            else:
                type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                explorer_link = getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")
                net_name = None
                if type_coin == "ERC-20":
                    net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                    contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    display_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
                    if contract is None or (contract and len(contract) < 1):
                        contract = None
                    main_balance = await store.http_wallet_getbalance(self.bot.erc_node_list[net_name], config.eth.MainAddress, COIN_NAME, contract)
                    if main_balance:
                        main_balance_balance = num_format_coin(float(main_balance / 10** coin_decimal), COIN_NAME, coin_decimal, False)
                        embed.add_field(name="WALLET **{}**".format(display_name), value="`{} {}`".format(main_balance_balance, COIN_NAME), inline=False)
                elif type_coin in ["TRC-20", "TRC-10"]:
                    type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                    explorer_link = getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")
                    net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                    contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    display_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
                    if contract is None or (contract and len(contract) < 1):
                        contract = None
                    main_balance = await store.trx_wallet_getbalance(config.trc.MainAddress, COIN_NAME, coin_decimal, type_coin, contract)
                    if main_balance:
                        # already divided decimal
                        main_balance_balance = num_format_coin(float(main_balance), COIN_NAME, coin_decimal, False)
                        embed.add_field(name="WALLET **{}**".format(display_name), value="`{} {}`".format(main_balance_balance, COIN_NAME), inline=False)
                elif type_coin == "TRTL-API":
                    key = getattr(getattr(self.bot.coin_list, COIN_NAME), "header")
                    method = "/balance"
                    headers = {
                        'X-API-KEY': key,
                        'Content-Type': 'application/json'
                    }
                    url = getattr(getattr(self.bot.coin_list, COIN_NAME), "wallet_address")
                    explorer_link = getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url + method, headers=headers, timeout=32) as response:
                                json_resp = await response.json()
                                if response.status == 200 or response.status == 201:
                                    balance_decimal = simple_number(float(Decimal(json_resp['unlocked'])/Decimal(10**coin_decimal)))
                                    embed.add_field(name="Main Balance", value="`{} {}`".format(balance_decimal, COIN_NAME), inline=False)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                elif type_coin == "TRTL-SERVICE":
                    url = getattr(getattr(self.bot.coin_list, COIN_NAME), "wallet_address")
                    explorer_link = getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    json_data = {"jsonrpc":"2.0", "id":1, "password":"passw0rd", "method":"getBalance", "params":{}}
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(url, json=json_data, headers=headers, timeout=32) as response:
                                if response.status == 200:
                                    res_data = await response.read()
                                    res_data = res_data.decode('utf-8')
                                    decoded_data = json.loads(res_data)
                                    json_resp = decoded_data
                                    balance_decimal = simple_number(float(Decimal(json_resp['result']['availableBalance'])/Decimal(10**coin_decimal)))
                                    embed.add_field(name="Main Balance", value="`{} {}`".format(balance_decimal, COIN_NAME), inline=False)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                elif type_coin == "XMR":
                    url = getattr(getattr(self.bot.coin_list, COIN_NAME), "wallet_address")
                    explorer_link = getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    json_data = {"jsonrpc":"2.0", "id":"0", "method":"get_balance", "params":{"account_index": 0,"address_indices":[]}}
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(url, json=json_data, headers=headers, timeout=32) as response:
                                if response.status == 200:
                                    res_data = await response.read()
                                    res_data = res_data.decode('utf-8')
                                    decoded_data = json.loads(res_data)
                                    json_resp = decoded_data
                                    balance_decimal = simple_number(float(Decimal(json_resp['result']['balance'])/Decimal(10**coin_decimal)))
                                    embed.add_field(name="Main Balance", value="`{} {}`".format(balance_decimal, COIN_NAME), inline=False)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                elif type_coin == "BTC":
                    url = getattr(getattr(self.bot.coin_list, COIN_NAME), "daemon_address")
                    explorer_link = getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(url, data='{"jsonrpc": "1.0", "id":"'+str(uuid.uuid4())+'", "method": "getbalance", "params": [] }', timeout=32) as response:
                                if response.status == 200:
                                    res_data = await response.read()
                                    res_data = res_data.decode('utf-8')
                                    decoded_data = json.loads(res_data)
                                    json_resp = decoded_data
                                    balance_decimal = simple_number(float(Decimal(json_resp['result'])))
                                    embed.add_field(name="Main Balance", value="`{} {}`".format(balance_decimal, COIN_NAME), inline=False)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                elif type_coin == "CHIA":
                    explorer_link = getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    json_data = {
                        "wallet_id": 1
                    }
                    try:
                        url = getattr(getattr(self.bot.coin_list, COIN_NAME), "rpchost") + '/' + "get_wallet_balance"
                        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                        ssl_context.load_cert_chain(getattr(getattr(self.bot.coin_list, COIN_NAME), "cert_path"), getattr(getattr(self.bot.coin_list, COIN_NAME), "key_path"))
                        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
                            async with session.post(url, json=json_data, headers=headers, timeout=32, ssl=ssl_context) as response:
                                if response.status == 200:
                                    res_data = await response.read()
                                    res_data = res_data.decode('utf-8')
                                    decoded_data = json.loads(res_data)['wallet_balance']
                                    balance_decimal = simple_number(float(Decimal(decoded_data['spendable_balance'])/Decimal(10**coin_decimal)))
                                    embed.add_field(name="Main Balance", value="`{} {}`".format(balance_decimal, COIN_NAME), inline=False)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                elif type_coin == "NANO":
                    url = getattr(getattr(self.bot.coin_list, COIN_NAME), "rpchost")
                    main_address = getattr(getattr(self.bot.coin_list, COIN_NAME), "MainAddress")
                    explorer_link = getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    json_data = {
                        "action": "account_balance",
                        "account": main_address
                    }
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(url, headers=headers, json=json_data, timeout=32) as response:
                                if response.status == 200:
                                    res_data = await response.read()
                                    res_data = res_data.decode('utf-8')
                                    decoded_data = json.loads(res_data)
                                    json_resp = decoded_data
                                    balance_decimal = simple_number(float(Decimal(json_resp['balance'])/Decimal(10**coin_decimal)))
                                    embed.add_field(name="Main Balance", value="`{} {}`".format(balance_decimal, COIN_NAME), inline=False)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                elif type_coin == "HNT":
                    try:
                        main_address = getattr(getattr(self.bot.coin_list, COIN_NAME), "MainAddress")
                        wallet_host = getattr(getattr(self.bot.coin_list, COIN_NAME), "wallet_address")
                        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                        explorer_link = getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")
                        headers = {
                            'Content-Type': 'application/json'
                        }
                        json_data = {
                            "jsonrpc": "2.0",
                            "id": "1",
                            "method": "account_get",
                            "params": {
                                "address": main_address
                            }
                        }
                        async with aiohttp.ClientSession() as session:
                            async with session.post(wallet_host, headers=headers, json=json_data, timeout=32) as response:
                                if response.status == 200:
                                    res_data = await response.read()
                                    res_data = res_data.decode('utf-8')
                                    decoded_data = json.loads(res_data)
                                    json_resp = decoded_data
                                    if 'result' in json_resp:
                                        embed.add_field(name="Main Balance", value="`{} {}`".format(simple_number(json_resp['result']['balance']/10**coin_decimal), COIN_NAME), inline=False)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                try:
                    get_tip_stats = await self.get_coin_tipping_stats(COIN_NAME)
                    if get_tip_stats:
                        embed.add_field(name="Tip/DB Records: {:,.0f}".format(get_tip_stats['numb_tip']), value="`{}`".format(simple_number(get_tip_stats['amount_tip'])), inline=False)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                try:
                    height = None
                    if net_name is None:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                    else:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                    if height:
                        embed.add_field(name="blockNumber", value="`{:,.0f}` | [Explorer Link]({})".format(height, explorer_link), inline=False)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        else:
            embed.add_field(name='Creator\'s Discord Name:', value='pluton#8888', inline=False)
            embed.add_field(name="Online", value='{:,.0f}'.format(sum(1 for m in self.bot.get_all_members() if m.status == disnake.Status.online)), inline=True)
            embed.add_field(name="Users", value='{:,.0f}'.format(sum(1 for m in self.bot.get_all_members() if m.bot == False)), inline=True)
            embed.add_field(name="Bots", value='{:,.0f}'.format(sum(1 for m in self.bot.get_all_members() if m.bot == True)), inline=True)
            embed.add_field(name='Note:', value='Use `/stats coin` to check each coin\'s stats.', inline=False)
            embed.set_footer(text='Made in Python!', icon_url='http://findicons.com/files/icons/2804/plex/512/python.png')
            embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
            embed.set_thumbnail(url=self.bot.user.display_avatar)
        await ctx.edit_original_message(content=None, embed=embed)


    @commands.slash_command(
        usage='stats', 
        options=[
                    Option("token", "Enter a coin/ticker name", OptionType.string, required=False)
                ],
        description='Get some statistic and information.'
    )
    async def stats(
        self, 
        inter: disnake.AppCmdInter,
        token: str=None
    ) -> None:
        try:
            await self.async_stats(inter, token)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


def setup(bot):
    bot.add_cog(Stats(bot))
