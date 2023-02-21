from aiohttp import web
import asyncio
import traceback, sys

import disnake
from disnake.ext import commands
import json, time
from decimal import Decimal
import time
from datetime import datetime
import random

import store

from Bot import SERVER_BOT, log_to_channel
from cogs.wallet import Faucet
from cogs.wallet import WalletAPI
from cogs.utils import Utils, num_format_coin


class DiscadiaVote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.reward_channel = self.bot.config['bot_vote_link']['reward_channel']
        self.utils = Utils(self.bot)

    async def guild_find_by_key(self, guild_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT `discadia_vote_secret` 
                    FROM `discord_server` WHERE `serverid`=%s
                    """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchone()
                    if result:
                        return result['discadia_vote_secret']
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def guild_find_by_id(self, guild_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT * FROM `discord_server` 
                    WHERE `serverid`=%s
                    """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchone()
                    if result:
                        sql = """ SELECT * FROM `discord_feature_roles` 
                        WHERE `guild_id`=%s
                        """
                        await cur.execute(sql, guild_id)
                        feature_roles = await cur.fetchall()
                        list_roles_feature = None
                        if feature_roles and len(feature_roles) > 0:
                            list_roles_feature = {}
                            for each in feature_roles:
                                list_roles_feature[each['role_id']] = {
                                    'faucet_multipled_by': each['faucet_multipled_by'],
                                    'guild_vote_multiplied_by': each['guild_vote_multiplied_by'],
                                    'faucet_cut_time_percent': each['faucet_cut_time_percent']
                                }
                        result['feature_roles'] = list_roles_feature
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def insert_guild_vote(
        self, user_id: str, directory: str, guild_id: str, type_vote: str
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ INSERT IGNORE INTO guild_vote 
                    (`user_id`, `directory`, `guild_id`, `type`, `date_voted`) 
                    VALUES (%s, %s, %s, %s, %s)
                    """
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
                    sql = """ SELECT * FROM `guild_vote` 
                    WHERE `user_id`=%s AND `directory`=%s AND `guild_id`=%s 
                    ORDER BY `date_voted` DESC LIMIT 1
                    """
                    await cur.execute(sql, (user_id, directory, guild_id))
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def insert_bot_vote(self, user_id: str, directory: str, bot_id: str, type_vote: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ INSERT IGNORE INTO bot_vote 
                    (`user_id`, `directory`, `bot_id`, `type`, `date_voted`) 
                    VALUES (%s, %s, %s, %s, %s) """
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
                    sql = """ SELECT * FROM `bot_vote` WHERE `user_id`=%s AND `directory`=%s 
                    ORDER BY `date_voted` DESC LIMIT 1
                    """
                    await cur.execute(sql, (user_id, directory))
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def webserver(self):
        async def handler_get(request):
            return web.Response(text="Hello, world")

        async def handler_post(request):
            try:
                if request.body_exists:
                    payload = await request.read()
                    headers = request.headers
                    full_payload = json.loads(payload)
                    if 'user_id' not in full_payload and 'guild_id' not in full_payload and 'vote_url' not in full_payload:
                        return web.Response(text="Invalid hook given!")
                    user_vote = full_payload['user_id']
                    guild_id = full_payload['guild_id']
                    vote_url = full_payload['vote_url']
                    type_vote = "upvote" # constant here
                    if not user_vote.isdigit() or not guild_id.isdigit():
                        return web.Response(text="Invalid user_id or guild_id!")

                    if str(request.rel_url).startswith("/discadia_server_vote/"):
                        # https://discadia.com/help/vote-webhooks
                        key = str(request.rel_url).lower().replace("/discadia_server_vote/", "").replace("/", "").strip()
                        if len(key) == 0:
                            return web.Response(text="Invalid key!")
                        """
                        Sample payload
                        {
                            "user_id": "213698532983570432",
                            "guild_id": "429603128736874516",
                            "server_title": "Example Server",
                            "server_slug": "example-server",
                            "vote_url": "https://discadia.com/vote/example-server"
                        }
                        """                        
                        get_guild_by_key = await self.guild_find_by_key(guild_id)
                        # Check vote
                        try:
                            # Check if user just vote less than 1h. Sometimes discadia.com 
                            # just push too fast multiple times.
                            check_last_vote = await self.check_last_guild_vote(user_vote, "discadia", guild_id)
                            if check_last_vote is not None and int(time.time()) - check_last_vote[
                                'date_voted'] < 3600 and type_vote != "test":
                                await log_to_channel(
                                    "vote",
                                    f"[{SERVER_BOT}] User <@{user_vote}> voted for guild `{guild_id}` "\
                                    f"at discadia type `{type_vote}` but less than 1h."
                                )
                                return web.Response(text="Thank you!")
                        except Exception:
                            traceback.print_exc(file=sys.stdout)

                        # Insert in DB no matter what
                        try:
                            insert_vote = await self.insert_guild_vote(
                                user_vote, "discadia", guild_id, type_vote
                            )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)

                        if get_guild_by_key and get_guild_by_key == key.strip():
                            # Check if bot is in that guild, if not post in log chan vote
                            guild = self.bot.get_guild(int(guild_id))
                            get_guild = await self.guild_find_by_id(guild_id)
                            if get_guild['vote_reward_amount'] and get_guild['vote_reward_amount'] > 0:
                                amount = get_guild['vote_reward_amount']
                                extra_amount = 0.0
                                previous_amount = 0.0
                                if get_guild['feature_roles'] is not None:
                                    try:
                                        member = guild.get_member(int(user_vote))
                                        if member and member.roles and len(member.roles) > 0:
                                            for r in member.roles:
                                                if str(r.id) in get_guild['feature_roles']:
                                                    extra_amount = amount * get_guild['feature_roles'][str(r.id)]['guild_vote_multiplied_by'] - amount
                                                    if extra_amount > previous_amount:
                                                        previous_amount = extra_amount
                                            extra_amount = previous_amount
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                # Tip
                                coin_name = get_guild['vote_reward_coin']
                                # Check balance of guild
                                net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                                type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                                price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                                user_from = await self.wallet_api.sql_get_userwallet(
                                    guild_id, coin_name, net_name, type_coin, SERVER_BOT, 0
                                )
                                if user_from is None:
                                    user_from = await self.wallet_api.sql_register_user(
                                        guild_id, coin_name, net_name, type_coin, SERVER_BOT, 0
                                    )
                                wallet_address = user_from['balance_wallet_address']
                                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                    wallet_address = user_from['paymentid']
                                elif type_coin in ["XRP"]:
                                    wallet_address = user_from['destination_tag']

                                height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                                # height can be None
                                userdata_balance = await store.sql_user_balance_single(
                                    guild_id, coin_name, wallet_address, type_coin,
                                    height, deposit_confirm_depth, SERVER_BOT
                                )
                                total_balance = userdata_balance['adjust']
                                if total_balance < amount + extra_amount:
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
                                        if price_with:
                                            per_unit = await self.utils.get_coin_price(coin_name, price_with)
                                            if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                                per_unit = per_unit['price']
                                                amount_in_usd = float(Decimal(per_unit) * Decimal(amount + extra_amount))

                                        try:
                                            key_coin = guild_id + "_" + coin_name + "_" + SERVER_BOT
                                            if key_coin in self.bot.user_balance_cache:
                                                del self.bot.user_balance_cache[key_coin]

                                            key_coin = user_vote + "_" + coin_name + "_" + SERVER_BOT
                                            if key_coin in self.bot.user_balance_cache:
                                                del self.bot.user_balance_cache[key_coin]
                                        except Exception:
                                            pass
                                        tip = await store.sql_user_balance_mv_single(
                                            guild_id, user_vote, "DISCADIA", "VOTE", amount + extra_amount, coin_name,
                                            "GUILDVOTE", coin_decimal, SERVER_BOT, contract, amount_in_usd, None
                                        )
                                        # update discadia link
                                        try:
                                            if get_guild['discadia_link'] is None:
                                                await store.sql_changeinfo_by_server(guild_id, 'discadia_link', vote_url)
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        # end of update discadia link
                                        if member is not None:
                                            extra_msg = ""
                                            if extra_amount > 0:
                                                extra_msg = " You have a guild's role that give you additional "\
                                                    f"bonus **" + num_format_coin(extra_amount) \
                                                    + " " + coin_name + "**."
                                            msg = f"Thank you for voting for guild `{guild.name}` at discadia.com. "\
                                                f"You got a reward {num_format_coin(amount + extra_amount)} "\
                                                f"{coin_name}.{extra_msg}"
                                            try:
                                                await member.send(msg)
                                                guild_owner = self.bot.get_user(guild.owner.id)
                                                try:
                                                    await guild_owner.send(
                                                        f"User {member.name}#{member.discriminator} / `{user_vote}` voted for your guild {guild.name} "\
                                                        f"at discadia.com. They got a reward "\
                                                        f"{num_format_coin(amount + extra_amount)} {coin_name}."
                                                    )
                                                except Exception:
                                                    pass
                                                # Log channel if there is
                                                try:
                                                    serverinfo = await store.sql_info_by_server(guild_id)
                                                    if serverinfo and serverinfo['vote_reward_channel']:
                                                        channel = self.bot.get_channel(
                                                            int(serverinfo['vote_reward_channel'])
                                                        )
                                                        try:
                                                            coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                                                            coin_emoji = coin_emoji + " " if coin_emoji else ""
                                                            if channel and channel.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is False:
                                                                coin_emoji = ""
                                                        except Exception:
                                                            traceback.print_exc(file=sys.stdout)
                                                        embed = disnake.Embed(
                                                            title="NEW GUILD VOTE!",
                                                            timestamp=datetime.now()
                                                        )
                                                        embed.add_field(
                                                            name="User",
                                                            value="<@{}>".format(user_vote),
                                                            inline=True
                                                        )
                                                        embed.add_field(
                                                            name=f"{coin_emoji}Reward",
                                                            value="{} {}".format(
                                                                num_format_coin(amount),
                                                                coin_name
                                                            ),
                                                            inline=True
                                                        )
                                                        if extra_amount > 0:
                                                            embed.add_field(name="Extra Reward", value="{} {}".format(
                                                                num_format_coin(extra_amount),
                                                                coin_name), inline=True)
                                                        embed.add_field(
                                                            name="Link",
                                                            value=vote_url,
                                                            inline=False
                                                        )
                                                        # if advert enable
                                                        if self.bot.config['discord']['enable_advert'] == 1 and len(self.bot.advert_list) > 0:
                                                            try:
                                                                random.shuffle(self.bot.advert_list)
                                                                embed.add_field(
                                                                    name="{}".format(self.bot.advert_list[0]['title']),
                                                                    value="```{}```👉 <{}>".format(self.bot.advert_list[0]['content'], self.bot.advert_list[0]['link']),
                                                                    inline=False
                                                                )
                                                                await self.utils.advert_impress(
                                                                    self.bot.advert_list[0]['id'], user_vote,
                                                                    "GUILD VOTE"
                                                                )
                                                            except Exception:
                                                                traceback.print_exc(file=sys.stdout)
                                                        # end advert
                                                        embed.set_author(
                                                            name=self.bot.user.name,
                                                            icon_url=self.bot.user.display_avatar
                                                        )
                                                        embed.set_thumbnail(url=member.display_avatar)
                                                        await channel.send(embed=embed)
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                                    await log_to_channel(
                                                        "vote",
                                                        f"[{SERVER_BOT}] Failed to send message to "\
                                                        f"reward channel in guild: `{guild_id}` / {guild.name}."
                                                    )
                                                    try:
                                                        if serverinfo['vote_reward_channel']:
                                                            await guild_owner.send(
                                                                f"I can't publish an embed message to channel <#{serverinfo['vote_reward_channel']}> in your guild {guild.name} "\
                                                                f"which a user just voted at discadia.com. You received this message because you are the owner of the guild and "\
                                                                f"please help to fix the permission."
                                                            )
                                                    except Exception:
                                                        pass
                                            except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                await log_to_channel(
                                                    "vote",
                                                    f'[{SERVER_BOT}] Failed to thank message to <@{user_vote}>.'
                                                )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                            if guild:
                                try:
                                    await log_to_channel(
                                        "vote",
                                        f"[{SERVER_BOT}] User <@{user_vote}> voted a guild `{guild_id}` / "\
                                        f"{guild.name} type `{type_vote}` in discadia.com."
                                    )
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            else:
                                try:
                                    await log_to_channel(
                                        "vote",
                                        f"[{SERVER_BOT}] User <@{user_vote}> voted a guild `{guild_id}` / "\
                                        f"type `{type_vote}` in discadia.com but I am not in that server or I can't find bot channel."
                                    )
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            return web.Response(text="Thank you!")
                        else:
                            try:
                                await log_to_channel(
                                    "vote",
                                    f"[{SERVER_BOT}] User <@{user_vote}> voted a guild `{guild_id}` type `{type_vote}` "\
                                    f"in discadia.com but I am not in that guild or I cannot find it. Given key: `{key}`"
                                )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            return web.Response(text="No such server by this key! Or not up to date!")
                    else:
                        await log_to_channel(
                            "vote",
                            f"[{SERVER_BOT}] User <@{user_vote}> voted type `{type_vote}` but not true from discadia.com.")
                        return web.Response(text="Thank you but not discadia!")
            except Exception:
                traceback.print_exc(file=sys.stdout)

        app = web.Application()
        app.router.add_get('/{tail:.*}', handler_get)
        app.router.add_post('/{tail:.*}', handler_post)
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(
            runner,
            self.bot.config['bot_vote_link']['binding_ip'],
            self.bot.config['bot_vote_link']['discadia_port']
        )
        await self.bot.wait_until_ready()
        await self.site.start()

    async def cog_load(self):
        await self.bot.wait_until_ready()

    def cog_unload(self):
        asyncio.ensure_future(self.site.stop())


def setup(bot):
    discardia = DiscadiaVote(bot)
    bot.add_cog(discardia)
    bot.loop.create_task(discardia.webserver())
