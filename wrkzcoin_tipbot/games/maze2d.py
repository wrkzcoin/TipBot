"""Maze Maker, by Al Sweigart al@inventwithpython.com
Make mazes with the recursive backtracker algorithm.
More info at: https://en.wikipedia.org/wiki/Maze_generation_algorithm#Recursive_backtracker
An animated demo: https://scratch.mit.edu/projects/17358777/
This and other games are available at https://nostarch.com/XX
Tags: large, maze"""

import random

# Set up the constants:
WALL = '#'
EMPTY = ' '
START = '@'
EXIT = 'E'
# BLOCK = chr(9617)  # Character 9617 is '░'
BLOCK = chr(9608)  # Character 9617 is '█'

NORTH = 'north'
SOUTH = 'south'
EAST = 'east'
WEST = 'west'


def displayMaze(maze, WIDTH: int, HEIGHT: int, playerx: int, playery: int, exitx: int, exity: int):
    PLAYER = '@'
    m = ''
    # Display the maze:
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if (x, y) == (playerx, playery):
                m += PLAYER
            elif (x, y) == (exitx, exity):
                m += 'X'
            elif maze[(x, y)] == WALL:
                m += BLOCK
            else:
                m += maze[(x, y)]
        m += '\n'
    return m


async def createMazeDump(WIDTH: int, HEIGHT: int, SEED: int):
    random.seed(SEED)
    # Create the filled-in maze to start:
    maze = {}
    for x in range(WIDTH):
        for y in range(HEIGHT):
            maze[(x, y)] = WALL

    # Create the maze:
    pathFromStart = [(1, 1)]
    hasVisited = [(1, 1)]

    while len(pathFromStart) > 0:
        x, y = pathFromStart[-1]
        maze[(x, y)] = EMPTY

        unvisitedNeighbors = []
        # Check the north neighbor:
        if y > 1 and (x, y - 2) not in hasVisited:
            unvisitedNeighbors.append(NORTH)
        # Check the south neighbor:
        if y < HEIGHT - 2 and (x, y + 2) not in hasVisited:
            unvisitedNeighbors.append(SOUTH)
        # Check the west neighbor:
        if x > 1 and (x - 2, y) not in hasVisited:
            unvisitedNeighbors.append(WEST)
        # Check the east neighbor:
        if x < WIDTH - 2 and (x + 2, y) not in hasVisited:
            unvisitedNeighbors.append(EAST)

        if len(unvisitedNeighbors) > 0:
            nextIntersection = random.choice(unvisitedNeighbors)
            if nextIntersection == NORTH:
                pathFromStart.append((x, y - 2))
                hasVisited.append((x, y - 2))
                maze[(x, y - 1)] = EMPTY
            elif nextIntersection == SOUTH:
                pathFromStart.append((x, y + 2))
                hasVisited.append((x, y + 2))
                maze[(x, y + 1)] = EMPTY
            elif nextIntersection == WEST:
                pathFromStart.append((x - 2, y))
                hasVisited.append((x - 2, y))
                maze[(x - 1, y)] = EMPTY
            elif nextIntersection == EAST:
                pathFromStart.append((x + 2, y))
                hasVisited.append((x + 2, y))
                maze[(x + 1, y)] = EMPTY
        else:
            pathFromStart.pop()

    # Add the start and end positions:
    maze[(1, 1)] = START
    maze[(WIDTH - 2, HEIGHT - 2)] = EXIT
    return maze

