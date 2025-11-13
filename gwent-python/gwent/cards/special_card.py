from dataclasses import dataclass
from .base_card import Card, Row, Faction, Ability, CardType


@dataclass
class SpecialCard(Card):
    """Special utility cards (Decoy, Scorch, Horn, Mardroeme, etc.)."""

    @classmethod
    def from_raw(cls, card: dict, uid: str):
        # Convert effect into Ability list
        ability = []
        if "Effect 1" in card:
            ability.extend(Ability.from_label(card["Effect 1"]))

        meta = {
            "quote": card.get("Quote", ""),
            "dlc": card.get("DLC"),
        }

        # Special cases: Avenger and Mardroeme trigger transformations
        if "Effect Prefix" in card:
            meta["group"] = card["Effect Prefix"]

        return cls(
            id=uid,
            name=card["Name"],
            faction=Faction.from_label(card["Faction"]),
            type=CardType.SPECIAL,
            row=Row.ALL,
            power=0,
            hero=False,
            abilities=ability,
            tags=[],
            meta=meta
        )
