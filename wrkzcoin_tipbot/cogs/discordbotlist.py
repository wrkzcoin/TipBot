from aiohttp import web
import asyncio
import traceback, sys
from disnake.ext import commands
from discord_webhook import DiscordWebhook
import json, time

import store
from config import config

from Bot import SERVER_BOT


class DiscordBotList(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    async def insert_bot_vote(self, user_id: str, directory: str, bot_id: str, type_vote: str, voter: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ INSERT IGNORE INTO bot_vote (`user_id`, `name`, `directory`, `bot_id`, `type`, `date_voted`, `uniq_user_id_date`) VALUES (%s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, ( user_id, voter, directory, bot_id, type_vote, date_vote, "{}-{}".format(user_id, date_vote) ))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False


    async def vote_logchan(self, content: str):
        try:
            webhook = DiscordWebhook(url=config.discordbotlist.discordbotlist_votehook, content=content)
            webhook.execute()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    async def webserver(self):
        async def handler_get(request):
            return web.Response(text="Hello, world")


        async def handler_post(request):
            try:
                if request.body_exists:
                    # {"id":"386761001808166912","username":"pluton","discriminator":"8888","avatar":"6024b9b750f4d02737193463dba0b4eb","admin":false}
                    payload = await request.read()
                    headers = request.headers
                    full_payload = json.loads(payload)
                    user_vote = full_payload['id']
                    type_vote = "upvote"
                    voter = "{}#{}".format(full_payload['username'], full_payload['discriminator'])
                    # https://docs.discordbotlist.com/vote-webhooks
                    if str(request.rel_url).startswith("/bot_vote/"):
                        bot_id = str(self.bot.user.id)
                        if 'Authorization' in request.headers and request.headers['Authorization'] == config.discordbotlist.auth:
                            insert_vote = await self.insert_bot_vote(user_vote, "discordbotlist", bot_id, type_vote, voter)
                            if insert_vote:
                                try:
                                    await self.vote_logchan(f'[{SERVER_BOT}] A user <@{user_vote}> voted a bot <@{bot_id}> type `{type_vote}` in discordbotlist.com.')
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                            return web.Response(text="Thank you!")
                    else:
                        await self.vote_logchan(f'[{SERVER_BOT}] A user <@{user_vote}> voted for bot <@{bot_id}> type `{type_vote}` but not true from discordbotlist.com.')
                        return web.Response(text="Thank you but not discordbotlist.com!")
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

        app = web.Application()
        app.router.add_get('/{tail:.*}', handler_get)
        app.router.add_post('/{tail:.*}', handler_post)
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, '127.0.0.1', 19904)
        await self.bot.wait_until_ready()
        await self.site.start()

    def __unload(self):
        asyncio.ensure_future(self.site.stop())


def setup(bot):
    discordbot = DiscordBotList(bot)
    bot.add_cog(discordbot)
    bot.loop.create_task(discordbot.webserver())
