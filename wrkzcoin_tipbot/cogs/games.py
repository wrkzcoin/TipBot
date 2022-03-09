import asyncio
import re
import sys
import time
import traceback
from datetime import datetime
import random

import disnake
from disnake.ext import commands

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
from disnake import ActionRow, Button, ButtonStyle

import store
from Bot import logchanbot, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_INFORMATION, num_format_coin, seconds_str, RowButton_row_close_any_message, SERVER_BOT, EMOJI_HOURGLASS_NOT_DONE

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
    
    
# Defines a simple view of row buttons.
class BlackJack_Buttons(disnake.ui.View):
    message: disnake.Message
    game_over: bool = False
    player_over: bool = False


    def __init__(self, ctx, free_game: bool=False, timeout: float=30.0):
        super().__init__(timeout=timeout)
        self.ctx = ctx
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
            result = 'You got reward of **{yyyy} {yyy}** to Tip balance!'
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
            result = 'You got reward of **{yyyy} {yyy}** to Tip balance!'
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
        else:
            dealer_get_display = blackjack_displayHands(self.playerHand, self.dealerHand, False)
            msg = '{} **BLACKJACK**\n```DEALER: {}\n{}\nPLAYER:  {}\n{}```'.format(interaction.author.mention, dealer_get_display['dealer_header'], dealer_get_display['dealer'], dealer_get_display['player_header'], dealer_get_display['player'])
            await self.message.edit(content=msg, view=self)


# Defines a simple view of row buttons.
class Maze_Buttons(disnake.ui.View):
    message: disnake.Message
    maze_created: str = None

    def __init__(self, ctx, free_game: bool=False, timeout: float=30.0):
        super().__init__(timeout=timeout)
        self.ctx = ctx
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
        self.time_start = int(time.time())


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
            result = 'You got reward of **{yyyy} {yyy}** to Tip balance!'
            if self.free_game == True:
                result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

            for child in self.children:
                if isinstance(child, disnake.ui.Button):
                    child.disabled = True
            await self.message.edit(view=self)

            duration = seconds_str(int(time.time()) - self.time_start)
            await self.message.reply(f'{self.ctx.author.mention} **MAZE** Grats! You completed! You completed in: **{duration}\n{result}**')
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
            result = 'You got reward of **{yyyy} {yyy}** to Tip balance!'
            if self.free_game == True:
                result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

            for child in self.children:
                if isinstance(child, disnake.ui.Button):
                    child.disabled = True
            await self.message.edit(view=self)

            duration = seconds_str(int(time.time()) - self.time_start)
            await self.message.reply(f'{self.ctx.author.mention} **MAZE** Grats! You completed! You completed in: **{duration}\n{result}**')
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
            result = 'You got reward of **{yyyy} {yyy}** to Tip balance!'
            if self.free_game == True:
                result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

            for child in self.children:
                if isinstance(child, disnake.ui.Button):
                    child.disabled = True
            await self.message.edit(view=self)

            duration = seconds_str(int(time.time()) - self.time_start)
            await self.message.reply(f'{self.ctx.author.mention} **MAZE** Grats! You completed! You completed in: **{duration}\n{result}**')
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
            result = 'You got reward of **{yyyy} {yyy}** to Tip balance!'
            if self.free_game == True:
                result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

            for child in self.children:
                if isinstance(child, disnake.ui.Button):
                    child.disabled = True
            await self.message.edit(view=self)

            duration = seconds_str(int(time.time()) - self.time_start)
            await self.message.reply(f'{self.ctx.author.mention} **MAZE** Grats! You completed! You completed in: **{duration}\n{result}**')
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
        await interaction.response.defer()
        await self.message.reply(f'{self.ctx.author.mention}, you gave up the current game.')
        self.game_over = True
        await interaction.response.defer()


