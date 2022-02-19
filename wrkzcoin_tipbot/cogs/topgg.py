from aiohttp import web
import asyncio
import traceback, sys
from disnake.ext import commands
from discord_webhook import DiscordWebhook
import json, time

import store
from config import config

from Bot import SERVER_BOT


class TopGGVote(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    async def guild_find_by_key(self, guild_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT `topgg_vote_secret` FROM `discord_server` WHERE `serverid`=%s """
                    await cur.execute(sql, ( guild_id ))
                    result = await cur.fetchone()
                    if result: return result['topgg_vote_secret']
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None


    async def insert_guild_vote(self, user_id: str, directory: str, guild_id: str, type_vote: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ INSERT IGNORE INTO guild_vote (`user_id`, `directory`, `guild_id`, `type`, `date_voted`, `uniq_user_id_date`) VALUES (%s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, ( user_id, directory, guild_id, type_vote, date_vote, "{}-{}".format(user_id, date_vote) ))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False


    async def insert_bot_vote(self, user_id: str, directory: str, bot_id: str, type_vote: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ INSERT IGNORE INTO bot_vote (`user_id`, `directory`, `bot_id`, `type`, `date_voted`, `uniq_user_id_date`) VALUES (%s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, ( user_id, directory, bot_id, type_vote, date_vote, "{}-{}".format(user_id, date_vote) ))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False


    async def vote_logchan(self, content: str):
        try:
            webhook = DiscordWebhook(url=config.topgg.topgg_votehook, content=content)
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
                    user_vote = full_payload['user']
                    type_vote = full_payload['type']
                    if str(request.rel_url).startswith("/topgg_server_vote/"):
                        # Example: {'user': '386761001808166912', 'type': 'test', 'query': '', 'guild': '460755304863498250'} ## type = upvote or test
                        if 'Authorization' in request.headers:
                            # Find Authorization correspond to server ID
                            key = request.headers['Authorization']
                            guild_id = full_payload['guild']
                            get_guild_by_key = await self.guild_find_by_key(guild_id)
                            # Insert in DB no matter what
                            try:
                                insert_vote = await self.insert_guild_vote(full_payload['user'], "topgg", full_payload['guild'], full_payload['type'])
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            
                            if get_guild_by_key and get_guild_by_key == key:
                                # Check if bot is in that guild, if not post in log chan vote
                                guild = self.bot.get_guild(int(guild_id))
                                # TODO: Find bot channel
                                if guild:
                                    try:
                                        # TODO: change to bot channel
                                        await self.vote_logchan(f'[{SERVER_BOT}] A user <@{user_vote}> voted a guild `<@{guild_id}>` type `{type_vote}` in top.gg.')
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                else:
                                    try:
                                        await self.vote_logchan(f'[{SERVER_BOT}] A user <@{user_vote}> voted a guild `<@{guild_id}>` type `{type_vote}` in top.gg but I am not in that server or I can\'t find bot channel.')
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                            else:
                                try:
                                    await self.vote_logchan(f'[{SERVER_BOT}] A user <@{user_vote}> voted a guild `<@{guild_id}>` type `{type_vote}` in top.gg but I am not in that guild or I cannot find it.')
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                return web.Response(text="No such server by this key! Or not up to date!")
                        else:
                            return web.Response(text="No Authorization! Or not up to date!")
                    elif str(request.rel_url).startswith("/topgg_bot_vote/"):
                        # Bot: {'user': '386761001808166912', 'type': 'test', 'query': '', 'bot': '474841349968101386'}
                        if 'Authorization' in request.headers and request.headers['Authorization'] == config.topgg.auth:
                            insert_vote = await self.insert_bot_vote(full_payload['user'], "topgg", full_payload['bot'], full_payload['type'])
                            vote_to = full_payload['bot']
                            if insert_vote:
                                try:
                                    await self.vote_logchan(f'[{SERVER_BOT}] A user <@{user_vote}> voted a bot <@{vote_to}> type `{type_vote}` in top.gg.')
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                            return web.Response(text="Thank you!")
                    else:
                        await self.vote_logchan(f'[{SERVER_BOT}] A user <@{user_vote}> voted for bot <@{vote_to}> type `{type_vote}` but not true from top.gg.')
                        return web.Response(text="Thank you but not topgg!")
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

        app = web.Application()
        app.router.add_get('/{tail:.*}', handler_get)
        app.router.add_post('/{tail:.*}', handler_post)
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, '127.0.0.1', 19902)
        await self.bot.wait_until_ready()
        await self.site.start()

    def __unload(self):
        asyncio.ensure_future(self.site.stop())


def setup(bot):
    topgg = TopGGVote(bot)
    bot.add_cog(topgg)
    bot.loop.create_task(topgg.webserver())
