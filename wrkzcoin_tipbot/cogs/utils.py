import sys
import traceback
from typing import List
import time
from cachetools import TTLCache
import pickle
import redis
import aiohttp
import json
# password gen
import secrets
import string
import random
import asyncio
# chart
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib as mpl
import pandas as pd
from colour import Color
import aiomysql
from aiomysql.cursors import DictCursor
import disnake
from disnake.ext import commands

import store
from Bot import RowButtonRowCloseAnyMessage, logchanbot, truncate
plt.style.use('ggplot')

def makechart(data, save_path_name: str):
    try:
        color = 'grey'
        mpl.rcParams["axes.edgecolor"] = color
        mpl.rcParams["axes.linewidth"]  = 1.25
        mpl.rcParams['text.color'] = color
        mpl.rcParams['axes.labelcolor'] = color
        mpl.rcParams['xtick.color'] = color
        mpl.rcParams['ytick.color'] = color

        chart_date = [datetime.fromtimestamp(i[0]/1000) for i in data['prices']]
        price_list = [i[1] for i in data['prices']]
        volume_list = [i[1] for i in data['total_volumes']]

        data = pd.DataFrame(data={'price': price_list, 'volume': volume_list}, index=chart_date)
        data_v = data.groupby(data.index.date).mean()

        red = Color("red")
        colors = list(red.range_to(Color("green"), len(data_v.volume)))
        colors = [color.rgb for color in colors]

        fig, ax = plt.subplots(nrows=2, sharex=True, figsize=(15,8))
        plt.xticks(rotation=90)

        selected_color = random.choice([color.rgb for color in list(Color("red").range_to(Color("green"), 10))]) # range 10 color
        ax[0].plot(data.index, data.price, color=selected_color)
        ax[0].fill_between(data.index, data.price, 0, color=selected_color, alpha=.25)
        ax[1].bar(data_v.index, data_v.volume, width=0.5, color=colors) # 1/len(data.index)
        # ax[1].plot(data.index, data.volume)

        xfmt = mpl.dates.DateFormatter('%m-%d')
        ax[1].xaxis.set_major_locator(mpl.dates.HourLocator(interval=24))
        ax[1].xaxis.set_major_formatter(xfmt)

        ax[1].xaxis.set_minor_locator(mpl.dates.HourLocator(interval=24))
        ax[1].xaxis.set_minor_formatter(xfmt)

        ax[1].get_xaxis().set_tick_params(which='major', pad=0)
        # fig.autofmt_xdate()

        # set grid
        ax[0].grid(which='major', linestyle = '--', color='grey')
        ax[1].grid(which='major', linestyle = '--', color='grey')

        # set auto number
        ax[1].get_yaxis().set_major_formatter(
            mpl.ticker.FuncFormatter(lambda x, p: format(int(x), ',')))

        # Set common labels
        ax[0].set_xlabel('Price (USD)')
        ax[1].set_xlabel('Volume (USD)')

        #ax[0].set_title('ax1 title')
        #ax[1].set_title('ax2 title')

        plt.savefig(save_path_name, transparent=True)
        return save_path_name
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

# https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

# https://geekflare.com/password-generator-python-code/
def gen_password(pwd_length: int=12):
    # define the alphabet
    letters = string.ascii_letters
    digits = string.digits
    special_chars = string.punctuation
    alphabet = letters + digits + special_chars

    # generate a password string
    pwd = ''
    for i in range(pwd_length):
        pwd += ''.join(secrets.choice(alphabet))
    return pwd

def num_format_coin(amount):
    if amount == 0:
        return "0.0"

    if amount < 0.00000001:
        amount_str = '{:,.10f}'.format(truncate(amount, 10))
    elif amount < 0.000001:
        amount_str = '{:,.8f}'.format(truncate(amount, 8))
    elif amount < 0.00001:
        amount_str = '{:,.7f}'.format(truncate(amount, 7))
    elif amount < 0.01:
        amount_str = '{:,.6f}'.format(truncate(amount, 6))
    elif amount < 1.0:
        amount_str = '{:,.5f}'.format(truncate(amount, 5))
    elif amount < 10:
        amount_str = '{:,.4f}'.format(truncate(amount, 4))
    elif amount < 1000.00:
        amount_str = '{:,.3f}'.format(truncate(amount, 3))
    else:
        amount_str = '{:,.2f}'.format(truncate(amount, 2))
    return amount_str.rstrip('0').rstrip('.') if '.' in amount_str else amount_str

# https://stackoverflow.com/questions/287871/how-do-i-print-colored-text-to-the-terminal

def print_color(prt, color: str):
    if color == "red":
        print(f"\033[91m{prt}\033[00m")
    elif color == "green":
        print(f"\033[92m{prt}\033[00m")
    elif color == "yellow":
        print(f"\033[93m{prt}\033[00m")
    elif color == "lightpurple":
        print(f"\033[94m{prt}\033[00m")
    elif color == "purple":
        print(f"\033[95m{prt}\033[00m")
    elif color == "cyan":
        print(f"\033[96m{prt}\033[00m")
    elif color == "lightgray":
        print(f"\033[97m{prt}\033[00m")
    elif color == "black":
        print(f"\033[98m{prt}\033[00m")
    else:
        print(f"\033[0m{prt}\033[00m")

