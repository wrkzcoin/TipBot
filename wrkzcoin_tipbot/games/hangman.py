"""Hangman, by Al Sweigart al@inventwithpython.com
Guess the letters to a secret word before the hangman is drawn.
This and other games are available at https://nostarch.com/XX
Tags: large, game, puzzle, word"""

# A version of this game is featured in the book, "Invent Your Own
# Computer Games with Python" https://nostarch.com/inventwithpython

import random, sys, re

# Set up the constants:
# (!) Try adding or changing the strings in HANGMAN_PICS to make a
# guillotine instead of a gallows.
HANGMAN_PICS = [r"""
 +--+
 |  |
    |
    |
    |
    |
=====""",
r"""
 +--+
 |  |
 O  |
    |
    |
    |
=====""",
r"""
 +--+
 |  |
 O  |
 |  |
    |
    |
=====""",
r"""
 +--+
 |  |
 O  |
/|  |
    |
    |
=====""",
r"""
 +--+
 |  |
 O  |
/|\ |
    |
    |
=====""",
r"""
 +--+
 |  |
 O  |
/|\ |
/   |
    |
=====""",
r"""
 +--+
 |  |
 O  |
/|\ |
/ \ |
    |
====="""]


def load_words():
    wordList = []
    with open('games/google-10000-english-usa-no-swears-medium.txt') as word_file:
        valid_words = set(word_file.read().split())
    for item in valid_words:
        if 5 <= len(item) <= 12 and re.match('[a-zA-Z]+', item):
            wordList.append(item)
    return wordList


def drawHangman(missedLetters, correctLetters, secretWord):
    """Draw the current state of the hangman, along with the missed and
    correctly-guessed letters of the secret word."""
    picture = HANGMAN_PICS[len(missedLetters)]

    # Show the incorrectly guessed letters:
    missed_letter = 'No missed letters yet.'
    if len(missedLetters) > 0:
        missed_letter = 'Missed letters: ' + ', '.join(missedLetters)

    # Display the blanks for the secret word (one blank per letter):
    blanks = ['_'] * len(secretWord)

    # Replace blanks with correctly guessed letters:
    for i in range(len(secretWord)):
        if secretWord[i] in correctLetters:
            blanks[i] = secretWord[i]

    # Show the secret word with spaces in between each letter:
    word_line = ' '.join(blanks)
    return {'picture': picture, 'missed_letter': missed_letter, 'word_line': word_line}
