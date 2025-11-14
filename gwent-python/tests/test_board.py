from gwent.cards.base_card import Card, Faction, CardType, Row, Ability
from gwent.game.board import Board
from gwent.cards.unit_card import UnitCard
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


def test_horn_targets_melee_row():
    board = Board(["P1", "P2"])
    u1 = Card(id="u1", name="Soldier", faction=Faction.NEUTRAL, type=CardType.UNIT, row=Row.MELEE, power=5)
    u2 = Card(id="u2", name="Soldier2", faction=Faction.NEUTRAL, type=CardType.UNIT, row=Row.MELEE, power=3)
    horn = Card(id="h1", name="Horn", faction=Faction.NEUTRAL, type=CardType.SPECIAL, row=Row.ALL, power=0, abilities=[Ability.HORN])
    board.play_card("P1", u1)
    board.play_card("P1", u2)
    # Without horn: 8
    assert board.row_strength("P1", Row.MELEE) == 8
    board.play_card("P1", horn, target_row=Row.MELEE)
    # With horn doubling non-hero units: 16
    assert board.row_strength("P1", Row.MELEE) == 16


def test_scorch_removes_strongest_non_hero():
    board = Board(["P1", "P2"])
    strong = Card(id="s1", name="Strong", faction=Faction.NEUTRAL, type=CardType.UNIT, row=Row.MELEE, power=10)
    hero = Card(id="h0", name="Hero", faction=Faction.NEUTRAL, type=CardType.UNIT, row=Row.MELEE, power=12, hero=True)
    weak = Card(id="w1", name="Weak", faction=Faction.NEUTRAL, type=CardType.UNIT, row=Row.MELEE, power=4)
    scorch = Card(id="sc", name="Scorch", faction=Faction.NEUTRAL, type=CardType.SPECIAL, row=Row.ALL, power=0, abilities=[Ability.SCORCH])
    board.play_card("P1", strong)
    board.play_card("P1", hero)
    board.play_card("P1", weak)
    # total before: 26
    assert board.row_strength("P1", Row.MELEE) == 26
    board.play_card("P1", scorch)
    # Strongest non-hero (10) removed; remaining hero 12 + weak 4 = 16
    assert board.row_strength("P1", Row.MELEE) == 16


def test_scorch_sends_victims_to_graveyard():
    board = Board(["P1", "P2"])
    a = Card(id="a", name="A", faction=Faction.NEUTRAL, type=CardType.UNIT, row=Row.MELEE, power=7)
    b = Card(id="b", name="B", faction=Faction.NEUTRAL, type=CardType.UNIT, row=Row.MELEE, power=5)
    scorch = Card(id="sc", name="Scorch", faction=Faction.NEUTRAL, type=CardType.SPECIAL, row=Row.ALL, abilities=[Ability.SCORCH])
    board.play_card("P1", a)
    board.play_card("P1", b)
    board.play_card("P1", scorch)
    gy = board.get_graveyard("P1")
    assert any(c.id == "a" for c in gy)


def test_clear_weather_clears_all_rows():
    board = Board(["P1", "P2"])
    frost = Card(id="wf", name="Biting Frost", faction=Faction.NEUTRAL, type=CardType.WEATHER, row=Row.ALL, abilities=[Ability.WEATHER])
    clear = Card(id="cw", name="Clear Weather", faction=Faction.NEUTRAL, type=CardType.WEATHER, row=Row.ALL, abilities=[Ability.WEATHER])
    u = Card(id="u1", name="Soldier", faction=Faction.NEUTRAL, type=CardType.UNIT, row=Row.MELEE, power=7)
    board.play_card("P1", u)
    assert board.row_strength("P1", Row.MELEE) == 7
    board.play_card("P1", frost)
    assert board.row_strength("P1", Row.MELEE) == 1
    board.play_card("P1", clear)
    assert board.row_strength("P1", Row.MELEE) == 7


def test_agile_auto_best_row_choice():
    board = Board(["P1", "P2"])
    # Prepare board to make RANGED better via morale on ranged
    r_boost = Card(id="rb", name="R Banner", faction=Faction.NEUTRAL, type=CardType.UNIT, row=Row.RANGED, power=1, abilities=[Ability.MORALE_BOOST])
    board.play_card("P1", r_boost)
    agile = UnitCard(
        id="ag1", name="Agile Unit", faction=Faction.NEUTRAL, type=CardType.UNIT,
        row=Row.ALL, power=5, hero=False, abilities=[], combat_rows=[Row.MELEE, Row.RANGED]
    )
    # Without specifying target_row, it should pick RANGED (gain 6 vs MELEE 5)
    board.play_card("P1", agile)
    assert board.row_strength("P1", Row.RANGED) >= 7  # at least 1 morale + 5 base doubled? depends on horn; ensure >=7


def test_muster_pulls_group_from_deck():
    board = Board(["P1", "P2"])
    # Primary muster card on melee
    m1 = Card(
        id="m1", name="Clan Member", faction=Faction.NEUTRAL, type=CardType.UNIT,
        row=Row.MELEE, power=4, abilities=[Ability.MUSTER], meta={"group": "Clan"}
    )
    # Two matching group units in deck
    m2 = Card(
        id="m2", name="Clan Member 2", faction=Faction.NEUTRAL, type=CardType.UNIT,
        row=Row.MELEE, power=3, abilities=[Ability.MUSTER], meta={"group": "Clan"}
    )
    m3 = Card(
        id="m3", name="Clan Member 3", faction=Faction.NEUTRAL, type=CardType.UNIT,
        row=Row.MELEE, power=2, abilities=[Ability.MUSTER], meta={"group": "Clan"}
    )
    board.add_to_deck("P1", [m2, m3])
    # Play the first muster card; should pull m2 and m3 from deck
    board.play_card("P1", m1)
    # All three on melee row: 4 + 3 + 2 = 9
    assert board.row_strength("P1", Row.MELEE) == 9


def test_weather_sets_all_row_units_to_one():
    board = Board(["P1", "P2"])
    u1 = Card(id="a", name="A", faction=Faction.NEUTRAL, type=CardType.UNIT, row=Row.MELEE, power=10)
    u2 = Card(id="b", name="B", faction=Faction.NEUTRAL, type=CardType.UNIT, row=Row.MELEE, power=6)
    u3 = Card(id="c", name="C", faction=Faction.NEUTRAL, type=CardType.UNIT, row=Row.MELEE, power=2)
    frost = Card(id="wf", name="Biting Frost", faction=Faction.NEUTRAL, type=CardType.WEATHER, row=Row.ALL, abilities=[Ability.WEATHER])
    board.play_card("P1", u1)
    board.play_card("P1", u2)
    board.play_card("P1", u3)
    assert board.row_strength("P1", Row.MELEE) == 18
    board.play_card("P1", frost)
    # Three non-hero units on affected row → total 3
    assert board.row_strength("P1", Row.MELEE) == 3


def test_mardroeme_transforms_berserker():
    board = Board(["P1", "P2"])
    berserker = Card(id="bz", name="Berserker", faction=Faction.NEUTRAL, type=CardType.UNIT, row=Row.MELEE, power=3, abilities=[Ability.BERSERKER])
    mardroeme = Card(id="md", name="Mardroeme", faction=Faction.NEUTRAL, type=CardType.SPECIAL, row=Row.ALL, abilities=[Ability.MARDROEME])
    board.play_card("P1", berserker)
    # Apply mardroeme targeting the berserker
    board.play_card("P1", mardroeme, target_unit=berserker)
    # Expect transformed unit with at least 8 power on the same row
    assert board.row_strength("P1", Row.MELEE) >= 8
