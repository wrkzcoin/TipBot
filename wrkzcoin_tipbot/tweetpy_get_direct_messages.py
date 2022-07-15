import asyncio
import json
import os
import sys
import time
import traceback

import aiomysql
import tweepy
from aiomysql.cursors import DictCursor
from discord_webhook import DiscordWebhook

from config import config

pool = None
sleep_no_records = 60
bot_id = '1343104498722467845'  # to avoid fetch own message


def logchanbot(content: str):
    try:
        webhook = DiscordWebhook(url=os.environ.get('debug_tipbot_webhook'), content=content[0:1000])
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def openConnection():
    global pool
    try:
        if pool is None:
            pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=2, maxsize=4,
                                              user=config.mysql.user, password=config.mysql.password,
                                              db=config.mysql.db, cursorclass=DictCursor, autocommit=True)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


# Let's run balance update by a separate process
async def fetch_bot_dm():
    global pool
    time_lap = 30  # seconds

    def api_get_direct_messages(count: int = 50):  # max 50
        if count > 50: count = 50
        consumer_key = os.environ.get('tweet_py_consumer_key')
        consumer_secret = os.environ.get('tweet_py_consumer_secret')

        access_token = os.environ.get('tweet_py_access_token')
        access_token_secret = os.environ.get('tweet_py_access_token_secret')

        auth = tweepy.OAuth1UserHandler(
            consumer_key, consumer_secret, access_token, access_token_secret
        )
        api = tweepy.API(auth)
        list_dms = []
        try:
            get_dms = api.get_direct_messages(count=count)
            if get_dms and len(get_dms) > 0:
                list_dms = [each._json for each in get_dms]
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            return None
        return list_dms

    while True:
        i = 0
        await asyncio.sleep(time_lap)
        try:
            await openConnection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT `id`, `message_id` FROM `twitter_fetch_bot_messages` 
                              ORDER BY `id` DESC """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    existing_msg_ids = []
                    if result and len(result) > 0:
                        existing_msg_ids = [each['message_id'] for each in result]
                    get_dm = api_get_direct_messages(count=50)
                    data_rows = []
                    if len(get_dm) > 0:
                        get_dm = sorted(get_dm, key=lambda d: d['id'])
                        fetched_at = int(time.time())
                        for each_msg in get_dm:
                            if len(existing_msg_ids) == 0 or (
                                    len(existing_msg_ids) > 0 and each_msg['id'] not in existing_msg_ids):
                                # Skip its own message
                                if each_msg['message_create']['sender_id'] != bot_id:
                                    data_rows.append((json.dumps(each_msg),
                                                      json.dumps(each_msg['message_create']['message_data']),
                                                      each_msg['message_create']['message_data']['text'],
                                                      each_msg['id'], each_msg['message_create']['sender_id'],
                                                      each_msg['message_create']['target']['recipient_id'],
                                                      int(int(each_msg['created_timestamp']) / 1000), fetched_at))
                        # insert to DB
                        if len(data_rows) > 0:
                            sql = """ INSERT INTO `twitter_fetch_bot_messages` (`message_json_dump`, `message_data_dump`, `text`, `message_id`, `sender_id`, `recipient_id`, `created_timestamp`, `inserted_date`)
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.executemany(sql, data_rows)
                            await conn.commit()
                            if cur.rowcount > 0:
                                msg = "[TWITTER] get_direct_messages - Inserted {} new records...".format(cur.rowcount)
                                logchanbot(msg)
                                print(msg)
                    if len(data_rows) == 0:
                        i += 1
                        if i > 0 and i % 50 == 0:
                            msg = "[TWITTER] - get_direct_messages no new records. Sleep {}s".format(sleep_no_records)
                            logchanbot(msg)
                            print(msg)
                        await asyncio.sleep(sleep_no_records)
                    await asyncio.sleep(time_lap)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)


loop = asyncio.get_event_loop()
loop.run_until_complete(fetch_bot_dm())
loop.close()
