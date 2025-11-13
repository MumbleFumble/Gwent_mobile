from dataclasses import dataclass
from typing import Dict, Any

from .base_card import Card, Row, Faction, Ability, CardType


@dataclass
class LeaderCard(Card):
    """Leader cards with special abilities."""
    leader_ability: str = ""

    @classmethod
    def from_raw(cls, card: dict, uid: str):
        meta = {
            "quote": card.get("Quote", ""),
            "dlc": card.get("DLC"),
        }

        return cls(
            id=uid,
            name=card["Name"],
            faction=Faction.from_label(card["Faction"]),
            type=CardType.LEADER,
            row=Row.ALL,
            power=0,
            hero=True,
            abilities=[Ability.HERO],     # Leader immunity
            tags=[],
            meta=meta,
            leader_ability=card.get("Ability", "")
        )
