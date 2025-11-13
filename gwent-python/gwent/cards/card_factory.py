import json
from pathlib import Path

from .unit_card import UnitCard
from .leader_card import LeaderCard
from .special_card import SpecialCard
from .weather_card import WeatherCard
from .base_card import Ability


class CardFactory:
    """
    Decides which Card subclass to instantiate from a raw JSON entry.
    """

    @staticmethod
    def is_weather(card: dict) -> bool:
        """Weather cards have Effect 1 = 'Weather' OR names that match known weather."""
        weather_names = {
            "Biting Frost",
            "Impenetrable Fog",
            "Torrential Rain",
            "Skellige Storm",
            "Clear Weather"
        }

        if card.get("Name") in weather_names:
            return True

        if card.get("Effect 1") == "Weather":
            return True

        return False

    @staticmethod
    def is_special(card: dict) -> bool:
        """Decoy, Horn, Scorch, Mardroeme, etc."""
        special_effects = {
            "Decoy",
            "Scorch",
            "Horn",
            "Mardroeme",
            "Avenger"
        }

        if card.get("Effect 1") in special_effects:
            return True

        # Some special cards have strength = 0 and are not weather
        if card.get("Strength") == 0 and "Combat 1" not in card:
            return True

        return False

    @staticmethod
    def is_leader(card: dict) -> bool:
        """Leader cards only appear in leaders.json."""
        return "Quote" in card and "Combat 1" not in card and "Strength" not in card

    @staticmethod
    def make(card: dict, uid: str):
        """Return an appropriate subclass instance."""
        if CardFactory.is_leader(card):
            return LeaderCard.from_raw(card, uid)

        if CardFactory.is_weather(card):
            return WeatherCard.from_raw(card, uid)

        if CardFactory.is_special(card):
            return SpecialCard.from_raw(card, uid)

        # Otherwise default to unit
        return UnitCard.from_raw(card, uid)
