from aiohttp import web
import asyncio
import traceback, sys

import disnake
from disnake.ext import commands
from discord_webhook import DiscordWebhook
import json, time
from decimal import Decimal
from datetime import datetime

import store
from config import config

from Bot import SERVER_BOT, num_format_coin
from cogs.wallet import Faucet
from cogs.wallet import WalletAPI
import redis_utils

class DiscordBotList(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.reward_channel = 522190259333890058


    async def insert_bot_vote(self, user_id: str, directory: str, bot_id: str, type_vote: str, voter: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ INSERT IGNORE INTO bot_vote (`user_id`, `name`, `directory`, `bot_id`, `type`, `date_voted`) VALUES (%s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, ( user_id, voter, directory, bot_id, type_vote, date_vote ))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def check_last_bot_vote(self, user_id: str, directory: str, bot_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT * FROM `bot_vote` WHERE `user_id`=%s AND `directory`=%s AND `bot_id`=%s ORDER BY `date_voted` DESC LIMIT 1 """
                    await cur.execute(sql, ( user_id, directory, bot_id ))
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

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
                    payload = await request.read()
                    headers = request.headers
                    full_payload = json.loads(payload)
                    user_vote = full_payload['id']
                    type_vote = "upvote"
                    voter = "{}#{}".format(full_payload['username'], full_payload['discriminator'])
                    # https://docs.discordbotlist.com/vote-webhooks
                    if str(request.rel_url).startswith("/bot_vote/"):
                        bot_id = str(config.discord.bot_id)
                        if 'Authorization' in request.headers and request.headers['Authorization'] == config.discordbotlist.auth:
                            try:
                                # Check if user just vote less than 1h. Sometimes top.gg just push too fast multiple times.
                                check_last_vote = await self.check_last_bot_vote(user_vote, "discordbotlist", bot_id)
                                if check_last_vote is not None and int(time.time()) - check_last_vote['date_voted'] < 3600:
                                    await self.vote_logchan(f'[{SERVER_BOT}] A user <@{user_vote}> voted for bot <@{bot_id}> type `{type_vote}` but less than 1h.')
                                    return web.Response(text="Thank you!")
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            insert_vote = await self.insert_bot_vote(user_vote, "discordbotlist", bot_id, type_vote, voter)
                            if insert_vote:
                                try:
                                    await self.vote_logchan(f'[{SERVER_BOT}] A user <@{user_vote}> voted a bot <@{bot_id}> type `{type_vote}` in discordbotlist.com.')
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)

                                try:
                                    faucet = Faucet(self.bot)
                                    # get user preferred coin
                                    get_user_coin = await faucet.get_user_faucet_coin(user_vote, SERVER_BOT)
                                    member = None
                                    try:
                                        member = self.bot.get_user(int(user_vote))
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                    if get_user_coin is not None:
                                        # add reward
                                        list_coins = await faucet.get_faucet_coin_list()
                                        amount = 0.0
                                        COIN_NAME = get_user_coin['coin_name']
                                        for each_coin in list_coins:
                                            if each_coin['coin_name'].upper() == COIN_NAME.upper():
                                                COIN_NAME = each_coin['coin_name'].upper()
                                                amount = each_coin['reward_amount']
                                                break
                                        if COIN_NAME is not None:
                                            insert_reward = await faucet.insert_reward(user_vote, "discordbotlist", amount, COIN_NAME, int(time.time()), SERVER_BOT)
                                            # Check balance of bot
                                            User_WalletAPI = WalletAPI(self.bot)
                                            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                                            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                                            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                                            user_from = await User_WalletAPI.sql_get_userwallet(str(config.discord.bot_id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                                            if user_from is None:
                                                user_from = await User_WalletAPI.sql_register_user(str(config.discord.bot_id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                                            wallet_address = user_from['balance_wallet_address']
                                            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                                wallet_address = user_from['paymentid']

                                            height = None
                                            try:
                                                if type_coin in ["ERC-20", "TRC-20"]:
                                                    height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                                                else:
                                                    height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                                            except Exception as e:
                                                traceback.print_exc(file=sys.stdout)

                                            # height can be None
                                            userdata_balance = await store.sql_user_balance_single(str(config.discord.bot_id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                                            total_balance = userdata_balance['adjust']
                                            if total_balance <= amount:
                                                await self.vote_logchan(f'[{SERVER_BOT}] vote reward for but TipBot for {COIN_NAME} but empty!!!')
                                                return web.Response(text="Thank you!")
                                            else:
                                                # move reward
                                                try:
                                                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                                                    contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                                                    usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
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
                                                    tip = await store.sql_user_balance_mv_single(config.discord.bot_id, user_vote, "DISCORDBOTLIST", "VOTE", amount, COIN_NAME, "BOTVOTE", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                                                    if member is not None:
                                                        msg = f"Thank you for voting our TipBot at {config.bot_vote_link.discordbotlist} . You just got a reward of {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}."
                                                        try:
                                                            await member.send(msg)
                                                        except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                            await self.vote_logchan(f'[{SERVER_BOT}] Failed to thank message to <@{user_vote}>.')
                                                        try:
                                                            channel = self.bot.get_channel(self.reward_channel)
                                                            embed = disnake.Embed(title = "NEW BOT VOTE!", timestamp=datetime.utcnow())
                                                            embed.add_field(name="User", value="<@{}>".format(user_vote), inline=True)
                                                            embed.add_field(name="Reward", value="{} {}".format(num_format_coin(amount, COIN_NAME, coin_decimal, False), COIN_NAME), inline=True)
                                                            embed.add_field(name="Link", value=config.bot_vote_link.discordbotlist, inline=False)
                                                            embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
                                                            await channel.send(embed=embed)
                                                        except Exception as e:
                                                            traceback.print_exc(file=sys.stdout)
                                                except Exception as e:
                                                    traceback.print_exc(file=sys.stdout)
                                    else:
                                        # User didn't put any prefer coin. Message him he could reward
                                        if member is not None:
                                            msg = f"Thank you for voting our TipBot at {config.bot_vote_link.discordbotlist} . You can get a reward! Know more by `/claim` or `/claim token_name` to set your preferred coin/token reward."
                                            try:
                                                await member.send(msg)
                                            except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                await self.vote_logchan(f'[{SERVER_BOT}] Failed to inform message to <@{user_vote}>.')
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
