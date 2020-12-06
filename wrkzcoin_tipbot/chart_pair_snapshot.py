# The standard library modules
# xvfb-run python3 test.py

import os, os.path
import sys, traceback

# The selenium module
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from selenium.webdriver.chrome.options import Options

from xvfbwrapper import Xvfb

import uuid
from PIL import Image
from io import BytesIO

from config import config
import store
from datetime import datetime
import time

# redis
import redis

redis_pool = None
redis_conn = None

def init():
    global redis_pool
    print("PID %d: initializing redis pool..." % os.getpid())
    redis_pool = redis.ConnectionPool(host='localhost', port=6379, decode_responses=True, db=8)


def openRedis():
    global redis_pool, redis_conn
    if redis_conn is None:
        try:
            redis_conn = redis.Redis(connection_pool=redis_pool)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


def get_snapshot_market(market_name: str, link_url_pair: str, filter_by: str, name_id: str, visible_list: str, pair_name: str):
    global redis_pool, redis_conn
    image_name = None
    key = "TIPBOT:CHART:"+market_name.upper()+"_"+pair_name.upper()
    try:
        if redis_conn is None: redis_conn = redis.Redis(connection_pool=redis_pool)
        if redis_conn and redis_conn.exists(key):
            image_name = redis_conn.get(key).decode()
            if os.path.exists(config.chart.static_chart_image_path + image_name):
                return image_name
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

    timeout = 20
    vdisplay = Xvfb()
    vdisplay.start()
    file_name = None
    
    try:
        # https://github.com/cgoldberg/xvfbwrapper
        # launch stuff inside virtual display here.
        # Wait for 20s
        opts = Options()
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option('useAutomationExtension', False)
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument(config.chart.user_agent)
        
        driver = webdriver.Chrome(options=opts)
        driver.set_window_position(0, 0)
        driver.set_window_size(config.chart.win_w, config.chart.win_h)
        driver.get(link_url_pair)            
        if filter_by == "ID":
            for each_id in visible_list.split(","):
                WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((By.ID, each_id)))
        elif filter_by == "NAME":
            for each_name in visible_list.split(","):
                WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((By.NAME, each_name)))
        elif filter_by == "CLASS":
            for each_name in visible_list.split(","):
                WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((By.CLASS_NAME, each_name)))
        if market_name == "BINANCE":
            try:
                # Click X yellow button
                # driver.find_elements_by_class_name("css-odo4pv").click()
                driver.find_element_by_xpath('//div[@class="css-odo4pv"]').click()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        # https://stackoverflow.com/questions/8900073/webdriver-screenshot
        # now that we have the preliminary stuff out of the way time to get that image :D
        if name_id != "NONE":
            if filter_by == "ID":
                element = driver.find_element_by_id(name_id) # find part of the page you want image of
            elif filter_by == "NAME":
                element = driver.find_element_by_name(name_id)
            elif filter_by == "CLASS":
                element = driver.find_element_by_class_name(name_id)
            location = element.location
            size = element.size
            png = driver.get_screenshot_as_png() # saves screenshot of entire page

            im = Image.open(BytesIO(png)) # uses PIL library to open image in memory
            left = location['x']
            top = location['y']
            right = location['x'] + size['width']
            bottom = location['y'] + size['height']

            im = im.crop((left, top, right, bottom)) # defines crop points
        else:
            png = driver.get_screenshot_as_png() # saves screenshot of entire page
            im = Image.open(BytesIO(png)) # uses PIL library to open image in memory
        file_name = "{}_snapshot_to_{}_image.png".format(datetime.now().strftime("%Y-%m-%d"), str(uuid.uuid4()))
        file_path = config.chart.static_chart_image_path + file_name
        im.save(file_path) # saves new cropped image
        driver.close() # closes the driver
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    finally:
        # always either wrap your usage of Xvfb() with try / finally,
        # or alternatively use Xvfb as a context manager.
        # If you don't, you'll probably end up with a bunch of junk in /tmp
        driver.quit()
        vdisplay.stop()
    try:
        openRedis()
        if redis_conn: redis_conn.set(key, file_name, ex=config.chart.duration_redis)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return file_name
