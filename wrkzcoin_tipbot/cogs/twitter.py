import sys, traceback
import time
import asyncio
import json
import functools
import tweepy
import random

import disnake
from disnake.ext import commands, tasks
from decimal import Decimal
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

from datetime import datetime, timezone
import aiomysql
from aiomysql.cursors import DictCursor

from config import config
from Bot import logchanbot, EMOJI_ERROR, EMOJI_RED_NO, SERVER_BOT, num_format_coin, text_to_num, is_ascii, decrypt_string, EMOJI_INFORMATION, DEFAULT_TICKER, NOTIFICATION_OFF_CMD, EMOJI_MONEYFACE, EMOJI_ARROW_RIGHTHOOK, EMOJI_HOURGLASS_NOT_DONE
import store
from cogs.wallet import WalletAPI
import redis_utils
from utils import MenuPage


class Twitter(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        redis_utils.openRedis()
        self.botLogChan = None

        # twitter_auth
        self.twitter_auth = None
        # twitter fetch latest tweet
        self.fetch_latest_tweets.start()
        # fetch reward status
        self.fetch_latest_status_list.start()
        # post to channel
        self.post_tweets.start()
        # twitter fetch latest DM
        # start later
        ## self.fetch_latest_dm.start()
        
        # enable_twitter_tip
        self.enable_twitter_tip = 1
        
        # DB
        self.pool = None


    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=2, maxsize=4, 
                                                       user=config.mysql.user, password=config.mysql.password,
                                                       db=config.mysql.db, cursorclass=DictCursor, autocommit=True)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)
        if self.twitter_auth is None:
            await self.get_twitter_auth()

    async def get_discord_by_twid(self, twid: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `twitter_linkme` WHERE `twitter_screen_name`=%s AND `is_verified`=1 LIMIT 1 """
                    await cur.execute(sql, ( twid ))
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    async def update_reward(self, guild_id: str, amount: float, coin_name: str, coin_decimal: int, added_by_uid: str, added_by_name: str, disable: bool=False, channel: str=None, rt_link: str=None, end_time: int=None):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if disable == True:
                        sql = """ UPDATE `discord_server` SET `rt_reward_amount`=%s, `rt_reward_coin`=%s, `rt_reward_channel`=%s, `rt_link`=%s, `rt_end_timestamp`=%s WHERE `serverid`=%s LIMIT 1 """
                        await cur.execute(sql, ( None, None, None, None, None, guild_id ))
                        await conn.commit()
                        return cur.rowcount
                    else:
                        sql = """ UPDATE `discord_server` SET `rt_reward_amount`=%s, `rt_reward_coin`=%s, `rt_reward_channel`=%s, `rt_link`=%s, `rt_end_timestamp`=%s WHERE `serverid`=%s LIMIT 1;
                                  
                                  INSERT INTO `twitter_rt_reward` (`guild_id`, `reward_amount`, `reward_coin`, `reward_coin_decimal`, `added_by_uid`, `added_by_name`, `reward_to_channel`, `tweet_link`, `added_date`, `expired_date`)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                  """
                        await cur.execute(sql, ( amount, coin_name.upper(), channel, rt_link, end_time, guild_id, 
                                                 guild_id, amount, coin_name.upper(), coin_decimal, added_by_uid, added_by_name, channel, rt_link, int(time.time()), end_time ))
                        await conn.commit()
                        return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def get_reward_guild_link(self, guild_id: str, rt_link: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `twitter_rt_reward` WHERE `guild_id`=%s AND `tweet_link`=%s LIMIT 1 """
                    await cur.execute(sql, ( guild_id, rt_link ))
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_twitter_auth(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `bot_settings` WHERE `name`=%s LIMIT 1 """
                    await cur.execute(sql, ( 'twitter_auth' ))
                    result = await cur.fetchone()
                    if result:
                        self.twitter_auth = json.loads(decrypt_string(result['value']))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def add_fetch_user(self, name: str, requested_by_uid: str, requested_by_name: str, result: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `twitter_fetch_users` (`name`, `result`, `requested_by_uid`, `requested_by_name`, `requested_date`) 
                              VALUE (%s, %s, %s, %s, %s) """
                    await cur.execute(sql, ( name, result, requested_by_uid, requested_by_name, int(time.time()) ))
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return 0

    async def add_fetch_tw(self, id_str: str, user_screen_name: str, status_link: str, text: str, json_dump: str, created_at: int, created_at_str: str, is_retweeted: int, retweet_count: int, favorite_count, refetched_at):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `twitter_fetch_status` (`id_str`, `user_screen_name`, `status_link`, `text`, `json_dump`, `created_at`, `created_at_str`, `retweet_count`, `is_retweeted`, `favorite_count`, `refetched_at`) 
                              VALUE (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
                              ON DUPLICATE KEY 
                              UPDATE 
                              `json_dump`=VALUES(`json_dump`), 
                              `retweet_count`=VALUES(`retweet_count`), 
                              `favorite_count`=VALUES(`favorite_count`), 
                              `refetched_at`=VALUES(`refetched_at`)
                              """
                    await cur.execute(sql, ( id_str, user_screen_name, status_link, text, json_dump, created_at, created_at_str, retweet_count, is_retweeted, favorite_count, refetched_at ))
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return 0

    async def add_fetch_timeline(self, subscribe_to: str, response_dump: str, latest_tweet_id_str: str, latest_created_at: str, latest_full_text: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `twitter_fetch_latest_user_timeline` (`subscribe_to`, `response_dump`, `latest_tweet_id_str`, `latest_created_at`, `latest_full_text`, `fetched_date`) 
                              VALUE (%s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, ( subscribe_to, response_dump, latest_tweet_id_str, latest_created_at, latest_full_text, int(time.time()) ))
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return 0

    async def get_latest_in_timeline(self, subscribe_to: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `twitter_fetch_latest_user_timeline` WHERE `subscribe_to`=%s ORDER BY `fetched_date` DESC LIMIT 1 """
                    await cur.execute(sql, ( subscribe_to ))
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    async def add_guild_sub(self, guild_id: str, subscribe_to: str, subscribe_to_user_id: str, push_to_channel_id: str, added_by_uid: str, added_by_uname: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `twitter_guild_subscribe` (`guild_id`, `subscribe_to`, `subscribe_to_user_id`, `push_to_channel_id`, `added_by_uid`, `added_by_uname`, `added_time`) 
                              VALUE (%s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, ( guild_id, subscribe_to, subscribe_to_user_id, push_to_channel_id, added_by_uid, added_by_uname, int(time.time()) ))
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return 0

    async def del_guild_sub(self, guild_id: str, subscribe_to: str, subscribe_to_user_id: str, added_by_uid: str, added_by_uname: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ DELETE FROM `twitter_guild_subscribe` WHERE `guild_id`=%s AND `subscribe_to`=%s LIMIT 1;
                              INSERT INTO `twitter_guild_unsubscribe` (`guild_id`, `subscribe_to`, `subscribe_to_user_id`, `deleted_by_uid`, `deleted_by_uname`, `date_deleted`) 
                              VALUE (%s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, ( guild_id, subscribe_to, guild_id, subscribe_to, subscribe_to_user_id, added_by_uid, added_by_uname, int(time.time()) ))
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return 0

    async def get_list_subscribe(self, guild_id: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `twitter_guild_subscribe` WHERE `guild_id`=%s """
                    await cur.execute(sql, ( guild_id ) )
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_list_subscribes(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT DISTINCT `subscribe_to_user_id` FROM `twitter_guild_subscribe` """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_list_fetched_tweets(self, lap: int):
        lap = int(time.time()) - lap # last fetched 1hrs
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """   SELECT 
                                    timeline.fetched_date,
                                    guild.guild_id, 
                                    guild.subscribe_to, 
                                    guild.subscribe_to_user_id,
                                    guild.push_to_channel_id,
                                    timeline.response_dump
                                FROM
                                    twitter_guild_subscribe guild
                                INNER JOIN twitter_fetch_latest_user_timeline timeline
                                    ON guild.subscribe_to = timeline.subscribe_to 
                                WHERE timeline.fetched_date>%s 
                                ORDER BY timeline.fetched_date DESC LIMIT 50; """
                    await cur.execute(sql, ( lap )) 
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []

    async def check_tweet_id_posted(self, tweet_id: str, guild_id: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `twitter_posted_guild` WHERE `tweet_id_str`=%s AND `guild_id`=%s LIMIT 1 """
                    await cur.execute(sql, ( tweet_id, guild_id ) )
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    async def add_posted(self, guild_id: str, subscribe_to: str, push_to_channel_id: str, tweet_id_str: str, msg_id: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `twitter_posted_guild` (`guild_id`, `subscribe_to`, `push_to_channel_id`, `tweet_id_str`, `msg_id`, `posted_date`) 
                              VALUE (%s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, ( guild_id, subscribe_to, push_to_channel_id, tweet_id_str, msg_id, int(time.time()) ))
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return 0

    async def get_latest_in_dm(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `twitter_fetch_bot_messages` ORDER BY `created_timestamp` DESC LIMIT 1 """
                    await cur.execute(sql, )
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []

    async def add_bot_dm_messages(self, data_rows):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `twitter_fetch_bot_messages` (`message_json_dump`, `message_data_dump`, `text`, `message_id`, `sender_id`, `recipient_id`, `created_timestamp`, `inserted_date`) 
                              VALUE (%s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.executemany(sql, data_rows )
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return 0

    async def twitter_linkme_add_or_regen(self, discord_user_id: str, discord_user_name: str, secret_key: str, generated_date: int, twitter_screen_name: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `twitter_linkme` (`discord_user_id`, `discord_user_name`, `secret_key`, `generated_date`, `twitter_screen_name`) 
                              VALUE (%s, %s, %s, %s, %s) 
                              ON DUPLICATE KEY 
                              UPDATE 
                              `secret_key`=VALUES(`secret_key`),
                              `generated_date`=VALUES(`generated_date`),
                              `twitter_screen_name`=VALUES(`twitter_screen_name`)
                              """
                    await cur.execute(sql, ( discord_user_id, discord_user_name, secret_key, generated_date, twitter_screen_name ) )
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return 0

    async def twitter_linkme_get_user(self, discord_user_id):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `twitter_linkme` 
                              WHERE `discord_user_id`=%s LIMIT 1
                              """
                    await cur.execute(sql, ( discord_user_id ) )
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def twitter_linkme_update_verify(self, discord_user_id: str, id_str: str, twitter_screen_name: str, status_link: str, text: str, json_dump: str, created_at: int):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `twitter_linkme` 
                              SET `id_str`=%s, `twitter_screen_name`=%s, `status_link`=%s, `text`=%s, `json_dump`=%s, `created_at`=%s, `is_verified`=%s, `verified_date`=%s 
                              WHERE `discord_user_id`=%s LIMIT 1
                              """
                    await cur.execute(sql, (id_str, twitter_screen_name, status_link, text, json_dump, created_at, 1, int(time.time()), discord_user_id ) )
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def twitter_unlink(self, discord_user_id: str, discord_user_name: str, twitter_screen_name: str, is_verified: int):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `twitter_unlinkme` (`discord_user_id`, `discord_user_name`, `twitter_screen_name`, `is_verified`, `unlink_date`)
                              VALUES (%s, %s, %s, %s, %s);
                              
                              DELETE FROM `twitter_linkme` WHERE `discord_user_id`=%s LIMIT 1;
                              """
                    await cur.execute(sql, ( discord_user_id, discord_user_name, twitter_screen_name, is_verified, int(time.time()), discord_user_id ) )
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_list_rt_reward_status(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    now = int(time.time())
                    sql = """ SELECT DISTINCT (`tweet_link`), `guild_id`, `rt_by_uids`, `rt_counts`, `rt_updated_date`, `id`, `expired_date` FROM `twitter_rt_reward` 
                              WHERE `expired_date`>%s """
                    await cur.execute(sql, (now) )
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []

    async def list_rt_update(self, rt_by_uids: str, rt_counts: int, guild_id: str, tweet_link: str, expired_date: int): #id_num
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # get list log first
                    given_ids = json.loads(rt_by_uids)
                    data_rows = []
                    sql = """ SELECT * FROM `twitter_rt_reward_logs` 
                              WHERE `guild_id`=%s AND `tweet_link`=%s """
                    await cur.execute(sql, ( guild_id, tweet_link ) )
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        ids_ins = [int(each['twitter_id']) for each in result]
                        if len(given_ids) > 0:
                            for each in given_ids:
                                if int(each) not in ids_ins:
                                    data_rows.append( ( guild_id, tweet_link, str(each), int(time.time()), expired_date ) )
                    else:
                        for each in given_ids:
                            data_rows.append( ( guild_id, tweet_link, str(each), int(time.time()), expired_date ) )
                    sql = """ UPDATE `twitter_rt_reward` 
                              SET `rt_by_uids`=%s, `rt_counts`=%s, `rt_updated_date`=%s 
                              WHERE `tweet_link`=%s AND `guild_id`=%s LIMIT 1;
                              """
                    await cur.execute(sql, (rt_by_uids, rt_counts, int(time.time()), tweet_link, guild_id ) )
                    if len(data_rows) > 0:
                        sql = """ INSERT INTO `twitter_rt_reward_logs` (`guild_id`, `tweet_link`, `twitter_id`, `rewarded_date`, `expired_date`)
                                  VALUES (%s, %s, %s, %s, %s)
                              """
                        await cur.executemany(sql, data_rows )
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_user(self, user_name: str, by_id: str, by_name: str): #screen_name
        if self.twitter_auth is None:
            await self.get_twitter_auth()
        def g_user(user_name: str):
            try:
                auth = tweepy.OAuth1UserHandler(
                   self.twitter_auth['consumer_key'], 
                   self.twitter_auth['consumer_secret'], 
                   self.twitter_auth['access_token'], 
                   self.twitter_auth['access_token_secret']
                )
                api = tweepy.API(auth)
                user = api.get_user(screen_name=user_name)
            except tweepy.errors.NotFound:
                return None
            return user
        func_get_user = functools.partial(g_user, user_name)
        fetch_user = await self.bot.loop.run_in_executor(None, func_get_user)
        # add to DB
        try:
            await self.add_fetch_user( user_name, by_id, by_name, json.dumps(fetch_user._json) if fetch_user is not None else None )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return fetch_user

    async def get_tweet(self, tweet_id_str: str): #screen_name
        if self.twitter_auth is None:
            await self.get_twitter_auth()
        def g_tweet(id_str: str):
            try:
                auth = tweepy.OAuth1UserHandler(
                   self.twitter_auth['consumer_key'], 
                   self.twitter_auth['consumer_secret'], 
                   self.twitter_auth['access_token'], 
                   self.twitter_auth['access_token_secret']
                )
                api = tweepy.API(auth)
                get_stats = api.lookup_statuses(id=[int(id_str)])
                return get_stats
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return []
            
        func_get_tw = functools.partial(g_tweet, tweet_id_str)
        fetch_tw = await self.bot.loop.run_in_executor(None, func_get_tw)
        # add to DB
        tweet = None
        try:
            tweet = fetch_tw[0]._json
            int_timestamp = int(datetime.strptime(tweet['created_at'],'%a %b %d %H:%M:%S +0000 %Y').timestamp())
            is_rt = 0
            if tweet['retweeted'] == True:
                is_rt = 1
            await self.add_fetch_tw( tweet_id_str, tweet['user']['screen_name'], "https://twitter.com/{}/status/{}".format(tweet['user']['screen_name'], tweet_id_str), tweet['text'], json.dumps(tweet), int_timestamp, tweet['created_at'], is_rt, tweet['retweet_count'], tweet['favorite_count'], int(time.time())  )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return tweet

    @tasks.loop(seconds=60.0)
    async def post_tweets(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        await asyncio.sleep(time_lap)
        get_latest_tweets = await self.get_list_fetched_tweets(3600)
        if len(get_latest_tweets) > 0:
            for each_tw in get_latest_tweets:
                # Check if this already posted.
                json_t = json.loads(each_tw['response_dump'])
                if len(json_t) > 0:
                    for each_t in json_t:
                        # Check if the post very old.. like 24h?
                        posted_timestamp = int(datetime.strptime(each_t['created_at'],'%a %b %d %H:%M:%S +0000 %Y').timestamp())
                        if posted_timestamp + 24*3600 < int(time.time()):
                            continue
                        else:
                            # less than 1 day, check if already posted.
                            check_tw = await self.check_tweet_id_posted(each_t['id_str'], each_tw['guild_id'])
                            if check_tw is None:
                                # Post and add to record...
                                try:
                                    # find the guild/channel
                                    channel = self.bot.get_channel(int(each_tw['push_to_channel_id']))
                                    if channel:
                                        embed = disnake.Embed(title = "New Tweet by {}!".format(each_t['user']['name']), timestamp=datetime.strptime(each_t['created_at'],'%a %b %d %H:%M:%S +0000 %Y').replace(tzinfo=timezone.utc))
                                        embed.add_field(name="Tweet", value=each_t['full_text'], inline=False)
                                        embed.add_field(name="Link", value="<https://twitter.com/{}/status/{}>".format(each_t['user']['screen_name'], each_t['id_str']), inline=False)
                                        embed.add_field(name="Usage", value="```With /twitter```", inline=False)
                                        try:
                                            if 'profile_image_url_https' in each_t['user'] and each_t['user']['profile_image_url_https'].startswith("https://"):
                                                avatar_url = each_t['user']['profile_image_url_https']
                                                embed.set_author(name=each_t['user']['screen_name'], icon_url=avatar_url)
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
                                        msg = await channel.send(embed=embed)
                                        await self.add_posted( each_tw['guild_id'], each_tw['subscribe_to'], each_tw['push_to_channel_id'], each_t['id_str'], str(msg.id) )
                                        await logchanbot("[TWITTER] - Posted to guild {} / channel {}:```{}```".format(each_tw['guild_id'], each_tw['push_to_channel_id'], each_t['full_text'] ))
                                    else:
                                        await logchanbot("[TWITTER] - Failed to find channel {} in guild {} for posting.".format(each_tw['push_to_channel_id'], each_tw['guild_id'] ))
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def fetch_latest_status_list(self):
        time_lap = 5 # seconds
        await self.bot.wait_until_ready()
        await asyncio.sleep(time_lap)

        if self.twitter_auth is None:
            await self.get_twitter_auth()
        def g_status(list_status_ids):
            try:
                auth = tweepy.OAuth1UserHandler(
                   self.twitter_auth['consumer_key'], 
                   self.twitter_auth['consumer_secret'], 
                   self.twitter_auth['access_token'], 
                   self.twitter_auth['access_token_secret']
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
                   self.twitter_auth['consumer_key'], 
                   self.twitter_auth['consumer_secret'], 
                   self.twitter_auth['access_token'], 
                   self.twitter_auth['access_token_secret']
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
        # get list subscribe to download
        get_list = await self.get_list_rt_reward_status()
        if get_list and len(get_list) > 0:
            rt_lists = {}
            try:
                list_ids = [int(each['tweet_link'].split("/")[-1]) for each in get_list]
                existing_list = {}
                twitter_status_id = {}
                expired_date = {}
                for each_one in get_list:
                    existing_list[each_one['tweet_link'].split("/")[-1]] = each_one
                    twitter_status_id[each_one['tweet_link'].split("/")[-1]] = each_one['tweet_link']
                    expired_date[each_one['tweet_link'].split("/")[-1]] = each_one['expired_date']
                func_get_st = functools.partial(g_status, list_ids)
                fetch_st = await self.bot.loop.run_in_executor(None, func_get_st)
                if fetch_st and len(fetch_st) > 0:
                    for each_status in fetch_st:
                        try:
                            each_status_json = each_status._json
                            if each_status_json and each_status_json['retweet_count'] > 0:
                                # get list retweet by ID
                                func_get_rt = functools.partial(g_rt, each_status_json['id'])
                                fetch_rt = await self.bot.loop.run_in_executor(None, func_get_rt)
                                if fetch_rt is not None and len(fetch_rt) > 0 and len(fetch_rt) > existing_list[str(each_status_json['id'])]['rt_counts']:
                                    # Update
                                    update = await self.list_rt_update( json.dumps(fetch_rt), each_status_json['retweet_count'], existing_list[str(each_status_json['id'])]['guild_id'], twitter_status_id[str(each_status_json['id'])], expired_date[str(each_status_json['id'])] )
                                else:
                                    await asyncio.sleep(5.0)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                else:
                    await asyncio.sleep(5.0)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def fetch_latest_tweets(self):
        time_lap = 10 # seconds
        await self.bot.wait_until_ready()
        await asyncio.sleep(time_lap)

        if self.twitter_auth is None:
            await self.get_twitter_auth()
        def g_tweets(user_name: str, count: int=20):
            try:
                auth = tweepy.OAuth1UserHandler(
                   self.twitter_auth['consumer_key'], 
                   self.twitter_auth['consumer_secret'], 
                   self.twitter_auth['access_token'], 
                   self.twitter_auth['access_token_secret']
                )
                api = tweepy.API(auth)
                response = api.user_timeline(screen_name=user_name, 
                                           # 200 is the maximum allowed count
                                           count=count,
                                           include_rts = False,
                                           # Necessary to keep full_text 
                                           # otherwise only the first 140 words are extracted
                                           tweet_mode = 'extended'
                                           )
            except Exception as e:
                return None
            return response

        # get list subscribe to download
        get_list = await self.get_list_subscribes()
        if len(get_list) > 0:
            for each_sub in get_list:
                try:
                    old_time = 0
                    latest_tweet_id_str = None
                    latest_full_text = None
                    func_tweets = functools.partial(g_tweets, each_sub['subscribe_to_user_id'], 20)
                    fetch_tweets = await self.bot.loop.run_in_executor(None, func_tweets)
                    if fetch_tweets is None:
                        user = each_sub['subscribe_to_user_id']
                        await logchanbot(f"[TWITTER] - Fetch @{user} doesn't get any response.")
                        await asyncio.sleep(time_lap)
                        continue
                    else:
                        tweets = []
                        if len(fetch_tweets) > 0:
                            for each_t in fetch_tweets:
                                tweets.append(each_t._json)
                                new_timestamp = int(datetime.strptime(each_t._json['created_at'],'%a %b %d %H:%M:%S +0000 %Y').timestamp())
                                if new_timestamp > old_time:
                                    old_time = new_timestamp
                                    latest_tweet_id_str = each_t._json['id_str']
                                    latest_full_text = each_t._json['full_text']
                        twitter_link = "https://twitter.com/{}".format(each_sub['subscribe_to_user_id'])
                        # Check latest one:
                        last_record = await self.get_latest_in_timeline( twitter_link )
                        if last_record is None:
                            inserts = await self.add_fetch_timeline( twitter_link, json.dumps(tweets), latest_tweet_id_str, old_time, latest_full_text  )
                        else:
                            if last_record['latest_tweet_id_str'] != latest_tweet_id_str:
                                inserts = await self.add_fetch_timeline( twitter_link, json.dumps(tweets), latest_tweet_id_str, old_time, latest_full_text  )
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=300.0)
    async def fetch_latest_dm(self):
        time_lap = 120 # seconds
        await self.bot.wait_until_ready()
        await asyncio.sleep(time_lap)

        if self.twitter_auth is None:
            await self.get_twitter_auth()

        def g_dm(count: int=20):
            try:
                auth = tweepy.OAuth1UserHandler(
                   self.twitter_auth['consumer_key'], 
                   self.twitter_auth['consumer_secret'], 
                   self.twitter_auth['access_token'], 
                   self.twitter_auth['access_token_secret']
                )
                api = tweepy.API(auth)
                get_msg = api.get_direct_messages(count=count)
            except tweepy.errors.TooManyRequests as e:
                return None
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                return None
            return get_msg

        try:
            func_dm = functools.partial(g_dm, 20)
            fetch_dm = await self.bot.loop.run_in_executor(None, func_dm)
            if fetch_dm is not None and len(fetch_dm) > 0:
                # get
                dms = []
                for each_dm in fetch_dm:
                    dms.append(each_dm._json)
                # Check latest one:
                last_record = await self.get_latest_in_dm()
                data_rows = []
                if last_record is None:
                    for each_msg in dms:
                        try:
                            if each_msg['type'] == "message_create":
                                data_rows.append( ( json.dumps(each_msg), json.dumps(each_msg['message_create']['message_data']), each_msg['message_create']['message_data']['text'], each_msg['id'], each_msg['message_create']['sender_id'], each_msg['message_create']['target']['recipient_id'], int(int(each_msg['created_timestamp'])/1000), int(time.time()) ) )
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                elif len(last_record) > 0:
                    list_rec_ids = [each['message_id'] for each in last_record]
                    for each_msg in dms:
                        if each_msg['id'] not in list_rec_ids:
                            data_rows.append( ( json.dumps(each_msg), json.dumps(each_msg['message_create']['message_data']), each_msg['message_create']['message_data']['text'], each_msg['id'], each_msg['message_create']['sender_id'], each_msg['message_create']['target']['recipient_id'], int(int(each_msg['created_timestamp'])/1000), int(time.time()) ))
                if len(data_rows) > 0:
                    inserts = await self.add_bot_dm_messages( data_rows )
                else:
                    await asyncio.sleep(time_lap)
            else:
                await logchanbot("[TWITTER] - tweepy.errors.TooManyRequests from fetch_latest_dm or error....")
                await asyncio.sleep(60.0)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(time_lap)

    @commands.guild_only()
    @commands.slash_command(description="Various twitter's commands.")
    async def twitter(self, ctx):
        pass

    @commands.guild_only()
    @twitter.sub_command(
        usage="twitter subscribe <channel> <twitter link>", 
        options=[
            Option('channel', 'channel', OptionType.channel, required=True),
            Option('twitter_link', 'twitter_link', OptionType.string, required=True)
        ],
        description="Subscribe to a twitter account link and push new tweet to a channel."
    )
    async def subscribe(
        self, 
        ctx, 
        channel: disnake.TextChannel, 
        twitter_link: str
    ):
        if not ctx.author.guild_permissions.manage_channels:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you do not have a permission to `/twitter subscribe` here."
            await ctx.response.send_message(msg)
            return

        await self.bot_log()
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))

        if twitter_link.endswith("/"): twitter_link = twitter_link[0:-1]
        user = twitter_link.split("/")[-1]

        try:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Bot's checking twitter..."
            await ctx.response.send_message(msg)
            try:
                embed = disnake.Embed(title = "[TWITTER] Subscription")
                embed.add_field(name="Link", value=f"<{twitter_link}>")
                embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
                msg = await channel.send(embed=embed)
                await msg.delete()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await ctx.response.send_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, error to post message in channel {channel.mention}")
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, no permission to send message to channel {channel.mention}...")
            return

        if not user.isalnum():
            await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, invalid twitter link or username.")
            return
        else:
            get_user = await self.get_user( user, str(ctx.author.id), "{}#{}".format(ctx.author.name, ctx.author.discriminator) )
            if get_user is None:
                await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, account link not exist <{twitter_link}>!")
                return
            else:
                twitter_link = "https://twitter.com/{}".format(user)
                # That exist, let's add
                # 1] Check if guild has maximum or sub
                # 2] Check if link is already in and active
                check_sub_link = await self.get_list_subscribe(str(ctx.guild.id))
                if len(check_sub_link) >= serverinfo['max_twitter_subscription']:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, your guild `{ctx.guild.name}` has maximum number of subscription already to twitter. If you need more, please contact TipBpt's dev."
                    await ctx.edit_original_message(content=msg)
                    return
                if len(check_sub_link) >= 0:
                    exist = False
                    if len(check_sub_link) > 0:
                        for each_sub in check_sub_link:
                            if each_sub['subscribe_to'].upper() == twitter_link.upper():
                                exist = True
                                break
                    if exist == True:
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, your guild `{ctx.guild.name}` already subscribe to <{twitter_link}>."
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        # let's add
                        # guild_id: str, subscribe_to: str, subscribe_to_user_id: str, push_to_channel_id: str, added_by_uid: str, added_by_uname: str):
                        add = await self.add_guild_sub( str(ctx.guild.id), "https://twitter.com/{}".format(user), user, str(channel.id), str(ctx.author.id), "{}#{}".format(ctx.author.name, ctx.author.discriminator) )
                        if add > 0:
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, successfully subscribe to <{twitter_link}> and to channel {channel.mention}."
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(f"[TWITTER] - New subscribe of guild {ctx.guild.name} / {ctx.guild.id} to <{twitter_link}> by {ctx.author.name}#{ctx.author.discriminator}.")
                        else:
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, internal error."
                            await ctx.edit_original_message(content=msg)
                        return


    @commands.guild_only()
    @twitter.sub_command(
        usage="twitter unsubscribe <twitter link>", 
        options=[
            Option('twitter_link', 'twitter_link', OptionType.string, required=True)
        ],
        description="Unsubscribe to a twitter account link"
    )
    async def unsubscribe(
        self, 
        ctx, 
        twitter_link: str
    ):
        if not ctx.author.guild_permissions.manage_channels:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you do not have a permission to `/twitter unsubscribe` here."
            await ctx.response.send_message(msg)
            return

        await self.bot_log()
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))

        if twitter_link.endswith("/"): twitter_link = twitter_link[0:-1]
        user = twitter_link.split("/")[-1]

        try:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Bot's checking twitter..."
            await ctx.response.send_message(msg)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, error to message you...")
            return

        if not user.isalnum():
            await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, invalid twitter link or username.")
            return
        else:
            # That exist, let's add
            # 1] Check if guild has maximum or sub
            # 2] Check if link is already in and active
            check_sub_link = await self.get_list_subscribe(str(ctx.guild.id))
            if len(check_sub_link) == 0:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, your guild `{ctx.guild.name}` don't have any subscription to remove!"
                await ctx.edit_original_message(content=msg)
                return
            else:
                exist = False
                for each_sub in check_sub_link:
                    if each_sub['subscribe_to'].upper() == twitter_link.upper():
                        exist = True
                        break
                if exist == False:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, your guild `{ctx.guild.name}` doesn't subscribe to <{twitter_link}>."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    # let's delete
                    delete = await self.del_guild_sub( str(ctx.guild.id), twitter_link, user, str(ctx.author.id), "{}#{}".format(ctx.author.name, ctx.author.discriminator) )
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, successfully unsubscribe from <{twitter_link}>."
                    await ctx.edit_original_message(content=msg)
                    await logchanbot(f"[TWITTER] - Unubscribe of guild {ctx.guild.name} / {ctx.guild.id} from <{twitter_link}> by {ctx.author.name}#{ctx.author.discriminator}.")


    @commands.guild_only()
    @twitter.sub_command(
        usage="twitter listsub", 
        description="List of subscribed twitter link."
    )
    async def listsub(
        self, 
        ctx, 
    ):
        if not ctx.author.guild_permissions.manage_channels:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you do not have a permission to `/twitter listsub` here."
            await ctx.response.send_message(msg)
            return

        await self.bot_log()
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))

        try:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Bot's checking twitter..."
            await ctx.response.send_message(msg)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, error to message you...")
            return

        check_sub_link = await self.get_list_subscribe(str(ctx.guild.id))
        if len(check_sub_link) == 0:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, your guild `{ctx.guild.name}` doesn't subscribe to any twitter yet."
            await ctx.edit_original_message(content=msg)
            return
        else:
            links = []
            for each in check_sub_link:
                links.append("<#{}> to: <{}> added by {}.".format(each['push_to_channel_id'], each['subscribe_to'], each['added_by_uname']))
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, your guild `{ctx.guild.name}` subscribed to:\n\n" + "\n".join(links)
            await ctx.edit_original_message(content=msg)
            return


    @commands.guild_only()
    @twitter.sub_command(
        usage="twitter rt_reward <amount> <coin> <duration> <channel> <twitter link>", 
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('coin', 'coin', OptionType.string, required=True),
            Option('duration', 'duration', OptionType.string, required=True, choices=[
                OptionChoice("1 DAY", "1"),
                OptionChoice("2 DAYS", "2"),
                OptionChoice("3 DAYS", "3"),
                OptionChoice("7 DAYS", "7")
            ]),
            Option('channel', 'channel', OptionType.channel, required=True),
            Option('twitter_link', 'twitter_link', OptionType.string, required=True)
        ],
        description="Give reward to twitter user who RT your Tweet."
    )
    async def rt_reward(
        self, 
        ctx, 
        amount: str, 
        coin: str, 
        duration: str, 
        channel: disnake.TextChannel, 
        twitter_link: str
    ):
        await self.bot_log()
        try:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Bot's checking twitter..."
            await ctx.response.send_message(msg)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, error to message...")
            return

        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo['is_premium'] == 0:
            msg = f'{ctx.author.mention}, not available in public right now. You can request pluton#8888 to allow this for your guild.'
            await ctx.edit_original_message(content=msg)
            return

        # Check if he still has some ongoing RT reward
        if serverinfo['rt_reward_amount'] and serverinfo['rt_reward_coin'] and serverinfo['rt_reward_channel'] and serverinfo['rt_link'] and serverinfo['rt_end_timestamp'] and serverinfo['rt_end_timestamp'] > int(time.time()) + 3600: # reserved 1hr
            rt_link = serverinfo['rt_link']
            msg = f'{ctx.author.mention}, you still have an ongoing RT reward <{rt_link}>.'
            await ctx.edit_original_message(content=msg)
            return
            
        if twitter_link.endswith("/"): twitter_link = twitter_link[0:-1]
        ids = twitter_link.split("/")[-1]

        if not ids.isdigit():
            await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, invalid twitter status link.")
            return
        else:
            get_tweet = await self.get_tweet( ids )
            if get_tweet is None:
                await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, status link not exist <{twitter_link}>!")
                return
            else:
                # Check if tweet has already too many tweet:
                if get_tweet['retweet_count'] > 100:
                    await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, status link <{twitter_link}> has many RT already, not supported yet!")
                    return
                else:
                    twitter_link = "https://twitter.com/{}/status/{}".format(get_tweet['user']['screen_name'], ids)

        # Check if previously run
        check_reward_exist = await self.get_reward_guild_link( str(ctx.guild.id), twitter_link )
        if check_reward_exist is not None:
            await ctx.edit_original_message(content=f'{ctx.author.mention}, this <{twitter_link}> exists already in your guild before or still running. Please try a new tweet.')
            return

        COIN_NAME = coin.upper()
        if not hasattr(self.bot.coin_list, COIN_NAME):
            await ctx.edit_original_message(content=f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
            return

        net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
        contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
        token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
        MinTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
        MaxTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
        
        Guild_WalletAPI = WalletAPI(self.bot)
        get_deposit = await Guild_WalletAPI.sql_get_userwallet(str(ctx.guild.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await Guild_WalletAPI.sql_register_user(str(ctx.guild.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 1)

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']

        height = None
        try:
            if type_coin in ["ERC-20", "TRC-20"]:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
            else:
                height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        userdata_balance = await store.sql_user_balance_single(str(ctx.guild.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])

        amount = amount.replace(",", "")
        amount = text_to_num(amount)
        if amount is None:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
            await ctx.edit_original_message(content=msg)
            return
        # We assume max reward by MaxTip / 10
        elif amount < MinTip or amount > MaxTip / 10:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, reward cannot be smaller than {num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display} or bigger than {num_format_coin(MaxTip / 10, COIN_NAME, coin_decimal, False)} {token_display}.'
            await ctx.edit_original_message(content=msg)
            return
        # We assume at least guild need to have 100x of reward or depends on guild's population
        elif amount*100 > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you need to have at least 100x reward balance. 100x rewards = {num_format_coin(amount*100, COIN_NAME, coin_decimal, False)} {token_display}.'
            await ctx.edit_original_message(content=msg)
            return
        elif amount*len(ctx.guild.members) > actual_balance:
            population = len(ctx.guild.members)
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} you need to have at least {str(population)}x reward balance. {str(population)}x rewards = {num_format_coin(amount*population, COIN_NAME, coin_decimal, False)} {token_display}.'
            await ctx.edit_original_message(content=msg)
            return
        else:
            # Check channel
            get_channel = self.bot.get_channel(int(channel.id))
            channel_str = str(channel.id)
            # Test message
            msg = f"New Twitter RT reward link <{twitter_link}> with {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} by {ctx.author.name}#{ctx.author.discriminator} and posting here."
            try:
                await get_channel.send(msg)
            except Exception as e:
                msg = f'{ctx.author.mention}, failed to message channel {channel.mention}. Set reward denied!'
                await ctx.edit_original_message(content=msg)
                traceback.print_exc(file=sys.stdout)
                return

            rt_reward = await self.update_reward(str(ctx.guild.id), float(amount), COIN_NAME, coin_decimal, str(ctx.author.id), "{}#{}".format(ctx.author.name, ctx.author.discriminator), False, channel_str, twitter_link, int(time.time())+int(duration)*24*3600)
            if rt_reward > 0:
                msg = f'{ctx.author.mention}, successfully set reward for RT in guild {ctx.guild.name} to {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} for RT link <{twitter_link}>.'
                await ctx.edit_original_message(content=msg)
                try:
                    await logchanbot(f'[TWITTER] A user {ctx.author.name}#{ctx.author.discriminator} set a RT reward in guild {ctx.guild.name} / {ctx.guild.id} to {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} for <{twitter_link}>.')
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            else:
                msg = f'{ctx.author.mention}, internal error or nothing updated.'
                await ctx.edit_original_message(content=msg)

    @twitter.sub_command(
        usage="twitter linkme <twitter_name> [optional status link]", 
        options=[
            Option('twitter_name', 'twitter_name', OptionType.string, required=True), 
            Option('status_link', 'status_link', OptionType.string, required=False)
        ],
        description="Associate your Discord to a twitter."
    )
    async def linkme(
        self, 
        ctx, 
        twitter_name: str, 
        status_link: str=None
    ):
        await self.bot_log()
        try:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Bot's checking your twitter..."
            await ctx.response.send_message(msg, ephemeral=True)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, error to message...", ephemeral=True)
            return
        if not twitter_name.isalnum():
            await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, twitter name `{twitter_name}` is invalid.")
            return
        
        # Check if exist in DB..
        # 1] If he is verified
        # 2] If he made a key but not yet verify
        get_linkme = await self.twitter_linkme_get_user(str(ctx.author.id))
        if get_linkme and get_linkme['is_verified'] == 1:
            msg = f"{ctx.author.mention}, you already verified. If you want to change, unlink first with `/twitter unlink`."
            await ctx.edit_original_message(content=msg)
            return
        
        if status_link is None:
            if get_linkme and get_linkme['is_verified'] == 0:
                secret_key = get_linkme['secret_key']
                screen_name = get_linkme['twitter_screen_name']
                if screen_name.upper() != twitter_name.upper():
                    # He already have in record but has't verify, show existing to him
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you generated a key already but not `{twitter_name}`. You tried to link before with `{screen_name}`. Please unlink it first, if you want to change to `{twitter_name}` with `/twitter unlink`."
                    await ctx.edit_original_message(content=msg)
                else:
                    # He already have in record but has't verify, show existing to him
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you generated a key already:```1) Open your twitter @{screen_name} and post a status by mentioning @BotTipsTweet and containing a string {secret_key} in your new tweet.\n2) Copy that tweet status full link to clipboard\n3) Execute command with TipBot /twitter linkme <your twitter name> <url_status>```"
                    await ctx.edit_original_message(content=msg)
                return
            elif get_linkme is None:
                # generate
                from string import ascii_uppercase
                secret_key = ''.join(random.choice(ascii_uppercase) for i in range(32))
                add = await self.twitter_linkme_add_or_regen( str(ctx.author.id), "{}#{}".format(ctx.author.name, ctx.author.discriminator), secret_key, int(time.time()), twitter_name )
                if add > 0:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, one more step to verify:```1) Open your twitter @{twitter_name} and post a status by mentioning @BotTipsTweet and containing a string {secret_key} in your new tweet.\n2) Copy that tweet status full link to clipboard\n3) Execute command with with TipBot /twitter linkme <your twitter name> <url_status>```"
                    await ctx.edit_original_message(content=msg)
                else:
                    msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, internal error, please report."
                    await ctx.edit_original_message(content=msg)
                return
        elif status_link:
            if "?" in status_link: status_link = status_link.split("?")[0] # reported by chooseuser#0308 when using mobile
            if get_linkme is None:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you didn't generate a `secret_key` yet. You can generate with `/twitter linkme <your twitter name>`."
                await ctx.edit_original_message(content=msg)
                return
            elif get_linkme and get_linkme['twitter_screen_name'] != twitter_name:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you didn't link yourself with twitter `{twitter_name}` before. If you want to change, unlink it first by `/twitter unlink`."
                await ctx.edit_original_message(content=msg)
                return
            else:
                if status_link.endswith("/"): status_link = status_link[0:-1]
                ids = status_link.split("/")[-1]

                if not ids.isdigit():
                    await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, invalid twitter status link.")
                    return
                else:
                    secret_key = get_linkme['secret_key']
                    get_tweet = await self.get_tweet( ids )
                    if get_tweet is None:
                        await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, status link <{status_link}> not exists or try again later!")
                        return
                    else:
                        bot_name = "BotTipsTweet"
                        screen_name = get_tweet['user']['screen_name']
                        status_link = "https://twitter.com/{}/status/{}".format(get_tweet['user']['screen_name'], ids)
                        int_timestamp = int(datetime.strptime(get_tweet['created_at'],'%a %b %d %H:%M:%S +0000 %Y').timestamp())
                        if secret_key not in get_tweet['text'] or bot_name.upper() not in get_tweet['text'].upper() or screen_name.upper() != get_linkme['twitter_screen_name'].upper():
                            twitter_screen_name = get_linkme['twitter_screen_name']
                            msg = "{} {}, the tweet <{}> doesn't contain your `secret_key`, or not from `{}` or not mentioning @{}.".format(EMOJI_INFORMATION, ctx.author.mention, status_link, twitter_screen_name, bot_name)
                            await ctx.edit_original_message(content=msg)
                        elif secret_key in get_tweet['text'] and bot_name.upper() in get_tweet['text'].upper() and screen_name.upper() == get_linkme['twitter_screen_name'].upper():
                            update = await self.twitter_linkme_update_verify( str(ctx.author.id), get_tweet['user']['id_str'], screen_name, status_link, get_tweet['text'], json.dumps(get_tweet), int_timestamp )
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, sucessfully verified you with twitter `@{screen_name}`."
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(f"[TWITTER] - Discord User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.id} linked with `@{screen_name}`.")
                        else:
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, error, please report."
                            await ctx.edit_original_message(content=msg)
                        return

    @twitter.sub_command(
        usage="twitter unlinkme", 
        description="Unlink your Discord from a twitter."
    )
    async def unlinkme(
        self, 
        ctx
    ):
        await self.bot_log()
        try:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Bot's checking your twitter..."
            await ctx.response.send_message(msg, ephemeral=True)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, error to message...", ephemeral=True)
            return

        # Check if exist in DB..
        get_linkme = await self.twitter_linkme_get_user(str(ctx.author.id))
        if get_linkme is None:
            msg = f"{ctx.author.mention}, you haven't linked with any twitter yet."
            await ctx.edit_original_message(content=msg)
        elif get_linkme and get_linkme['is_verified'] == 0:
            # If use haven't verified, move it to twitter_unlinkme
            unlink_user = await self.twitter_unlink( str(ctx.author.id), "{}#{}".format(ctx.author.name, ctx.author.discriminator), get_linkme['twitter_screen_name'], get_linkme['is_verified'] )
            msg = f"{ctx.author.mention}, you haven't verified but we removed the pending one as per your request."
            await ctx.edit_original_message(content=msg)
        elif get_linkme and get_linkme['is_verified'] == 1:
            twitter_screen_name = get_linkme['twitter_screen_name']
            unlink_user = await self.twitter_unlink( str(ctx.author.id), "{}#{}".format(ctx.author.name, ctx.author.discriminator), get_linkme['twitter_screen_name'], get_linkme['is_verified'] )
            msg = f"{ctx.author.mention}, sucessfully unlink with `{twitter_screen_name}`."
            await ctx.edit_original_message(content=msg)
            await logchanbot(f"[TWITTER] - Discord User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.id} unlinked with `@{twitter_screen_name}`.")

    @twitter.sub_command(
        usage="twitter tip <amount> <coin> <twitter link | username>", 
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('coin', 'coin', OptionType.string, required=True),
            Option('twitter', 'twitter', OptionType.string, required=True)
        ],
        description="Tip to Twitter user by name or link who verified with Discord TipBot."
    )
    async def tip(
        self, 
        ctx, 
        amount: str, 
        coin: str, 
        twitter: str
    ):
        old_twitter = twitter
        has_link = False
        await self.bot_log()
        try:
            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Bot's checking twitter..."
            await ctx.response.send_message(msg)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, error to message...")
            return

        COIN_NAME = coin.upper()
        if not hasattr(self.bot.coin_list, COIN_NAME):
            await ctx.edit_original_message(content=f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
            return

        if '?' in twitter: twitter = twitter.split("?")[0]
        if 'https://twitter.com/' in twitter:
            has_link = True
            twitter = twitter.replace("https://twitter.com/", "")
            if "/" in twitter:
                twitter = twitter.split("/")[0]
        elif 'https://mobile.twitter.com/' in twitter:
            has_link = True
            twitter = twitter.replace("https://mobile.twitter.com/", "")
            if "/" in twitter:
                twitter = twitter.split("/")[0]
        if not twitter.isalnum():
            await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, twitter name `{old_twitter}` is invalid.")
            return
        else:
            # Find if he is verified and what is his/her Discord
            get_user = await self.get_discord_by_twid( twitter )
            if get_user is None:
                await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, can't find a Discord user with twitter `{old_twitter}`. He may not be verified. How to get verified <https://www.youtube.com/watch?v=q79_1M0_Hsw>.")
                return
            else:
                # Check if himself
                if int(get_user['discord_user_id']) == ctx.author.id:
                    await ctx.edit_original_message(content=f"{EMOJI_INFORMATION} {ctx.author.mention}, that is your own twitter!")
                    return
                else:
                    # Let's tip
                    net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                    type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                    deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    MinTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
                    MaxTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
                    usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")

                    # token_info = getattr(self.bot.coin_list, COIN_NAME)
                    token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
                    contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                    User_WalletAPI = WalletAPI(self.bot)
                    
                    get_deposit = await User_WalletAPI.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                    if get_deposit is None:
                        get_deposit = await User_WalletAPI.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

                    wallet_address = get_deposit['balance_wallet_address']
                    if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        wallet_address = get_deposit['paymentid']

                    # Check if tx in progress
                    if ctx.author.id in self.bot.TX_IN_PROCESS:
                        msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
                        await ctx.edit_original_message(content=msg)
                        return

                    height = None
                    try:
                        if type_coin in ["ERC-20", "TRC-20"]:
                            height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                        else:
                            height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)

                    # check if amount is all
                    all_amount = False
                    if not amount.isdigit() and amount.upper() == "ALL":
                        all_amount = True
                        userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                        amount = float(userdata_balance['adjust'])
                    # If $ is in amount, let's convert to coin/token
                    elif "$" in amount[-1] or "$" in amount[0]: # last is $
                        # Check if conversion is allowed for this coin.
                        amount = amount.replace(",", "").replace("$", "")
                        if usd_equivalent_enable == 0:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{COIN_NAME}`."
                            await ctx.edit_original_message(content=msg)
                            return
                        else:
                            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                            COIN_NAME_FOR_PRICE = COIN_NAME
                            if native_token_name:
                                COIN_NAME_FOR_PRICE = native_token_name
                            per_unit = None
                            if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                                id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                                per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                            else:
                                per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
                            if per_unit and per_unit > 0:
                                amount = float(Decimal(amount) / Decimal(per_unit))
                            else:
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method.'
                                await ctx.edit_original_message(content=msg)
                                return
                    else:
                        amount = amount.replace(",", "")
                        amount = text_to_num(amount)
                        if amount is None:
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                            await ctx.edit_original_message(content=msg)
                            return
                    # end of check if amount is all
                    notifyList = await store.sql_get_tipnotify()
                    userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                    actual_balance = float(userdata_balance['adjust'])

                    if amount > MaxTip or amount < MinTip:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than **{num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}** or smaller than **{num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display}**.'
                        await ctx.edit_original_message(content=msg)
                        return
                    elif amount > actual_balance:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a random tip of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}**.'
                        await ctx.edit_original_message(content=msg)
                        return

                    # add queue also randtip
                    if ctx.author.id in self.bot.TX_IN_PROCESS:
                        msg = f'{EMOJI_ERROR} {ctx.author.mention} {EMOJI_HOURGLASS_NOT_DONE}, you have another tx in progress.'
                        await ctx.edit_original_message(content=msg)
                        return

                    equivalent_usd = ""
                    amount_in_usd = 0.0
                    if usd_equivalent_enable == 1:
                        native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                        COIN_NAME_FOR_PRICE = COIN_NAME
                        if native_token_name:
                            COIN_NAME_FOR_PRICE = native_token_name
                        if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                            id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                            per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                        else:
                            per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
                        if per_unit and per_unit > 0:
                            amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                            if amount_in_usd > 0.0001:
                                equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)

                    tip = None
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                    Tip_WalletAPI = WalletAPI(self.bot)
                    user_to = await User_WalletAPI.sql_get_userwallet(get_user['discord_user_id'], COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                    if user_to is None:
                        user_to = await User_WalletAPI.sql_register_user(get_user['discord_user_id'], COIN_NAME, net_name, type_coin, SERVER_BOT, 0)

                    try:
                        guild_id = "DM"
                        channel_id = "DM"
                        if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                            guild_id = str(ctx.guild.id)
                            channel_id = str(ctx.channel.id)
                        tip = await store.sql_user_balance_mv_single(str(ctx.author.id), get_user['discord_user_id'], guild_id, channel_id, amount, COIN_NAME, "TWITTERTIP", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                    # remove queue from randtip
                    if ctx.author.id in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    if tip:
                        # tipper shall always get DM. Ignore notifyList
                        try:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you sent a twitter tip of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}** to `{old_twitter}`.'
                            await ctx.edit_original_message(content=msg)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        if get_user['discord_user_id'] not in notifyList:
                            via_link = ""
                            if has_link == True:
                                via_link = f" via <{old_twitter}>." 
                            try:
                                tw_user = self.bot.get_user(int(get_user['discord_user_id']))
                                await tw_user.send(
                                    f'{EMOJI_MONEYFACE} You got a twitter tip of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} '
                                    f'{token_display}** from {ctx.author.name}#{ctx.author.discriminator}{via_link}.'
                                    f'{NOTIFICATION_OFF_CMD}')
                            except Exception as e:
                                pass


def setup(bot):
    bot.add_cog(Twitter(bot))