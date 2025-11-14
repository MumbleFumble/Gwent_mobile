from __future__ import annotations

from gwent.cards.base_card import Row
from gwent.game.board import Board


def clear_weather(board: Board) -> None:
    for r in board.active_weather:
        board.active_weather[r] = False
    _sync(board)


def apply_weather(board: Board, name: str) -> None:
    name = name.lower()
    mapping = {
        "biting frost": [Row.MELEE],
        "impenetrable fog": [Row.RANGED],
        "torrential rain": [Row.SIEGE],
        "skellige storm": [Row.MELEE, Row.RANGED, Row.SIEGE],
    }
    for r in mapping.get(name, []):
        board.active_weather[r] = True
    _sync(board)


def activate_leader(board: Board, player_id: str, ability_text: str) -> bool:
    """Very light parsing of leader ability text to trigger simple effects.

    Returns True if an effect was applied.
    """
    t = ability_text.lower()
    if "clear" in t and "weather" in t:
        clear_weather(board)
        return True
    if "biting frost" in t:
        apply_weather(board, "biting frost")
        return True
    if "impenetrable fog" in t:
        apply_weather(board, "impenetrable fog")
        return True
    if "torrential rain" in t:
        apply_weather(board, "torrential rain")
        return True
    if "skellige storm" in t:
        apply_weather(board, "skellige storm")
        return True
    # Row doubling (Commander's Horn-like leader effects)
    if ("double" in t or "commander" in t) and ("melee" in t or "close" in t):
        board.rows[player_id][Row.MELEE].horn_active = True
        return True
    if ("double" in t or "commander" in t) and ("ranged" in t or "range" in t):
        board.rows[player_id][Row.RANGED].horn_active = True
        return True
    if ("double" in t or "commander" in t) and "siege" in t:
        board.rows[player_id][Row.SIEGE].horn_active = True
        return True
    return False


def _sync(board: Board) -> None:
    for p in board.players:
        for r, state in board.rows[p].items():
            state.weather_active = board.active_weather[r]
