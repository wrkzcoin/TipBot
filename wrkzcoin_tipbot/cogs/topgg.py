from aiohttp import web
import asyncio
import traceback, sys
from disnake.ext import commands
from discord_webhook import DiscordWebhook
import json, time
from decimal import Decimal

import store
from config import config

from Bot import SERVER_BOT, num_format_coin
from cogs.wallet import Faucet
from cogs.wallet import WalletAPI
import redis_utils

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

    async def guild_find_by_id(self, guild_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT * FROM `discord_server` WHERE `serverid`=%s """
                    await cur.execute(sql, ( guild_id ))
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    async def insert_guild_vote(self, user_id: str, directory: str, guild_id: str, type_vote: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ INSERT IGNORE INTO guild_vote (`user_id`, `directory`, `guild_id`, `type`, `date_voted`) VALUES (%s, %s, %s, %s, %s) """
                    await cur.execute(sql, ( user_id, directory, guild_id, type_vote, date_vote ))
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
                    sql = """ INSERT IGNORE INTO bot_vote (`user_id`, `directory`, `bot_id`, `type`, `date_voted`) VALUES (%s, %s, %s, %s, %s) """
                    await cur.execute(sql, ( user_id, directory, bot_id, type_vote, date_vote ))
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
                                get_guild = await self.guild_find_by_id(guild_id)
                                if get_guild['vote_reward_amount'] and get_guild['vote_reward_amount'] >  0:
                                    # Tip
                                    COIN_NAME = get_guild['vote_reward_coin']
                                    # Check balance of guild
                                    User_WalletAPI = WalletAPI(self.bot)
                                    net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                                    type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                                    deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                                    contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                                    usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
                                    user_from = await User_WalletAPI.sql_get_userwallet(guild_id, COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                                    if user_from is None:
                                        user_from = await User_WalletAPI.sql_register_user(guild_id, COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
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
                                    userdata_balance = await store.sql_user_balance_single(guild_id, COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                                    total_balance = userdata_balance['adjust']
                                    if total_balance < get_guild['vote_reward_amount']:
                                        # Alert guild owner
                                        guild_owner = self.bot.get_user(guild.owner.id)
                                        await guild_owner.send(f'Your guild run out of guild\'s reward for {COIN_NAME}. Deposit more!')
                                    else:
                                        # Tip
                                        try:
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
                                            tip = await store.sql_user_balance_mv_single(guild_id, user_vote, "TOPGG", "VOTE", amount, COIN_NAME, "GUILDVOTE", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                                            if member is not None:
                                                msg = f"Thank you for voting guild `{guild.name}` at top.gg. You just got a reward of {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}."
                                                try:
                                                    await member.send(msg)
                                                    guild_owner = self.bot.get_user(guild.owner.id)
                                                    await guild_owner.send(f'User `{user_vote}` voted your guild {guild.name} at top.gg. He/she just got a reward of {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}.')
                                                except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                    await self.vote_logchan(f'[{SERVER_BOT}] Failed to thank message to <@{user_vote}>.')
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
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
                                return web.Response(text="Thank you!")
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
                                    if int(vote_to) == config.discord.bot_id:
                                        # It's TipBot
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
                                                    insert_reward = await faucet.insert_reward(user_vote, "topgg", amount, COIN_NAME, int(time.time()), SERVER_BOT)
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
                                                            tip = await store.sql_user_balance_mv_single(config.discord.bot_id, user_vote, "TOPGG", "VOTE", amount, COIN_NAME, "BOTVOTE", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                                                            if member is not None:
                                                                msg = f"Thank you for voting our TipBot at {config.bot_vote_link.topgg} . You just got a reward of {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}."
                                                                try:
                                                                    await member.send(msg)
                                                                except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                                    await self.vote_logchan(f'[{SERVER_BOT}] Failed to thank message to <@{user_vote}>.')
                                                        except Exception as e:
                                                            traceback.print_exc(file=sys.stdout)
                                            else:
                                                # User didn't put any prefer coin. Message him he could reward
                                                if member is not None:
                                                    msg = f"Thank you for voting our TipBot at {config.bot_vote_link.topgg} . You can get a reward! Know more by `/claim` or `/claim token_name` to set your preferred coin/token reward."
                                                    try:
                                                        await member.send(msg)
                                                    except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                        await self.vote_logchan(f'[{SERVER_BOT}] Failed to inform message to <@{user_vote}>.')
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
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