class Games(commands.Cog):

    def __init__(self, bot):
        self.db = database_games()
        self.bot = bot
        self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)


    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)


    # game_name: BAGEL, HANGMAN, BLACKJACK, SLOT, MAZE, DICE, SNAIL, 2048, SOKOBAN
    async def settle_game(self, ctx, game_name: str, win: bool=True):
        # TODO: Check if the guild has more reward (premium?)
        # TODO: Check if user already reached free paid play?
        pass


    async def game_blackjack(
        self,
        ctx
    ):
        await self.bot_log()
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

        # TODO: Check if game is enabled in the guild, check if it's in game channel or bot channel

        count_played = await self.db.sql_game_count_user(str(ctx.author.id), config.game.duration_24h, SERVER_BOT, False)
        count_played_free = await self.db.sql_game_count_user(str(ctx.author.id), config.game.duration_24h, SERVER_BOT, True)
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
        
        view = BlackJack_Buttons(ctx, free_game, timeout=10.0)
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

        # TODO: Check if game is enabled in the guild, check if it's in game channel or bot channel

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
        result = 'You lose! Good luck later!'

        result_reward = 'You got reward of **{yyyy} {yyy}** to Tip balance!'
        if free_game == True:
            result_reward = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'

        if slot1 == slot2 == slot3 == 'seven':
            slotOutput_2 = '$$ JACKPOT $$\n'
            won = True
        elif slot1 == slot2 == slot3:
            slotOutput_2 = '$$ GREAT $$'
            won = True

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

        view = Maze_Buttons(ctx, free_game, timeout=15.0)
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
            return {"error": f"{ctx.author.mention} You are ongoing with one **game dice** play."}

        await asyncio.sleep(2)

        try:
            game_over = False
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
                result = 'You got reward of **{yyyy} {yyy}** to Tip balance!'
                if free_game == True:
                    result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'
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
                                result = ''
                                if free_game == False:
                                    if won:
                                        result = f'You won **snail#{str(your_snail)}**! {ctx.author.mention} got reward of **XXXX XXXX** to Tip balance!'
                                    else:
                                        result = f'You lose! **snail{randomSnailName}** is the winner!!! You bet for **snail#{str(your_snail)}**'
                                else:
                                    if won:
                                        result = f'You won! **snail#{str(your_snail)}** but this is a free game without **reward**! Waiting to refresh your paid plays (24h max).'
                                    else:
                                        result = f'You lose! **snail{randomSnailName}** is the winner!!! You bet for **snail#{str(your_snail)}**'
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

        score = 0
        game_text = '''
    Slide all the tiles on the board in one of four directions. Tiles with
    like numbers will combine into larger-numbered tiles. A new 2 tile is
    added to the board on each move. You win if you can create a 2048 tile.
    You lose if the board fills up the tiles before then.'''
        # We do not always show credit
        if random.randint(1,100) < 30:
            msg = await ctx.reply(f'{ctx.author.mention} ```{game_text}```')
            await msg.add_reaction(EMOJI_OK_BOX)

        game_over = False
        gameBoard = g2048_getNewBoard()
        try:
            board = g2048_drawBoard(gameBoard) # string
            try:
                msg = await ctx.reply(f'**GAME 2048 starts**...')
            except Exception as e:
                if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                    self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} **GAME 2048** failed to send message in {ctx.guild.name} / {ctx.guild.id}')
                return

            # Create a row of buttons
            row = ActionRow(
                Button(
                    style=ButtonStyle.blurple,
                    label="🔼",
                    custom_id="up"
                ),
                Button(
                    style=ButtonStyle.blurple,
                    label="🔽",
                    custom_id="down"
                ),
                Button(
                    style=ButtonStyle.blurple,
                    label="◀️",
                    custom_id="left"
                ),
                Button(
                    style=ButtonStyle.blurple,
                    label="▶️",
                    custom_id="right"
                ),
                Button(
                    style=ButtonStyle.blurple,
                    label="⏹️",
                    custom_id="stop"
                )
            )
            time_start = int(time.time())
            inter_msg = False
            while not game_over:
                try:
                    if inter_msg == False: await msg.edit(content=f'{ctx.author.mention}```GAME 2048\n{board}```Your score: **{score}**', components=[row])
                except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                    if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                        self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
                    await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} **GAME 2048** was deleted or I can not find it. Game stop!')
                    return
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                score = g2048_getScore(gameBoard)

                if IS_RESTARTING:
                    if type(ctx) is not disnake.interactions.MessageInteraction: await ctx.message.add_reaction(EMOJI_REFRESH)
                    await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
                    return

                def check(inter):
                    return inter.message.id == msg.id and ctx.author == inter.author
                try:
                    inter = await self.bot.wait_for('button_click', check=check, timeout=120)
                except asyncio.TimeoutError:
                    if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                        self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
                    if free_game == True:
                        try:
                            await store.sql_game_free_add(board, str(ctx.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), '2048', int(time.time()) - time_start, SERVER_BOT)
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                    else:
                        try:
                            reward = await store.sql_game_add(board, str(ctx.author.id), 'None', 'WIN' if won else 'LOSE', 0, 0, str(ctx.guild.id), '2048', int(time.time()) - time_start, SERVER_BOT)
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                    await ctx.reply(f'{ctx.author.mention} **2048 GAME** has waited you too long. Game exits. Your score **{score}**.')
                    game_over = True
                    return

                if inter.clicked_button.custom_id == "stop":
                    await ctx.reply(f'{ctx.author.mention} You gave up the current game. Your score **{score}**.')
                    game_over = True
                    if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                        self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)

                    if free_game == True:
                        try:
                            await store.sql_game_free_add(board, str(ctx.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), '2048', int(time.time()) - time_start, SERVER_BOT)
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                    else:
                        try:
                            reward = await store.sql_game_add(board, str(ctx.author.id), 'None', 'WIN' if won else 'LOSE', 0, 0, str(ctx.guild.id), '2048', int(time.time()) - time_start, SERVER_BOT)
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                    await asyncio.sleep(1)
                    try:
                        await msg.delete()
                    except Exception as e:
                        pass
                    break
                    return

                playerMove = None
                if inter.clicked_button.custom_id == "up":
                    playerMove = 'W'
                elif inter.clicked_button.custom_id == "down":
                    playerMove = 'S'
                elif inter.clicked_button.custom_id == "left":
                    playerMove = 'A'
                elif inter.clicked_button.custom_id == "right":
                    playerMove = 'D'
                if playerMove in ('W', 'A', 'S', 'D'):
                    gameBoard = g2048_makeMove(gameBoard, playerMove)
                    g2048_addTwoToBoard(gameBoard)
                    board = g2048_drawBoard(gameBoard)
                if g2048_isFull(gameBoard):
                    game_over = True
                    won = True # we assume won but it is not a winner
                    if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                        self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
                    board = g2048_drawBoard(gameBoard)

                    # Handle whether the player won, lost, or tied:
                    COIN_NAME = random.choice(GAME_COIN)
                    amount = GAME_SLOT_REWARD[COIN_NAME] * (int(score / 100) if score / 100 > 1 else 1) # testing first
                    if COIN_NAME in ENABLE_COIN_ERC:
                        coin_family = "ERC-20"
                    elif COIN_NAME in ENABLE_COIN_TRC:
                        coin_family = "TRC-20"
                    else:
                        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                    real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO", "XCH"] else float(amount)
                    result = f'You got reward of **{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}** to Tip balance!'
                    duration = seconds_str(int(time.time()) - time_start)
                    if free_game == True:
                        result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'
                        try:
                            await store.sql_game_free_add(board, str(ctx.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), '2048', int(time.time()) - time_start, SERVER_BOT)
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                    else:
                        try:
                            reward = await store.sql_game_add(board, str(ctx.author.id), COIN_NAME, 'WIN' if won else 'LOSE', real_amount if won else 0, get_decimal(COIN_NAME) if won else 0, str(ctx.guild.id), '2048', int(time.time()) - time_start, SERVER_BOT)
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                    await inter.create_response(content=f'**{ctx.author.mention} Game Over**```{board}```Your score: **{score}**\nYou have spent time: **{duration}**\n{result}', type=dislash.ResponseType.UpdateMessage)
                    return
                else:
                    inter_msg = True
                    await inter.create_response(content=f'{ctx.author.mention}```GAME 2048\n{board}```Your score: **{score}**', components=[row], type=dislash.ResponseType.UpdateMessage)

        except Exception as e:
            await logchanbot(traceback.format_exc())
        if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
            self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)


    async def game_sokoban(
        self,
        ctx,
        is_test: bool=False
    ):
        await self.bot_log()
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

        # Set up the constants:
        WIDTH = 'width'
        HEIGHT = 'height'

        # Characters in level files that represent objects:
        WALL = '#'
        FACE = '@'
        CRATE = '$'
        GOAL = '.'
        CRATE_ON_GOAL = '*'
        PLAYER_ON_GOAL = '+'
        EMPTY = ' '

        # How objects should be displayed on the screen:
        # WALL_DISPLAY = random.choice([':red_square:', ':orange_square:', ':yellow_square:', ':blue_square:', ':purple_square:']) # '#' # chr(9617)   # Character 9617 is '░'
        WALL_DISPLAY = random.choice(['🟥', '🟧', '🟨', '🟦', '🟪'])
        FACE_DISPLAY = ':zany_face:' # '<:smiling_face:700888455877754991>' some guild not support having this
        # CRATE_DISPLAY = ':brown_square:'  # Character 9679 is '▪'
        CRATE_DISPLAY = '🟫'
        # GOAL_DISPLAY = ':negative_squared_cross_mark:'
        GOAL_DISPLAY = '❎'
        # A list of chr() codes is at https://inventwithpython.com/chr
        # CRATE_ON_GOAL_DISPLAY = ':green_square:'
        CRATE_ON_GOAL_DISPLAY = '🟩'
        PLAYER_ON_GOAL_DISPLAY = '😁' # '<:grinning_face:700888456028487700>'
        # EMPTY_DISPLAY = ':black_large_square:'
        # EMPTY_DISPLAY = '⬛' already initial

        CHAR_MAP = {WALL: WALL_DISPLAY, FACE: FACE_DISPLAY,
                    CRATE: CRATE_DISPLAY, PLAYER_ON_GOAL: PLAYER_ON_GOAL_DISPLAY,
                    GOAL: GOAL_DISPLAY, CRATE_ON_GOAL: CRATE_ON_GOAL_DISPLAY,
                    EMPTY: EMPTY_DISPLAY}

        won = False
        game_text = f'''Push the solid crates {CRATE_DISPLAY} onto the {GOAL_DISPLAY}. You can only push,
    you cannot pull. Re-act with direction to move up-left-down-right,
    respectively. You can also reload game level.'''
        # We do not always show credit
        if random.randint(1,100) < 30:
            msg = await ctx.reply(f'{ctx.author.mention} ```{game_text}```')
            await msg.add_reaction(EMOJI_OK_BOX)

        # get max level user already played.
        level = 0
        get_level_user = await store.sql_game_get_level_user(str(ctx.author.id), 'SOKOBAN')
        if get_level_user < 0:
            level = 0
        elif get_level_user >= 0:
            level = get_level_user + 1

        get_level = await store.sql_game_get_level_tpl(level, 'SOKOBAN')
        
        if get_level is None:
            if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
            await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} **GAME SOKOBAN** failed get level **{str(level)}** in {ctx.guild.name} / {ctx.guild.id}')
            return {"error": f"{ctx.author.mention} Game sokban loading failed. Check back later."}


        def loadLevel(level_str: str):
            level_str = level_str
            currentLevel = {WIDTH: 0, HEIGHT: 0}
            y = 0

            # Add the line to the current level.
            # We use line[:-1] so we don't include the newline:
            for line in level_str.splitlines():
                line += "\n"
                for x, levelChar in enumerate(line[:-1]):
                    currentLevel[(x, y)] = levelChar
                y += 1

                if len(line) - 1 > currentLevel[WIDTH]:
                    currentLevel[WIDTH] = len(line) - 1
                if y > currentLevel[HEIGHT]:
                    currentLevel[HEIGHT] = y

            return currentLevel

        def displayLevel(levelData):
            # Draw the current level.
            solvedCrates = 0
            unsolvedCrates = 0

            level_display = ''
            for y in range(levelData[HEIGHT]):
                for x in range(levelData[WIDTH]):
                    if levelData.get((x, y), EMPTY) == CRATE:
                        unsolvedCrates += 1
                    elif levelData.get((x, y), EMPTY) == CRATE_ON_GOAL:
                        solvedCrates += 1
                    prettyChar = CHAR_MAP[levelData.get((x, y), EMPTY)]
                    level_display += prettyChar
                level_display += '\n'
            totalCrates = unsolvedCrates + solvedCrates
            level_display += "\nSolved: {}/{}".format(solvedCrates, totalCrates)
            return level_display

        game_over = False

        try:
            currentLevel = loadLevel(get_level['template_str'])
            display_level = displayLevel(currentLevel)

            embed = disnake.Embed(title=f'SOKOBAN GAME {ctx.author.name}#{ctx.author.discriminator}', description='**SOKOBAN GAME** starts...', timestamp=datetime.utcnow(), colour=7047495)
            embed.add_field(name="LEVEL", value=f'{level}')
            embed.add_field(name="OTHER LINKS", value="[Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format(config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
            try:
                msg = await ctx.reply(embed=embed)
            except Exception as e:
                if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                    self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} **GAME SOKOBAN** failed to send embed in {ctx.guild.name} / {ctx.guild.id}')
                return {"error": f"{ctx.author.mention} I can not send any embed message here. Seemed no permission."}

            # Create a row of buttons
            row = ActionRow(
                Button(
                    style=ButtonStyle.blurple,
                    label="🔼",
                    custom_id="up"
                ),
                Button(
                    style=ButtonStyle.blurple,
                    label="🔽",
                    custom_id="down"
                ),
                Button(
                    style=ButtonStyle.blurple,
                    label="◀️",
                    custom_id="left"
                ),
                Button(
                    style=ButtonStyle.blurple,
                    label="▶️",
                    custom_id="right"
                ),
                Button(
                    style=ButtonStyle.blurple,
                    label="⏹️",
                    custom_id="stop"
                )
            )
            time_start = int(time.time())
            inter_msg = False
            while not game_over:
                if IS_RESTARTING:
                    await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
                    return

                display_level = displayLevel(currentLevel)
                embed = disnake.Embed(title=f'SOKOBAN GAME {ctx.author.name}#{ctx.author.discriminator}', description=f'{display_level}', timestamp=datetime.utcnow(), colour=7047495)
                embed.add_field(name="LEVEL", value=f'{level}')
                embed.add_field(name="OTHER LINKS", value="[Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format(config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                try:
                    if inter_msg ==False:
                        await msg.edit(embed=embed, components=[row])
                    else:
                        await inter.create_response(embed=embed, components=[row], type=dislash.ResponseType.UpdateMessage)
                except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                    if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                        self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
                    return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} **GAME SOKOBAN** was deleted or I can not find it. Game stop!"}
                # Find the player position:
                for position, character in currentLevel.items():
                    if character in (FACE, PLAYER_ON_GOAL):
                        playerX, playerY = position

                def check(inter):
                    return inter.message.id == msg.id and ctx.author == inter.author
                try:
                    inter = await self.bot.wait_for('button_click', check=check, timeout=120)
                    inter_msg = True
                except (asyncio.TimeoutError, asyncio.exceptions.TimeoutError) as e:
                    if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                        self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
                    await ctx.reply(f'{ctx.author.mention} **SOKOBAN GAME** has waited you too long. Game exits.')
                    game_over = True
                    if free_game == True:
                        try:
                            await store.sql_game_free_add(str(level), str(ctx.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'SOKOBAN', int(time.time()) - time_start, SERVER_BOT)
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                    else:
                        try:
                            reward = await store.sql_game_add(str(level), str(ctx.author.id), 'None', 'WIN' if won else 'LOSE', 0, 0, str(ctx.guild.id), 'SOKOBAN', int(time.time()) - time_start, SERVER_BOT)
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                    return
                if inter.clicked_button.custom_id == "stop":
                    await ctx.reply(f'{ctx.author.mention} **SOKOBAN GAME** You gave up the current game.')
                    game_over = True
                    if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                        self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)

                    if free_game == True:
                        try:
                            await store.sql_game_free_add(str(level), str(ctx.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'SOKOBAN', int(time.time()) - time_start, SERVER_BOT)
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                    else:
                        try:
                            reward = await store.sql_game_add(str(level), str(ctx.author.id), 'None', 'WIN' if won else 'LOSE', 0, 0, str(ctx.guild.id), 'SOKOBAN', int(time.time()) - time_start, SERVER_BOT)
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                    await asyncio.sleep(1)
                    try:
                        await msg.delete()
                    except Exception as e:
                        pass
                    return
                elif inter.clicked_button.custom_id == "up":
                    moveX, moveY = 0, -1
                elif inter.clicked_button.custom_id == "down":
                    moveX, moveY = 0, 1
                elif inter.clicked_button.custom_id == "left":
                    moveX, moveY = -1, 0
                elif inter.clicked_button.custom_id == "right":
                     moveX, moveY = 1, 0
     
                moveToX = playerX + moveX
                moveToY = playerY + moveY
                moveToSpace = currentLevel.get((moveToX, moveToY), EMPTY)

                # If the move-to space is empty or a goal, just move there:
                if moveToSpace == EMPTY or moveToSpace == GOAL:
                    # Change the player's old position:
                    if currentLevel[(playerX, playerY)] == FACE:
                        currentLevel[(playerX, playerY)] = EMPTY
                    elif currentLevel[(playerX, playerY)] == PLAYER_ON_GOAL:
                        currentLevel[(playerX, playerY)] = GOAL

                    # Set the player's new position:
                    if moveToSpace == EMPTY:
                        currentLevel[(moveToX, moveToY)] = FACE
                    elif moveToSpace == GOAL:
                        currentLevel[(moveToX, moveToY)] = PLAYER_ON_GOAL

                # If the move-to space is a wall, don't move at all:
                elif moveToSpace == WALL:
                    pass

                # If the move-to space has a crate, see if we can push it:
                elif moveToSpace in (CRATE, CRATE_ON_GOAL):
                    behindMoveToX = playerX + (moveX * 2)
                    behindMoveToY = playerY + (moveY * 2)
                    behindMoveToSpace = currentLevel.get((behindMoveToX, behindMoveToY), EMPTY)
                    if behindMoveToSpace in (WALL, CRATE, CRATE_ON_GOAL):
                        # Can't push the crate because there's a wall or
                        # crate behind it:
                        continue
                    if behindMoveToSpace in (GOAL, EMPTY):
                        # Change the player's old position:
                        if currentLevel[(playerX, playerY)] == FACE:
                            currentLevel[(playerX, playerY)] = EMPTY
                        elif currentLevel[(playerX, playerY)] == PLAYER_ON_GOAL:
                            currentLevel[(playerX, playerY)] = GOAL

                        # Set the player's new position:
                        if moveToSpace == CRATE:
                            currentLevel[(moveToX, moveToY)] = FACE
                        elif moveToSpace == CRATE_ON_GOAL:
                            currentLevel[(moveToX, moveToY)] = PLAYER_ON_GOAL

                        # Set the crate's new position:
                        if behindMoveToSpace == EMPTY:
                            currentLevel[(behindMoveToX, behindMoveToY)] = CRATE
                        elif behindMoveToSpace == GOAL:
                            currentLevel[(behindMoveToX, behindMoveToY)] = CRATE_ON_GOAL

                # Check if the player has finished the level:
                levelIsSolved = True
                for position, character in currentLevel.items():
                    if character == CRATE:
                        levelIsSolved = False
                        break
                display_level = displayLevel(currentLevel)
                if levelIsSolved:
                    won = True
                    # game end, check win or lose
                    try:
                        result = ''
                        if free_game == False:
                            won_x = 2
                            if won:
                                COIN_NAME = random.choice(GAME_COIN)
                                amount = GAME_SLOT_REWARD[COIN_NAME] * won_x
                                if COIN_NAME in ENABLE_COIN_ERC:
                                    coin_family = "ERC-20"
                                elif COIN_NAME in ENABLE_COIN_TRC:
                                    coin_family = "TRC-20"
                                else:
                                    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                                real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO", "XCH"] else float(amount)
                                reward = await store.sql_game_add(str(level), str(ctx.author.id), COIN_NAME, 'WIN', real_amount, get_decimal(COIN_NAME), str(ctx.guild.id), 'SOKOBAN', int(time.time()) - time_start, SERVER_BOT)
                                result = f'You won! {ctx.author.mention} got reward of **{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}** to Tip balance!'
                            else:
                                reward = await store.sql_game_add(str(level), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'SOKOBAN', int(time.time()) - time_start, SERVER_BOT)
                                result = f'You lose!'
                        else:
                            if won:
                                result = f'You won! but this is a free game without **reward**! Waiting to refresh your paid plays (24h max).'
                            else:
                                result = f'You lose!'
                            try:
                                await store.sql_game_free_add(str(level), str(ctx.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'SOKOBAN', int(time.time()) - time_start, SERVER_BOT)
                            except Exception as e:
                                await logchanbot(traceback.format_exc())
                        await ctx.reply(f'{ctx.author.mention} **SOKOBAN GAME** {result}')
                        if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                            self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)

                    except Exception as e: # edit
                        await logchanbot(traceback.format_exc())
                    embed = disnake.Embed(title=f'SOKOBAN GAME FINISHED {ctx.author.name}#{ctx.author.discriminator}', description=f'{display_level}', timestamp=datetime.utcnow(), colour=7047495)
                    embed.add_field(name="LEVEL", value=f'{level}')
                    duration = seconds_str(int(time.time()) - time_start)
                    embed.add_field(name="DURATION", value=f'{duration}')
                    embed.add_field(name="OTHER LINKS", value="[Invite TipBot]({}) / [Support Server]({}) / [TipBot Github]({})".format(config.discord.invite_link, config.discord.support_server_link, config.discord.github_link), inline=False)
                    inter_msg = True
                    await inter.create_response(embed=embed, components=[row], type=dislash.ResponseType.UpdateMessage)
                    game_over = True
                    break
                    return

            if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
                self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)
            return
        except Exception as e:
            await logchanbot(traceback.format_exc())
        if ctx.author.id in self.bot.GAME_INTERACTIVE_PRGORESS:
            self.bot.GAME_INTERACTIVE_PRGORESS.remove(ctx.author.id)


    @commands.slash_command(description="Various game commands.")
    async def game(self, ctx):
        pass


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
            await ctx.reply(game_blackjack['error'])


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
                await ctx.reply(game_maze['error'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


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
            if game_dice and "error" in game_dice:
                await ctx.reply(game_dice['error'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


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
                await ctx.reply(game_snail['error'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


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
                await ctx.reply(game_2048['error'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


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
                await ctx.reply(game_sokoban['error'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


def setup(bot):
    bot.add_cog(Games(bot))