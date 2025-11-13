from dataclasses import dataclass, field
from typing import List, Dict, Any

from .base_card import Card, Row, Faction, Ability, CardType


def extract_rows(card: dict) -> List[Row]:
    """Extract all rows a unit can be played on (handles Agile units)."""
    rows = []
    for key in ("Combat 1", "Combat 2", "Combat 3"):
        if key in card:
            label = card[key]
            try:
                rows.append(Row.from_label(label))
            except:
                pass
    return rows or [Row.MELEE]


def extract_abilities(card: dict) -> List[Ability]:
    """Extract abilities Effect 1, Effect 2, etc."""
    abilities = []
    for key in ("Effect 1", "Effect 2"):
        if key in card:
            abilities.extend(Ability.from_label(card[key]))
    return abilities


@dataclass
class UnitCard(Card):
    """Represents a standard Gwent unit card."""

    combat_rows: List[Row] = field(default_factory=list)

    @classmethod
    def from_raw(cls, card: dict, uid: str):
        rows = extract_rows(card)
        abilities = extract_abilities(card)

        meta = {
            "quote": card.get("Quote", ""),
            "occurrences": card.get("Occurrences", 1),
            "dlc": card.get("DLC"),
        }

        # Muster group (Effect Prefix)
        if "Effect Prefix" in card:
            meta["group"] = card["Effect Prefix"]

        return cls(
            id=uid,
            name=card["Name"],
            faction=Faction.from_label(card["Faction"]),
            type=CardType.UNIT,
            row=rows[0],          # base row
            combat_rows=rows,     # Agile or multi-row
            power=int(card.get("Strength", 0)),
            hero=(card.get("Hero") == "Yes"),
            abilities=abilities,
            tags=[],
            meta=meta,
        )
