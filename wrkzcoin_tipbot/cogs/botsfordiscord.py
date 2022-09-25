import asyncio
import json
import sys
import time
import traceback
from datetime import datetime
from decimal import Decimal

import disnake
import store
from Bot import SERVER_BOT, num_format_coin
from aiohttp import web
from cogs.wallet import Faucet
from cogs.wallet import WalletAPI
from config import config
from discord_webhook import DiscordWebhook
from disnake.ext import commands


## this is also known as: https://discords.com/


class BFDBotVote(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.reward_channel = 522190259333890058

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
            webhook = DiscordWebhook(url=config.botsfordiscord.botsfordiscord_votehook, content=content)
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
                    # {'user': 'xxxxxxxxxx', 'bot': 'bot', 'query': {'one': 'hello', 'two': 'world'}, 'votes': {'totalVotes': 5, 'votes24': 5, 'votesMonth': 5, 'hasVoted': ['', '111111111111111111', '222222222222222222', '333333333333333333', '444444444444444444'], 'hasVoted24': ['xxxxxxxxxx', '111111111111111111', '222222222222222222']}, 'type': 'test'}
                    user_vote = full_payload['user']
                    type_vote = full_payload['type']
                    if str(request.rel_url).startswith("/bfd_bot_vote/"):  # discords.com
                        # Bot:
                        if 'Authorization' in request.headers and request.headers[
                            'Authorization'] == config.botsfordiscord.auth:
                            vote_to = str(config.discord.bot_id)  # full_payload['bot'] = 'bot'
                            try:
                                # Check if user just vote less than 1h. Sometimes just push too fast multiple times.
                                check_last_vote = await self.check_last_bot_vote(user_vote, "botsfordiscord")
                                if check_last_vote is not None and int(time.time()) - check_last_vote[
                                    'date_voted'] < 3600:
                                    await self.vote_logchan(
                                        f'[{SERVER_BOT}] A user <@{user_vote}> voted for bot <@{vote_to}> type `{type_vote}` but less than 1h.')
                                    return web.Response(text="Thank you!")
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            insert_vote = await self.insert_bot_vote(full_payload['user'], "botsfordiscord",
                                                                     full_payload['bot'], full_payload['type'])

                            if insert_vote:
                                try:
                                    await self.vote_logchan(
                                        f'[{SERVER_BOT}] A user <@{user_vote}> voted a bot <@{vote_to}> type `{type_vote}` in botsfordiscord.com.')
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
                                                            each_coin['reward_for'] == "botsfordiscord":
                                                        coin_name = each_coin['coin_name'].upper()
                                                        amount = each_coin['reward_amount']
                                                        break
                                                if coin_name is not None:
                                                    insert_reward = await faucet.insert_reward(user_vote,
                                                                                               "botsfordiscord", amount,
                                                                                               coin_name,
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
                                                        wallet_address = user_from['destination_tag']

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
                                                            try:
                                                                key_coin = config.discord.bot_id + "_" + coin_name + "_" + SERVER_BOT
                                                                if key_coin in self.bot.user_balance_cache:
                                                                    del self.bot.user_balance_cache[key_coin]

                                                                key_coin = user_vote + "_" + coin_name + "_" + SERVER_BOT
                                                                if key_coin in self.bot.user_balance_cache:
                                                                    del self.bot.user_balance_cache[key_coin]
                                                            except Exception:
                                                                pass
                                                            tip = await store.sql_user_balance_mv_single(
                                                                config.discord.bot_id, user_vote, "BOTSFORDISCORD",
                                                                "VOTE", amount, coin_name, "BOTVOTE", coin_decimal,
                                                                SERVER_BOT, contract, amount_in_usd, None)
                                                            if member is not None:
                                                                msg = f"Thank you for voting for our TipBot at <{config.bot_vote_link.botsfordiscord}>. You got a reward {num_format_coin(amount, coin_name, coin_decimal, False)} {coin_name}. Check with `/claim` for voting list at other websites."
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
                                                                                    value=config.bot_vote_link.botsfordiscord,
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
                                                    msg = f"Thank you for voting for our TipBot at <{config.bot_vote_link.botsfordiscord}>. You can get a reward! Know more by `/claim` or `/claim token_name` to set your preferred coin/token reward."
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
                            return web.Response(text="Unknown! Thank you!")
                    else:
                        await self.vote_logchan(
                            f'[{SERVER_BOT}] A user <@{user_vote}> voted for bot <@{self.bot.user.id}> type `{type_vote}` but not true from botsfordiscord.com.')
                        return web.Response(text="Thank you but not botsfordiscord!")
            except Exception:
                traceback.print_exc(file=sys.stdout)

        app = web.Application()
        app.router.add_get('/{tail:.*}', handler_get)
        app.router.add_post('/{tail:.*}', handler_post)
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, '127.0.0.1', 19905)
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
    BotsforDiscord = BFDBotVote(bot)
    bot.add_cog(BotsforDiscord)
    bot.loop.create_task(BotsforDiscord.webserver())
