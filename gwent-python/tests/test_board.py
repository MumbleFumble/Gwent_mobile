from gwent.cards.base_card import Card, Faction, CardType, Row, Ability
from gwent.game.board import Board
import sys
from pathlib import Path


# Ensure package path for static analysis tools
sys.path.append(str(Path(__file__).resolve().parent.parent))




def make_unit(name: str, power: int, abilities=None, hero=False):
    return Card(
        id=name.lower(),
        name=name,
        faction=Faction.NEUTRAL,
        type=CardType.UNIT,
        row=Row.MELEE,
        power=power,
        hero=hero,
        abilities=abilities or [],
    )


def test_bond_strength():
    board = Board(["P1", "P2"])
    a1 = make_unit("Commando", 4, [Ability.TIGHT_BOND])
    a2 = make_unit("Commando", 4, [Ability.TIGHT_BOND])
    board.play_card("P1", a1)
    board.play_card("P1", a2)
    # Each card strength becomes base * count (4 * 2 = 8) total = 16
    assert board.row_strength("P1", Row.MELEE) == 16


def test_morale_boost():
    board = Board(["P1", "P2"])
    morale = make_unit("Banner", 2, [Ability.MORALE_BOOST])
    u1 = make_unit("Soldier", 5)
    u2 = make_unit("Archer", 3)
    board.play_card("P1", morale)
    board.play_card("P1", u1)
    board.play_card("P1", u2)
    # Morale gives +1 to other units: soldier 6, archer 4, morale 2 = 12
    assert board.row_strength("P1", Row.MELEE) == 12
