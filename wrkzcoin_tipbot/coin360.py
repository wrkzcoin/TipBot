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


def get_coin360():
    global redis_pool, redis_conn
    image_name = None
    key = "TIPBOT:COIN360:MAP"
    try:
        if redis_conn is None: redis_conn = redis.Redis(connection_pool=redis_pool)
        if redis_conn and redis_conn.exists(key):
            image_name = redis_conn.get(key).decode()
            if os.path.exists(config.coin360.static_coin360_path + image_name):
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
        opts.add_argument(config.selenium_setting.user_agent)
        
        driver = webdriver.Chrome()
        driver.set_window_position(0, 0)
        driver.set_window_size(config.selenium_setting.win_w, config.selenium_setting.win_h)

        driver.get(config.coin360.url)
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.ID, "SHA256")))
        WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((By.ID, "EtHash")))

        # https://stackoverflow.com/questions/8900073/webdriver-screenshot
        # now that we have the preliminary stuff out of the way time to get that image :D
        element = driver.find_element_by_id(config.coin360.id_crop) # find part of the page you want image of
        location = element.location
        size = element.size
        png = driver.get_screenshot_as_png() # saves screenshot of entire page

        im = Image.open(BytesIO(png)) # uses PIL library to open image in memory
        left = location['x']
        top = location['y']
        right = location['x'] + size['width']
        bottom = location['y'] + size['height']

        im = im.crop((left, top, right, bottom)) # defines crop points

        file_name = "coin360_{}_image.png".format(str(uuid.uuid4()))
        file_path = config.coin360.static_coin360_path + file_name
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
        if redis_conn: redis_conn.set(key, file_name, ex=config.coin360.duration_redis)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return file_name

