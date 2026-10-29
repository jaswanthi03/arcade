"""Fallback terminal player for environments without browser port preview."""
from .engine import initial_state, observe
from .levels import LEVELS
from .server import GameService

SYMBOLS = {
    'wall': '##', 'floor': '  ', 'goal': ' *',
    'red_tile': ' R', 'blue_tile': ' B',
    'red_barrier': '|r', 'blue_barrier': '|b', 'neutral_barrier': '|n',
}
MOVES = {'w': 'up', 'a': 'left', 's': 'down', 'd': 'right'}


def draw(session):
    observation = session['observation']
    player = observation['player']
    print('\n' + session['level_name'])
    for y, row in enumerate(observation['grid']):
        print(''.join((' @' if (x, y) == (player['x'], player['y']) else SYMBOLS[tile])
                      for x, tile in enumerate(row)))
    print(f"Color: {player['color']} | Feedback: {session['feedback']} | "
          f"Attempts: {session['stats']['attempts']} | "
          f"Blocked: {session['stats']['invalid_moves']}")


def main():
    print('COLOR LAB — W/A/S/D move, R reset, E explain, N next, Q quit')
    service = GameService()
    ids = list(LEVELS)
    index = 0
    game = service.start(ids[index], 'human')
    draw(game)
    while True:
        command = input('> ').strip().lower()
        try:
            if command in MOVES:
                if game['observation']['completed']:
                    print('Solved. Enter N for the next room.')
                    continue
                game = service.act(game['session_id'], MOVES[command])
                draw(game)
            elif command == 'r':
                game = service.reset(game['session_id'])
                draw(game)
            elif command == 'e':
                explanation = input('Your rule hypothesis: ')
                service.explain(game['session_id'], explanation)
                print('Hypothesis recorded.')
            elif command == 'n':
                if index == len(ids)-1:
                    print('No more rooms.')
                    continue
                index += 1
                game = service.start(ids[index], 'human')
                draw(game)
            elif command == 'q':
                break
            else:
                print('Use W/A/S/D to move, R reset, E explain, N next, Q quit.')
        except ValueError as exc:
            print('Error:', exc)


if __name__ == '__main__':
    main()
