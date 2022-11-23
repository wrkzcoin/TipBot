import sys
import traceback

import json
import aiohttp, asyncio
import disnake
from disnake.ext import commands, tasks
import time
import datetime
import functools
import random

# The selenium module
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from PIL import Image
from io import BytesIO
import os.path
from pyvirtualdisplay import Display
import os
from cachetools import TTLCache

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

from Bot import EMOJI_CHART_DOWN, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_FLOPPY, logchanbot, EMOJI_HOURGLASS_NOT_DONE, SERVER_BOT

import store
from cogs.utils import Utils


# https://api.coinpaprika.com/#tag/Tags/paths/~1tags~1{tag_id}/get

def get_trade_view_by_id(
    display_id: str, selenium_setting, web_url: str, id_coin: str, saved_path: str, option: str = None
):
    timeout = 20
    return_to = None
    file_name = "tradeview_{}_image_{}_{}.png".format(
        id_coin, datetime.datetime.now().strftime("%Y-%m-%d-%H-%M"), option.lower() if option else ""
    )  #
    file_path = saved_path + file_name
    if os.path.exists(file_path):
        return file_name
    try:
        os.environ['DISPLAY'] = display_id
        display = Display(visible=0, size=(1920, 1080))
        display.start()
        # Wait for 20s

        options = Options()
        options.add_argument('--no-sandbox')  # Bypass OS security model
        options.add_argument('--disable-gpu')  # applicable to windows os only
        options.add_argument('start-maximized')  #
        options.add_argument('disable-infobars')
        options.add_argument("--disable-extensions")
        userAgent = selenium_setting['user_agent']
        options.add_argument(f'user-agent={userAgent}')
        options.add_argument("--user-data-dir=chrome-data")
        options.headless = True

        driver = webdriver.Chrome(options=options)
        driver.set_window_position(0, 0)
        driver.set_window_size(selenium_setting['win_w'], selenium_setting['win_h'])

        driver.get(web_url)
        WebDriverWait(driver, timeout).until(
            EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe[id^='tradingview']")))
        ## WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.ID, "tv_chart_container")))
        WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((By.CLASS_NAME, "chart-markup-table")))
        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.CLASS_NAME, "chart-container-border")))

        if option is None:
            time.sleep(5.0)
            # https://stackoverflow.com/questions/8900073/webdriver-screenshot
            # now that we have the preliminary stuff out of the way time to get that image :D
            # element = driver.find_element_by_class_name( "js-rootresizer__contents" ) # find part of the page you want image of

            # driver.switch_to.default_content()
            driver.switch_to.default_content()
            element = driver.find_element(By.ID, "tv_chart_container")
            # Updated switch back to default
        # https://stackoverflow.com/questions/43489391/python-selenium-data-style-name
        elif option.lower() in ["1d", "7d", "1m", "1q", "1y", "5y"]:
            time.sleep(5.0)
            ## elements = driver.find_elements_by_xpath("//div[@data-name=date-ranges-tabs]")
            ## elements = driver.find_elements_by_xpath("//div[contains(@class, 'sliderRow')]")
            # element = driver.find_element_by_xpath("//*[starts-with(@class, 'sliderRow-') and contains(@data-name, 'date-ranges-tabs')]")
            element_date = driver.find_element_by_xpath("//*[starts-with(@class, 'dateRangeExpanded-')]")
            names = element_date.find_elements(By.XPATH, "//*[starts-with(@class, 'item-')]")
            found = False
            for each_i in names:
                if each_i.text == option.lower():
                    each_i.click()
                    found = True
                    break
            time.sleep(5.0)
            driver.switch_to.default_content()
            element = driver.find_element(By.ID, "tv_chart_container")
        location = element.location
        size = element.size
        png = driver.get_screenshot_as_png()  # saves screenshot of entire page

        im = Image.open(BytesIO(png))  # uses PIL library to open image in memory
        left = location['x']
        top = location['y']
        right = location['x'] + size['width']
        bottom = location['y'] + size['height']

        im = im.crop((left, top, right, bottom))  # defines crop points
        im.save(file_path)  # saves new cropped image
        driver.close()  # closes the driver
        return_to = file_name
    except Exception:
        traceback.print_exc(file=sys.stdout)
    finally:
        display.stop()

    return return_to


