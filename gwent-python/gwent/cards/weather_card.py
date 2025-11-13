from dataclasses import dataclass
from .base_card import Card, Row, Faction, Ability, CardType


@dataclass
class WeatherCard(Card):
    """Weather card affecting rows (Frost, Fog, Rain, Storm)."""

    @classmethod
    def from_raw(cls, card: dict, uid: str):
        # All weather effects share Ability.WEATHER
        meta = {
            "quote": card.get("Quote", ""),
            "dlc": card.get("DLC"),
        }

        return cls(
            id=uid,
            name=card["Name"],
            faction=Faction.from_label(card["Faction"]),
            type=CardType.WEATHER,
            row=Row.ALL,                     # Weather applies globally
            power=0,
            hero=False,
            abilities=[Ability.WEATHER],
            tags=[],
            meta=meta
        )
