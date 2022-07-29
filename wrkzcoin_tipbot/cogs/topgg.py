from aiohttp import web
import asyncio
import traceback, sys

import disnake
from disnake.ext import commands
from discord_webhook import DiscordWebhook
import json, time
from decimal import Decimal
import time
from datetime import datetime

import store
from config import config

from Bot import SERVER_BOT, num_format_coin
from cogs.wallet import Faucet
from cogs.wallet import WalletAPI


class TopGGVote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.reward_channel = 522190259333890058

    async def guild_find_by_key(self, guild_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT `topgg_vote_secret` FROM `discord_server` WHERE `serverid`=%s """
                    await cur.execute(sql, (guild_id))
                    result = await cur.fetchone()
                    if result: return result['topgg_vote_secret']
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def guild_find_by_id(self, guild_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT * FROM `discord_server` WHERE `serverid`=%s """
                    await cur.execute(sql, (guild_id))
                    result = await cur.fetchone()
                    if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def insert_guild_vote(self, user_id: str, directory: str, guild_id: str, type_vote: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ INSERT IGNORE INTO guild_vote (`user_id`, `directory`, `guild_id`, `type`, `date_voted`) VALUES (%s, %s, %s, %s, %s) """
                    await cur.execute(sql, (user_id, directory, guild_id, type_vote, date_vote))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def check_last_guild_vote(self, user_id: str, directory: str, guild_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT * FROM `guild_vote` WHERE `user_id`=%s AND `directory`=%s AND `guild_id`=%s ORDER BY `date_voted` DESC LIMIT 1 """
                    await cur.execute(sql, (user_id, directory, guild_id))
                    result = await cur.fetchone()
                    if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def insert_bot_vote(self, user_id: str, directory: str, bot_id: str, type_vote: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ INSERT IGNORE INTO bot_vote (`user_id`, `directory`, `bot_id`, `type`, `date_voted`) VALUES (%s, %s, %s, %s, %s) """
                    await cur.execute(sql, (user_id, directory, bot_id, type_vote, date_vote))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def check_last_bot_vote(self, user_id: str, directory: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT * FROM `bot_vote` WHERE `user_id`=%s AND `directory`=%s ORDER BY `date_voted` DESC LIMIT 1 """
                    await cur.execute(sql, (user_id, directory))
                    result = await cur.fetchone()
                    if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def vote_logchan(self, content: str):
        try:
            webhook = DiscordWebhook(url=config.topgg.topgg_votehook, content=content)
            webhook.execute()
        except Exception:
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
                        if 'Authorization' in request.headers:
                            # Find Authorization correspond to server ID
                            key = request.headers['Authorization']
                            guild_id = full_payload['guild']
                            get_guild_by_key = await self.guild_find_by_key(guild_id)
                            # Check vote
                            try:
                                # Check if user just vote less than 1h. Sometimes top.gg just push too fast multiple times.
                                check_last_vote = await self.check_last_guild_vote(user_vote, "topgg", guild_id)
                                if check_last_vote is not None and int(time.time()) - check_last_vote[
                                    'date_voted'] < 3600 and type_vote != "test":
                                    await self.vote_logchan(
                                        f'[{SERVER_BOT}] A user <@{user_vote}> voted for guild `{guild_id}` type `{type_vote}` but less than 1h.')
                                    return web.Response(text="Thank you!")
                            except Exception:
                                traceback.print_exc(file=sys.stdout)

                            # Insert in DB no matter what
                            try:
                                insert_vote = await self.insert_guild_vote(full_payload['user'], "topgg",
                                                                           full_payload['guild'], full_payload['type'])
                            except Exception:
                                traceback.print_exc(file=sys.stdout)

                            if get_guild_by_key and get_guild_by_key == key.strip():
                                # Check if bot is in that guild, if not post in log chan vote
                                guild = self.bot.get_guild(int(guild_id))
                                get_guild = await self.guild_find_by_id(guild_id)
                                if get_guild['vote_reward_amount'] and get_guild['vote_reward_amount'] > 0:
                                    # Tip
                                    coin_name = get_guild['vote_reward_coin']
                                    # Check balance of guild
                                    net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                                    type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                                    deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name),
                                                                    "deposit_confirm_depth")
                                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                    contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                                    usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name),
                                                                    "usd_equivalent_enable")
                                    user_from = await self.wallet_api.sql_get_userwallet(guild_id, coin_name, net_name,
                                                                                         type_coin, SERVER_BOT, 0)
                                    if user_from is None:
                                        user_from = await self.wallet_api.sql_register_user(guild_id, coin_name,
                                                                                            net_name, type_coin,
                                                                                            SERVER_BOT, 0)
                                    wallet_address = user_from['balance_wallet_address']
                                    if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                        wallet_address = user_from['paymentid']
                                    elif type_coin in ["XRP"]:
                                        wallet_address = get_deposit['destination_tag']

                                    height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                                    # height can be None
                                    userdata_balance = await store.sql_user_balance_single(guild_id, coin_name,
                                                                                           wallet_address, type_coin,
                                                                                           height,
                                                                                           deposit_confirm_depth,
                                                                                           SERVER_BOT)
                                    total_balance = userdata_balance['adjust']
                                    amount = get_guild['vote_reward_amount']
                                    if total_balance < amount:
                                        # Alert guild owner
                                        guild_owner = self.bot.get_user(guild.owner.id)
                                        await guild_owner.send(
                                            f'Your guild run out of guild\'s reward for {coin_name}. Deposit more!')
                                    else:
                                        # Tip
                                        member = None
                                        try:
                                            member = self.bot.get_user(int(user_vote))
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        try:
                                            amount_in_usd = 0.0
                                            if usd_equivalent_enable == 1:
                                                native_token_name = getattr(getattr(self.bot.coin_list, coin_name),
                                                                            "native_token_name")
                                                coin_name_for_price = coin_name
                                                if native_token_name:
                                                    coin_name_for_price = native_token_name
                                                if coin_name_for_price in self.bot.token_hints:
                                                    id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                                                    per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                                                else:
                                                    per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price][
                                                        'price_usd']
                                                if per_unit and per_unit > 0:
                                                    amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                                            tip = await store.sql_user_balance_mv_single(guild_id, user_vote, "TOPGG",
                                                                                         "VOTE", amount, coin_name,
                                                                                         "GUILDVOTE", coin_decimal,
                                                                                         SERVER_BOT, contract,
                                                                                         amount_in_usd, None)
                                            if member is not None:
                                                msg = f"Thank you for voting for guild `{guild.name}` at top.gg. You got a reward {num_format_coin(amount, coin_name, coin_decimal, False)} {coin_name}."
                                                try:
                                                    await member.send(msg)
                                                    guild_owner = self.bot.get_user(guild.owner.id)
                                                    try:
                                                        await guild_owner.send(
                                                            f'User `{user_vote}` voted for your guild {guild.name} at top.gg. They got a reward {num_format_coin(amount, coin_name, coin_decimal, False)} {coin_name}.')
                                                    except Exception:
                                                        pass
                                                    # Log channel if there is
                                                    try:
                                                        serverinfo = await store.sql_info_by_server(guild_id)
                                                        if serverinfo and serverinfo['vote_reward_channel']:
                                                            channel = self.bot.get_channel(
                                                                int(serverinfo['vote_reward_channel']))
                                                            embed = disnake.Embed(title="NEW GUILD VOTE!",
                                                                                  timestamp=datetime.now())
                                                            embed.add_field(name="User",
                                                                            value="<@{}>".format(user_vote),
                                                                            inline=True)
                                                            embed.add_field(name="Reward", value="{} {}".format(
                                                                num_format_coin(amount, coin_name, coin_decimal, False),
                                                                coin_name), inline=True)
                                                            embed.add_field(name="Link",
                                                                            value="https://top.gg/servers/{}".format(
                                                                                guild_id), inline=False)
                                                            embed.set_author(name=self.bot.user.name,
                                                                             icon_url=self.bot.user.display_avatar)
                                                            await channel.send(embed=embed)
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                                        await self.vote_logchan(
                                                            f'[{SERVER_BOT}] Failed to send message to reward channel in guild: `{guild_id}` / {guild.name}.')
                                                except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                    await self.vote_logchan(
                                                        f'[{SERVER_BOT}] Failed to thank message to <@{user_vote}>.')
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                # TODO: Find bot channel
                                if guild:
                                    try:
                                        # TODO: change to bot channel
                                        await self.vote_logchan(
                                            f'[{SERVER_BOT}] A user <@{user_vote}> voted a guild `{guild_id}` type `{type_vote}` in top.gg.')
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                else:
                                    try:
                                        await self.vote_logchan(
                                            f'[{SERVER_BOT}] A user <@{user_vote}> voted a guild `{guild_id}` type `{type_vote}` in top.gg but I am not in that server or I can\'t find bot channel.')
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                return web.Response(text="Thank you!")
                            else:
                                try:
                                    await self.vote_logchan(
                                        f'[{SERVER_BOT}] A user <@{user_vote}> voted a guild `{guild_id}` type `{type_vote}` in top.gg but I am not in that guild or I cannot find it. Given key: `{key}`')
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                return web.Response(text="No such server by this key! Or not up to date!")
                        else:
                            return web.Response(text="No Authorization! Or not up to date!")
                    elif str(request.rel_url).startswith("/topgg_bot_vote/"):
                        # Bot: {'user': '386761001808166912', 'type': 'test', 'query': '', 'bot': '474841349968101386'}
                        if 'Authorization' in request.headers and request.headers['Authorization'] == config.topgg.auth:
                            vote_to = full_payload['bot']
                            try:
                                # Check if user just vote less than 1h. Sometimes top.gg just push too fast multiple times.
                                check_last_vote = await self.check_last_bot_vote(user_vote, "topgg")
                                if check_last_vote is not None and int(time.time()) - check_last_vote[
                                    'date_voted'] < 3600:
                                    await self.vote_logchan(
                                        f'[{SERVER_BOT}] A user <@{user_vote}> voted for bot <@{vote_to}> type `{type_vote}` but less than 1h.')
                                    return web.Response(text="Thank you!")
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            insert_vote = await self.insert_bot_vote(full_payload['user'], "topgg", full_payload['bot'],
                                                                     full_payload['type'])

                            if insert_vote:
                                try:
                                    await self.vote_logchan(
                                        f'[{SERVER_BOT}] A user <@{user_vote}> voted a bot <@{vote_to}> type `{type_vote}` in top.gg.')
                                    if int(vote_to) == config.discord.bot_id:
                                        # It's TipBot
                                        try:
                                            faucet = Faucet(self.bot)
                                            # get user preferred coin
                                            get_user_coin = await faucet.get_user_faucet_coin(user_vote, SERVER_BOT)
                                            member = None
                                            try:
                                                member = self.bot.get_user(int(user_vote))
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                            if get_user_coin is not None:
                                                # add reward
                                                list_coins = await faucet.get_faucet_coin_list()
                                                amount = 0.0
                                                coin_name = get_user_coin['coin_name']
                                                for each_coin in list_coins:
                                                    if each_coin['coin_name'].upper() == coin_name.upper() and \
                                                            each_coin['reward_for'] == "topgg":
                                                        coin_name = each_coin['coin_name'].upper()
                                                        amount = each_coin['reward_amount']
                                                        break
                                                if coin_name is not None:
                                                    insert_reward = await faucet.insert_reward(user_vote, "topgg",
                                                                                               amount, coin_name,
                                                                                               int(time.time()),
                                                                                               SERVER_BOT)
                                                    # Check balance of bot
                                                    net_name = getattr(getattr(self.bot.coin_list, coin_name),
                                                                       "net_name")
                                                    type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                                                    deposit_confirm_depth = getattr(
                                                        getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                                                    user_from = await self.wallet_api.sql_get_userwallet(
                                                        str(config.discord.bot_id), coin_name, net_name, type_coin,
                                                        SERVER_BOT, 0)
                                                    if user_from is None:
                                                        user_from = await self.wallet_api.sql_register_user(
                                                            str(config.discord.bot_id), coin_name, net_name, type_coin,
                                                            SERVER_BOT, 0)
                                                    wallet_address = user_from['balance_wallet_address']
                                                    if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                                        wallet_address = user_from['paymentid']
                                                    elif type_coin in ["XRP"]:
                                                        wallet_address = get_deposit['destination_tag']

                                                    height = self.wallet_api.get_block_height(type_coin, coin_name,
                                                                                              net_name)

                                                    # height can be None
                                                    userdata_balance = await store.sql_user_balance_single(
                                                        str(config.discord.bot_id), coin_name, wallet_address,
                                                        type_coin, height, deposit_confirm_depth, SERVER_BOT)
                                                    total_balance = userdata_balance['adjust']
                                                    if total_balance <= amount:
                                                        await self.vote_logchan(
                                                            f'[{SERVER_BOT}] vote reward for but TipBot for {coin_name} but empty!!!')
                                                        return web.Response(text="Thank you!")
                                                    else:
                                                        # move reward
                                                        try:
                                                            coin_decimal = getattr(
                                                                getattr(self.bot.coin_list, coin_name), "decimal")
                                                            contract = getattr(getattr(self.bot.coin_list, coin_name),
                                                                               "contract")
                                                            usd_equivalent_enable = getattr(
                                                                getattr(self.bot.coin_list, coin_name),
                                                                "usd_equivalent_enable")
                                                            amount_in_usd = 0.0
                                                            if usd_equivalent_enable == 1:
                                                                native_token_name = getattr(
                                                                    getattr(self.bot.coin_list, coin_name),
                                                                    "native_token_name")
                                                                coin_name_for_price = coin_name
                                                                if native_token_name:
                                                                    coin_name_for_price = native_token_name
                                                                if coin_name_for_price in self.bot.token_hints:
                                                                    id = self.bot.token_hints[coin_name_for_price][
                                                                        'ticker_name']
                                                                    per_unit = self.bot.coin_paprika_id_list[id][
                                                                        'price_usd']
                                                                else:
                                                                    per_unit = self.bot.coin_paprika_symbol_list[
                                                                        coin_name_for_price]['price_usd']
                                                                if per_unit and per_unit > 0:
                                                                    amount_in_usd = float(
                                                                        Decimal(per_unit) * Decimal(amount))
                                                            tip = await store.sql_user_balance_mv_single(
                                                                config.discord.bot_id, user_vote, "TOPGG", "VOTE",
                                                                amount, coin_name, "BOTVOTE", coin_decimal, SERVER_BOT,
                                                                contract, amount_in_usd, None)
                                                            if member is not None:
                                                                msg = f"Thank you for voting for our TipBot at <{config.bot_vote_link.topgg}>. You just got a reward {num_format_coin(amount, coin_name, coin_decimal, False)} {coin_name}. Check with `/claim` for voting list at other websites."
                                                                try:
                                                                    await member.send(msg)
                                                                except (
                                                                disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                                    await self.vote_logchan(
                                                                        f'[{SERVER_BOT}] Failed to thank message to <@{user_vote}>.')
                                                                try:
                                                                    channel = self.bot.get_channel(self.reward_channel)
                                                                    embed = disnake.Embed(title="NEW BOT VOTE!",
                                                                                          timestamp=datetime.now())
                                                                    embed.add_field(name="User",
                                                                                    value="<@{}>".format(user_vote),
                                                                                    inline=True)
                                                                    embed.add_field(name="Reward", value="{} {}".format(
                                                                        num_format_coin(amount, coin_name, coin_decimal,
                                                                                        False), coin_name), inline=True)
                                                                    embed.add_field(name="Link",
                                                                                    value=config.bot_vote_link.topgg,
                                                                                    inline=False)
                                                                    embed.set_author(name=self.bot.user.name,
                                                                                     icon_url=self.bot.user.display_avatar)
                                                                    await channel.send(embed=embed)
                                                                except Exception:
                                                                    traceback.print_exc(file=sys.stdout)
                                                        except Exception:
                                                            traceback.print_exc(file=sys.stdout)
                                            else:
                                                # User didn't put any prefer coin. Message him he could reward
                                                if member is not None:
                                                    msg = f"Thank you for voting for our TipBot at <{config.bot_vote_link.topgg}>. You can get a reward! Know more by `/claim` or `/claim token_name` to set your preferred coin/token reward."
                                                    try:
                                                        await member.send(msg)
                                                    except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                        await self.vote_logchan(
                                                            f'[{SERVER_BOT}] Failed to inform message to <@{user_vote}>.')
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            return web.Response(text="Thank you!")
                    else:
                        await self.vote_logchan(
                            f'[{SERVER_BOT}] A user <@{user_vote}> voted type `{type_vote}` but not true from top.gg.')
                        return web.Response(text="Thank you but not topgg!")
            except Exception:
                traceback.print_exc(file=sys.stdout)

        app = web.Application()
        app.router.add_get('/{tail:.*}', handler_get)
        app.router.add_post('/{tail:.*}', handler_post)
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, '127.0.0.1', 19902)
        await self.bot.wait_until_ready()
        await self.site.start()

    async def cog_load(self):
        # Automatically called when the cog is loaded
        # with the added benefit of being async!

        # Ensure the task is started when the cog is loaded,
        # and only after the bot is ready.
        await self.bot.wait_until_ready()

    def cog_unload(self):
        asyncio.ensure_future(self.site.stop())


def setup(bot):
    topgg = TopGGVote(bot)
    bot.add_cog(topgg)
    bot.loop.create_task(topgg.webserver())