async def get_all_coin_names(
    what: str,
    value: int,
    limit: int=25
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT `coin_name` FROM `coin_settings` 
                WHERE `"""+what+"""`=%s
                LIMIT 
                """ + str(limit)
                await cur.execute(sql, value)
                result = await cur.fetchall()
                if result:
                    coin_list = [each["coin_name"] for each in result]
                    return coin_list
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return ["N/A"]

# stellar utils
async def stellar_get_tx_info(tx: str, timeout: int=30):
    try:
        url = "https://horizon.stellar.org/transactions/" + tx
        async with aiohttp.ClientSession() as cs:
            async with cs.get(url, timeout=timeout) as r:
                res_data = await r.read()
                res_data = res_data.decode('utf-8')
                result = json.loads(res_data)
                return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def btc_get_tx_info(url: str, tx: str, timeout: int=30):
    try:
        data = '{"jsonrpc": "1.0", "id": "curltest", "method": "gettransaction", "params": ["' + tx + '"] }'
        async with aiohttp.ClientSession() as cs:
            async with cs.post(url, data=data, timeout=timeout) as r:
                res_data = await r.read()
                res_data = res_data.decode('utf-8')
                result = json.loads(res_data)
                return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def erc20_get_tx_info(url: str, tx: str, timeout: int = 64):
    data = '{"jsonrpc":"2.0", "method": "eth_getTransactionReceipt", "params":["' + tx + '"], "id":1}'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers={'Content-Type': 'application/json'},
                json=json.loads(data),
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data and 'result' in decoded_data:
                        return decoded_data['result']
    except asyncio.TimeoutError:
        print('TIMEOUT: {} get block number {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def erc20_get_block_number(url: str, timeout: int = 64):
    data = '{"jsonrpc":"2.0", "method":"eth_blockNumber", "params":[], "id":1}'
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.post(
                url, headers={'Content-Type': 'application/json'},
                json=json.loads(data),
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data and 'result' in decoded_data:
                        return int(decoded_data['result'], 16)
    except asyncio.TimeoutError:
        print('TIMEOUT: {} get block number {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def tezos_get_tx(url: str, tx_hash: str, timeout: int=16):
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url + "operations/transactions/" + tx_hash,
                headers=headers,
                timeout=timeout
            ) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    if len(json_resp) == 1 and "status" in json_resp[0] and "level" in json_resp[0]:
                        return json_resp[0]
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

# Defines a simple paginator of buttons for the embed.
class MenuPage(disnake.ui.View):
    message: disnake.Message

    def __init__(self, inter, embeds: List[disnake.Embed], timeout: float = 60, disable_remove: bool=False):
        super().__init__(timeout=timeout)
        self.inter = inter

        # Sets the embed list variable.
        self.embeds = embeds

        # Current embed number.
        self.embed_count = 0

        # Disables previous page button by default.
        self.prev_page.disabled = True

        self.first_page.disabled = True

        if disable_remove is True:
            self.remove.disabled = True

        # Sets the footer of the embeds with their respective page numbers.
        for i, embed in enumerate(self.embeds):
            embed.set_footer(text=f"Page {i + 1} of {len(self.embeds)}")

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True

        if type(self.inter) == disnake.ApplicationCommandInteraction:
            await self.inter.edit_original_message(view=RowButtonRowCloseAnyMessage())
        else:
            if self.message:
                try:
                    await self.message.edit(view=RowButtonRowCloseAnyMessage())
                except Exception as e:
                    pass

    @disnake.ui.button(label="⏪", style=disnake.ButtonStyle.red)
    async def first_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return

        # Decrements the embed count.
        self.embed_count = 0

        # Gets the embed object.
        try:
            embed = self.embeds[self.embed_count]
        except IndexError:
            return

        self.last_page.disabled = False

        # Enables the next page button and disables the previous page button if we're on the first embed.
        self.next_page.disabled = False
        if self.embed_count == 0:
            self.prev_page.disabled = True
            self.first_page.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    @disnake.ui.button(label="◀️", style=disnake.ButtonStyle.red)
    async def prev_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return

        # Decrements the embed count.
        self.embed_count -= 1

        # Gets the embed object.
        try:
            embed = self.embeds[self.embed_count]
        except IndexError:
            self.embed_count += 1
            return

        self.last_page.disabled = False

        # Enables the next page button and disables the previous page button if we're on the first embed.
        self.next_page.disabled = False
        if self.embed_count == 0:
            self.prev_page.disabled = True
            self.first_page.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    # @disnake.ui.button(label="⏹️", style=disnake.ButtonStyle.red)
    @disnake.ui.button(label="⏹️", style=disnake.ButtonStyle.red)
    async def remove(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return
        # await interaction.response.edit_message(view=None)
        try:
            if type(self.inter) == disnake.ApplicationCommandInteraction:
                await self.inter.delete_original_message()
            else:
                await interaction.message.delete()
        except Exception as e:
            pass

    # @disnake.ui.button(label="", emoji="▶️", style=disnake.ButtonStyle.green)
    @disnake.ui.button(label="▶️", style=disnake.ButtonStyle.green)
    async def next_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return
        # Increments the embed count.
        self.embed_count += 1

        # Gets the embed object.
        try:
            embed = self.embeds[self.embed_count]
        except IndexError:
            self.embed_count -= 1
            return

        # Enables the previous page button and disables the next page button if we're on the last embed.
        self.prev_page.disabled = False

        self.first_page.disabled = False

        if self.embed_count == len(self.embeds) - 1:
            self.next_page.disabled = True
            self.last_page.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    @disnake.ui.button(label="⏩", style=disnake.ButtonStyle.green)
    async def last_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return
        # Increments the embed count.
        self.embed_count = len(self.embeds) - 1

        # Gets the embed object.
        try:
            embed = self.embeds[self.embed_count]
        except IndexError:
            self.embed_count = len(self.embeds) + 1
            return

        self.first_page.disabled = False

        # Enables the previous page button and disables the next page button if we're on the last embed.
        self.prev_page.disabled = False
        if self.embed_count == len(self.embeds) - 1:
            self.next_page.disabled = True
            self.last_page.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

class DBPlace():
    pass

class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.commanding_save = 10
        self.adding_commands = False
        self.cache_pdb = DBPlace()
        self.cache_db_ttl = TTLCache(maxsize=10000, ttl=60.0)
        self.pool = None
        try:
            self.redis_pool = redis.ConnectionPool(host='localhost', port=6379, db=0)
            self.r = redis.Redis(connection_pool=self.redis_pool)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(
                    host=self.bot.config['mysql']['host'], port=3306, minsize=1, maxsize=2,
                    user=self.bot.config['mysql']['user'], password=self.bot.config['mysql']['password'],
                    db=self.bot.config['mysql']['db'], cursorclass=DictCursor, autocommit=True
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def ai_reload_model_tts(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `ai_tts_models`
                    """
                    await cur.execute(sql,)
                    result_tts_models = await cur.fetchall()
                    if result_tts_models and len(result_tts_models) > 0:
                        tts_models = {}
                        for i in result_tts_models:
                            if i['enable'] == 1:
                                tts_models[i['name']] = i['url']
                        self.bot.other_data['ai_tts_models'] = tts_models.copy()
                        del tts_models
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def get_list_guilds(self):
        result_guilds = []
        list_roles_feature = {}
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_server`
                    """
                    await cur.execute(sql,)
                    result_guilds = await cur.fetchall()

                    sql = """
                    SELECT * FROM `discord_feature_roles`
                    """
                    await cur.execute(sql,)
                    feature_roles = await cur.fetchall()
                    
                    if feature_roles and len(feature_roles) > 0:
                        for each in feature_roles:
                            if each['guild_id'] not in list_roles_feature:
                                list_roles_feature[each['guild_id']] = {}
                            list_roles_feature[each['guild_id']][each['role_id']] = {
                                'faucet_multipled_by': each['faucet_multipled_by'],
                                'guild_vote_multiplied_by': each['guild_vote_multiplied_by'],
                                'faucet_cut_time_percent': each['faucet_cut_time_percent']
                            }
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return {'guilds': result_guilds, 'feature_roles': list_roles_feature}

    async def bot_reload_guilds(self):
        try:
            # re-load guild list
            list_guilds = await self.get_list_guilds()
            if list_guilds.get('guilds') and len(list_guilds['guilds']) > 0:
                guild_data = {}
                for i in list_guilds['guilds']:
                    guild_data[i['serverid']] = i
                    if i['serverid'] in list_guilds.get('feature_roles') and len(list_guilds['feature_roles'][i['serverid']]) > 0:
                        guild_data[i['serverid']]['feature_roles'] = list_guilds['feature_roles'][i['serverid']]
                    else:
                        guild_data[i['serverid']]['feature_roles'] = None
                self.bot.other_data['guild_list'] = guild_data.copy()
                del guild_data
                return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def get_bot_settings(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `bot_settings` """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    res = {}
                    for each in result:
                        res[each['name']] = each['value']
                    return res
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def update_user_balance_call(self, user_id: str, type_coin: str=None):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if type_coin is None:
                        sql = """ UPDATE `erc20_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        sql += """ UPDATE `trc20_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        sql += """ UPDATE `sol_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        sql += """ UPDATE `tezos_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        sql += """ UPDATE `neo_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        sql += """ UPDATE `near_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        sql += """ UPDATE `zil_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        sql += """ UPDATE `vet_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        data_rows = [int(time.time()), user_id]*8
                    elif type_coin.upper() == "ERC-20":
                        sql = """ UPDATE `erc20_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        data_rows = [int(time.time()), user_id]
                    elif type_coin.upper() == "TRC-10" or type_coin.upper() == "TRC-20":
                        sql = """ UPDATE `trc20_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        data_rows = [int(time.time()), user_id]
                    elif type_coin.upper() == "SOL" or type_coin.upper() == "SPL":
                        sql = """ UPDATE `sol_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        data_rows = [int(time.time()), user_id]
                    elif type_coin.upper() == "XTZ":
                        sql = """ UPDATE `tezos_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        data_rows = [int(time.time()), user_id]
                    elif type_coin.upper() == "NEO":
                        sql = """ UPDATE `neo_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        data_rows = [int(time.time()), user_id]
                    elif type_coin.upper() == "NEAR":
                        sql = """ UPDATE `near_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        data_rows = [int(time.time()), user_id]
                    elif type_coin.upper() == "ZIL":
                        sql = """ UPDATE `zil_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        data_rows = [int(time.time()), user_id]
                    elif type_coin.upper() == "VET":
                        sql = """ UPDATE `vet_user` SET `called_Update`=%s WHERE `user_id`=%s; """
                        data_rows = [int(time.time()), user_id]
                    else:
                        return
                    await cur.execute(sql, tuple(data_rows))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("utils " +str(traceback.format_exc()))
        return None

    async def bot_task_logs_add(self, task_name: str, run_at: int):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `bot_task_logs` (`task_name`, `run_at`)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY 
                    UPDATE 
                    `run_at`=VALUES(`run_at`)
                    """
                    await cur.execute(sql, (task_name, run_at))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def bot_task_logs_check(self, task_name: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `bot_task_logs` 
                    WHERE `task_name`=%s ORDER BY `id` DESC LIMIT 1
                    """
                    await cur.execute(sql, task_name)
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def add_command_calls(self):
        if len(self.bot.commandings) <= self.commanding_save:
            return
        if self.adding_commands is True:
            return
        else:
            self.adding_commands = True
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `bot_commanded` 
                    (`guild_id`, `user_id`, `user_server`, `command`, `timestamp`)
                    VALUES (%s, %s, %s, %s, %s)
                    """
                    await cur.executemany(sql, self.bot.commandings)
                    await conn.commit()
                    if cur.rowcount > 0:
                        self.bot.commandings = []
        except Exception:
            traceback.print_exc(file=sys.stdout)
            # could be some length issue
            for each in self.bot.commandings:
                if len(each) != 5:
                    self.bot.commandings.remove(each)
                    await logchanbot("[bot_commanded] removed: " +str(each))
        self.adding_commands = False

    async def advert_impress(self, ad_id: int, user_id: str, guild_id: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `bot_advert_list_impression` 
                    (`ad_id`, `date`, `user_id`, `guild`)
                    VALUES (%s, %s, %s, %s);
                    UPDATE `bot_advert_list` SET `numb_impression`=`numb_impression`+1
                    WHERE `id`=%s;
                    """
                    await cur.execute(sql, (ad_id, int(time.time()), user_id, guild_id, ad_id))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def get_trade_channel_list(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_server`
                    WHERE `trade_channel` IS NOT NULL
                        AND `enable_trade`=%s
                    """
                    await cur.execute(sql, "YES")
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    # Recent Activity
    async def recent_tips(
        self, user_id: str, user_server: str, token_name: str, coin_family: str, what: str, limit: int
    ):
        global pool
        coin_name = token_name.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if what.lower() == "withdraw":
                        if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                            sql = """
                            SELECT * FROM `cn_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "BTC":
                            sql = """
                            SELECT * FROM `doge_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "NEO":
                            sql = """
                            SELECT * FROM `neo_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "NEAR":
                            sql = """
                            SELECT * FROM `near_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "NANO":
                            sql = """
                            SELECT * FROM `nano_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "CHIA":
                            sql = """
                            SELECT * FROM `xch_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "ERC-20":
                            sql = """
                            SELECT * FROM `erc20_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "XTZ":
                            sql = """
                            SELECT * FROM `tezos_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "ZIL":
                            sql = """
                            SELECT * FROM `zil_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "VET":
                            sql = """
                            SELECT * FROM `vet_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "VITE":
                            sql = """
                            SELECT * FROM `vite_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "TRC-20":
                            sql = """
                            SELECT * FROM `trc20_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "HNT":
                            sql = """
                            SELECT * FROM `hnt_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "XRP":
                            sql = """
                            SELECT * FROM `xrp_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "XLM":
                            sql = """
                            SELECT * FROM `xlm_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "COSMOS":
                            sql = """
                            SELECT * FROM `cosmos_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s AND `success`=1
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "ADA":
                            sql = """
                            SELECT * FROM `xlm_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "SOL" or coin_family == "SPL":
                            sql = """
                            SELECT * FROM `sol_external_tx` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                            ORDER BY `date` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                    elif what.lower() == "deposit":
                        if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                            sql = """
                            SELECT a.*, b.*
                            FROM cn_user_paymentid a
                                INNER JOIN cn_get_transfers b
                                    ON a.paymentid = b.payment_id
                            WHERE a.user_id=%s AND a.user_server=%s and a.coin_name=%s
                            ORDER BY b.time_insert DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "BTC":
                            sql = """
                            SELECT a.*, b.*
                            FROM doge_user a
                                INNER JOIN doge_get_transfers b
                                    ON a.balance_wallet_address = b.address
                            WHERE a.user_id=%s AND a.user_server=%s and a.coin_name=%s
                            ORDER BY b.time_insert DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "NEO":
                            sql = """
                            SELECT a.*, b.*
                            FROM neo_user a
                                INNER JOIN neo_get_transfers b
                                    ON a.balance_wallet_address = b.address
                            WHERE a.user_id=%s AND a.user_server=%s and b.coin_name=%s
                            ORDER BY b.time_insert DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "NEAR":
                            sql = """
                            SELECT * 
                            FROM `near_move_deposit`
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "NANO":
                            sql = """
                            SELECT * 
                            FROM `nano_move_deposit`
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "CHIA":
                            sql = """
                            SELECT a.*, b.*
                            FROM xch_user a
                                INNER JOIN xch_get_transfers b
                                    ON a.balance_wallet_address = b.address
                            WHERE a.user_id=%s AND a.user_server=%s and b.coin_name=%s
                            ORDER BY b.time_insert DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "ERC-20":
                            sql = """
                            SELECT * 
                            FROM `erc20_move_deposit` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "XTZ":
                            sql = """
                            SELECT * 
                            FROM `tezos_move_deposit`
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "ZIL":
                            sql = """
                            SELECT * 
                            FROM `zil_move_deposit` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "VET":
                            sql = """
                            SELECT * 
                            FROM `vet_move_deposit`
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "VITE":
                            sql = """
                            SELECT * 
                            FROM `vite_get_transfers`
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "TRC-20":
                            sql = """
                            SELECT * 
                            FROM `trc20_move_deposit`
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "HNT":
                            sql = """
                            SELECT * 
                            FROM `hnt_get_transfers`
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "XRP":
                            sql = """
                            SELECT * 
                            FROM `xrp_get_transfers` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "XLM":
                            sql = """
                            SELECT * 
                            FROM `xlm_get_transfers` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "COSMOS":
                            sql = """
                            SELECT * 
                            FROM `cosmos_get_transfers` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "ADA":
                            sql = """
                            SELECT * 
                            FROM `ada_get_transfers`
                            WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name))
                            result = await cur.fetchall()
                            if result:
                                return result
                        elif coin_family == "SOL" or coin_family == "SPL":
                            sql = """
                            SELECT * 
                            FROM `sol_move_deposit` 
                            WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                            ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                            await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                            result = await cur.fetchall()
                            if result:
                                return result
                    elif what.lower() == "receive":
                        sql = """ SELECT * FROM `user_balance_mv` 
                        WHERE `to_userid`=%s AND `user_server`=%s AND `token_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif what.lower() == "expense":
                        sql = """ SELECT * FROM `user_balance_mv` 
                        WHERE `from_userid`=%s AND `user_server`=%s AND `token_name`=%s AND `to_userid`<>%s
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name, "TRADE"))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif what.lower() == "cexswaplp":
                        sql = """
                        SELECT `cexswap_distributing_fee`.*, `cexswap_pools`.`pairs`, `cexswap_pools`.`pool_id` FROM `cexswap_distributing_fee`
                        INNER JOIN `cexswap_pools` ON `cexswap_distributing_fee`.`pool_id`=`cexswap_pools`.`pool_id`
                        WHERE `cexswap_distributing_fee`.`distributed_user_id`=%s AND `cexswap_distributing_fee`.`got_ticker`=%s 
                            AND `cexswap_distributing_fee`.`distributed_user_server`=%s 
                        ORDER BY `cexswap_distributing_fee`.`date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, coin_name, user_server))
                        result = await cur.fetchall()
                        if result:
                            return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []
    # End of recent activity

    # bidding
    async def get_all_bids(self, status: str="ONGOING"):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_bidding_list` 
                    WHERE `status`=%s
                    """
                    await cur.execute(sql, status)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_bid_id(self, message_id: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_bidding_list` 
                    WHERE `message_id`=%s LIMIT 1
                    """
                    await cur.execute(sql, message_id)
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    async def get_bid_attendant(self, message_id: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_bidding_joined` 
                    WHERE `message_id`=%s ORDER BY `bid_amount` DESC
                    """
                    await cur.execute(sql, message_id)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []

    async def discord_bid_ongoing(self, guild_id: str, status: str = "ONGOING"):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT COUNT(*) AS numb FROM `discord_bidding_list` 
                    WHERE `guild_id`=%s AND `status`=%s
                    """
                    await cur.execute(sql, (
                        guild_id, status
                        )
                    )
                    result = await cur.fetchone()
                    if result:
                        return result['numb']
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return 0
    
    async def discord_bid_cancel(
        self, message_id: str,
        user_id: str, guild_id: str, channel_id: str,
        list_balance_updates, payment_logs
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    UPDATE `discord_bidding_list` 
                    SET `status`=%s
                    WHERE `message_id`=%s LIMIT 1;

                    UPDATE `discord_bidding_joined` 
                    SET `status`=%s
                    WHERE `message_id`=%s;

                    INSERT INTO `discord_bidding_logs`
                    (`type`, `message_id`, `user_id`, `guild_id`, `channel_id`, `time`, `other`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """
                    await cur.execute(sql, (
                        "CANCELLED", message_id, "CANCELLED", message_id,
                        "CANCELLED", message_id, user_id, guild_id, channel_id, int(time.time()), message_id
                    ))
                    await conn.commit()
                    # refund
                    if len(list_balance_updates) > 0:
                        sql = """
                        INSERT INTO `user_balance_mv_data`
                        (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            `balance`=`balance`+VALUES(`balance`),
                            `update_date`=VALUES(`update_date`);
                        """
                        await cur.executemany(sql, list_balance_updates)
                        await conn.commit()
                    if payment_logs is not None and len(payment_logs) > 0:
                        sql = """
                        INSERT INTO `discord_bidding_logs`
                        (`type`, `message_id`, `user_id`, `guild_id`, `channel_id`, `time`, `other`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """
                        await cur.executemany(sql, payment_logs)
                        await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def bid_add_new(
        self, title: str, token_name: str, contract: str, token_decimal: str,
        user_id: str, username: str, message_id: str, channel_id: str, guild_id: str,
        guild_name: str, minimum_amount: float, step_amount: float, message_time: int, 
        bid_open_time: int, status: str, original_name: str, 
        saved_name: str, file_type: str, sha256: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `discord_bidding_list`
                    (`title`, `token_name`, `contract`, `token_decimal`,
                    `user_id`, `username`, `message_id`, `channel_id`, `guild_id`,
                    `guild_name`, `minimum_amount`, `step_amount`, `message_time`, 
                    `bid_open_time`, `status`, `original_name`, 
                    `saved_name`, `file_type`, `sha256`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    data_rows = [
                        title, token_name, contract, token_decimal,
                        user_id, username, message_id, channel_id, guild_id,
                        guild_name, minimum_amount, step_amount, message_time, 
                        bid_open_time, status, original_name, 
                        saved_name, file_type, sha256
                    ]
                    sql += """
                    INSERT INTO `discord_bidding_logs`
                    (`type`, `user_id`, `guild_id`, `channel_id`, `amount`, `token_name`, `time`, `other`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    data_rows += [
                        "CREATE", user_id, guild_id, channel_id, minimum_amount, token_name, int(time.time()), title
                    ]
                    await cur.execute(sql, tuple(data_rows))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def update_bid_failed(self, message_id: str, turn_off: bool=False):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if turn_off is False:
                        sql = """
                        UPDATE `discord_bidding_list` 
                        SET `failed_check`=`failed_check`+1 
                        WHERE `message_id`=%s 
                        LIMIT 1
                        """
                        await cur.execute(sql, message_id)
                        await conn.commit()
                        return True
                    else:
                        # Change status
                        sql = """
                        UPDATE `discord_bidding_list` 
                        SET `status`=%s 
                        WHERE `message_id`=%s 
                        LIMIT 1
                        """
                        await cur.execute(sql, ("CANCELLED", message_id))
                        await conn.commit()
                        return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def update_bid_no_winning(self, message_id: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    UPDATE `discord_bidding_list` 
                    SET `status`=%s 
                    WHERE `message_id`=%s 
                    LIMIT 1;
                    """
                    await cur.execute(sql, ("COMPLETED", message_id))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def update_bid_with_winner(
        self, message_id: str, winner_user_id: str, winner_amount: float,
        list_balance_updates, payment_logs
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    UPDATE `discord_bidding_list` 
                    SET `status`=%s, `winner_user_id`=%s, `winner_amount`=%s, `winning_date`=%s
                    WHERE `message_id`=%s 
                    LIMIT 1;
                    """
                    data_rows = [
                        "COMPLETED", winner_user_id, winner_amount, int(time.time()), message_id
                    ]

                    sql += """
                    UPDATE `discord_bidding_joined`
                    SET `status`=%s WHERE `message_id`=%s AND `user_id`<>%s;
                    """
                    data_rows += [
                        "LOSE", message_id, winner_user_id
                    ]

                    sql += """
                    UPDATE `discord_bidding_joined`
                    SET `status`=%s WHERE `message_id`=%s AND `user_id`=%s;
                    """
                    data_rows += [
                        "WIN", message_id, winner_user_id
                    ]
                    await cur.execute(sql, tuple(data_rows))
                    await conn.commit()
                    # refund to losers
                    if len(list_balance_updates) > 0:
                        sql = """
                        INSERT INTO `user_balance_mv_data`
                        (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            `balance`=`balance`+VALUES(`balance`),
                            `update_date`=VALUES(`update_date`);
                        """
                        await cur.executemany(sql, list_balance_updates)
                        await conn.commit()
                    if payment_logs is not None and len(payment_logs) > 0:
                        sql = """
                        INSERT INTO `discord_bidding_logs`
                        (`type`, `message_id`, `user_id`, `guild_id`, `channel_id`, `time`, `other`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """
                        await cur.executemany(sql, payment_logs)
                        await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def update_bid_winner_instruction(
        self, message_id: str, instruction: str, method_for: str,
        list_balance_updates, payment_logs,
        user_id: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if method_for == "winner":
                        sql = """
                        UPDATE `discord_bidding_list` 
                        SET `winner_instruction`=%s, `winner_instruction_date`=%s, `owner_request_to_update`=%s
                        WHERE `message_id`=%s 
                        LIMIT 1;
                        """
                        data_rows = [
                            instruction, int(time.time()), 0, message_id
                        ]

                        sql += """
                        INSERT INTO `discord_bidding_logs`
                        (`type`, `message_id`, `user_id`, `time`, `other`)
                        VALUES (%s, %s, %s, %s, %s);
                        """
                        data_rows += [
                            "UPDATE INPUT", message_id, user_id, int(time.time()), instruction
                        ]
                        await cur.execute(sql, tuple(data_rows))
                        await conn.commit()
                    elif method_for == "owner":
                        sql = """ UPDATE `discord_bidding_list` 
                        SET `owner_respond`=%s, `owner_respond_date`=%s
                        WHERE `message_id`=%s 
                        LIMIT 1;
                        """
                        data_rows = [
                            instruction, int(time.time()), message_id
                        ]
                        sql += """
                        INSERT INTO `discord_bidding_logs`
                        (`type`, `message_id`, `user_id`, `time`, `other`)
                        VALUES (%s, %s, %s, %s, %s);
                        """
                        data_rows += [
                            "UPDATE INPUT", message_id, user_id, int(time.time()), instruction
                        ]
                        await cur.execute(sql, tuple(data_rows))
                        await conn.commit()
                    elif method_for == "final":
                        sql = """ UPDATE `discord_bidding_list` 
                        SET `winner_confirmation_date`=%s
                        WHERE `message_id`=%s 
                        LIMIT 1;
                        """
                        data_rows = [
                            int(time.time()), message_id
                        ]
                        sql += """
                        INSERT INTO `discord_bidding_logs`
                        (`type`, `message_id`, `user_id`, `time`, `other`)
                        VALUES (%s, %s, %s, %s, %s);
                        """
                        data_rows += [
                            "UPDATE INPUT", message_id, user_id, int(time.time()), "COMPLETED"
                        ]
                        await cur.execute(sql, tuple(data_rows))
                        await conn.commit()
                        if list_balance_updates is not None and len(list_balance_updates) > 0:
                            # update balance
                            sql = """
                            INSERT INTO `user_balance_mv_data`
                            (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                            VALUES (%s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                `balance`=`balance`+VALUES(`balance`),
                                `update_date`=VALUES(`update_date`);
                            """
                            await cur.executemany(sql, list_balance_updates)
                            await conn.commit()

                            # update logs
                            sql = """
                            INSERT INTO `discord_bidding_logs`
                            (`type`, `message_id`, `user_id`, `guild_id`, `channel_id`, `time`, `other`)
                            VALUES (%s, %s, %s, %s, %s, %s, %s);
                            """
                            await cur.executemany(sql, payment_logs)
                            await conn.commit()
                    else:
                        return False
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def discord_bid_max_bid(self, message_id: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_bidding_joined` 
                    WHERE `message_id`=%s ORDER BY `bid_amount` DESC LIMIT 1
                    """
                    await cur.execute(sql, (message_id))
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    async def bid_new_join(
        self, message_id: str, user_id: str, username: str,
        bid_amount: float, bid_coin: str, guild_id: str, channel_id: str,
        user_server: str, additional_amount: float,
        is_extending: bool=False, current_closed_time: int=None
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `discord_bidding_joined` 
                    (`message_id`, `user_id`, `username`, `bid_amount`, `bid_coin`, `bid_time`, `status`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        `bid_amount`=VALUES(`bid_amount`),
                        `status`=%s,
                        `bid_time`=VALUES(`bid_time`);
                    """
                    data_rows = [
                        message_id, user_id, username, bid_amount, bid_coin, int(time.time()), "BID", "REBID"
                    ]
                    sql += """
                    INSERT INTO `discord_bidding_logs`
                    (`type`, `message_id`, `user_id`, `guild_id`, `channel_id`, `time`, `other`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """
                    data_rows += [
                        "BID", message_id, user_id, guild_id, channel_id, int(time.time()), num_format_coin(bid_amount)
                    ]

                    if additional_amount > 0:
                        sql += """
                        INSERT INTO `user_balance_mv_data`
                        (`user_id`, `token_name`, `user_server`, `balance`, `update_date`)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            `balance`=`balance`+VALUES(`balance`),
                            `update_date`=VALUES(`update_date`);
                        """
                        data_rows += [
                            user_id , bid_coin, user_server, -additional_amount, int(time.time())
                        ]
                    if is_extending is True and current_closed_time is not None:
                        sql += """
                        UPDATE `discord_bidding_list`
                        SET `bid_extended_time`=%s, `number_extension`=`number_extension`+1
                        WHERE `message_id`=%s LIMIT 1;
                        """
                        data_rows += [
                            current_closed_time, message_id
                        ]
                    await cur.execute(sql, tuple(data_rows))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def bid_update_desc(
        self, message_id: str, user_id: str,
        description: str, guild_id: str, channel_id: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    UPDATE `discord_bidding_list`
                    SET `description`=%s
                    WHERE `message_id`=%s LIMIT 1;
                    """
                    data_rows = [description, message_id]

                    sql += """
                    INSERT INTO `discord_bidding_logs`
                    (`type`, `message_id`, `user_id`, `guild_id`, `channel_id`, `time`, `other`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """
                    data_rows += [
                        "UPDATE DESC", message_id, user_id, guild_id, channel_id, int(time.time()), description
                    ]
                    await cur.execute(sql, tuple(data_rows))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def bidding_joined_by_userid(self, user_id: str, limit: int=25):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_bidding_joined` 
                    WHERE `user_id`=%s ORDER BY `bid_time` DESC LIMIT %s
                    """
                    await cur.execute(sql, (user_id, limit))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []

    async def bidding_logs_by_userid(self, user_id: str, limit: int=50):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_bidding_logs` 
                    WHERE `user_id`=%s ORDER BY `time` DESC LIMIT %s
                    """
                    await cur.execute(sql, (user_id, limit))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []

    async def bidding_list_by_guildid(self, guild_id: str, limit: int=25):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_bidding_list` 
                    WHERE `guild_id`=%s ORDER BY `message_time` DESC LIMIT %s
                    """
                    await cur.execute(sql, (guild_id, limit))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []

    async def bid_add_report(
        self, user_id: str, username: str, list_message_id: str,
        owner_id: str, channel_id: str, guild_id: str, guild_name: str,
        reported_content: str, how_to_contact: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `discord_bidding_reports`
                    (`user_id`, `username`, `list_message_id`, `owner_id`, `channel_id`,
                    `guild_id`, `guild_name`, `reported_content`, `how_to_contact`, `time`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    data_rows = [
                        user_id, username, list_message_id, owner_id, channel_id, 
                        guild_id, guild_name, reported_content, how_to_contact,
                        int(time.time())
                    ]
                    await cur.execute(sql, tuple(data_rows))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def bid_get_report(self, report_id: int=None):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `discord_bidding_reports`
                    """
                    data_rows = []
                    if report_id is not None:
                        sql += """
                        WHERE `report_id`=%s LIMIT 1
                        """
                        data_rows += [report_id]
                    else:
                        sql += """
                        ORDER BY `time` DESC LIMIT 25
                        """
                    await cur.execute(sql, tuple(data_rows))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []

    async def bid_req_winner_update(
        self, message_id: str, user_id: str,
        channel_id: str, guild_id: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    UPDATE `discord_bidding_list`
                    SET `owner_request_to_update`=%s, `request_to_date`=%s
                    WHERE `message_id`=%s LIMIT 1;
                    """
                    data_rows = [
                        1, int(time.time()), message_id
                    ]
                    sql += """
                    INSERT INTO `discord_bidding_logs`
                    (`type`, `message_id`, `user_id`, `guild_id`, `channel_id`, `time`)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """
                    data_rows += [
                        "OWNER REQUESTS UPDATE", message_id, user_id, guild_id, channel_id, int(time.time())
                    ]
                    await cur.execute(sql, tuple(data_rows))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False
    # end of bidding

    # favorite coins
    async def fav_coin_add(self, user_id: str, user_server: str, coin_name: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `coin_favorites`
                    (`user_id`, `user_server`, `coin_name`)
                    VALUES (%s, %s, %s)
                    """
                    await cur.execute(sql, (user_id, user_server, coin_name))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def fav_coin_remove(self, user_id: str, user_server: str, coin_name: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    DELETE FROM `coin_favorites`
                    WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                    LIMIT 1;
                    """
                    await cur.execute(sql, (user_id, user_server, coin_name))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def check_if_fav_coin(self, user_id: str, user_server: str, coin_name: str=None):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if coin_name is None:
                        sql = """
                        SELECT * FROM `coin_favorites`
                        WHERE `user_id`=%s AND `user_server`=%s
                        """
                        await cur.execute(sql, (user_id, user_server))
                        result = await cur.fetchall()
                        if result:
                            return result
                        else:
                            return []
                    else:
                        sql = """
                        SELECT * FROM `coin_favorites`
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                        LIMIT 1;
                        """
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchone()
                        if result:
                            return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False
    # end of favorite coins

    # price, gecko, etc
    async def gecko_get_coin_db(self, coin_name: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `coin_coingecko_list`
                    WHERE `id`=%s
                    """
                    await cur.execute(sql, coin_name)
                    result = await cur.fetchall()
                    if result:
                        return result
                    else:
                        sql = """
                        SELECT * FROM `coin_coingecko_list`
                        WHERE `name`=%s
                        """
                        result_name = await cur.fetchall()
                        if result_name:
                            return result_name
                        else:
                            sql = """
                            SELECT * FROM `coin_coingecko_list`
                            WHERE `symbol`=%s
                            """
                            await cur.execute(sql, coin_name)
                            result = await cur.fetchall()
                            if result:
                                return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []

    async def gecko_fetch_marketchart_coin(self, coin_name: str):
        try:
            key = 'marketchart_'+coin_name.lower()
            if key in self.bot.other_data and \
                int(time.time()) - self.bot.other_data[key]['fetched_time'] < 5*60:
                return self.bot.other_data[key]['data']
            url = "https://api.coingecko.com/api/v3/coins/" + coin_name + "/market_chart?vs_currency=usd&days=30"
            async with aiohttp.ClientSession() as cs:
                async with cs.get(url, timeout=30) as r:
                    res_data = await r.read()
                    res_data = res_data.decode('utf-8')
                    result = json.loads(res_data)
                    # store cache
                    self.bot.other_data[key] = {"fetched_time": int(time.time()), "data": result} 
                    return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None
    
    async def gecko_fetch_marketdata_coin(self, coin_name: str):
        try:
            key = 'marketdata_'+coin_name.lower()
            if key in self.bot.other_data and \
                int(time.time()) - self.bot.other_data[key]['fetched_time'] < 5*60:
                return self.bot.other_data[key]['data']

            url = "https://api.coingecko.com/api/v3/coins/" + coin_name + "?tickers=false&market_data=true&community_data=false"
            async with aiohttp.ClientSession() as cs:
                async with cs.get(url, timeout=30) as r:
                    res_data = await r.read()
                    res_data = res_data.decode('utf-8')
                    result = json.loads(res_data)
                    # store cache
                    self.bot.other_data['marketdata_'+coin_name.lower()] = {"fetched_time": int(time.time()), "data": result}  
                    return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None
    # end of price, gecko, etc

    # Check if a user lock
    def is_locked_user(self, user_id: str, user_server: str="DISCORD"):
        # Check in table
        try:
            if self.bot.other_data.get('ban_list') and len(self.bot.other_data.get('ban_list')) > 0 and \
                str(user_id) in self.bot.other_data.get('ban_list'):
                return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    # get coin emoji
    def get_coin_emoji(self, coin_name: str, get_link: bool=False):
        coin_emoji = ""
        try:
            coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
            if coin_emoji is None:
                coin_emoji = ""
            else:
                if get_link is True:
                    split_id = coin_emoji.split(":")[2]
                    link = 'https://cdn.discordapp.com/emojis/' + str(split_id.replace(">", "")) + '.gif'
                    return link
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return coin_emoji

    def get_explorer_link(self, coin_name: str, tx: str):
        explorer_link = ""
        try:
            explorer_link = getattr(getattr(self.bot.coin_list, coin_name), "explorer_tx_prefix")
            if explorer_link is None:
                explorer_link = ""
            else:
                explorer_link = "\nLink: <" + explorer_link.replace("{tx_hash_here}", tx) + ">"
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return explorer_link

    async def get_coin_price(self, coin_name: str, source: str):
        try:
            id_gecko = getattr(
                getattr(self.bot.coin_list, coin_name),
                "id_gecko"
            )
            id_paprika = getattr(
                getattr(self.bot.coin_list, coin_name),
                "id_paprika"
            )
            id_cmc = getattr(
                getattr(self.bot.coin_list, coin_name),
                "id_cmc"
            )
            if source == "PAPRIKA":
                coin_name = id_paprika
                try:
                    if coin_name in self.bot.other_data['price_paprika'] and \
                        int(time.time()) - self.bot.other_data['price_paprika'][coin_name]['fetched_time'] < 10*60:
                        return self.bot.other_data['price_paprika'][coin_name]
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                table = self.bot.config['kv_db']['prefix_paprika']
                
            elif source == "GECKO":
                coin_name = id_gecko
                try:
                    if coin_name in self.bot.other_data['price_gecko'] and \
                        int(time.time()) - self.bot.other_data['price_gecko'][coin_name]['fetched_time'] < 10*60:
                        return self.bot.other_data['price_gecko'][coin_name]
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                table = self.bot.config['kv_db']['prefix_gecko']

            price_dict = await self.async_get_cache_kv(
                table,
                "PRICE:" + coin_name.upper()
            )
            if price_dict and type(price_dict) == dict:
                if 'price_'+source.lower() not in self.bot.other_data:
                    self.bot.other_data['price_'+source.lower()] = {}    
                self.bot.other_data['price_'+source.lower()][coin_name] = price_dict
                return price_dict
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    def get_usd_paprika(self, coin_name: str):
        usd_equivalent_enable = getattr(
            getattr(self.bot.coin_list, coin_name),
            "usd_equivalent_enable"
        )
        if usd_equivalent_enable == 1:
            native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
            coin_name_for_price = coin_name
            if native_token_name:
                coin_name_for_price = native_token_name
            per_unit = None
            if coin_name_for_price in self.bot.token_hints:
                id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
            else:
                per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
            if per_unit and per_unit > 0:
                return per_unit
        else:
            return 0

    def get_cache_kv(self, table: str, key: str):
        try:
            if table + "_" + key in self.cache_db_ttl:
                return self.cache_db_ttl[table + "_" + key]
            else:
                res = self.r.get(table + "_" + key)
                result = pickle.loads(res)
                if result is not None:
                    self.cache_db_ttl[table + "_" + key] = result
                    return result
        except TypeError:
            pass
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def async_set_cache_kv(self, table: str, key: str, value):
        try:
            p_mydict = pickle.dumps(value)
            self.r.set(table + "_" + key, p_mydict)
            self.cache_db_ttl[table + "_" + key] = value
            return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def async_get_cache_kv(self, table: str, key: str):
        try:
            if table + "_" + key in self.cache_db_ttl:
                return self.cache_db_ttl[table + "_" + key]
            else:
                res = self.r.get(table + "_" + key)
                result = pickle.loads(res)
                if result is not None:
                    self.cache_db_ttl[table + "_" + key] = result
                    return result
        except TypeError:
            pass
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    def del_cache_kv(self, table: str, key: str):
        try:
            self.r.delete(table + "_" + key)
            return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    # Solana utils
    async def solana_reset_balance_cache(
        self,
        proxy: str,
        timeout: int=60
    ):
        try:
            async with aiohttp.ClientSession() as cs:
                async with cs.get(proxy, timeout=timeout) as r:
                    res_data = await r.read()
                    res_data = res_data.decode('utf-8')
                    result = json.loads(res_data)
                    return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def solana_create_address(
        self,
        proxy: str,
        timeout: int=60
    ):
        try:
            async with aiohttp.ClientSession() as cs:
                async with cs.get(proxy, timeout=timeout) as r:
                    res_data = await r.read()
                    res_data = res_data.decode('utf-8')
                    result = json.loads(res_data)
                    return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def solana_get_balance(
        self,
        proxy: str,
        url: str,
        address: str,
        timeout:int = 60
    ):
        try:
            data = {
                "endpoint": url,
                "address": address
            }
            async with aiohttp.ClientSession() as cs:
                async with cs.post(proxy, json=data, timeout=timeout) as r:
                    res_data = await r.read()
                    res_data = res_data.decode('utf-8')
                    result = json.loads(res_data)
                    return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def solana_send_tx(
        self,
        proxy: str,
        url: str,
        from_key: str,
        to_addr: str,
        atomic_amount: int,
        timeout:int = 60
    ):
        try:
            data = {
                "endpoint": url,
                "from_key": from_key,
                "to_addr": to_addr,
                "atomic_amount": atomic_amount
            }
            async with aiohttp.ClientSession() as cs:
                async with cs.post(proxy, json=data, timeout=timeout) as r:
                    res_data = await r.read()
                    res_data = res_data.decode('utf-8')
                    result = json.loads(res_data)
                    return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def cog_load(self):
        pass

    def cog_unload(self):
        pass

def setup(bot):
    bot.add_cog(Utils(bot))
