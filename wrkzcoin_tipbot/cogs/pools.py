import sys, traceback
import time
import asyncio
from datetime import datetime

import disnake
from disnake.ext import tasks, commands
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
import aiohttp
import json

from config import config
from Bot import logchanbot, RowButton_row_close_any_message, SERVER_BOT
import store
import redis_utils
from utils import MenuPage


class Pools(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        redis_utils.openRedis()
        self.get_miningpool_coinlist.start()


    async def sql_miningpoolstat_fetch(self, coin_name: str, user_id: str, user_name: str, requested_date: int, \
    respond_date: int, response: str, guild_id: str, guild_name: str, channel_id: str, is_cache: str='NO', user_server: str='DISCORD', using_browser: str='NO'):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `miningpoolstat_fetch` (`coin_name`, `user_id`, `user_name`, `requested_date`, `respond_date`, 
                              `response`, `guild_id`, `guild_name`, `channel_id`, `user_server`, `is_cache`, `using_browser`)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (coin_name, user_id, user_name, requested_date, respond_date, response, guild_id, 
                                            guild_name, channel_id, user_server, is_cache, using_browser))
                    await conn.commit()
                    return True
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return False


    def hhashes(self, num) -> str:
        for x in ['H/s', 'KH/s', 'MH/s', 'GH/s', 'TH/s', 'PH/s', 'EH/s']:
            if num < 1000.0:
                return "%3.1f%s" % (num, x)
            num /= 1000.0
        return "%3.1f%s" % (num, 'TH/s')


    @tasks.loop(seconds=60.0)
    async def get_miningpool_coinlist(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            try:
                async with aiohttp.ClientSession() as cs:
                    async with cs.get(config.miningpoolstat.coinlist_link+"??timestamp="+str(int(time.time())), timeout=config.miningpoolstat.timeout) as r:
                        if r.status == 200:
                            res_data = await r.read()
                            res_data = res_data.decode('utf-8')
                            res_data = res_data.replace("var coin_list = ", "").replace(";", "")
                            decoded_data = json.loads(res_data)
                            key = config.redis.prefix + ":MININGPOOL:"
                            key_hint = config.redis.prefix + ":MININGPOOL:SHORTNAME:"
                            if decoded_data and len(decoded_data) > 0:
                                # print(decoded_data)
                                redis_utils.openRedis()
                                for kc, cat in decoded_data.items():
                                    if not isinstance(cat, int) and not isinstance(cat, str):
                                        for k, v in cat.items():
                                            # Should have no expire.
                                            redis_utils.redis_conn.set((key+k).upper(), json.dumps(v))
                                            redis_utils.redis_conn.set((key_hint+v['s']).upper(), k.upper())
            except asyncio.TimeoutError:
                print('TIMEOUT: Fetching from miningpoolstats')
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
            await asyncio.sleep(time_lap)

    async def get_miningpoolstat_coin(
        self, 
        coin: str
    ):
        COIN_NAME = coin.upper()
        key = config.redis.prefix + ":MININGPOOLDATA:" + COIN_NAME
        if redis_utils.redis_conn.exists(key):
            return json.loads(redis_utils.redis_conn.get(key).decode())
        else:
            try:
                redis_utils.openRedis()
                try:
                    link = config.miningpoolstat.coinapi.replace("COIN_NAME", coin.lower())
                    print(f"Fetching {link}")
                    async with aiohttp.ClientSession() as cs:
                        async with cs.get(link, timeout=config.miningpoolstat.timeout) as r:
                            if r.status == 200:
                                res_data = await r.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                await cs.close()
                                if decoded_data and len(decoded_data) > 0 and 'data' in decoded_data:
                                    redis_utils.redis_conn.set(key, json.dumps(decoded_data), ex=config.miningpoolstat.expired)
                                    return decoded_data
                                else:
                                    print(f'MININGPOOLSTAT: Error {link} Fetching from miningpoolstats')
                                    return None
                except asyncio.TimeoutError:
                    print(f'TIMEOUT: Fetching from miningpoolstats {COIN_NAME}')
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return None


    async def get_pools(
        self,
        ctx,
        coin: str
    ):
        COIN_NAME = coin
        try:
            requested_date = int(time.time())
            if config.miningpoolstat.enable != 1:
                await ctx.response.send_message(f'{ctx.author.mention}, command temporarily disable.')
                return
            key = config.redis.prefix + ":MININGPOOL:" + COIN_NAME
            key_hint = config.redis.prefix + ":MININGPOOL:SHORTNAME:" + COIN_NAME
            if not redis_utils.redis_conn.exists(key):
                if redis_utils.redis_conn.exists(key_hint):
                    COIN_NAME = redis_utils.redis_conn.get(key_hint).decode().upper()
                    key = config.redis.prefix + ":MININGPOOL:" + COIN_NAME
                else:
                    await ctx.response.send_message(f'{ctx.author.mention}, unknown coin **{COIN_NAME}**.')
                    return
            if redis_utils.redis_conn.exists(key):
                # check if already in redis
                key_p = key + ":POOLS" # config.redis.prefix + :MININGPOOL:COIN_NAME:POOLS
                key_data = config.redis.prefix + ":MININGPOOLDATA:" + COIN_NAME
                get_pool_data = None
                is_cache = 'NO'
                if redis_utils.redis_conn.exists(key_data):
                    get_pool_data = json.loads(redis_utils.redis_conn.get(key_data).decode())
                    is_cache = 'YES'
                else:
                    if ctx.author.id not in self.bot.MINGPOOLSTAT_IN_PROCESS:
                        self.bot.MINGPOOLSTAT_IN_PROCESS.append(ctx.author.id)
                    else:
                        await ctx.response.send_message(f'{ctx.author.mention} You have another check of pools stats in progress.')
                        return
                    try:
                        get_pool_data = await self.get_miningpoolstat_coin(COIN_NAME)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        return
                pool_nos_per_page = 8
                if get_pool_data and 'data' in get_pool_data:
                    if len(get_pool_data['data']) == 0:
                        await ctx.response.send_message(f"{ctx.author.name}#{ctx.author.discriminator}, Received 0 length of data for **{COIN_NAME}**.")
                        return
                    elif len(get_pool_data['data']) <= pool_nos_per_page:
                        embed = disnake.Embed(title='Mining Pools for {}'.format(COIN_NAME), description='', timestamp=datetime.now(), colour=7047495)
                        if 'symbol' in get_pool_data:
                            embed.add_field(name="Ticker", value=get_pool_data['symbol'], inline=True)
                        if 'algo' in get_pool_data:
                            embed.add_field(name="Algo", value=get_pool_data['algo'], inline=True)
                        if 'hashrate' in get_pool_data:
                            embed.add_field(name="Hashrate", value=self.hhashes(get_pool_data['hashrate']), inline=True)
                        
                        if len(get_pool_data['data']) > 0:
                            async def sorted_pools(pool_list):
                                # https://web.archive.org/web/20150222160237/stygianvision.net/updates/python-sort-list-object-dictionary-multiple-key/
                                mylist = sorted(pool_list, key=lambda k: -k['hashrate'])
                                return mylist
                            pool_links = ''
                            pool_list = await sorted_pools(get_pool_data['data'])
                            i = 1
                            for each_pool in pool_list:
                                percentage = "[0.00%]"
                                try:
                                    hash_rate = self.hhashes(each_pool['hashrate'])
                                    percentage = "[{0:.2f}%]".format(each_pool['hashrate'] / get_pool_data['hashrate'] * 100)
                                except Exception as e:
                                    pass
                                pool_name = None
                                if 'pool_id' in each_pool:
                                    pool_name = each_pool['pool_id']
                                elif 'text' in each_pool:
                                    pool_name = each_pool['text']
                                if pool_name is None:
                                    pool_name = each_pool['url'].replace("https://", "").replace("http://", "").replace("www", "")
                                pool_links += "#{}. [{}]({}) - {} __{}__\n".format(i, pool_name, each_pool['url'], hash_rate if hash_rate else '0H/s', percentage)
                                i += 1
                            try:
                                embed.add_field(name="Pool List", value=pool_links)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                        embed.add_field(name="OTHER LINKS", value="{} / [Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format("[More pools](https://miningpoolstats.stream/{})".format(COIN_NAME.lower()), config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                        embed.set_footer(text="Data from https://miningpoolstats.stream")
                        try:
                            await ctx.response.send_message(embed=embed, view=RowButton_row_close_any_message())
                            respond_date = int(time.time())
                            await self.sql_miningpoolstat_fetch(COIN_NAME, str(ctx.author.id), 
                                                                '{}#{}'.format(ctx.author.name, ctx.author.discriminator), 
                                                                requested_date, respond_date, json.dumps(get_pool_data), str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM", 
                                                                ctx.guild.name if hasattr(ctx, "guild") and hasattr(ctx.guild, "name") else "DM", 
                                                                str(ctx.channel.id), is_cache, SERVER_BOT, 'NO')
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    else:
                        ## if pool list more than pool_nos_per_page
                        try:                            
                            async def sorted_pools(pool_list):
                                # https://web.archive.org/web/20150222160237/stygianvision.net/updates/python-sort-list-object-dictionary-multiple-key/
                                mylist = sorted(pool_list, key=lambda k: -k['hashrate'])
                                return mylist
                            pool_links = ''
                            pool_list = await sorted_pools(get_pool_data['data'])
                            num_pool = 0
                            all_pages = []
                            for each_pool in pool_list:
                                if num_pool == 0 or num_pool % pool_nos_per_page == 0:
                                    pool_links = ''
                                    page = disnake.Embed(title='Mining Pools for {}'.format(COIN_NAME), description='', timestamp=datetime.now(), colour=7047495)
                                    if 'symbol' in get_pool_data:
                                        page.add_field(name="Ticker", value=get_pool_data['symbol'], inline=True)
                                    if 'algo' in get_pool_data:
                                        page.add_field(name="Algo", value=get_pool_data['algo'], inline=True)
                                    if 'hashrate' in get_pool_data:
                                        page.add_field(name="Hashrate", value=self.hhashes(get_pool_data['hashrate']), inline=True)

                                    page.set_footer(text=f"Requested by: {ctx.author.name}#{ctx.author.discriminator} | Use the reactions to flip pages.")
                                percentage = "[0.00%]"

                                try:
                                    hash_rate = self.hhashes(each_pool['hashrate'])
                                    percentage = "[{0:.2f}%]".format(each_pool['hashrate'] / get_pool_data['hashrate'] * 100)
                                except Exception as e:
                                    pass
                                pool_name = None
                                if 'pool_id' in each_pool:
                                    pool_name = each_pool['pool_id']
                                elif 'text' in each_pool:
                                    pool_name = each_pool['text']
                                if pool_name is None:
                                    pool_name = each_pool['url'].replace("https://", "").replace("http://", "").replace("www", "")
                                pool_links += "#{}. [{}]({}) - {} __{}__\n".format(num_pool+1, pool_name, each_pool['url'], hash_rate if hash_rate else '0H/s', percentage)
                                num_pool += 1
                                if num_pool > 0 and num_pool % pool_nos_per_page == 0:
                                    page.add_field(name="Pool List", value=pool_links)
                                    page.add_field(name="OTHER LINKS", value="{} / [Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format("[More pools](https://miningpoolstats.stream/{})".format(COIN_NAME.lower()), config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                                    page.set_footer(text=f"Data from https://miningpoolstats.stream | Requested by: {ctx.author.name}#{ctx.author.discriminator}")
                                    all_pages.append(page)
                                    if num_pool < len(pool_list):
                                        pool_links = ''
                                        page = disnake.Embed(title='Mining Pools for {}'.format(COIN_NAME), description='', timestamp=datetime.now(), colour=7047495)
                                        if 'symbol' in get_pool_data:
                                            page.add_field(name="Ticker", value=get_pool_data['symbol'], inline=True)
                                        if 'algo' in get_pool_data:
                                            page.add_field(name="Algo", value=get_pool_data['algo'], inline=True)
                                        if 'hashrate' in get_pool_data:
                                            page.add_field(name="Hashrate", value=self.hhashes(get_pool_data['hashrate']), inline=True)
                                        page.set_footer(text=f"Data from https://miningpoolstats.stream | Requested by: {ctx.author.name}#{ctx.author.discriminator}")
                                    else:
                                        page.add_field(name="Pool List", value=pool_links)
                                        page.add_field(name="OTHER LINKS", value="{} / [Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format("[More pools](https://miningpoolstats.stream/{})".format(COIN_NAME.lower()), config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                                        page.set_footer(text=f"Data from https://miningpoolstats.stream | Requested by: {ctx.author.name}#{ctx.author.discriminator}")
                                        all_pages.append(page)
                                        break
                                elif num_pool == len(pool_list):
                                    page.add_field(name="Pool List", value=pool_links)
                                    page.add_field(name="OTHER LINKS", value="{} / [Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format("[More pools](https://miningpoolstats.stream/{})".format(COIN_NAME.lower()), config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                                    page.set_footer(text=f"Data from https://miningpoolstats.stream | Requested by: {ctx.author.name}#{ctx.author.discriminator}")
                                    all_pages.append(page)
                                    break
                            try:
                                view = MenuPage(ctx, all_pages, timeout=30)
                                view.message = await ctx.response.send_message(embed=all_pages[0], view=view)
                                await self.sql_miningpoolstat_fetch(COIN_NAME, str(ctx.author.id), 
                                                                    '{}#{}'.format(ctx.author.name, ctx.author.discriminator), 
                                                                    requested_date, int(time.time()), json.dumps(get_pool_data), str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM", 
                                                                    ctx.guild.name if hasattr(ctx, "guild") and hasattr(ctx.guild, "name") else "DM", 
                                                                    str(ctx.channel.id), is_cache, SERVER_BOT, 'NO')
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    if ctx.author.id in self.bot.MINGPOOLSTAT_IN_PROCESS:
                        self.bot.MINGPOOLSTAT_IN_PROCESS.remove(ctx.author.id)
                else:
                    # Try old way
                    # if not exist, add to queue in redis
                    key_queue = config.redis.prefix + ":MININGPOOL2:QUEUE"
                    if redis_utils.redis_conn.llen(key_queue) > 0:
                        list_coin_queue = redis_utils.redis_conn.lrange(key_queue, 0, -1)
                        if COIN_NAME not in list_coin_queue:
                            redis_utils.redis_conn.lpush(key_queue, COIN_NAME)
                    elif redis_utils.redis_conn.llen(key_queue) == 0:
                        redis_utils.redis_conn.lpush(key_queue, COIN_NAME)
                    try:
                        # loop and waiting for another fetch
                        retry = 0
                        while True:
                            key = config.redis.prefix + ":MININGPOOL2:" + COIN_NAME
                            key_p = key + ":POOLS" # config.redis.prefix + :MININGPOOL2:COIN_NAME:POOLS
                            await asyncio.sleep(5)
                            if redis_utils.redis_conn.exists(key_p):
                                result = json.loads(redis_utils.redis_conn.get(key_p).decode())
                                is_cache = 'NO'
                                try:
                                    embed = disnake.Embed(title='Mining Pools for {}'.format(COIN_NAME), description='', timestamp=datetime.now(), colour=7047495)
                                    i = 0
                                    if result and len(result) > 0:
                                        pool_links = ''
                                        hash_rate = ''
                                        for each in result:
                                            if i < 15 and i < len(result):
                                                if len(each) >= 4:
                                                    hash_list = ['H/s', 'KH/s', 'MH/s', 'GH/s', 'TH/s', 'PH/s', 'EH/s']
                                                    if [ele for ele in hash_list if((ele in each[2]) and ('Hashrate' not in each[2]))]:
                                                        hash_rate = each[2]
                                                    elif [ele for ele in hash_list if((ele in each[3]) and ('Hashrate' not in each[3]))]:
                                                        hash_rate = each[3]
                                                    else:
                                                        hash_rate = ''
                                                    if hash_rate == '' and len(each) >= 5 and [ele for ele in hash_list if((ele in each[4]) and ('Hashrate' not in each[4]))]:
                                                        hash_rate = each[4]
                                                    elif hash_rate == '' and len(each) >= 6 and [ele for ele in hash_list if((ele in each[5]) and ('Hashrate' not in each[5]))]:
                                                        hash_rate = each[5]
                                                    elif hash_rate == '' and len(each) >= 7 and [ele for ele in hash_list if((ele in each[6]) and ('Hashrate' not in each[6]))]:
                                                        hash_rate = each[6]
                                                    pool_links += each[0] + ' ' + each[1] + ' ' + hash_rate + '\n'
                                                else:
                                                    pool_links += each[0] + ' ' + each[1] + '\n'
                                                i += 1
                                        try:
                                            embed.add_field(name="List", value=pool_links)
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
                                    embed.add_field(name="OTHER LINKS", value="{} / [Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format("[More pools](https://miningpoolstats.stream/{})".format(COIN_NAME.lower()), config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                                    embed.set_footer(text="Data from https://miningpoolstats.stream")

                                    await ctx.response.send_message(embed=embed)
                                    respond_date = int(time.time())
                                    await self.sql_miningpoolstat_fetch(COIN_NAME, str(ctx.author.id), 
                                                                        '{}#{}'.format(ctx.author.name, ctx.author.discriminator), 
                                                                        requested_date, respond_date, json.dumps(result), str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM", 
                                                                        ctx.guild.name if hasattr(ctx, "guild") and hasattr(ctx.guild, "name") else "DM", 
                                                                        str(ctx.channel.id), is_cache, SERVER_BOT, 'YES')
                                    break
                                    if ctx.author.id in self.bot.MINGPOOLSTAT_IN_PROCESS:
                                        self.bot.MINGPOOLSTAT_IN_PROCESS.remove(ctx.author.id)
                                    return
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                    if ctx.author.id in self.bot.MINGPOOLSTAT_IN_PROCESS:
                                        self.bot.MINGPOOLSTAT_IN_PROCESS.remove(ctx.author.id)
                                    return
                            elif not redis_utils.redis_conn.exists(key_p):
                                retry += 1
                            if retry >= 5:
                                redis_utils.redis_conn.lrem(key_queue, 0, COIN_NAME)
                                await ctx.response.send_message(f'{ctx.author.mention} We can not fetch data for **{COIN_NAME}**.')
                                break
                                if ctx.author.id in self.bot.MINGPOOLSTAT_IN_PROCESS:
                                    self.bot.MINGPOOLSTAT_IN_PROCESS.remove(ctx.author.id)
                                return
                    except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                        if ctx.author.id in self.bot.MINGPOOLSTAT_IN_PROCESS:
                            self.bot.MINGPOOLSTAT_IN_PROCESS.remove(ctx.author.id)
                        return
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
            if ctx.author.id in self.bot.MINGPOOLSTAT_IN_PROCESS:
                self.bot.MINGPOOLSTAT_IN_PROCESS.remove(ctx.author.id)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.slash_command(usage="pools <coin>",
                            options=[
                                Option("coin", "Enter a coin/ticker name", OptionType.string, required=True)
                            ],
                            description="Check hashrate of a coin.")
    async def pools(
        self, 
        ctx, 
        coin: str
    ):
        COIN_NAME = coin.upper()
        await self.get_pools(ctx, COIN_NAME)


def setup(bot):
    bot.add_cog(Pools(bot))