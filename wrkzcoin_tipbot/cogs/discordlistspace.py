from aiohttp import web
import aiohttp
import asyncio
import traceback, sys
from disnake.ext import tasks, commands
from discord_webhook import DiscordWebhook
import json, time

import store
from config import config

from Bot import SERVER_BOT


class DiscordListVote(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.fetch_bot_vote.start()


    @tasks.loop(seconds=60.0)
    async def fetch_bot_vote(self):
        time_lap = 60 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(config.discordlist.fetch_vote_api, headers={'Content-Type': 'application/json', 'Authorization': config.discordlist.token}, timeout=5.0) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            await session.close()
                            vote_list = json.loads(res_data)['data']
                            get_last_votes = await self.select_last_bot_votes(str(config.discordlist.bot_id))
                            vote_data = []
                            new_votes = []
                            type_vote = "upvote"
                            if len(vote_list) > 0:
                                for each in vote_list:
                                    if int(each['user']) not in get_last_votes:
                                        try:
                                            date_voted = int(each['timestamp'] / 1000)
                                            # longer than a day, skip
                                            if int(time.time()) - date_voted > 24*3600:
                                                continue
                                            vote_data.append((each['user'], None, "discordlistspace", str(config.discordlist.bot_id), type_vote, date_voted ))
                                            new_votes.append(int(each['user']))
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
                            if len(vote_data) > 0:
                                print("discordlistspace: has {} votes to insert.".format(len(vote_data)))
                                insert_votes = await self.insert_bot_vote_many(vote_data)
                                if insert_votes > 0:
                                    for each_user in new_votes:
                                        try:
                                            await self.vote_logchan(f'[{SERVER_BOT}] A user <@{str(each_user)}> voted a bot <@{str(config.discordlist.bot_id)}> type `{type_vote}` in discordlist.space.')
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
                                        await asyncio.sleep(2.0)
                        else:
                            await self.vote_logchan(f"discordlistspace: failed to fetch votes.")
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)


    async def guild_find_by_key(self, guild_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT `discordlist_vote_secret` FROM `discord_server` WHERE `serverid`=%s """
                    await cur.execute(sql, ( guild_id ))
                    result = await cur.fetchone()
                    if result: return result['discordlist_vote_secret']
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None


    async def insert_guild_vote(self, user_id: str, directory: str, guild_id: str, type_vote: str, voter: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ INSERT IGNORE INTO guild_vote (`user_id`, `name`, `directory`, `guild_id`, `type`, `date_voted`) VALUES (%s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, ( user_id, voter, directory, guild_id, type_vote, date_vote ))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False


    async def insert_bot_vote(self, user_id: str, directory: str, bot_id: str, type_vote: str, voter: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ INSERT IGNORE INTO bot_vote (`user_id`, `name`, `directory`, `bot_id`, `type`, `date_voted`) VALUES (%s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, ( user_id, voter, directory, bot_id, type_vote, date_vote ))
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def insert_bot_vote_many(self, data):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT IGNORE INTO bot_vote (`user_id`, `name`, `directory`, `bot_id`, `type`, `date_voted`) VALUES (%s, %s, %s, %s, %s, %s) """
                    await cur.executemany(sql, data)
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return 0


    async def select_last_bot_votes(self, bot_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT * FROM `bot_vote` WHERE `bot_id`=%s AND `directory`=%s ORDER BY `id` DESC LIMIT 50 """
                    await cur.execute(sql, ( bot_id, "discordlistspace" ))
                    result = await cur.fetchall()
                    if result and len(result) > 0: return [int(each['user_id']) for each in result]
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return []


    async def vote_logchan(self, content: str):
        try:
            webhook = DiscordWebhook(url=config.discordlist.discordlist_votehook, content=content)
            webhook.execute()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    async def webserver(self):
        async def handler_get(request):
            return web.Response(text="Hello, world")


        async def handler_post(request):
            try:
                if request.body_exists:
                    payload = await request.read()
                    headers = request.headers
                    full_payload = json.loads(payload)
                    user_vote = full_payload['user']['id']
                    type_vote = full_payload['trigger']
                    voter = "{}#{}".format(full_payload['user']['username'], full_payload['user']['discriminator'])
                    # https://docs.discordlist.space/reference/webhooks
                    if str(request.rel_url).startswith("/server_vote/"):
                        guild_id = full_payload['server']['id']
                        if 'Authorization' in request.headers:
                            # Find Authorization correspond to server ID
                            key = request.headers['Authorization']
                            get_guild_by_key = await self.guild_find_by_key(guild_id)
                            # Insert in DB no matter what
                            try:
                                insert_vote = await self.insert_guild_vote(user_vote, "discordlistspace", guild_id, type_vote, voter)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            
                            if get_guild_by_key and get_guild_by_key == key:
                                # Check if bot is in that guild, if not post in log chan vote
                                guild = self.bot.get_guild(int(guild_id))
                                # TODO: Find bot channel
                                if guild:
                                    try:
                                        # TODO: change to bot channel
                                        await self.vote_logchan(f'[{SERVER_BOT}] A user <@{user_vote}> voted a guild `<@{guild_id}>` type `{type_vote}` in discordlist.space.')
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                else:
                                    try:
                                        await self.vote_logchan(f'[{SERVER_BOT}] A user <@{user_vote}> voted a guild `<@{guild_id}>` type `{type_vote}` in discordlist.space but I am not in that server or I can\'t find bot channel.')
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                            else:
                                try:
                                    await self.vote_logchan(f'[{SERVER_BOT}] A user <@{user_vote}> voted a guild `<@{guild_id}>` type `{type_vote}` in discordlist.space but I am not in that guild or I cannot find it.')
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                return web.Response(text="No such server by this key! Or not up to date!")
                        else:
                            return web.Response(text="No Authorization! Or not up to date!")
                    elif str(request.rel_url).startswith("/bot_vote/"):
                        bot_id = full_payload['bot']['id']
                        if 'Authorization' in request.headers and request.headers['Authorization'] == config.discordlist.auth:
                            insert_vote = await self.insert_bot_vote(user_vote, "discordlistspace", bot_id, type_vote, voter)
                            if insert_vote > 0:
                                try:
                                    await self.vote_logchan(f'[{SERVER_BOT}] A user <@{user_vote}> voted a bot <@{bot_id}> type `{type_vote}` in discordlist.space.')
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                            return web.Response(text="Thank you!")
                    else:
                        await self.vote_logchan(f'[{SERVER_BOT}] A user <@{user_vote}> voted for bot <@{bot_id}> type `{type_vote}` but not true from discordlist.space.')
                        return web.Response(text="Thank you but not discordlist.space!")
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

        app = web.Application()
        app.router.add_get('/{tail:.*}', handler_get)
        app.router.add_post('/{tail:.*}', handler_post)
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, '127.0.0.1', 19903)
        await self.bot.wait_until_ready()
        await self.site.start()

    def __unload(self):
        asyncio.ensure_future(self.site.stop())


def setup(bot):
    discordlist = DiscordListVote(bot)
    bot.add_cog(discordlist)
    bot.loop.create_task(discordlist.webserver())
