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

from cogs.wallet import WalletAPI
from config import load_config

config = load_config()

pool = None
sleep_no_records = 60
bot_id = '1343104498722467845'  # to avoid fetch own message
prefix_command_dm = ('deposit', 'balance', 'withdraw', 'donate', 'help')


def logchanbot(content: str):
    try:
        webhook = DiscordWebhook(
            url=config['discord']['twitter_webhook'],
            content=content[0:1000]
        )
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def openConnection():
    global pool
    try:
        if pool is None:
            pool = await aiomysql.create_pool(
                host=config['mysql']['host'], port=3306, minsize=1, maxsize=2,
                user=config['mysql']['user'], password=config['mysql']['password'],
                db=config['mysql']['db'], cursorclass=DictCursor, autocommit=True
            )
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def update_reply(message_id: str, replied_text: str, replied_json_dump: str, replied_date: int):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `twitter_fetch_bot_messages` 
                          SET `replied_text`=%s, `replied_json_dump`=%s, `replied_date`=%s 
                          WHERE `message_id`=%s AND `replied_date` IS NULL LIMIT 1
                """
                await cur.execute(sql, (replied_text, replied_json_dump, replied_date, message_id))
                await conn.commit()
                return cur.rowcount
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return 0


# Let's run balance update by a separate process
async def fetch_bot_dm():
    global pool
    time_lap = 15  # seconds

    def api_send_direct_message(recipient_id: int, text: str):
        consumer_key = os.environ.get('tweet_py_consumer_key')
        consumer_secret = os.environ.get('tweet_py_consumer_secret')

        access_token = os.environ.get('tweet_py_access_token')
        access_token_secret = os.environ.get('tweet_py_access_token_secret')

        auth = tweepy.OAuth1UserHandler(
            consumer_key, consumer_secret, access_token, access_token_secret
        )
        api = tweepy.API(auth)
        try:
            send_msg = api.send_direct_message(recipient_id=recipient_id, text=text)
            return send_msg._json
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    while True:
        await asyncio.sleep(time_lap)
        try:
            await openConnection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `twitter_fetch_bot_messages` 
                              WHERE `draft_response_text` IS NOT NULL AND `replied_date` IS NULL 
                              ORDER BY `created_timestamp` ASC """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    i = 0
                    if result and len(result) > 0:
                        if len(result) > 0:
                            msg = "[TWITTER] - send_direct_message has {} messages to respond.".format(len(result))
                            logchanbot(msg)
                        for each_msg in result:
                            try:
                                send_msg = api_send_direct_message(int(each_msg['sender_id']),
                                                                   text=each_msg['draft_response_text'])
                                if send_msg:
                                    await update_reply(each_msg['message_id'],
                                                       send_msg['message_create']['message_data']['text'],
                                                       json.dumps(send_msg),
                                                       int(int(send_msg['created_timestamp']) / 1000))
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            msg = "[TWITTER] - send_direct_message responded to a user message_id: {} ".format(
                                each_msg['message_id'])
                            logchanbot(msg)
                        await asyncio.sleep(3.0)
                    else:
                        i += 1
                        if i > 0 and i % 50 == 0:
                            msg = "[TWITTER] - send_direct_message nothing to respond. Sleep {}s".format(
                                sleep_no_records)
                            logchanbot(msg)
                            print(msg)
                        await asyncio.sleep(sleep_no_records)
                    await asyncio.sleep(time_lap)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(fetch_bot_dm())
loop.close()