class Paprika(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)
        self.utils = Utils(self.bot)
        self.paprika_coin_cache = TTLCache(maxsize=2048, ttl=60.0)
        self.paprika_coinlist_cache = TTLCache(maxsize=4, ttl=3600.0)

        # enable trade-view
        # Example: https://coinpaprika.com/trading-view/wrkz-wrkzcoin
        self.tradeview = True
        self.tradeview_url = "https://coinpaprika.com/trading-view/"
        self.tradeview_path = "./discordtip_v2_paprika_tradeview/"
        self.tradeview_static_png = "https://tipbot-static.wrkz.work/discordtip_v2_paprika_tradeview/"
        self.display_list = [f":{str(i)}" for i in range(100, 200)]

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    @tasks.loop(seconds=3600)
    async def fetch_paprika_pricelist(self):
        time_lap = 1800  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "fetch_paprika_pricelist"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        url = "https://api.coinpaprika.com/v1/tickers"
        try:
            print(f"/paprika fetching: {url}")
            async with aiohttp.ClientSession() as cs:
                async with cs.get(url, timeout=30) as r:
                    res_data = await r.read()
                    res_data = res_data.decode('utf-8')
                    decoded_data = json.loads(res_data)
                    update_time = int(time.time())
                    update_date = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
                    if len(decoded_data) > 0:
                        update_list = []
                        for each_coin in decoded_data:
                            try:
                                quote_usd = each_coin['quotes']['USD']
                                ath_date = None

                                if quote_usd['ath_date'] and "." in quote_usd['ath_date']:
                                    ath_date = datetime.datetime.strptime(
                                        quote_usd['ath_date'], '%Y-%m-%dT%H:%M:%S.%fZ'
                                    )
                                elif quote_usd['ath_date'] and "." not in quote_usd['ath_date']:
                                    ath_date = datetime.datetime.strptime(quote_usd['ath_date'], '%Y-%m-%dT%H:%M:%SZ')

                                if "." in each_coin['last_updated']:
                                    last_updated = datetime.datetime.strptime(
                                        each_coin['last_updated'], '%Y-%m-%dT%H:%M:%S.%fZ'
                                    )
                                else:
                                    last_updated = datetime.datetime.strptime(
                                        each_coin['last_updated'], '%Y-%m-%dT%H:%M:%SZ'
                                    )
                                update_list.append((
                                    each_coin['id'], each_coin['symbol'], each_coin['name'],
                                    each_coin['rank'], each_coin['circulating_supply'],
                                    each_coin['total_supply'], each_coin['max_supply'],
                                    quote_usd['price'], update_time, last_updated, quote_usd['price'],
                                    quote_usd['volume_24h'], quote_usd['volume_24h_change_24h'],
                                    quote_usd['market_cap'], quote_usd['market_cap_change_24h'],
                                    quote_usd['percent_change_15m'], quote_usd['percent_change_30m'],
                                    quote_usd['percent_change_1h'], quote_usd['percent_change_6h'],
                                    quote_usd['percent_change_12h'], quote_usd['percent_change_24h'],
                                    quote_usd['percent_change_7d'], quote_usd['percent_change_30d'],
                                    quote_usd['percent_change_1y'], quote_usd['ath_price'], ath_date,
                                    quote_usd['percent_from_price_ath']
                                ))
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                        if len(update_list) > 0:
                            try:
                                await store.openConnection()
                                async with store.pool.acquire() as conn:
                                    async with conn.cursor() as cur:
                                        sql = """ INSERT INTO coin_paprika_list (`id`, `symbol`, `name`, `rank`, `circulating_supply`, `total_supply`, `max_supply`, `price_usd`, `price_time`, `last_updated`, `quotes_USD_price`, `quotes_USD_volume_24h`, `quotes_USD_volume_24h_change_24h`, `quotes_USD_market_cap`, `quotes_USD_market_cap_change_24h`, `quotes_USD_percent_change_15m`, `quotes_USD_percent_change_30m`, `quotes_USD_percent_change_1h`, `quotes_USD_percent_change_6h`, `quotes_USD_percent_change_12h`, `quotes_USD_percent_change_24h`, `quotes_USD_percent_change_7d`, `quotes_USD_percent_change_30d`, `quotes_USD_percent_change_1y`, `quotes_USD_ath_price`, `quotes_USD_ath_date`, `quotes_USD_percent_from_price_ath`) 
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY 
                                        UPDATE 
                                        `rank`=VALUES(`rank`), 
                                        `circulating_supply`=VALUES(`circulating_supply`), 
                                        `total_supply`=VALUES(`total_supply`), 
                                        `max_supply`=VALUES(`max_supply`), 
                                        `price_usd`=VALUES(`price_usd`), 
                                        `price_time`=VALUES(`price_time`), 
                                        `last_updated`=VALUES(`last_updated`), 
                                        `quotes_USD_price`=VALUES(`quotes_USD_price`), 
                                        `quotes_USD_volume_24h`=VALUES(`quotes_USD_volume_24h`), 
                                        `quotes_USD_volume_24h_change_24h`=VALUES(`quotes_USD_volume_24h_change_24h`), 
                                        `quotes_USD_market_cap`=VALUES(`quotes_USD_market_cap`), 
                                        `quotes_USD_market_cap_change_24h`=VALUES(`quotes_USD_market_cap_change_24h`), 
                                        `quotes_USD_percent_change_15m`=VALUES(`quotes_USD_percent_change_15m`), 
                                        `quotes_USD_percent_change_30m`=VALUES(`quotes_USD_percent_change_30m`), 
                                        `quotes_USD_percent_change_1h`=VALUES(`quotes_USD_percent_change_1h`), 
                                        `quotes_USD_percent_change_6h`=VALUES(`quotes_USD_percent_change_6h`), 
                                        `quotes_USD_percent_change_12h`=VALUES(`quotes_USD_percent_change_12h`), 
                                        `quotes_USD_percent_change_24h`=VALUES(`quotes_USD_percent_change_24h`), 
                                        `quotes_USD_percent_change_7d`=VALUES(`quotes_USD_percent_change_7d`), 
                                        `quotes_USD_percent_change_30d`=VALUES(`quotes_USD_percent_change_30d`), 
                                        `quotes_USD_percent_change_1y`=VALUES(`quotes_USD_percent_change_1y`), 
                                        `quotes_USD_ath_price`=VALUES(`quotes_USD_ath_price`), 
                                        `quotes_USD_ath_date`=VALUES(`quotes_USD_ath_date`), 
                                        `quotes_USD_percent_from_price_ath`=VALUES(`quotes_USD_percent_from_price_ath`)
                                        """
                                        await cur.executemany(sql, update_list)
                                        await conn.commit()
                                        update_list = []
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
        except asyncio.TimeoutError:
            print('TIMEOUT: Fetching from coingecko price')
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    async def paprika_coin(
        self,
        ctx,
        coin: str,
        option: str
    ):
        await ctx.response.send_message(f"{EMOJI_HOURGLASS_NOT_DONE} {ctx.author.mention}, checking coinpaprika..")
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, f"/paprika {coin}", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        coin_name = coin.upper()
        key = self.bot.config['kv_db']['prefix_paprika'] + coin.upper()
        # Get from kv
        try:
            if key in self.paprika_coin_cache:
                response_text = self.paprika_coin_cache[key]
                msg = f"{ctx.author.mention}, {response_text}"
                await ctx.edit_original_message(content=msg)
                # fetch tradeview image
                if self.tradeview is True:
                    try:
                        if coin_name in self.bot.token_hints:
                            id = self.bot.token_hints[coin_name]['ticker_name']
                        elif coin_name in self.bot.token_hint_names:
                            id = self.bot.token_hint_names[coin_name]['ticker_name']
                        else:
                            coin_list_key = self.bot.config['kv_db']['prefix_paprika'] + "COINSLIST"
                            if  coin_list_key in self.paprika_coinlist_cache:
                                j = self.paprika_coinlist_cache[coin_list_key]
                            else:
                                link = 'https://api.coinpaprika.com/v1/coins'
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(link) as resp:
                                        if resp.status == 200:
                                            j = await resp.json()
                                            try:
                                                self.paprika_coinlist_cache[coin_list_key] = j
                                            except Exception:
                                                traceback.format_exc()
                            if coin_name.isdigit():
                                for i in j:
                                    if int(coin_name) == int(i['rank']):
                                        id = i['id']
                            else:
                                for i in j:
                                    if coin_name.lower() == i['name'].lower() or coin_name.lower() == i['symbol'].lower():
                                        id = i['id']  # i['name']
                        if len(self.display_list) > 2:
                            display_id = random.choice(self.display_list)
                            self.display_list.remove(display_id)
                            fetch_tradeview = functools.partial(
                                get_trade_view_by_id, display_id, self.bot.config['selenium_setting'], self.tradeview_url + id, id, self.tradeview_path, option
                            )
                            self.display_list.append(display_id)
                            tv_image = await self.bot.loop.run_in_executor(None, fetch_tradeview)
                            if tv_image:
                                e = disnake.Embed(timestamp=datetime.datetime.now(), description=response_text)
                                if option:
                                    e.add_field(name="Range", value=option.lower(), inline=False)
                                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                                e.set_image(url=self.tradeview_static_png + tv_image)
                                e.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
                                await ctx.edit_original_message(content=None, embed=e)
                    except Exception:
                        traceback.format_exc()
                return
        except Exception:
            traceback.format_exc()
            await logchanbot("paprika " +str(traceback.format_exc()))
            msg = f"{ctx.author.mention}, internal error from cache."
            await ctx.edit_original_message(content=msg)
            return

        if coin_name in self.bot.token_hints:
            id = self.bot.token_hints[coin_name]['ticker_name']
        elif coin_name in self.bot.token_hint_names:
            id = self.bot.token_hint_names[coin_name]['ticker_name']
        else:
            coin_list_key = self.bot.config['kv_db']['prefix_paprika'] + "COINSLIST"
            if coin_list_key in self.paprika_coinlist_cache:
                j = self.paprika_coinlist_cache[coin_list_key]
            else:
                link = 'https://api.coinpaprika.com/v1/coins'
                async with aiohttp.ClientSession() as session:
                    async with session.get(link) as resp:
                        if resp.status == 200:
                            j = await resp.json()
                            try:
                                self.paprika_coinlist_cache[coin_list_key] = j
                            except Exception:
                                traceback.format_exc()
            if coin_name.isdigit():
                for i in j:
                    if int(coin_name) == int(i['rank']):
                        id = i['id']
            else:
                for i in j:
                    if coin_name.lower() == i['name'].lower() or coin_name.lower() == i['symbol'].lower():
                        id = i['id']  # i['name']
        try:
            async with aiohttp.ClientSession() as session:
                url = 'https://api.coinpaprika.com/v1/tickers/{}'.format(id)
                print(f"/paprika fetching: {url}")
                async with session.get(url) as resp:
                    if resp.status == 200:
                        j = await resp.json()
                        if 'error' in j and j['error'] == 'id not found':
                            msg = f"{ctx.author.mention}, can not get data **{coin_name}** from paprika."
                            await ctx.edit_original_message(content=msg)
                            return
                        if float(j['quotes']['USD']['price']) > 100:
                            trading_at = "${:.2f}".format(float(j['quotes']['USD']['price']))
                        elif float(j['quotes']['USD']['price']) > 1:
                            trading_at = "${:.3f}".format(float(j['quotes']['USD']['price']))
                        elif float(j['quotes']['USD']['price']) > 0.01:
                            trading_at = "${:.4f}".format(float(j['quotes']['USD']['price']))
                        else:
                            trading_at = "${:.8f}".format(float(j['quotes']['USD']['price']))
                        response_text = "{} ({}) is #{} by marketcap (${:,.2f}), trading at {} with a 24h vol of ${:,.2f}. It's changed {}% over 24h, {}% over 7d, {}% over 30d, and {}% over 1y with an ath of ${} on {}.".format(
                            j['name'], j['symbol'], j['rank'], float(j['quotes']['USD']['market_cap']), trading_at,
                            float(j['quotes']['USD']['volume_24h']), j['quotes']['USD']['percent_change_24h'],
                            j['quotes']['USD']['percent_change_7d'], j['quotes']['USD']['percent_change_30d'],
                            j['quotes']['USD']['percent_change_1y'], j['quotes']['USD']['ath_price'],
                            j['quotes']['USD']['ath_date'])
                        try:
                            self.paprika_coin_cache[key] = response_text
                        except Exception:
                            traceback.format_exc()
                            await logchanbot("paprika " +str(traceback.format_exc()))
                        await ctx.edit_original_message(content=f"{ctx.author.mention}, {response_text}")
                        # fetch tradeview image
                        if self.tradeview is True:
                            try:
                                if coin_name in self.bot.token_hints:
                                    id = self.bot.token_hints[coin_name]['ticker_name']
                                elif coin_name in self.bot.token_hint_names:
                                    id = self.bot.token_hint_names[coin_name]['ticker_name']
                                else:
                                    coin_list_key = self.bot.config['kv_db']['prefix_paprika'] + "COINSLIST"
                                    if coin_list_key in self.paprika_coinlist_cache:
                                        j = self.paprika_coinlist_cache[coin_list_key]
                                    else:
                                        link = 'https://api.coinpaprika.com/v1/coins'
                                        print(f"/paprika fetching: {link}")
                                        async with aiohttp.ClientSession() as session:
                                            async with session.get(link) as resp:
                                                if resp.status == 200:
                                                    j = await resp.json()
                                                    try:
                                                        self.paprika_coinlist_cache[coin_list_key] = j
                                                    except Exception:
                                                        traceback.format_exc()
                                    if coin_name.isdigit():
                                        for i in j:
                                            if int(coin_name) == int(i['rank']):
                                                id = i['id']
                                    else:
                                        for i in j:
                                            if coin_name.lower() == i['name'].lower() or coin_name.lower() == i[
                                                'symbol'].lower():
                                                id = i['id']  # i['name']
                                if len(self.display_list) > 2:
                                    display_id = random.choice(self.display_list)
                                    self.display_list.remove(display_id)
                                    fetch_tradeview = functools.partial(
                                        get_trade_view_by_id, display_id, self.bot.config['selenium_setting'], self.tradeview_url + id, id, self.tradeview_path, option
                                    )
                                    self.display_list.append(display_id)
                                    tv_image = await self.bot.loop.run_in_executor(None, fetch_tradeview)
                                    if tv_image:
                                        e = disnake.Embed(timestamp=datetime.datetime.now(), description=response_text)
                                        if option:
                                            e.add_field(name="Range", value=option.lower(), inline=False)
                                        e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                                        e.set_image(url=self.tradeview_static_png + tv_image)
                                        e.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
                                        await ctx.edit_original_message(content=None, embed=e)
                            except Exception:
                                traceback.format_exc()
                    else:
                        await ctx.edit_original_message(
                            content=f"{ctx.author.mention}, can not get data **{coin_name}** from paprika.")
                    return
        except Exception:
            traceback.format_exc()
        await ctx.edit_original_message(content=f"{ctx.author.mention}, no paprika only salt.")

    @commands.slash_command(
        usage="paprika [coin]",
        options=[
            Option("coin", "Enter coin ticker/name", OptionType.string, required=True),
            Option('range_choice', 'range duration', OptionType.string, required=False, choices=[
                OptionChoice("1d", "1d"),
                OptionChoice("7d", "7d"),
                OptionChoice("1m", "1m"),
                OptionChoice("1q", "1q"),
                OptionChoice("1y", "1y"),
                OptionChoice("5y", "5y")
            ])
        ],
        description="Check coin at Paprika."
    )
    async def paprika(
        self,
        ctx,
        coin: str,
        range_choice: str = None
    ):
        get_pap = await self.paprika_coin(ctx, coin, range_choice)

    @commands.Cog.listener()
    async def on_ready(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.fetch_paprika_pricelist.is_running():
                self.fetch_paprika_pricelist.start()

    async def cog_load(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            if not self.fetch_paprika_pricelist.is_running():
                self.fetch_paprika_pricelist.start()

    def cog_unload(self):
        # Ensure the task is stopped when the cog is unloaded.
        self.fetch_paprika_pricelist.cancel()


def setup(bot):
    bot.add_cog(Paprika(bot))
