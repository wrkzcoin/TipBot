import asyncio
import re
import sys
import time
import traceback
from datetime import datetime
import random
from decimal import Decimal

import disnake
from disnake.ext import commands

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
from disnake import ActionRow, Button, ButtonStyle
import json

import store
from Bot import logchanbot, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_INFORMATION, num_format_coin, seconds_str, RowButton_row_close_any_message, SERVER_BOT, EMOJI_HOURGLASS_NOT_DONE, remap_keys

# games.bagels
from games.bagels import getSecretNum as bagels_getSecretNum
from games.bagels import getClues as bagels_getClues
from games.hangman import drawHangman as hm_drawHangman
from games.hangman import load_words as hm_load_words

from games.maze2d import displayMaze as maze_displayMaze
from games.maze2d import createMazeDump as maze_createMazeDump

from games.blackjack import getDeck as blackjack_getDeck
from games.blackjack import displayHands as blackjack_displayHands
from games.blackjack import getCardValue as blackjack_getCardValue

from games.twentyfortyeight import getNewBoard as g2048_getNewBoard
from games.twentyfortyeight import drawBoard as g2048_drawBoard
from games.twentyfortyeight import getScore as g2048_getScore
from games.twentyfortyeight import addTwoToBoard as g2048_addTwoToBoard
from games.twentyfortyeight import isFull as g2048_isFull
from games.twentyfortyeight import makeMove as g2048_makeMove


from config import config


