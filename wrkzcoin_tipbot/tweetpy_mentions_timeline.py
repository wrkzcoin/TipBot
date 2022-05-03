import traceback, sys
import os

import tweepy
import asyncio
import aiomysql
from aiomysql.cursors import DictCursor
from datetime import datetime
import time
import json
from discord_webhook import DiscordWebhook

from config import config
pool=None
sleep_no_records=60

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
async def fetch_bot_timeline():
    global pool
    time_lap = 10 # seconds

    def api_mentions_timeline(count: int, since_id: int=None):
        consumer_key = os.environ.get('tweet_py_consumer_key')
        consumer_secret = os.environ.get('tweet_py_consumer_secret')

        access_token = os.environ.get('tweet_py_access_token')
        access_token_secret = os.environ.get('tweet_py_access_token_secret')

        auth = tweepy.OAuth1UserHandler(
           consumer_key, consumer_secret, access_token, access_token_secret
        )
        api = tweepy.API(auth)
        list_mentions = []
        try:
            if since_id:
                get_mentions = api.mentions_timeline(since_id=since_id, count=count)
                if get_mentions and len(get_mentions) > 0:
                    list_mentions = [each._json for each in get_mentions]
            else:
                get_mentions = api.mentions_timeline(count=count)
                if get_mentions and len(get_mentions) > 0:
                    list_mentions = [each._json for each in get_mentions]
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            return None
        return list_mentions

    while True:
        await asyncio.sleep(time_lap)
        try:
            i = 0
            await openConnection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `twitter_mentions_timeline` 
                              ORDER BY `id` DESC LIMIT 1 """
                    await cur.execute(sql,)
                    result = await cur.fetchone()
                    get_mentions = []
                    if result:
                        # there are records, get the latest ID to fetch
                        get_mentions = api_mentions_timeline(count=200, since_id=result['twitter_id'])
                    else:
                        # there is no record, fetch from the begining
                        get_mentions = api_mentions_timeline(count=200)
                    if len(get_mentions) > 0:
                        get_mentions = sorted(get_mentions, key=lambda d: d['id'])
                        data_rows = []
                        fetched_at = int(time.time())
                        for each_rec in get_mentions:
                            int_timestamp = int(datetime.strptime(each_rec['created_at'],'%a %b %d %H:%M:%S +0000 %Y').timestamp())
                            user_mentions = None
                            if len(each_rec['entities']['user_mentions']) > 0:
                                user_mentions = json.dumps(each_rec['entities']['user_mentions'])
                            data_rows.append( ( each_rec['id'], each_rec['id_str'], int_timestamp, each_rec['created_at'], each_rec['text'], user_mentions, json.dumps(each_rec), fetched_at ) )
                        # insert to DB
                        if len(data_rows) > 0:
                            sql = """ INSERT INTO `twitter_mentions_timeline` (`twitter_id`, `twitter_id_str`, `created_at`, `created_at_str`, `text`, `user_mentions_list`, `json_dump`, `fetched_at`)
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.executemany(sql, data_rows )
                            await conn.commit()
                            if cur.rowcount > 0:
                                msg = "[TWITTER] mentions_timeline - Inserted {} new records...".format(cur.rowcount)
                                logchanbot(msg)
                                print(msg)
                    else:
                        i += 1
                        if i > 0 and i % 50 == 0:
                            msg = "[TWITTER] - mentions_timeline no new records. Sleep {}s".format(sleep_no_records)
                            logchanbot(msg)
                            print(msg)
                        await asyncio.sleep(sleep_no_records) 
                    await asyncio.sleep(time_lap)                        
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)


loop = asyncio.get_event_loop()  
loop.run_until_complete(fetch_bot_timeline())  
loop.close()  
