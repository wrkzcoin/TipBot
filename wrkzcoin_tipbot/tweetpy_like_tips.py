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

async def update_like(tweet_id: str, response: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `twitter_mentions_timeline` 
                          SET `response_like_json`=%s 
                          WHERE `response_like_json` IS NULL AND `twitter_id`=%s LIMIT 1
                """
                await cur.execute(sql, ( response, tweet_id ) )
                await conn.commit()
                return cur.rowcount
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return 0

# Let's run balance update by a separate process
async def respond_tipping():
    global pool
    time_lap = 30 # seconds

    def api_like_tweet(tweet_id: int):
        consumer_key = os.environ.get('tweet_py_consumer_key')
        consumer_secret = os.environ.get('tweet_py_consumer_secret')

        access_token = os.environ.get('tweet_py_access_token')
        access_token_secret = os.environ.get('tweet_py_access_token_secret')
        
        bearer_token  = os.environ.get('tweet_py_bearer_token')
        try:
            client = tweepy.Client(bearer_token=bearer_token, consumer_key=consumer_key, consumer_secret=consumer_secret, access_token=access_token, access_token_secret=access_token_secret)
            a=client.like(tweet_id=tweet_id)
            return a
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    while True:
        await asyncio.sleep(time_lap)
        try:
            await openConnection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `twitter_mentions_timeline` 
                              WHERE `has_tip`=1 AND `response_like_json` IS NULL 
                              ORDER BY `created_at` ASC """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        if len(result) > 15:
                            msg = "[TWITTER] - has {} tips messages to respond.".format(len(result))
                            logchanbot(msg)
                        for each_msg in result:
                            try:
                                like = api_like_tweet(each_msg['twitter_id'])
                                if like is not None:
                                    await update_like( each_msg['twitter_id'], json.dumps(like) )
                                    msg = "[TWITTER] - Liked tweet ID {} after tipping.".format( each_msg['twitter_id'] )
                                    logchanbot(msg)
                                else:
                                    msg = "[TWITTER] - failed to like {} .".format( each_msg['twitter_id'] )
                                    logchanbot(msg)
                                    await asyncio.sleep(10.0)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                        await asyncio.sleep(3.0)
                    await asyncio.sleep(time_lap)                        
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)


loop = asyncio.get_event_loop()  
loop.run_until_complete(respond_tipping())  
loop.close()