class database_games():

    async def sql_game_reward_random(self, game_name: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_bot_reward_games` 
                              WHERE `game_name`=%s 
                              ORDER BY RAND() LIMIT 1 """
                    await cur.execute(sql, (game_name))
                    result = await cur.fetchone()
                    if result is not None:
                        return result
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None


    async def sql_game_add(self, game_result: str, played_user: str, coin_name: str, win_lose: str, won_amount: float, decimal: int, played_server: str, game_type: str, duration: int=0, user_server: str = 'DISCORD'):
        game_result = game_result.replace("\t", "")
        user_server = user_server.upper()
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_game (`played_user`, `coin_name`, `win_lose`, 
                              `won_amount`, `decimal`, `played_server`, `played_at`, `game_type`, `user_server`, `game_result`, `duration`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (played_user, coin_name, win_lose, won_amount, decimal, played_server, 
                                            int(time.time()), game_type, user_server, game_result, duration))
                    await conn.commit()
                    return True
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None


    async def sql_game_free_add(self, game_result: str, played_user: str, win_lose: str, played_server: str, game_type: str, duration: int=0, user_server: str = 'DISCORD'):
        game_result = game_result.replace("\t", "")
        user_server = user_server.upper()
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_game_free (`played_user`, `win_lose`, `played_server`, `played_at`, `game_type`, `user_server`, `game_result`, `duration`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (played_user, win_lose, played_server, int(time.time()), game_type, user_server, game_result, duration))
                    await conn.commit()
                    return True
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None


    async def sql_game_stat(self):
        stat = {}
        GAME_COIN = config.game.coin_game.split(",")
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_game """
                    await cur.execute(sql,)
                    result_game = await cur.fetchall()
                    if result_game and len(result_game) > 0:
                        stat['paid_play'] = len(result_game)
                        # https://stackoverflow.com/questions/21518271/how-to-sum-values-of-the-same-key-in-a-dictionary
                        stat['paid_hangman_play'] = sum(d.get('HANGMAN', 0) for d in result_game)
                        stat['paid_bagel_play'] = sum(d.get('BAGEL', 0) for d in result_game)
                        stat['paid_slot_play'] = sum(d.get('SLOT', 0) for d in result_game)
                        for each in GAME_COIN:
                            stat[each] = sum(d.get('won_amount', 0) for d in result_game if d['coin_name'] == each)
                    sql = """ SELECT * FROM discord_game_free """
                    await cur.execute(sql,)
                    result_game_free = await cur.fetchall()
                    if result_game_free and len(result_game_free) > 0:
                        stat['free_play'] = len(result_game_free)
                        stat['free_hangman_play'] = sum(d.get('HANGMAN', 0) for d in result_game_free)
                        stat['free_bagel_play'] = sum(d.get('BAGEL', 0) for d in result_game_free)
                        stat['free_slot_play'] = sum(d.get('SLOT', 0) for d in result_game_free)
                return stat
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None


    async def sql_game_count_user(self, userID: str, lastDuration: int, user_server: str = 'DISCORD', free: bool=False):
        lapDuration = int(time.time()) - lastDuration
        user_server = user_server.upper()
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if free == False:
                        sql = """ SELECT COUNT(*) FROM discord_game WHERE `played_user` = %s AND `user_server`=%s 
                                  AND `played_at`>%s """
                    else:
                        sql = """ SELECT COUNT(*) FROM discord_game_free WHERE `played_user` = %s AND `user_server`=%s 
                                  AND `played_at`>%s """
                    await cur.execute(sql, (userID, user_server, lapDuration))
                    result = await cur.fetchone()
                    return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None


    async def sql_game_get_level_user(self, userid: str, game_name: str):
        level = -1
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_game WHERE `played_user`=%s 
                              AND `game_type`=%s AND `win_lose`=%s ORDER BY `played_at` DESC LIMIT 1 """
                    await cur.execute(sql, (userid, game_name.upper(), 'WIN'))
                    result = await cur.fetchone()
                    if result and len(result) > 0:
                        try:
                            level = int(result['game_result'])
                        except Exception as e:
                            await logchanbot(traceback.format_exc())

                    sql = """ SELECT * FROM discord_game_free WHERE `played_user`=%s 
                              AND `game_type`=%s AND `win_lose`=%s ORDER BY `played_at` DESC LIMIT 1 """
                    await cur.execute(sql, (userid, game_name.upper(), 'WIN'))
                    result = await cur.fetchone()
                    if result and len(result) > 0:
                        try:
                            if level and int(result['game_result']) > level:
                                level = int(result['game_result'])
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                    return level
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return level


    async def sql_game_get_level_tpl(self, level: int, game_name: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_game_level_tpl WHERE `level`=%s 
                              AND `game_name`=%s LIMIT 1 """
                    await cur.execute(sql, (level, game_name.upper()))
                    result = await cur.fetchone()
                    if result and len(result) > 0:
                        return result
                    else:
                        return None
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None
    
# Defines a simple view of row buttons.
class BlackJack_Buttons(disnake.ui.View):
    message: disnake.Message
    game_over: bool = False
    player_over: bool = False


    def __init__(self, ctx, bot, free_game: bool=False, timeout: float=30.0):
        super().__init__(timeout=timeout)
        self.time_start = int(time.time())
        self.ctx = ctx
        self.bot = bot
        self.free_game = free_game
        self.db = database_games()
        self.deck = blackjack_getDeck()
        self.dealerHand = [self.deck.pop(), self.deck.pop()]
        self.playerHand = [self.deck.pop(), self.deck.pop()]
        self.get_display = blackjack_displayHands(self.playerHand, self.dealerHand, False)
        self.playerValue = blackjack_getCardValue(self.playerHand)
        self.dealerValue = blackjack_getCardValue(self.dealerHand)
        if blackjack_getCardValue(self.playerHand) >= 21:
            self.player_over = True

        self.stand_button.disabled = True
        self.hit_button.disabled = True


    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)


    # Creates a row of buttons and when one of them is pressed, it will send a message with the number of the button.
    @disnake.ui.button(label="Start", style=ButtonStyle.red)
    async def start_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return

        try:
            msg = '{} **BLACKJACK**\n```DEALER: {}\n{}\nPLAYER:  {}\n{}```'.format(interaction.author.mention, self.get_display['dealer_header'], self.get_display['dealer'], self.get_display['player_header'], self.get_display['player'])
            button.disabled = True
            self.stand_button.disabled = False
            self.hit_button.disabled = False
            await self.message.edit(content=msg, view=self)
            await interaction.response.send_message("Blackjack started...")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    # Creates a row of buttons and when one of them is pressed, it will send a message with the number of the button.
    @disnake.ui.button(label="✋ Stand", style=ButtonStyle.red)
    async def stand_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return

        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True

        await self.message.edit(view=self)
        await interaction.response.send_message('{} **BLACKJACK** You selected to stand.'.format(interaction.author.mention))
        self.player_over = True

        if blackjack_getCardValue(self.playerHand) <= 21:
            while not self.game_over:
                if blackjack_getCardValue(self.dealerHand) >= 17 or blackjack_getCardValue(self.dealerHand) >= blackjack_getCardValue(self.playerHand):
                    self.game_over = True
                    break
                else:
                    while blackjack_getCardValue(self.dealerHand) < 17:
                        # The dealer hits:
                        try:
                            dealer_msg = await interaction.channel.send("{} **BLACKJACK**\n```Dealer hits...```".format(interaction.author.mention))
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        newCard = self.deck.pop()
                        rank, suit = newCard
                        self.dealerHand.append(newCard)
                        await asyncio.sleep(2)
                        await dealer_msg.edit(content='{} **BLACKJACK** Dealer drew a {} of {}'.format(interaction.author.mention, rank, suit))

                        if blackjack_getCardValue(self.dealerHand) > 21:
                            self.game_over = True  # The dealer has busted.
                            break
                        else:
                            await asyncio.sleep(2)
        else:
            self.game_over = True

        playerValue = blackjack_getCardValue(self.playerHand)
        dealerValue = blackjack_getCardValue(self.dealerHand)

        if self.game_over == True and self.player_over == True:
            won = False
            get_random_reward = await self.db.sql_game_reward_random("BLACKJACK")
            amount = get_random_reward['reward_amount']
            COIN_NAME = get_random_reward['coin_name']
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")

            result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
            if self.free_game == True:
                result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

            dealer_get_display = blackjack_displayHands(self.playerHand, self.dealerHand, True)
            msg = '{} **BLACKJACK**\n```DEALER: {}\n{}\nPLAYER:  {}\n{}```'.format(interaction.author.mention, dealer_get_display['dealer_header'], dealer_get_display['dealer'], dealer_get_display['player_header'], dealer_get_display['player'])
            await self.message.edit(content=msg, view=None)
            if dealerValue > 21:
                won = True
                await interaction.channel.send('{} **BLACKJACK**\n```Dealer busts! You win! {}```'.format(interaction.author.mention, result))
            elif playerValue > 21 or playerValue < dealerValue:
                await interaction.channel.send('{} **BLACKJACK**\n```You lost!```'.format(interaction.author.mention))
            elif playerValue > dealerValue:
                won = True
                await interaction.channel.send('{} **BLACKJACK**\n```You won! {}```'.format(interaction.author.mention, result))
            elif playerValue == dealerValue:
                await interaction.channel.send('{} **BLACKJACK**\n```It\'s a tie!```'.format(interaction.author.mention))

            # Start reward
            if self.free_game == False:
                try:
                    reward = await self.db.sql_game_add('BLACKJACK: PLAYER={}, DEALER={}'.format(playerValue, dealerValue), str(interaction.author.id), COIN_NAME, 'WIN' if won else 'LOSE', amount, coin_decimal, str(interaction.guild.id), 'BLACKJACK', int(time.time()) - self.time_start, SERVER_BOT)
                    
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                # add reward him credit
                if won:
                    amount_in_usd = 0.0
                    per_unit = None
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
                    try:
                        tip = await store.sql_user_balance_mv_single(self.bot.user.id, str(interaction.user.id), str(interaction.guild.id), str(interaction.channel.id), amount, COIN_NAME, "GAME", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
            else:
                try:
                    await self.db.sql_game_free_add('BLACKJACK: PLAYER={}, DEALER={}'.format(playerValue, dealerValue), str(interaction.author.id), 'WIN' if won else 'LOSE', str(interaction.guild.id), 'BLACKJACK', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            # End reward
        else:
            dealer_get_display = blackjack_displayHands(self.playerHand, self.dealerHand, False)
            msg = '{} **BLACKJACK**\n```DEALER: {}\n{}\nPLAYER:  {}\n{}```'.format(interaction.author.mention, dealer_get_display['dealer_header'], dealer_get_display['dealer'], dealer_get_display['player_header'], dealer_get_display['player'])
            await self.message.edit(content=msg, view=self)


    @disnake.ui.button(label="☝️ Hit", style=ButtonStyle.red)
    async def hit_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return

        newCard = self.deck.pop()
        rank, suit = newCard
        await interaction.response.send_message('{} **BLACKJACK** You drew a {} of {}'.format(interaction.author.mention, rank, suit))
        self.playerHand.append(newCard)

        dealer_get_display = blackjack_displayHands(self.playerHand, self.dealerHand, False)
        msg = '{} **BLACKJACK**\n```DEALER: {}\n{}\nPLAYER:  {}\n{}```'.format(interaction.author.mention, dealer_get_display['dealer_header'], dealer_get_display['dealer'], dealer_get_display['player_header'], dealer_get_display['player'])

        if blackjack_getCardValue(self.playerHand) >= 21:
            # The player has busted:
            self.player_over = True
            self.game_over = True
            button.disabled = True
        else:
            if blackjack_getCardValue(self.dealerHand) >= 17:
                self.game_over = True
            else:
                if blackjack_getCardValue(self.dealerHand) < 17:
                    # The dealer hits:
                    try:
                        dealer_msg = await interaction.channel.send("{} **BLACKJACK**\n```Dealer hits...```".format(interaction.author.mention))
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    newCard = self.deck.pop()
                    rank, suit = newCard
                    self.dealerHand.append(newCard)
                    await asyncio.sleep(1)
                    await dealer_msg.edit(content='{} **BLACKJACK** Dealer drew a {} of {}'.format(interaction.author.mention, rank, suit))

                    if blackjack_getCardValue(self.dealerHand) > 21:
                        self.game_over = True  # The dealer has busted.
                    else:
                        await asyncio.sleep(1)

        playerValue = blackjack_getCardValue(self.playerHand)
        dealerValue = blackjack_getCardValue(self.dealerHand)

        if self.game_over == True and self.player_over == True:
            won = False
            get_random_reward = await self.db.sql_game_reward_random("BLACKJACK")
            amount = get_random_reward['reward_amount']
            COIN_NAME = get_random_reward['coin_name']
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
            if self.free_game == True:
                result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

            dealer_get_display = blackjack_displayHands(self.playerHand, self.dealerHand, True)
            msg = '{} **BLACKJACK**\n```DEALER: {}\n{}\nPLAYER:  {}\n{}```'.format(interaction.author.mention, dealer_get_display['dealer_header'], dealer_get_display['dealer'], dealer_get_display['player_header'], dealer_get_display['player'])
            await self.message.edit(content=msg, view=None)
            if dealerValue > 21:
                won = True
                await interaction.channel.send('{} **BLACKJACK**\n```Dealer busts! You win! {}```'.format(interaction.author.mention, result))
            elif playerValue > 21 or playerValue < dealerValue:
                await interaction.channel.send('{} **BLACKJACK**\n```You lost!```'.format(interaction.author.mention))
            elif playerValue > dealerValue:
                won = True
                await interaction.channel.send('{} **BLACKJACK**\n```You won! {}```'.format(interaction.author.mention, result))
            elif playerValue == dealerValue:
                await interaction.channel.send('{} **BLACKJACK**\n```It\'s a tie!```'.format(interaction.author.mention))

            # Start reward
            if self.free_game == False:
                try:
                    reward = await self.db.sql_game_add('BLACKJACK: PLAYER={}, DEALER={}'.format(playerValue, dealerValue), str(interaction.author.id), COIN_NAME, 'WIN' if won else 'LOSE', amount, coin_decimal, str(interaction.guild.id), 'BLACKJACK', int(time.time()) - self.time_start, SERVER_BOT)
                    
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                # add reward him credit
                if won:
                    amount_in_usd = 0.0
                    per_unit = None
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
                    try:
                        tip = await store.sql_user_balance_mv_single(self.bot.user.id, str(interaction.user.id), str(interaction.guild.id), str(interaction.channel.id), amount, COIN_NAME, "GAME", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
            else:
                try:
                    await self.db.sql_game_free_add('BLACKJACK: PLAYER={}, DEALER={}'.format(playerValue, dealerValue), str(interaction.author.id), 'WIN' if won else 'LOSE', str(interaction.guild.id), 'BLACKJACK', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            # End reward
        else:
            dealer_get_display = blackjack_displayHands(self.playerHand, self.dealerHand, False)
            msg = '{} **BLACKJACK**\n```DEALER: {}\n{}\nPLAYER:  {}\n{}```'.format(interaction.author.mention, dealer_get_display['dealer_header'], dealer_get_display['dealer'], dealer_get_display['player_header'], dealer_get_display['player'])
            await self.message.edit(content=msg, view=self)


# Defines a simple view of row buttons.
class Maze_Buttons(disnake.ui.View):
    message: disnake.Message
    maze_created: str = None

    def __init__(self, ctx, bot, free_game: bool=False, timeout: float=30.0):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.bot = bot
        self.time_start = int(time.time())
        self.game_over = False
        self.free_game = free_game
        self.db = database_games()

        self.WALL = '#'
        self.WIDTH = random.choice([25, 27, 29, 31, 33, 35])
        self.HEIGHT = random.choice([15, 17, 19, 21, 23, 25])
        self.SEED = random.randint(25, 50)
        self.EMPTY = ' '
        self.maze_data = maze_createMazeDump(self.WIDTH, self.HEIGHT, self.SEED)
        self.playerx, self.playery = 1, 1
        self.exitx, self.exity = self.WIDTH - 2, self.HEIGHT - 2
        self.maze_created = maze_displayMaze(self.maze_data, self.WIDTH, self.HEIGHT, self.playerx, self.playery, self.exitx, self.exity)


    async def on_timeout(self):
        if self.game_over == False:
            for child in self.children:
                if isinstance(child, disnake.ui.Button):
                    child.disabled = True
            await self.message.edit(view=self)
            await self.message.reply(f'{self.ctx.author.mention}, time running out.')


    @disnake.ui.button(label="🔼", style=ButtonStyle.red)
    async def up_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return

        if self.maze_data[(self.playerx, self.playery - 1)] == self.EMPTY:
            while True:
                self.playery -= 1
                if (self.playerx, self.playery) == (self.exitx, self.exity):
                    break
                if self.maze_data[(self.playerx, self.playery - 1)] == self.WALL:
                    break  # Break if we've hit a wall.
                if (self.maze_data[(self.playerx - 1, self.playery)] == self.EMPTY
                    or self.maze_data[(self.playerx + 1, self.playery)] == self.EMPTY):
                    break  # Break if we've reached a branch point.

        try:
            maze_edit = maze_displayMaze(self.maze_data, self.WIDTH, self.HEIGHT, self.playerx, self.playery, self.exitx, self.exity)
            await self.message.edit(content=f'{self.ctx.author.mention} Maze:\n```{maze_edit}```', view=self)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        if (self.playerx, self.playery) == (self.exitx, self.exity):
            self.game_over = True
            won = True
            get_random_reward = await self.db.sql_game_reward_random("MAZE")
            amount = get_random_reward['reward_amount']
            COIN_NAME = get_random_reward['coin_name']
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            
            result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
            if self.free_game == True:
                result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

            for child in self.children:
                if isinstance(child, disnake.ui.Button):
                    child.disabled = True
            await self.message.edit(view=self)

            duration = seconds_str(int(time.time()) - self.time_start)
            await self.message.reply(f'{self.ctx.author.mention} **MAZE** Grats! You completed! You completed in: **{duration}\n{result}**')

            # Start reward
            if self.free_game == False:
                try:
                    reward = await self.db.sql_game_add(json.dumps(remap_keys(self.maze_data)), str(interaction.author.id), COIN_NAME, 'WIN' if won else 'LOSE', amount, coin_decimal, str(interaction.guild.id), 'MAZE', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                # add reward him credit
                if won:
                    amount_in_usd = 0.0
                    per_unit = None
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
                    try:
                        tip = await store.sql_user_balance_mv_single(self.bot.user.id, str(interaction.user.id), str(interaction.guild.id), str(interaction.channel.id), amount, COIN_NAME, "GAME", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
            else:
                try:
                    await self.db.sql_game_free_add(json.dumps(remap_keys(self.maze_data)), str(interaction.author.id), 'WIN' if won else 'LOSE', str(interaction.guild.id), 'MAZE', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            # End reward

        await interaction.response.defer()


    @disnake.ui.button(label="🔽", style=ButtonStyle.red)
    async def down_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return
        if  self.maze_data[(self.playerx, self.playery + 1)] == self.EMPTY:
            while True:
                self.playery += 1
                if (self.playerx, self.playery) == (self.exitx, self.exity):
                    break
                if self.maze_data[(self.playerx, self.playery + 1)] == self.WALL:
                    break  # Break if we've hit a wall.
                if (self.maze_data[(self.playerx - 1, self.playery)] == self.EMPTY
                    or self.maze_data[(self.playerx + 1, self.playery)] == self.EMPTY):
                    break  # Break if we've reached a branch point.

        try:
            maze_edit = maze_displayMaze(self.maze_data, self.WIDTH, self.HEIGHT, self.playerx, self.playery, self.exitx, self.exity)
            await self.message.edit(content=f'{self.ctx.author.mention} Maze:\n```{maze_edit}```', view=self)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        if (self.playerx, self.playery) == (self.exitx, self.exity):
            self.game_over = True
            won = True
            get_random_reward = await self.db.sql_game_reward_random("MAZE")
            amount = get_random_reward['reward_amount']
            COIN_NAME = get_random_reward['coin_name']
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            
            result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
            if self.free_game == True:
                result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

            for child in self.children:
                if isinstance(child, disnake.ui.Button):
                    child.disabled = True
            await self.message.edit(view=self)

            duration = seconds_str(int(time.time()) - self.time_start)
            await self.message.reply(f'{self.ctx.author.mention} **MAZE** Grats! You completed! You completed in: **{duration}\n{result}**')

           # Start reward
            if self.free_game == False:
                try:
                    reward = await self.db.sql_game_add(json.dumps(remap_keys(self.maze_data)), str(interaction.author.id), COIN_NAME, 'WIN' if won else 'LOSE', amount, coin_decimal, str(interaction.guild.id), 'MAZE', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                # add reward him credit
                if won:
                    amount_in_usd = 0.0
                    per_unit = None
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
                    try:
                        tip = await store.sql_user_balance_mv_single(self.bot.user.id, str(interaction.user.id), str(interaction.guild.id), str(interaction.channel.id), amount, COIN_NAME, "GAME", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
            else:
                try:
                    await self.db.sql_game_free_add(json.dumps(remap_keys(self.maze_data)), str(interaction.author.id), 'WIN' if won else 'LOSE', str(interaction.guild.id), 'MAZE', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            # End reward

        await interaction.response.defer()


    @disnake.ui.button(label="◀️", style=ButtonStyle.red)
    async def left_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return
        if self.maze_data[(self.playerx - 1, self.playery)] == self.EMPTY:
            while True:
                self.playerx -= 1
                if (self.playerx, self.playery) == (self.exitx, self.exity):
                    break
                if self.maze_data[(self.playerx - 1, self.playery)] == self.WALL:
                    break  # Break if we've hit a wall.
                if (self.maze_data[(self.playerx, self.playery - 1)] == self.EMPTY
                    or self.maze_data[(self.playerx, self.playery + 1)] == self.EMPTY):
                    break  # Break if we've reached a branch point.

        try:
            maze_edit = maze_displayMaze(self.maze_data, self.WIDTH, self.HEIGHT, self.playerx, self.playery, self.exitx, self.exity)
            await self.message.edit(content=f'{self.ctx.author.mention} Maze:\n```{maze_edit}```', view=self)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        if (self.playerx, self.playery) == (self.exitx, self.exity):
            self.game_over = True
            won = True
            get_random_reward = await self.db.sql_game_reward_random("MAZE")
            amount = get_random_reward['reward_amount']
            COIN_NAME = get_random_reward['coin_name']
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            
            result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
            if self.free_game == True:
                result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

            for child in self.children:
                if isinstance(child, disnake.ui.Button):
                    child.disabled = True
            await self.message.edit(view=self)

            duration = seconds_str(int(time.time()) - self.time_start)
            await self.message.reply(f'{self.ctx.author.mention} **MAZE** Grats! You completed! You completed in: **{duration}\n{result}**')

            # Start reward
            if self.free_game == False:
                try:
                    reward = await self.db.sql_game_add(json.dumps(remap_keys(self.maze_data)), str(interaction.author.id), COIN_NAME, 'WIN' if won else 'LOSE', amount, coin_decimal, str(interaction.guild.id), 'MAZE', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                # add reward him credit
                if won:
                    amount_in_usd = 0.0
                    per_unit = None
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
                    try:
                        tip = await store.sql_user_balance_mv_single(self.bot.user.id, str(interaction.user.id), str(interaction.guild.id), str(interaction.channel.id), amount, COIN_NAME, "GAME", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
            else:
                try:
                    await self.db.sql_game_free_add(json.dumps(remap_keys(self.maze_data)), str(interaction.author.id), 'WIN' if won else 'LOSE', str(interaction.guild.id), 'MAZE', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            # End reward

        await interaction.response.defer()


    @disnake.ui.button(label="▶️", style=ButtonStyle.red)
    async def right_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return
        if self.maze_data[(self.playerx + 1, self.playery)] == self.EMPTY:
            while True:
                self.playerx += 1
                if (self.playerx, self.playery) == (self.exitx, self.exity):
                    break
                if self.maze_data[(self.playerx + 1, self.playery)] == self.WALL:
                    break  # Break if we've hit a wall.
                if (self.maze_data[(self.playerx, self.playery - 1)] == self.EMPTY
                    or self.maze_data[(self.playerx, self.playery + 1)] == self.EMPTY):
                    break  # Break if we've reached a branch point.

        try:
            maze_edit = maze_displayMaze(self.maze_data, self.WIDTH, self.HEIGHT, self.playerx, self.playery, self.exitx, self.exity)
            await self.message.edit(content=f'{self.ctx.author.mention} Maze:\n```{maze_edit}```', view=self)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        if (self.playerx, self.playery) == (self.exitx, self.exity):
            self.game_over = True
            won = True
            get_random_reward = await self.db.sql_game_reward_random("MAZE")
            amount = get_random_reward['reward_amount']
            COIN_NAME = get_random_reward['coin_name']
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            
            result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
            if self.free_game == True:
                result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

            for child in self.children:
                if isinstance(child, disnake.ui.Button):
                    child.disabled = True
            await self.message.edit(view=self)

            duration = seconds_str(int(time.time()) - self.time_start)
            await self.message.reply(f'{self.ctx.author.mention} **MAZE** Grats! You completed! You completed in: **{duration}\n{result}**')

           # Start reward
            if self.free_game == False:
                try:
                    reward = await self.db.sql_game_add(json.dumps(remap_keys(self.maze_data)), str(interaction.author.id), COIN_NAME, 'WIN' if won else 'LOSE', amount, coin_decimal, str(interaction.guild.id), 'MAZE', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                # add reward him credit
                if won:
                    amount_in_usd = 0.0
                    per_unit = None
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
                    try:
                        tip = await store.sql_user_balance_mv_single(self.bot.user.id, str(interaction.user.id), str(interaction.guild.id), str(interaction.channel.id), amount, COIN_NAME, "GAME", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
            else:
                try:
                    await self.db.sql_game_free_add(json.dumps(remap_keys(self.maze_data)), str(interaction.author.id), 'WIN' if won else 'LOSE', str(interaction.guild.id), 'MAZE', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            # End reward

        await interaction.response.defer()


    @disnake.ui.button(label="⏹️", style=ButtonStyle.red)
    async def stop_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return

        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)
        await self.message.reply(f'{self.ctx.author.mention}, you gave up the current game.')
        self.game_over = True
        await interaction.response.defer()


# Defines a simple view of row buttons.
class g2048_Buttons(disnake.ui.View):
    message: disnake.Message

    def __init__(self, ctx, bot, free_game: bool=False, timeout: float=30.0):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.bot = bot
        self.free_game = free_game
        self.db = database_games()
        self.time_start = int(time.time())
        self.game_over = False

        self.score = 0
        self.gameBoard = g2048_getNewBoard()
        self.board = g2048_drawBoard(self.gameBoard)


    async def on_timeout(self):
        if self.game_over == False:
            for child in self.children:
                if isinstance(child, disnake.ui.Button):
                    child.disabled = True
            await self.message.edit(view=self)
            await self.message.reply(f'{self.ctx.author.mention}, time running out.')


    @disnake.ui.button(label="🔼", style=ButtonStyle.red)
    async def up_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return

        self.gameBoard = g2048_makeMove(self.gameBoard, 'W')
        g2048_addTwoToBoard(self.gameBoard)
        self.board = g2048_drawBoard(self.gameBoard)
        self.score = g2048_getScore(self.gameBoard)
        if g2048_isFull(self.gameBoard):
            if self.ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                self.bot.GAME_INTERACTIVE_PRGORESS.remove(self.ctx.author.id)
            self.board = g2048_drawBoard(self.gameBoard)
            duration = seconds_str(int(time.time()) - self.time_start)

            get_random_reward = await self.db.sql_game_reward_random("SOKOBAN")
            amount = get_random_reward['reward_amount']
            COIN_NAME = get_random_reward['coin_name']
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
            if self.free_game == True:
                result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

            for child in self.children:
                if isinstance(child, disnake.ui.Button):
                    child.disabled = True

            await self.message.edit(content=f'**{self.ctx.author.mention} Game Over**```{self.board}```Your score: **{self.score}**\nYou have spent time: **{duration}**\n{result}', view=None)

            # Start reward
            if self.free_game == False:
                try:
                    reward = await self.db.sql_game_add(self.board, str(interaction.author.id), COIN_NAME, str(self.score), amount, coin_decimal, str(interaction.guild.id), '2048', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                # add reward him credit
                amount_in_usd = 0.0
                per_unit = None
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
                try:
                    tip = await store.sql_user_balance_mv_single(self.bot.user.id, str(interaction.user.id), str(interaction.guild.id), str(interaction.channel.id), amount, COIN_NAME, "GAME", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            else:
                try:
                    await self.db.sql_game_free_add(self.board, str(interaction.author.id), str(self.score), str(interaction.guild.id), '2048', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            # End reward
        else:
            await self.message.edit(content=f'{self.ctx.author.mention}```GAME 2048\n{self.board}```Your score: **{self.score}**', view=self)

        # Defer
        await interaction.response.defer()


    @disnake.ui.button(label="🔽", style=ButtonStyle.red)
    async def down_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return

        self.gameBoard = g2048_makeMove(self.gameBoard, 'S')
        g2048_addTwoToBoard(self.gameBoard)
        self.board = g2048_drawBoard(self.gameBoard)
        self.score = g2048_getScore(self.gameBoard)
        if g2048_isFull(self.gameBoard):
            if self.ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                self.bot.GAME_INTERACTIVE_PRGORESS.remove(self.ctx.author.id)
            self.board = g2048_drawBoard(self.gameBoard)
            duration = seconds_str(int(time.time()) - self.time_start)

            get_random_reward = await self.db.sql_game_reward_random("SOKOBAN")
            amount = get_random_reward['reward_amount']
            COIN_NAME = get_random_reward['coin_name']
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
            if self.free_game == True:
                result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

            for child in self.children:
                if isinstance(child, disnake.ui.Button):
                    child.disabled = True

            await self.message.edit(content=f'**{self.ctx.author.mention} Game Over**```{self.board}```Your score: **{self.score}**\nYou have spent time: **{duration}**\n{result}', view=None)

            # Start reward
            if self.free_game == False:
                try:
                    reward = await self.db.sql_game_add(self.board, str(interaction.author.id), COIN_NAME, str(self.score), amount, coin_decimal, str(interaction.guild.id), '2048', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                # add reward him credit
                amount_in_usd = 0.0
                per_unit = None
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
                try:
                    tip = await store.sql_user_balance_mv_single(self.bot.user.id, str(interaction.user.id), str(interaction.guild.id), str(interaction.channel.id), amount, COIN_NAME, "GAME", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            else:
                try:
                    await self.db.sql_game_free_add(self.board, str(interaction.author.id), str(self.score), str(interaction.guild.id), '2048', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            # End reward
        else:
            await self.message.edit(content=f'{self.ctx.author.mention}```GAME 2048\n{self.board}```Your score: **{self.score}**', view=self)

        # Defer
        await interaction.response.defer()


    @disnake.ui.button(label="◀️", style=ButtonStyle.red)
    async def left_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return

        self.gameBoard = g2048_makeMove(self.gameBoard, 'A')
        g2048_addTwoToBoard(self.gameBoard)
        self.board = g2048_drawBoard(self.gameBoard)
        self.score = g2048_getScore(self.gameBoard)
        if g2048_isFull(self.gameBoard):
            if self.ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                self.bot.GAME_INTERACTIVE_PRGORESS.remove(self.ctx.author.id)
            self.board = g2048_drawBoard(self.gameBoard)
            duration = seconds_str(int(time.time()) - self.time_start)

            get_random_reward = await self.db.sql_game_reward_random("SOKOBAN")
            amount = get_random_reward['reward_amount']
            COIN_NAME = get_random_reward['coin_name']
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
            if self.free_game == True:
                result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

            for child in self.children:
                if isinstance(child, disnake.ui.Button):
                    child.disabled = True

            await self.message.edit(content=f'**{self.ctx.author.mention} Game Over**```{self.board}```Your score: **{self.score}**\nYou have spent time: **{duration}**\n{result}', view=None)

            # Start reward
            if self.free_game == False:
                try:
                    reward = await self.db.sql_game_add(self.board, str(interaction.author.id), COIN_NAME, str(self.score), amount, coin_decimal, str(interaction.guild.id), '2048', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                # add reward him credit
                amount_in_usd = 0.0
                per_unit = None
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
                try:
                    tip = await store.sql_user_balance_mv_single(self.bot.user.id, str(interaction.user.id), str(interaction.guild.id), str(interaction.channel.id), amount, COIN_NAME, "GAME", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            else:
                try:
                    await self.db.sql_game_free_add(self.board, str(interaction.author.id), str(self.score), str(interaction.guild.id), '2048', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            # End reward
        else:
            await self.message.edit(content=f'{self.ctx.author.mention}```GAME 2048\n{self.board}```Your score: **{self.score}**', view=self)
        # Defer
        await interaction.response.defer()


    @disnake.ui.button(label="▶️", style=ButtonStyle.red)
    async def right_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return

        self.gameBoard = g2048_makeMove(self.gameBoard, 'D')
        g2048_addTwoToBoard(self.gameBoard)
        self.board = g2048_drawBoard(self.gameBoard)
        self.score = g2048_getScore(self.gameBoard)
        if g2048_isFull(self.gameBoard):
            if self.ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                self.bot.GAME_INTERACTIVE_PRGORESS.remove(self.ctx.author.id)
            self.board = g2048_drawBoard(self.gameBoard)
            duration = seconds_str(int(time.time()) - self.time_start)

            get_random_reward = await self.db.sql_game_reward_random("SOKOBAN")
            amount = get_random_reward['reward_amount']
            COIN_NAME = get_random_reward['coin_name']
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
            if self.free_game == True:
                result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

            for child in self.children:
                if isinstance(child, disnake.ui.Button):
                    child.disabled = True

            await self.message.edit(content=f'**{self.ctx.author.mention} Game Over**```{self.board}```Your score: **{self.score}**\nYou have spent time: **{duration}**\n{result}', view=None)

            # Start reward
            if self.free_game == False:
                try:
                    reward = await self.db.sql_game_add(self.board, str(interaction.author.id), COIN_NAME, str(self.score), amount, coin_decimal, str(interaction.guild.id), '2048', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                # add reward him credit
                amount_in_usd = 0.0
                per_unit = None
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
                try:
                    tip = await store.sql_user_balance_mv_single(self.bot.user.id, str(interaction.user.id), str(interaction.guild.id), str(interaction.channel.id), amount, COIN_NAME, "GAME", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            else:
                try:
                    await self.db.sql_game_free_add(self.board, str(interaction.author.id), str(self.score), str(interaction.guild.id), '2048', int(time.time()) - self.time_start, SERVER_BOT)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            # End reward
        else:
            await self.message.edit(content=f'{self.ctx.author.mention}```GAME 2048\n{self.board}```Your score: **{self.score}**', view=self)
        # Defer
        await interaction.response.defer()


    @disnake.ui.button(label="⏹️", style=ButtonStyle.red)
    async def stop_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return

        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)
        await self.message.reply(f'{self.ctx.author.mention}, you gave up the current game.')
        self.game_over = True
        await interaction.response.defer()


# Defines a simple view of row buttons.
class Sokoban_Buttons(disnake.ui.View):
    message: disnake.Message

    def __init__(self, ctx, bot, free_game: bool=False, timeout: float=30.0):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.bot = bot
        self.free_game = free_game
        self.db = database_games()
        self.time_start = int(time.time())
        self.game_over = False

        self.level = None
        self.currentLevel = None
        # Set up the constants:
        self.WIDTH = 'width'
        self.HEIGHT = 'height'

        self.playerX = None
        self.playerY = None

        # Characters in level files that represent objects:
        self.WALL = '#'
        self.FACE = '@'
        self.CRATE = '$'
        self.GOAL = '.'
        self.CRATE_ON_GOAL = '*'
        self.PLAYER_ON_GOAL = '+'
        self.EMPTY = ' '

        self.CRATE_DISPLAY = '🟫'
        # GOAL_DISPLAY = ':negative_squared_cross_mark:'
        self.GOAL_DISPLAY = '❎'

        # How objects should be displayed on the screen:
        # WALL_DISPLAY = random.choice([':red_square:', ':orange_square:', ':yellow_square:', ':blue_square:', ':purple_square:']) # '#' # chr(9617)   # Character 9617 is '░'
        self.WALL_DISPLAY = random.choice(['🟥', '🟧', '🟨', '🟦', '🟪'])
        self.FACE_DISPLAY = ':zany_face:' # '<:smiling_face:700888455877754991>' some guild not support having this

        # A list of chr() codes is at https://inventwithpython.com/chr
        # CRATE_ON_GOAL_DISPLAY = ':green_square:'
        self.CRATE_ON_GOAL_DISPLAY = '🟩'
        self.PLAYER_ON_GOAL_DISPLAY = '😁' # '<:grinning_face:700888456028487700>'
        # EMPTY_DISPLAY = ':black_large_square:'
        self.EMPTY_DISPLAY = '⬛' # already initial

        self.CHAR_MAP = {self.WALL: self.WALL_DISPLAY, self.FACE: self.FACE_DISPLAY,
                    self.CRATE: self.CRATE_DISPLAY, self.PLAYER_ON_GOAL: self.PLAYER_ON_GOAL_DISPLAY,
                    self.GOAL: self.GOAL_DISPLAY, self.CRATE_ON_GOAL: self.CRATE_ON_GOAL_DISPLAY,
                    self.EMPTY: self.EMPTY_DISPLAY}


    def loadLevel(self, level_str: str):
        self.currentLevel = {self.WIDTH: 0, self.HEIGHT: 0}
        y = 0

        # Add the line to the current level.
        # We use line[:-1] so we don't include the newline:
        for line in level_str.splitlines():
            line += "\n"
            for x, levelChar in enumerate(line[:-1]):
                self.currentLevel[(x, y)] = levelChar
            y += 1

            if len(line) - 1 > self.currentLevel[self.WIDTH]:
                self.currentLevel[self.WIDTH] = len(line) - 1
            if y > self.currentLevel[self.HEIGHT]:
                self.currentLevel[self.HEIGHT] = y

        return self.currentLevel

    def displayLevel(self, levelData):
        # Draw the current level.
        solvedCrates = 0
        unsolvedCrates = 0

        level_display = ''
        for y in range(levelData[self.HEIGHT]):
            for x in range(levelData[self.WIDTH]):
                if levelData.get((x, y), self.EMPTY) == self.CRATE:
                    unsolvedCrates += 1
                elif levelData.get((x, y), self.EMPTY) == self.CRATE_ON_GOAL:
                    solvedCrates += 1
                prettyChar = self.CHAR_MAP[levelData.get((x, y), self.EMPTY)]
                level_display += prettyChar
            level_display += '\n'
        totalCrates = unsolvedCrates + solvedCrates
        level_display += "\nSolved: {}/{}".format(solvedCrates, totalCrates)
        return level_display


    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)
        if self.game_over == False:
            await self.message.reply(f'{self.ctx.author.mention}, time running out.')


    @disnake.ui.button(label="🔼", style=ButtonStyle.red)
    async def up_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return

        try:
            # Find the player position:
            for position, character in self.currentLevel.items():
                if character in (self.FACE, self.PLAYER_ON_GOAL):
                    self.playerX, self.playerY = position

            moveX, moveY = 0, -1
            moveToX = self.playerX + moveX
            moveToY = self.playerY + moveY
            moveToSpace = self.currentLevel.get((moveToX, moveToY), self.EMPTY)

            # If the move-to space is empty or a goal, just move there:
            if moveToSpace == self.EMPTY or moveToSpace == self.GOAL:
                # Change the player's old position:
                if self.currentLevel[(self.playerX, self.playerY)] == self.FACE:
                    self.currentLevel[(self.playerX, self.playerY)] = self.EMPTY
                elif self.currentLevel[(self.playerX, self.playerY)] == self.PLAYER_ON_GOAL:
                    self.currentLevel[(self.playerX, self.playerY)] = self.GOAL

                # Set the player's new position:
                if moveToSpace == self.EMPTY:
                    self.currentLevel[(moveToX, moveToY)] = self.FACE
                elif moveToSpace == self.GOAL:
                    self.currentLevel[(moveToX, moveToY)] = self.PLAYER_ON_GOAL

            # If the move-to space is a wall, don't move at all:
            elif moveToSpace == self.WALL:
                pass

            # If the move-to space has a crate, see if we can push it:
            elif moveToSpace in (self.CRATE, self.CRATE_ON_GOAL):
                behindMoveToX = self.playerX + (moveX * 2)
                behindMoveToY = self.playerY + (moveY * 2)
                behindMoveToSpace = self.currentLevel.get((behindMoveToX, behindMoveToY), self.EMPTY)
                if behindMoveToSpace in (self.WALL, self.CRATE, self.CRATE_ON_GOAL):
                    # Can't push the crate because there's a wall or
                    # crate behind it:
                    pass
                elif behindMoveToSpace in (self.GOAL, self.EMPTY):
                    # Change the player's old position:
                    if self.currentLevel[(self.playerX, self.playerY)] == self.FACE:
                        self.currentLevel[(self.playerX, self.playerY)] = self.EMPTY
                    elif self.currentLevel[(self.playerX, self.playerY)] == self.PLAYER_ON_GOAL:
                        self.currentLevel[(self.playerX, self.playerY)] = self.GOAL

                    # Set the player's new position:
                    if moveToSpace == self.CRATE:
                        self.currentLevel[(moveToX, moveToY)] = self.FACE
                    elif moveToSpace == self.CRATE_ON_GOAL:
                        self.currentLevel[(moveToX, moveToY)] = self.PLAYER_ON_GOAL

                    # Set the crate's new position:
                    if behindMoveToSpace == self.EMPTY:
                        self.currentLevel[(behindMoveToX, behindMoveToY)] = self.CRATE
                    elif behindMoveToSpace == self.GOAL:
                        self.currentLevel[(behindMoveToX, behindMoveToY)] = self.CRATE_ON_GOAL

            # Check if the player has finished the level:
            levelIsSolved = True
            for position, character in self.currentLevel.items():
                if character == self.CRATE:
                    levelIsSolved = False
                    break

            if levelIsSolved == True:
                display_level = self.displayLevel(self.currentLevel)
                embed = disnake.Embed(title=f'SOKOBAN GAME {self.ctx.author.name}#{self.ctx.author.discriminator}', description=f'{display_level}', timestamp=datetime.utcnow())
                embed.add_field(name="LEVEL", value=f'{self.level}')
                embed.add_field(name="OTHER LINKS", value="[Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format(config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                
                ## game end
                for child in self.children:
                    if isinstance(child, disnake.ui.Button):
                        child.disabled = True
                await interaction.response.defer()
                await self.message.edit(embed=embed, view=self)
                self.game_over = True

                get_random_reward = await self.db.sql_game_reward_random("SOKOBAN")
                amount = get_random_reward['reward_amount']
                COIN_NAME = get_random_reward['coin_name']
                coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
                native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
                if self.free_game == True:
                    result = f'You got no reward. Waiting to refresh your paid plays (24h max).'

                if self.free_game == True:
                    await self.db.sql_game_free_add(str(self.level), str(self.ctx.author.id), 'WIN', str(self.ctx.guild.id), 'SOKOBAN', int(time.time()) - self.time_start, SERVER_BOT)
                else:
                    reward = await self.db.sql_game_add(str(self.level), str(self.ctx.author.id), COIN_NAME, 'WIN', amount, coin_decimal, str(self.ctx.guild.id), 'SOKOBAN', int(time.time()) - self.time_start, SERVER_BOT)
                duration = seconds_str(int(time.time()) - self.time_start)
                await self.message.reply(content=f'**Level {self.level} completed. You have spent time: **{duration}**\n{result}', view=None)
            else:
                display_level = self.displayLevel(self.currentLevel)
                embed = disnake.Embed(title=f'SOKOBAN GAME {self.ctx.author.name}#{self.ctx.author.discriminator}', description=f'{display_level}', timestamp=datetime.utcnow())
                embed.add_field(name="LEVEL", value=f'{self.level}')
                embed.add_field(name="OTHER LINKS", value="[Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format(config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                await interaction.response.defer()
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # Defer
        try:
            await interaction.response.defer()
        except Exception as e:
            pass


    @disnake.ui.button(label="🔽", style=ButtonStyle.red)
    async def down_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return

        try:
            # Find the player position:
            for position, character in self.currentLevel.items():
                if character in (self.FACE, self.PLAYER_ON_GOAL):
                    self.playerX, self.playerY = position

            moveX, moveY = 0, 1
            moveToX = self.playerX + moveX
            moveToY = self.playerY + moveY
            moveToSpace = self.currentLevel.get((moveToX, moveToY), self.EMPTY)

            # If the move-to space is empty or a goal, just move there:
            if moveToSpace == self.EMPTY or moveToSpace == self.GOAL:
                # Change the player's old position:
                if self.currentLevel[(self.playerX, self.playerY)] == self.FACE:
                    self.currentLevel[(self.playerX, self.playerY)] = self.EMPTY
                elif self.currentLevel[(self.playerX, self.playerY)] == self.PLAYER_ON_GOAL:
                    self.currentLevel[(self.playerX, self.playerY)] = self.GOAL

                # Set the player's new position:
                if moveToSpace == self.EMPTY:
                    self.currentLevel[(moveToX, moveToY)] = self.FACE
                elif moveToSpace == self.GOAL:
                    self.currentLevel[(moveToX, moveToY)] = self.PLAYER_ON_GOAL

            # If the move-to space is a wall, don't move at all:
            elif moveToSpace == self.WALL:
                pass

            # If the move-to space has a crate, see if we can push it:
            elif moveToSpace in (self.CRATE, self.CRATE_ON_GOAL):
                behindMoveToX = self.playerX + (moveX * 2)
                behindMoveToY = self.playerY + (moveY * 2)
                behindMoveToSpace = self.currentLevel.get((behindMoveToX, behindMoveToY), self.EMPTY)
                if behindMoveToSpace in (self.WALL, self.CRATE, self.CRATE_ON_GOAL):
                    # Can't push the crate because there's a wall or
                    # crate behind it:
                    pass
                elif behindMoveToSpace in (self.GOAL, self.EMPTY):
                    # Change the player's old position:
                    if self.currentLevel[(self.playerX, self.playerY)] == self.FACE:
                        self.currentLevel[(self.playerX, self.playerY)] = self.EMPTY
                    elif self.currentLevel[(self.playerX, self.playerY)] == self.PLAYER_ON_GOAL:
                        self.currentLevel[(self.playerX, self.playerY)] = self.GOAL

                    # Set the player's new position:
                    if moveToSpace == self.CRATE:
                        self.currentLevel[(moveToX, moveToY)] = self.FACE
                    elif moveToSpace == self.CRATE_ON_GOAL:
                        self.currentLevel[(moveToX, moveToY)] = self.PLAYER_ON_GOAL

                    # Set the crate's new position:
                    if behindMoveToSpace == self.EMPTY:
                        self.currentLevel[(behindMoveToX, behindMoveToY)] = self.CRATE
                    elif behindMoveToSpace == self.GOAL:
                        self.currentLevel[(behindMoveToX, behindMoveToY)] = self.CRATE_ON_GOAL

            # Check if the player has finished the level:
            levelIsSolved = True
            for position, character in self.currentLevel.items():
                if character == self.CRATE:
                    levelIsSolved = False
                    break

            if levelIsSolved == True:
                display_level = self.displayLevel(self.currentLevel)
                embed = disnake.Embed(title=f'SOKOBAN GAME {self.ctx.author.name}#{self.ctx.author.discriminator}', description=f'{display_level}', timestamp=datetime.utcnow())
                embed.add_field(name="LEVEL", value=f'{self.level}')
                embed.add_field(name="OTHER LINKS", value="[Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format(config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                
                ## game end
                for child in self.children:
                    if isinstance(child, disnake.ui.Button):
                        child.disabled = True
                await interaction.response.defer()
                await self.message.edit(embed=embed, view=self)
                self.game_over = True
                get_random_reward = await self.db.sql_game_reward_random("SOKOBAN")
                amount = get_random_reward['reward_amount']
                COIN_NAME = get_random_reward['coin_name']
                coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
                native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
                if self.free_game == True:
                    result = f'You got no reward. Waiting to refresh your paid plays (24h max).'
                if self.free_game == True:
                    await self.db.sql_game_free_add(str(self.level), str(self.ctx.author.id), 'WIN', str(self.ctx.guild.id), 'SOKOBAN', int(time.time()) - self.time_start, SERVER_BOT)
                else:
                    reward = await self.db.sql_game_add(str(self.level), str(self.ctx.author.id), COIN_NAME, 'WIN', amount, coin_decimal, str(self.ctx.guild.id), 'SOKOBAN', int(time.time()) - self.time_start, SERVER_BOT)

                duration = seconds_str(int(time.time()) - self.time_start)
                await self.message.reply(content=f'**Level {self.level} completed. You have spent time: **{duration}**\n{result}', view=None)
            else:
                display_level = self.displayLevel(self.currentLevel)
                embed = disnake.Embed(title=f'SOKOBAN GAME {self.ctx.author.name}#{self.ctx.author.discriminator}', description=f'{display_level}', timestamp=datetime.utcnow())
                embed.add_field(name="LEVEL", value=f'{self.level}')
                embed.add_field(name="OTHER LINKS", value="[Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format(config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                await interaction.response.defer()
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # Defer
        try:
            await interaction.response.defer()
        except Exception as e:
            pass


    @disnake.ui.button(label="◀️", style=ButtonStyle.red)
    async def left_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return

        try:
            # Find the player position:
            for position, character in self.currentLevel.items():
                if character in (self.FACE, self.PLAYER_ON_GOAL):
                    self.playerX, self.playerY = position

            moveX, moveY = -1, 0
            moveToX = self.playerX + moveX
            moveToY = self.playerY + moveY
            moveToSpace = self.currentLevel.get((moveToX, moveToY), self.EMPTY)

            # If the move-to space is empty or a goal, just move there:
            if moveToSpace == self.EMPTY or moveToSpace == self.GOAL:
                # Change the player's old position:
                if self.currentLevel[(self.playerX, self.playerY)] == self.FACE:
                    self.currentLevel[(self.playerX, self.playerY)] = self.EMPTY
                elif self.currentLevel[(self.playerX, self.playerY)] == self.PLAYER_ON_GOAL:
                    self.currentLevel[(self.playerX, self.playerY)] = self.GOAL

                # Set the player's new position:
                if moveToSpace == self.EMPTY:
                    self.currentLevel[(moveToX, moveToY)] = self.FACE
                elif moveToSpace == self.GOAL:
                    self.currentLevel[(moveToX, moveToY)] = self.PLAYER_ON_GOAL

            # If the move-to space is a wall, don't move at all:
            elif moveToSpace == self.WALL:
                pass

            # If the move-to space has a crate, see if we can push it:
            elif moveToSpace in (self.CRATE, self.CRATE_ON_GOAL):
                behindMoveToX = self.playerX + (moveX * 2)
                behindMoveToY = self.playerY + (moveY * 2)
                behindMoveToSpace = self.currentLevel.get((behindMoveToX, behindMoveToY), self.EMPTY)
                if behindMoveToSpace in (self.WALL, self.CRATE, self.CRATE_ON_GOAL):
                    # Can't push the crate because there's a wall or
                    # crate behind it:
                    pass
                elif behindMoveToSpace in (self.GOAL, self.EMPTY):
                    # Change the player's old position:
                    if self.currentLevel[(self.playerX, self.playerY)] == self.FACE:
                        self.currentLevel[(self.playerX, self.playerY)] = self.EMPTY
                    elif self.currentLevel[(self.playerX, self.playerY)] == self.PLAYER_ON_GOAL:
                        self.currentLevel[(self.playerX, self.playerY)] = self.GOAL

                    # Set the player's new position:
                    if moveToSpace == self.CRATE:
                        self.currentLevel[(moveToX, moveToY)] = self.FACE
                    elif moveToSpace == self.CRATE_ON_GOAL:
                        self.currentLevel[(moveToX, moveToY)] = self.PLAYER_ON_GOAL

                    # Set the crate's new position:
                    if behindMoveToSpace == self.EMPTY:
                        self.currentLevel[(behindMoveToX, behindMoveToY)] = self.CRATE
                    elif behindMoveToSpace == self.GOAL:
                        self.currentLevel[(behindMoveToX, behindMoveToY)] = self.CRATE_ON_GOAL

            # Check if the player has finished the level:
            levelIsSolved = True
            for position, character in self.currentLevel.items():
                if character == self.CRATE:
                    levelIsSolved = False
                    break

            if levelIsSolved == True:
                display_level = self.displayLevel(self.currentLevel)
                embed = disnake.Embed(title=f'SOKOBAN GAME {self.ctx.author.name}#{self.ctx.author.discriminator}', description=f'{display_level}', timestamp=datetime.utcnow())
                embed.add_field(name="LEVEL", value=f'{self.level}')
                embed.add_field(name="OTHER LINKS", value="[Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format(config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                
                ## game end
                for child in self.children:
                    if isinstance(child, disnake.ui.Button):
                        child.disabled = True
                await interaction.response.defer()
                await self.message.edit(embed=embed, view=self)
                self.game_over = True
                get_random_reward = await self.db.sql_game_reward_random("SOKOBAN")
                amount = get_random_reward['reward_amount']
                COIN_NAME = get_random_reward['coin_name']
                coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
                native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
                if self.free_game == True:
                    result = f'You got no reward. Waiting to refresh your paid plays (24h max).'
                if self.free_game == True:
                    await self.db.sql_game_free_add(str(self.level), str(self.ctx.author.id), 'WIN', str(self.ctx.guild.id), 'SOKOBAN', int(time.time()) - self.time_start, SERVER_BOT)
                else:
                    reward = await self.db.sql_game_add(str(self.level), str(self.ctx.author.id), COIN_NAME, 'WIN', amount, coin_decimal, str(self.ctx.guild.id), 'SOKOBAN', int(time.time()) - self.time_start, SERVER_BOT)

                duration = seconds_str(int(time.time()) - self.time_start)
                await self.message.reply(content=f'**Level {self.level} completed. You have spent time: **{duration}**\n{result}', view=None)
            else:
                display_level = self.displayLevel(self.currentLevel)
                embed = disnake.Embed(title=f'SOKOBAN GAME {self.ctx.author.name}#{self.ctx.author.discriminator}', description=f'{display_level}', timestamp=datetime.utcnow())
                embed.add_field(name="LEVEL", value=f'{self.level}')
                embed.add_field(name="OTHER LINKS", value="[Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format(config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                await interaction.response.defer()
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # Defer
        try:
            await interaction.response.defer()
        except Exception as e:
            pass


    @disnake.ui.button(label="▶️", style=ButtonStyle.red)
    async def right_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return
        try:
            # Find the player position:
            for position, character in self.currentLevel.items():
                if character in (self.FACE, self.PLAYER_ON_GOAL):
                    self.playerX, self.playerY = position
                        
            moveX, moveY = 1, 0
            moveToX = self.playerX + moveX
            moveToY = self.playerY + moveY
            moveToSpace = self.currentLevel.get((moveToX, moveToY), self.EMPTY)

            # If the move-to space is empty or a goal, just move there:
            if moveToSpace == self.EMPTY or moveToSpace == self.GOAL:
                # Change the player's old position:
                if self.currentLevel[(self.playerX, self.playerY)] == self.FACE:
                    self.currentLevel[(self.playerX, self.playerY)] = self.EMPTY
                elif self.currentLevel[(self.playerX, self.playerY)] == self.PLAYER_ON_GOAL:
                    self.currentLevel[(self.playerX, self.playerY)] = self.GOAL

                # Set the player's new position:
                if moveToSpace == self.EMPTY:
                    self.currentLevel[(moveToX, moveToY)] = self.FACE
                elif moveToSpace == self.GOAL:
                    self.currentLevel[(moveToX, moveToY)] = self.PLAYER_ON_GOAL

            # If the move-to space is a wall, don't move at all:
            elif moveToSpace == self.WALL:
                pass

            # If the move-to space has a crate, see if we can push it:
            elif moveToSpace in (self.CRATE, self.CRATE_ON_GOAL):
                behindMoveToX = self.playerX + (moveX * 2)
                behindMoveToY = self.playerY + (moveY * 2)
                behindMoveToSpace = self.currentLevel.get((behindMoveToX, behindMoveToY), self.EMPTY)
                if behindMoveToSpace in (self.WALL, self.CRATE, self.CRATE_ON_GOAL):
                    # Can't push the crate because there's a wall or
                    # crate behind it:
                    pass
                elif behindMoveToSpace in (self.GOAL, self.EMPTY):
                    # Change the player's old position:
                    if self.currentLevel[(self.playerX, self.playerY)] == self.FACE:
                        self.currentLevel[(self.playerX, self.playerY)] = self.EMPTY
                    elif self.currentLevel[(self.playerX, self.playerY)] == self.PLAYER_ON_GOAL:
                        self.currentLevel[(self.playerX, self.playerY)] = self.GOAL

                    # Set the player's new position:
                    if moveToSpace == self.CRATE:
                        self.currentLevel[(moveToX, moveToY)] = self.FACE
                    elif moveToSpace == self.CRATE_ON_GOAL:
                        self.currentLevel[(moveToX, moveToY)] = self.PLAYER_ON_GOAL

                    # Set the crate's new position:
                    if behindMoveToSpace == self.EMPTY:
                        self.currentLevel[(behindMoveToX, behindMoveToY)] = self.CRATE
                    elif behindMoveToSpace == self.GOAL:
                        self.currentLevel[(behindMoveToX, behindMoveToY)] = self.CRATE_ON_GOAL

            # Check if the player has finished the level:
            levelIsSolved = True
            for position, character in self.currentLevel.items():
                if character == self.CRATE:
                    levelIsSolved = False
                    break

            if levelIsSolved == True:
                display_level = self.displayLevel(self.currentLevel)
                embed = disnake.Embed(title=f'SOKOBAN GAME {self.ctx.author.name}#{self.ctx.author.discriminator}', description=f'{display_level}', timestamp=datetime.utcnow())
                embed.add_field(name="LEVEL", value=f'{self.level}')
                embed.add_field(name="OTHER LINKS", value="[Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format(config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                
                ## game end
                for child in self.children:
                    if isinstance(child, disnake.ui.Button):
                        child.disabled = True
                await interaction.response.defer()
                await self.message.edit(embed=embed, view=self)
                self.game_over = True
                get_random_reward = await self.db.sql_game_reward_random("SOKOBAN")
                amount = get_random_reward['reward_amount']
                COIN_NAME = get_random_reward['coin_name']
                coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
                native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
                if self.free_game == True:
                    result = f'You got no reward. Waiting to refresh your paid plays (24h max).'
                if self.free_game == True:
                    await self.db.sql_game_free_add(str(self.level), str(self.ctx.author.id), 'WIN', str(self.ctx.guild.id), 'SOKOBAN', int(time.time()) - self.time_start, SERVER_BOT)
                else:
                    reward = await self.db.sql_game_add(str(self.level), str(self.ctx.author.id), COIN_NAME, 'WIN', amount, coin_decimal, str(self.ctx.guild.id), 'SOKOBAN', int(time.time()) - self.time_start, SERVER_BOT)

                duration = seconds_str(int(time.time()) - self.time_start)
                await self.message.reply(content=f'**Level {self.level} completed. You have spent time: **{duration}**\n{result}', view=None)
            else:
                display_level = self.displayLevel(self.currentLevel)
                embed = disnake.Embed(title=f'SOKOBAN GAME {self.ctx.author.name}#{self.ctx.author.discriminator}', description=f'{display_level}', timestamp=datetime.utcnow())
                embed.add_field(name="LEVEL", value=f'{self.level}')
                embed.add_field(name="OTHER LINKS", value="[Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format(config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                await interaction.response.defer()
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # Defer
        try:
            await interaction.response.defer()
        except Exception as e:
            pass


    @disnake.ui.button(label="⏹️", style=ButtonStyle.red)
    async def stop_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if self.ctx.author.id != interaction.author.id:
            # Not you
            await interaction.response.defer()
            return

        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)
        await self.message.reply(f'{self.ctx.author.mention}, you gave up the current game.')
        self.game_over = True
        await interaction.response.defer()


class Games(commands.Cog):

    def __init__(self, bot):
        self.db = database_games()
        self.bot = bot
        self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)
        self.enable_logchan = True


    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)


    async def get_guild_info(self, ctx):
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        return serverinfo


    async def game_blackjack(
        self,
        ctx
    ):
        await self.bot_log()
        serverinfo = await self.get_guild_info(ctx)
        # Game enable check
        if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **/game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
            msg = f"{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `/SETTING GAME`"
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        try:
            name = "blackjack"
            index_game = f"game_{name}_channel"
            # check if bot channel is set:
            if serverinfo and serverinfo[index_game] and ctx.channel.id != int(serverinfo[index_game]):
                gameChan = self.bot.get_channel(int(serverinfo[index_game]))
                if gameChan:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **{name}** channel!!!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
            # If there is a bot channel
            elif serverinfo and serverinfo['botchan'] and serverinfo[index_game] is None and ctx.channel.id != int(serverinfo['botchan']):
                bot_chan = self.bot.get_channel(int(serverinfo['botchan']))
                if bot_chan:
                    msg = f"{EMOJI_RED_NO}, {bot_chan.mention} is the bot channel here!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
        except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
            return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # End game enable check

        # check if user create account less than 3 days
        try:
            account_created = ctx.author.created_at
            if (datetime.now().astimezone() - account_created).total_seconds() <= config.game.account_age_to_play:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this."
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        free_game = False
        won = False

        count_played = await self.db.sql_game_count_user(str(ctx.author.id), config.game.duration_24h, SERVER_BOT, False)
        if count_played and count_played >= config.game.max_daily_play:
            free_game = True

        game_text = '''
    Rules:
        Try to get as close to 21 without going over.
        Kings, Queens, and Jacks are worth 10 points.
        Aces are worth 1 or 11 points.
        Cards 2 through 10 are worth their face value.
        (H)it to take another card.
        (S)tand to stop taking cards.
        The dealer stops hitting at 17.'''
        
        view = BlackJack_Buttons(ctx, self.bot, free_game, timeout=10.0)
        try:
            await ctx.response.send_message("New Blackjack! tap button...", ephemeral=True)
            view.message = await ctx.channel.send(content=f'{ctx.author.mention} ```{game_text}```', view=view)
        except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
            pass


    async def game_slot(
        self,
        ctx
    ):
        await self.bot_log()

        serverinfo = await self.get_guild_info(ctx)
        # Game enable check
        if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **/game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
            msg = f"{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `/SETTING GAME`"
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        try:
            name = "slot"
            index_game = f"game_{name}_channel"
            # check if bot channel is set:
            if serverinfo and serverinfo[index_game] and ctx.channel.id != int(serverinfo[index_game]):
                gameChan = self.bot.get_channel(int(serverinfo[index_game]))
                if gameChan:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **{name}** channel!!!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
            # If there is a bot channel
            elif serverinfo and serverinfo['botchan'] and serverinfo[index_game] is None and ctx.channel.id != int(serverinfo['botchan']):
                bot_chan = self.bot.get_channel(int(serverinfo['botchan']))
                if bot_chan:
                    msg = f"{EMOJI_RED_NO}, {bot_chan.mention} is the bot channel here!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
        except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
            return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # End game enable check

        # check if user create account less than 3 days
        try:
            account_created = ctx.author.created_at
            if (datetime.now().astimezone() - account_created).total_seconds() <= config.game.account_age_to_play:
                await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.")
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        free_game = False
        won = False

        count_played = await self.db.sql_game_count_user(str(ctx.author.id), config.game.duration_24h, SERVER_BOT, False)
        count_played_free = await self.db.sql_game_count_user(str(ctx.author.id), config.game.duration_24h, SERVER_BOT, True)
        if count_played and count_played >= config.game.max_daily_play:
            free_game = True

        count_played = await self.db.sql_game_count_user(str(ctx.author.id), config.game.duration_24h, SERVER_BOT, False)
        count_played_free = await self.db.sql_game_count_user(str(ctx.author.id), config.game.duration_24h, SERVER_BOT, True)
        if count_played and count_played >= config.game.max_daily_play:
            free_game = True

        # Portion from https://github.com/MitchellAW/Discord-Bot/blob/master/features/rng.py
        slots = ['chocolate_bar', 'bell', 'tangerine', 'apple', 'cherries', 'seven']
        slot1 = slots[random.randint(0, 5)]
        slot2 = slots[random.randint(0, 5)]
        slot3 = slots[random.randint(0, 5)]
        slotOutput = '|\t:{}:\t|\t:{}:\t|\t:{}:\t|'.format(slot1, slot2, slot3)

        time_start = int(time.time())

        if ctx.author.id not in self.bot.GAME_SLOT_IN_PRGORESS:
            self.bot.GAME_SLOT_IN_PRGORESS.append(ctx.author.id)
        else:
            return {"error": f"{ctx.author.mention} You are ongoing with one **game** play."}
        won = False
        slotOutput_2 = '$ TRY AGAIN! $'

        if slot1 == slot2 == slot3 == 'seven':
            slotOutput_2 = '$$ JACKPOT $$\n'
            won = True
        elif slot1 == slot2 == slot3:
            slotOutput_2 = '$$ GREAT $$'
            won = True

        get_random_reward = await self.db.sql_game_reward_random("SLOT")
        amount = get_random_reward['reward_amount']
        COIN_NAME = get_random_reward['coin_name']
        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
        contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
        native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")

        result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
        if free_game == True:
            if won:
                result = f'You won! but this is a free game without **reward**! Waiting to refresh your paid plays (24h max).'
            else:
                result = f'You lose! Good luck later!'
        else:
            if not won:
                result = f'You lose! Good luck later!'

        embed = disnake.Embed(title="TIPBOT FREE SLOT ({} REWARD)".format("WITHOUT" if free_game else "WITH"), description="Anyone can freely play!", color=0x00ff00)
        embed.add_field(name="Player", value="{}#{}".format(ctx.author.name, ctx.author.discriminator), inline=False)
        embed.add_field(name="Last 24h you played", value=str(count_played_free+count_played+1), inline=False)
        embed.add_field(name="Result", value=slotOutput, inline=False)
        embed.add_field(name="Comment", value=slotOutput_2, inline=False)
        embed.add_field(name="Reward", value=result, inline=False)
        embed.add_field(name='More', value=f'[TipBot Github]({config.discord.github_link}) | {config.discord.invite_link} ', inline=False)
        embed.set_footer(text="Randomed Coin: {}".format(config.game.coin_game))
        try:
            if ctx.author.id in self.bot.GAME_SLOT_IN_PRGORESS:
                self.bot.GAME_SLOT_IN_PRGORESS.remove(ctx.author.id)
            await ctx.response.send_message(embed=embed)
            await ctx.response.defer()
            await asyncio.sleep(config.game.game_slot_sleeping) # sleep 5s
        except (disnake.errors.NotFound, disnake.errors.Forbidden, disnake.errors.NotFound) as e:
            pass
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if ctx.author.id in self.bot.GAME_SLOT_IN_PRGORESS:
            self.bot.GAME_SLOT_IN_PRGORESS.remove(ctx.author.id)

        return {"result": True}


    async def game_maze(
        self,
        ctx
    ):
        await self.bot_log()

        serverinfo = await self.get_guild_info(ctx)
        # Game enable check
        if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **/game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
            msg = f"{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `/SETTING GAME`"
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        try:
            name = "maze"
            index_game = f"game_{name}_channel"
            # check if bot channel is set:
            if serverinfo and serverinfo[index_game] and ctx.channel.id != int(serverinfo[index_game]):
                gameChan = self.bot.get_channel(int(serverinfo[index_game]))
                if gameChan:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **{name}** channel!!!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
            # If there is a bot channel
            elif serverinfo and serverinfo['botchan'] and serverinfo[index_game] is None and ctx.channel.id != int(serverinfo['botchan']):
                bot_chan = self.bot.get_channel(int(serverinfo['botchan']))
                if bot_chan:
                    msg = f"{EMOJI_RED_NO}, {bot_chan.mention} is the bot channel here!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
        except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
            return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # End game enable check

        # check if user create account less than 3 days
        try:
            account_created = ctx.author.created_at
            if (datetime.now().astimezone() - account_created).total_seconds() <= config.game.account_age_to_play:
                await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.")
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        free_game = False
        won = False

        if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
            return {"error": f"{ctx.author.mention} You are ongoing with one **game** play."}

        count_played = await self.db.sql_game_count_user(str(ctx.author.id), config.game.duration_24h, SERVER_BOT, False)
        if count_played and count_played >= config.game.max_daily_play:
            free_game = True

        view = Maze_Buttons(ctx, self.bot, free_game, timeout=15.0)
        try:
            await ctx.response.send_message("New Maze Game! tap button...", ephemeral=True)
            view.message = await ctx.channel.send(content=f'{ctx.author.mention} New Maze:\n```{view.maze_created}```', view=view)
        except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
            pass


    async def game_dice(
        self,
        ctx
    ):
        await self.bot_log()

        serverinfo = await self.get_guild_info(ctx)
        # Game enable check
        if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **/game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
            msg = f"{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `/SETTING GAME`"
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        try:
            name = "dice"
            index_game = f"game_{name}_channel"
            # check if bot channel is set:
            if serverinfo and serverinfo[index_game] and ctx.channel.id != int(serverinfo[index_game]):
                gameChan = self.bot.get_channel(int(serverinfo[index_game]))
                if gameChan:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **{name}** channel!!!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
            # If there is a bot channel
            elif serverinfo and serverinfo['botchan'] and serverinfo[index_game] is None and ctx.channel.id != int(serverinfo['botchan']):
                bot_chan = self.bot.get_channel(int(serverinfo['botchan']))
                if bot_chan:
                    msg = f"{EMOJI_RED_NO}, {bot_chan.mention} is the bot channel here!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
        except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
            return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # End game enable check

        # check if user create account less than 3 days
        try:
            account_created = ctx.author.created_at
            if (datetime.now().astimezone() - account_created).total_seconds() <= config.game.account_age_to_play:
                await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.")
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        free_game = False
        won = False

        if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
            msg = f"{ctx.author.mention} You are ongoing with one **game** play."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        count_played = await self.db.sql_game_count_user(str(ctx.author.id), config.game.duration_24h, SERVER_BOT, False)
        if count_played and count_played >= config.game.max_daily_play:
            free_game = True

        game_text = '''A player rolls two dice. Each die has six faces. 
    These faces contain 1, 2, 3, 4, 5, and 6 spots. 
    After the dice have come to rest, the sum of the spots on the two upward faces is calculated. 

    * If the sum is 7 or 11 on the first throw, the player wins.
     
    * If the sum is not 7 or 11 on the first throw, then the sum becomes the player's "point." 
    To win, you must continue rolling the dice until you "make your point." 

    * The player loses if they got 7 or 11 for their points.'''
        time_start = int(time.time())
        try:
            await ctx.response.send_message(f'{ctx.author.mention},```{game_text}```')
        except Exception as e:
            return

        if ctx.author.id not in self.bot.GAME_DICE_IN_PRGORESS:
            self.bot.GAME_DICE_IN_PRGORESS.append(ctx.author.id)
        else:
            msg = f"{ctx.author.mention} You are ongoing with one **game dice** play."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        await asyncio.sleep(2)

        won = False
        game_over = False
        try:
            sum_dice = 0
            dice_time = 0
            while not game_over:
                dice1 = random.randint(1, 6)
                dice2 = random.randint(1, 6)
                dice_time += 1
                msg = await ctx.channel.send(f'#{dice_time} {ctx.author.mention} your dices: **{dice1}** and **{dice2}**')
                if sum_dice == 0:
                    # first dice
                    sum_dice = dice1 + dice2
                    if sum_dice == 7 or sum_dice == 11:
                        won = True
                        game_over = True
                        break
                else:
                    # not first dice
                    if dice1 + dice2 == 7 or dice1 + dice2 == 11:
                        game_over = True
                    elif dice1 + dice2 == sum_dice:
                        won = True
                        game_over = True
                        break
                if game_over == False:
                    msg2 = await msg.reply(f'{ctx.author.mention} re-throwing dices...')
                    await msg2.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                    await asyncio.sleep(2)
            # game end, check win or lose
            try:
                get_random_reward = await self.db.sql_game_reward_random("DICE")
                amount = get_random_reward['reward_amount']
                COIN_NAME = get_random_reward['coin_name']
                coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
                native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                result = f'You got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
                if free_game == True:
                    if won:
                        result = f'You won! but this is a free game without **reward**! Waiting to refresh your paid plays (24h max).'
                    else:
                        result = f'You lose!'
                else:
                    if not won:
                        result = f'You lose!'
                # Start reward
                if free_game == False:
                    try:
                        reward = await self.db.sql_game_add('{}:{}:{}:{}'.format(dice_time, sum_dice, dice1, dice2), str(ctx.author.id), COIN_NAME, 'WIN' if won else 'LOSE', amount, coin_decimal, str(ctx.guild.id), 'DICE', int(time.time()) - time_start, SERVER_BOT)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                    # add reward him credit
                    amount_in_usd = 0.0
                    per_unit = None
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
                    try:
                        tip = await store.sql_user_balance_mv_single(self.bot.user.id, str(ctx.user.id), str(ctx.guild.id), str(ctx.channel.id), amount, COIN_NAME, "GAME", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        await self.db.sql_game_free_add('{}:{}:{}:{}'.format(dice_time, sum_dice, dice1, dice2), str(ctx.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'DICE', int(time.time()) - time_start, SERVER_BOT)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                # End reward

                if ctx.author.id in self.bot.GAME_DICE_IN_PRGORESS:
                    self.bot.GAME_DICE_IN_PRGORESS.remove(ctx.author.id)
                await msg.reply(f'{ctx.author.mention} **Dice: ** You threw dices **{dice_time}** times. {result}')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
            pass
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if ctx.author.id in self.bot.GAME_DICE_IN_PRGORESS:
            self.bot.GAME_DICE_IN_PRGORESS.remove(ctx.author.id)


    async def game_snail(
        self,
        ctx,
        bet_numb
    ):
        await self.bot_log()

        serverinfo = await self.get_guild_info(ctx)
        # Game enable check
        if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **/game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
            msg = f"{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `/SETTING GAME`"
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        try:
            name = "snail"
            index_game = f"game_{name}_channel"
            # check if bot channel is set:
            if serverinfo and serverinfo[index_game] and ctx.channel.id != int(serverinfo[index_game]):
                gameChan = self.bot.get_channel(int(serverinfo[index_game]))
                if gameChan:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **{name}** channel!!!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
            # If there is a bot channel
            elif serverinfo and serverinfo['botchan'] and serverinfo[index_game] is None and ctx.channel.id != int(serverinfo['botchan']):
                bot_chan = self.bot.get_channel(int(serverinfo['botchan']))
                if bot_chan:
                    msg = f"{EMOJI_RED_NO}, {bot_chan.mention} is the bot channel here!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
        except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
            return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # End game enable check

        # check if user create account less than 3 days
        try:
            account_created = ctx.author.created_at
            if (datetime.now().astimezone() - account_created).total_seconds() <= config.game.account_age_to_play:
                await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.")
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        free_game = False
        won = False

        if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
            return {"error": f"{ctx.author.mention} You are ongoing with one **game** play."}

        count_played = await self.db.sql_game_count_user(str(ctx.author.id), config.game.duration_24h, SERVER_BOT, False)
        if count_played and count_played >= config.game.max_daily_play:
            free_game = True

        if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
            return {"error": f"{ctx.author.mention} You are ongoing with one **game** play."}

        time_start = int(time.time())
        won = False
        game_text = '''Snail Race, Fast-paced snail racing action!'''
        # We do not always show credit
        try:
            await ctx.response.send_message(f'{ctx.author.mention},```{game_text}```')
        except Exception as e:
            return

        your_snail = 0
        try:
            your_snail = int(bet_numb)
        except ValueError:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} Please put a valid snail number **(1 to 8)**"}
        if ctx.author.id not in self.bot.GAME_INTERACTIVE_PRGORESS:
            self.bot.GAME_INTERACTIVE_PRGORESS.append(ctx.author.id)

        MAX_NUM_SNAILS = 8
        MAX_NAME_LENGTH = 20
        FINISH_LINE = 22  # (!) Try modifying this number.

        if 1 <= your_snail <= MAX_NUM_SNAILS:
            # valid betting
            # sleep 1s
            await asyncio.sleep(1)
            try:
                game_over = False
                # Enter the names of each snail:
                snailNames = []  # List of the string snail names.
                for i in range(1, MAX_NUM_SNAILS + 1):
                    snailNames.append("#" + str(i))
                start_line_mention = '{}#{} bet for #{}\n'.format(ctx.author.name, ctx.author.discriminator, your_snail)
                
                start_line = 'START' + (' ' * (FINISH_LINE - len('START')) + 'FINISH') + '\n'
                start_line += '|' + (' ' * (FINISH_LINE - len('|')) + '|')
                try:
                    msg_racing = await ctx.channel.send(f'{start_line_mention}```{start_line}```')
                except Exception as e:
                    if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                        self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
                    await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} **GAME SNAIL** failed to send message in {ctx.guild.name} / {ctx.guild.id}')
                    return

                # sleep
                await asyncio.sleep(1.5)
                snailProgress = {}
                list_snails = ''
                for snailName in snailNames:
                    list_snails += snailName[:MAX_NAME_LENGTH] + '\n'
                    list_snails += '@v'
                    snailProgress[snailName] = 0
                try:
                    await msg_racing.edit(content=f'{start_line_mention}```{start_line}\n{list_snails}```')
                except Exception as e:
                    if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                        self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
                    return {"error": f"{EMOJI_INFORMATION} {ctx.author.mention} Failed to start snail game, please try again."}

                while not game_over:
                    # Pick random snails to move forward:
                    for i in range(random.randint(1, MAX_NUM_SNAILS // 2)):
                        randomSnailName = random.choice(snailNames)
                        snailProgress[randomSnailName] += 1

                        # Check if a snail has reached the finish line:
                        if snailProgress[randomSnailName] == FINISH_LINE:
                            game_over = True
                            if '#' + str(your_snail) == randomSnailName:
                                # You won
                                won = True
                            # add to DB, game end, check win or lose
                            try:
                                get_random_reward = await self.db.sql_game_reward_random("DICE")
                                amount = get_random_reward['reward_amount']
                                COIN_NAME = get_random_reward['coin_name']
                                coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                                contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                                usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
                                native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")

                                result = ''
                                if free_game == False:
                                    if won:
                                        result = f'You won **snail#{str(your_snail)}**! {ctx.author.mention} got reward of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** to Tip balance!'
                                    else:
                                        result = f'You lose! **snail{randomSnailName}** is the winner!!! You bet for **snail#{str(your_snail)}**'
                                else:
                                    if won:
                                        result = f'You won! **snail#{str(your_snail)}** but this is a free game without **reward**! Waiting to refresh your paid plays (24h max).'
                                    else:
                                        result = f'You lose! **snail{randomSnailName}** is the winner!!! You bet for **snail#{str(your_snail)}**'
                                
                                if free_game == False:
                                    try:
                                        reward = await self.db.sql_game_add('BET:#{}/WINNER:{}'.format(your_snail, randomSnailName), str(ctx.author.id), COIN_NAME, 'WIN' if won else 'LOSE', amount, coin_decimal, str(ctx.guild.id), 'SNAIL', int(time.time()) - time_start, SERVER_BOT)
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot(traceback.format_exc())
                                    # add reward him credit
                                    amount_in_usd = 0.0
                                    per_unit = None
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
                                    try:
                                        tip = await store.sql_user_balance_mv_single(self.bot.user.id, str(ctx.user.id), str(ctx.guild.id), str(ctx.channel.id), amount, COIN_NAME, "GAME", coin_decimal, SERVER_BOT, contract, amount_in_usd)
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot(traceback.format_exc())
                                else:
                                    try:
                                        await self.db.sql_game_free_add('BET:#{}/WINNER:{}'.format(your_snail, randomSnailName), str(ctx.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'SNAIL', int(time.time()) - time_start, SERVER_BOT)
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot(traceback.format_exc())

                                await msg_racing.reply(f'{ctx.author.mention} **Snail Racing** {result}')
                                if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                                    self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
                                return
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            break
                    # (!) EXPERIMENT: Add a cheat here that increases a snail's progress
                    # if it has your name.

                    await asyncio.sleep(0.5)  # (!) EXPERIMENT: Try changing this value.
                    # Display the snails (with name tags):
                    list_snails = ''
                    for snailName in snailNames:
                        spaces = snailProgress[snailName]
                        list_snails += (' ' * spaces) + snailName[:MAX_NAME_LENGTH]
                        list_snails += '\n'
                        list_snails += ('.' * snailProgress[snailName]) + '@v'
                        list_snails += '\n'
                    try:
                        await msg_racing.edit(content=f'{start_line_mention}```{start_line}\n{list_snails}```')
                    except Exception as e:
                        if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                            self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
                        await logchanbot(traceback.format_exc())
                        return
                return
            except Exception as e:
                await logchanbot(traceback.format_exc())
            if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
        else:
            # invalid betting
            if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} Please put a valid snail number **(1 to 8)**"}


    async def game_2048(
        self,
        ctx
    ):
        await self.bot_log()

        serverinfo = await self.get_guild_info(ctx)
        # Game enable check
        if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **/game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
            msg = f"{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `/SETTING GAME`"
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        try:
            name = "2048"
            index_game = f"game_{name}_channel"
            # check if bot channel is set:
            if serverinfo and serverinfo[index_game] and ctx.channel.id != int(serverinfo[index_game]):
                gameChan = self.bot.get_channel(int(serverinfo[index_game]))
                if gameChan:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **{name}** channel!!!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
            # If there is a bot channel
            elif serverinfo and serverinfo['botchan'] and serverinfo[index_game] is None and ctx.channel.id != int(serverinfo['botchan']):
                bot_chan = self.bot.get_channel(int(serverinfo['botchan']))
                if bot_chan:
                    msg = f"{EMOJI_RED_NO}, {bot_chan.mention} is the bot channel here!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
        except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
            return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # End game enable check

        # check if user create account less than 3 days
        try:
            account_created = ctx.author.created_at
            if (datetime.now().astimezone() - account_created).total_seconds() <= config.game.account_age_to_play:
                await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.")
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        free_game = False
        won = False

        if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
            return {"error": f"{ctx.author.mention} You are ongoing with one **game** play."}

        count_played = await self.db.sql_game_count_user(str(ctx.author.id), config.game.duration_24h, SERVER_BOT, False)
        if count_played and count_played >= config.game.max_daily_play:
            free_game = True

        if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
            return {"error": f"{ctx.author.mention} You are ongoing with one **game** play."}

        view = g2048_Buttons(ctx, self.bot, free_game, timeout=15.0)
        try:
            await ctx.response.send_message("New 2048 Game! tap button...", ephemeral=True)                
            view.message = await ctx.channel.send(content=f'{ctx.author.mention}```GAME 2048\n{view.board}```Your score: **{0}**', view=view)
        except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
            return


    async def game_sokoban(
        self,
        ctx,
        is_test: bool=False
    ):
        await self.bot_log()

        serverinfo = await self.get_guild_info(ctx)
        # Game enable check
        if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **/game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
            msg = f"{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `/SETTING GAME`"
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        try:
            name = "sokoban"
            index_game = f"game_{name}_channel"
            # check if bot channel is set:
            if serverinfo and serverinfo[index_game] and ctx.channel.id != int(serverinfo[index_game]):
                gameChan = self.bot.get_channel(int(serverinfo[index_game]))
                if gameChan:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **{name}** channel!!!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
            # If there is a bot channel
            elif serverinfo and serverinfo['botchan'] and serverinfo[index_game] is None and ctx.channel.id != int(serverinfo['botchan']):
                bot_chan = self.bot.get_channel(int(serverinfo['botchan']))
                if bot_chan:
                    msg = f"{EMOJI_RED_NO}, {bot_chan.mention} is the bot channel here!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
        except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
            return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # End game enable check

        # check if user create account less than 3 days
        try:
            account_created = ctx.author.created_at
            if (datetime.now().astimezone() - account_created).total_seconds() <= config.game.account_age_to_play:
                await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.")
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        free_game = False
        won = False

        if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
            return {"error": f"{ctx.author.mention} You are ongoing with one **game** play."}

        count_played = await self.db.sql_game_count_user(str(ctx.author.id), config.game.duration_24h, SERVER_BOT, False)
        if count_played and count_played >= config.game.max_daily_play:
            free_game = True

        if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
            return {"error": f"{ctx.author.mention} You are ongoing with one **game** play."}

        view = Sokoban_Buttons(ctx, free_game, timeout=15.0)
        try:
            # CRATE_DISPLAY = ':brown_square:'  # Character 9679 is '▪'
            CRATE_DISPLAY = '🟫'
            # GOAL_DISPLAY = ':negative_squared_cross_mark:'
            GOAL_DISPLAY = '❎'
            game_text = f'''```Push the solid crates {CRATE_DISPLAY} onto the {GOAL_DISPLAY}. You can only push, you cannot pull. Re-act with direction to move up-left-down-right, respectively. You can also reload game level.```'''
            await ctx.channel.send(content=game_text)

            # get max level user already played.
            level = 0
            get_level_user = await self.db.sql_game_get_level_user(str(ctx.author.id), 'SOKOBAN')
            if get_level_user < 0:
                level = 0
            elif get_level_user >= 0:
                level = get_level_user + 1

            get_level = await self.db.sql_game_get_level_tpl(level, 'SOKOBAN')
            if get_level is None:
                if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                    self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
                return {"error": f"{ctx.author.mention} Game sokban loading failed. Check back later."}

            view = Sokoban_Buttons(ctx, self.bot, free_game, timeout=15.0)
            try:
                await ctx.response.send_message("New Sokoban Game! tap button...", ephemeral=True)
                view.currentLevel = view.loadLevel(get_level['template_str'])
                display_level = view.displayLevel(view.currentLevel)
                embed = disnake.Embed(title=f'SOKOBAN GAME {ctx.author.name}#{ctx.author.discriminator}', description=f'{display_level}', timestamp=datetime.utcnow())
                embed.add_field(name="LEVEL", value=f'{level}')
                embed.add_field(name="OTHER LINKS", value="[Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format(config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                view.message = await ctx.channel.send(embed=embed, view=view)
                view.level = level
                # Find the player position:
                for position, character in view.currentLevel.items():
                    if character in (view.FACE, view.PLAYER_ON_GOAL):
                        view.playerX, view.playerY = position
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.slash_command(description="Various game commands.")
    async def game(self, ctx):
        pass


    @commands.guild_only()
    @game.sub_command(
        usage="game blackjack", 
        description="Blackjack, original code by Al Sweigart al@inventwithpython.com."
    )
    async def blackjack(
        self, 
        ctx
    ):
        await self.bot_log()
        game_blackjack = await self.game_blackjack(ctx)
        if game_blackjack and "error" in game_blackjack:
            await ctx.response.send_message(game_blackjack['error'])


    @commands.guild_only()
    @game.sub_command(
        usage="game slot", 
        description="Play a slot game."
    )
    async def slot(
        self, 
        ctx
    ):
        await self.bot_log()
        try:
            game_slot = await self.game_slot(ctx)
            if game_slot and "error" in game_slot:
                await ctx.response.send_message(game_slot['error'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.guild_only()
    @game.sub_command(
        usage="game maze", 
        description="Interactive 2D ascii maze game."
    )
    async def maze(
        self, 
        ctx
    ):
        await self.bot_log()
        try:
            game_maze = await self.game_maze(ctx)
            if game_maze and "error" in game_maze:
                await ctx.response.send_message(game_maze['error'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.guild_only()
    @game.sub_command(
        usage="game dice", 
        description="Simple dice game."
    )
    async def dice(
        self, 
        ctx
    ):
        await self.bot_log()
        try:
            game_dice = await self.game_dice(ctx)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.guild_only()
    @game.sub_command(
        usage="game snail <bet number>", 
        options=[
            Option('bet_numb', 'bet_numb', OptionType.integer, required=True)
        ],
        description="Snail racing game. You bet which one."
    )
    async def snail(
        self, 
        ctx,
        bet_numb: int,
    ):
        await self.bot_log()
        try:
            game_snail = await self.game_snail(ctx, bet_numb)
            if game_snail and "error" in game_snail:
                await ctx.response.send_message(game_snail['error'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.guild_only()
    @game.sub_command(
        usage="game g2048",  
        description="Classic 2048 game. Slide all the tiles on the board in one of four directions."
    )
    async def g2048(
        self, 
        ctx
    ):
        await self.bot_log()
        try:
            game_2048 = await self.game_2048(ctx)
            if game_2048 and "error" in game_2048:
                await ctx.response.send_message(game_2048['error'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.guild_only()
    @game.sub_command(
        usage="game sokoban", 
        description="Sokoban interactive game."
    )
    async def sokoban(
        self, 
        ctx
    ):
        await self.bot_log()
        try:
            game_sokoban = await self.game_sokoban(ctx)
            if game_sokoban and "error" in game_sokoban:
                print(game_sokoban['error'])
                await ctx.response.send_message(game_sokoban['error'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


def setup(bot):
    bot.add_cog(Games(bot))