import asyncio
import json
import os
import sys
import time
import traceback

import tweepy
from discord_webhook import DiscordWebhook

import store
from config import load_config

config = load_config()

sleep_no_records = 60


def logchanbot(content: str):
    try:
        webhook = DiscordWebhook(
            url=config['discord']['twitter_webhook'],
            content=content[0:1000]
        )
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

# Let's run balance update by a separate process
async def fetch_latest_status_list():
    time_lap = 15  # seconds

    async def get_list_rt_reward_status():
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    now = int(time.time())
                    sql = """ SELECT DISTINCT (`tweet_link`), `guild_id`, `rt_by_uids`, `rt_counts`, `rt_updated_date`, `id`, `expired_date` FROM `twitter_rt_reward` 
                              WHERE `expired_date`>%s """
                    await cur.execute(sql, (now))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []

    async def list_rt_update(
        rt_by_uids: str, rt_counts: int, guild_id: str, tweet_link: str,
        expired_date: int
    ):  # id_num
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # get list log first
                    given_ids = json.loads(rt_by_uids)
                    data_rows = []
                    sql = """ SELECT * FROM `twitter_rt_reward_logs` 
                              WHERE `guild_id`=%s AND `tweet_link`=%s """
                    await cur.execute(sql, (guild_id, tweet_link))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        ids_ins = [int(each['twitter_id']) for each in result]
                        if len(given_ids) > 0:
                            for each in given_ids:
                                if int(each) not in ids_ins:
                                    data_rows.append((
                                        guild_id, tweet_link, str(each), int(time.time()), expired_dat
                                    ))
                    else:
                        for each in given_ids:
                            data_rows.append((guild_id, tweet_link, str(each), int(time.time()), expired_date))
                    sql = """ UPDATE `twitter_rt_reward` 
                              SET `rt_by_uids`=%s, `rt_counts`=%s, `rt_updated_date`=%s 
                              WHERE `tweet_link`=%s AND `guild_id`=%s LIMIT 1;
                              """
                    await cur.execute(sql, (rt_by_uids, rt_counts, int(time.time()), tweet_link, guild_id))
                    if len(data_rows) > 0:
                        sql = """ INSERT INTO `twitter_rt_reward_logs` (`guild_id`, `tweet_link`, `twitter_id`, `rewarded_date`, `expired_date`)
                                  VALUES (%s, %s, %s, %s, %s)
                              """
                        await cur.executemany(sql, data_rows)
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    def g_status(list_status_ids):
        try:
            auth = tweepy.OAuth1UserHandler(
                os.environ.get('tweet_py_consumer_key'),
                os.environ.get('tweet_py_consumer_secret'),
                os.environ.get('tweet_py_access_token'),
                os.environ.get('tweet_py_access_token_secret')
            )
            api = tweepy.API(auth)
            get_stats = api.lookup_statuses(id=list_status_ids)
        except tweepy.errors.TooManyRequests as e:
            print("[TWITTER] - tweepy.errors.TooManyRequests g_status")
            time.sleep(60.0)
            return None
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            time.sleep(30.0)
            return None
        return get_stats

    def g_rt(id_n: int):
        try:
            auth = tweepy.OAuth1UserHandler(
                os.environ.get('tweet_py_consumer_key'),
                os.environ.get('tweet_py_consumer_secret'),
                os.environ.get('tweet_py_access_token'),
                os.environ.get('tweet_py_access_token_secret')
            )
            api = tweepy.API(auth)
            get_rt = api.get_retweeter_ids(id=id_n, count=100)
        except tweepy.errors.TooManyRequests as e:
            print("[TWITTER] - tweepy.errors.TooManyRequests g_rt")
            time.sleep(60.0)
            return None
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            time.sleep(30.0)
            return None
        return get_rt

    while True:
        i = 0
        await asyncio.sleep(time_lap)
        try:
            # get list subscribe to download
            get_list = await get_list_rt_reward_status()
            if get_list and len(get_list) > 0:
                try:
                    list_ids = [int(each['tweet_link'].split("/")[-1]) for each in get_list]
                    existing_list = {}
                    twitter_status_id = {}
                    expired_date = {}
                    for each_one in get_list:
                        existing_list[each_one['tweet_link'].split("/")[-1]] = each_one
                        twitter_status_id[each_one['tweet_link'].split("/")[-1]] = each_one['tweet_link']
                        expired_date[each_one['tweet_link'].split("/")[-1]] = each_one['expired_date']

                    fetch_st = g_status(list_ids)
                    if fetch_st and len(fetch_st) > 0:
                        for each_status in fetch_st:
                            try:
                                each_status_json = each_status._json
                                if each_status_json and each_status_json['retweet_count'] > 0:
                                    # get list retweet by ID
                                    fetch_rt = g_rt(each_status_json['id'])
                                    # print(twitter_status_id[str(each_status_json['id'])])
                                    # print(fetch_rt is not None and len(fetch_rt) > 0 and len(fetch_rt) > existing_list[str(each_status_json['id'])]['rt_counts'])
                                    # print(each_status_json['retweet_count'])
                                    if fetch_rt is not None and len(fetch_rt) > 0 and len(fetch_rt) > \
                                            existing_list[str(each_status_json['id'])]['rt_counts']:
                                        # Update
                                        update = await list_rt_update(
                                            json.dumps(fetch_rt),
                                            each_status_json['retweet_count'],
                                            existing_list[str(each_status_json['id'])]['guild_id'],
                                            twitter_status_id[str(each_status_json['id'])],
                                            expired_date[str(each_status_json['id'])]
                                        )
                                    else:
                                        await asyncio.sleep(5.0)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                    else:
                        await asyncio.sleep(5.0)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(fetch_latest_status_list())
loop.close()
