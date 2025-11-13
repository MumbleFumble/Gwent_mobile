from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any


# ============================================================
# ENUMS
# ============================================================

class Faction(str, Enum):
    NORTHERN_REALMS = "northern_realms"
    NILFGAARDIAN_EMPIRE = "nilfgaardian_empire"
    SCOIATAEL = "scoiatael"
    MONSTERS = "monsters"
    SKELLIGE = "skellige"
    NEUTRAL = "neutral"

    @classmethod
    def from_label(cls, name: str):
        """Convert human-friendly faction label into enum value."""
        normalized = (
            name.lower()
            .replace(" ", "_")
            .replace("'", "")
            .replace("’", "")
        )
        for f in cls:
            if f.value == normalized:
                return f
        raise ValueError(f"Unknown faction: {name} → {normalized}")


class CardType(str, Enum):
    UNIT = "unit"
    WEATHER = "weather"
    SPECIAL = "special"
    LEADER = "leader"


class Row(str, Enum):
    MELEE = "melee"
    RANGED = "ranged"
    SIEGE = "siege"
    ALL = "all"  # For weather/special cards affecting all rows

    @classmethod
    def from_label(cls, name: str):
        """Turn 'Close', 'Ranged', 'Siege' → enum row."""
        mapping = {
            "close": cls.MELEE,
            "melee": cls.MELEE,
            "ranged": cls.RANGED,
            "range": cls.RANGED,
            "siege": cls.SIEGE,
            "all": cls.ALL,
        }
        key = name.lower()
        if key in mapping:
            return mapping[key]
        raise ValueError(f"Invalid row label: {name}")


class Ability(str, Enum):
    # Common Witcher 3 minigame effects
    TIGHT_BOND = "tight_bond"
    MORALE_BOOST = "morale_boost"
    MEDIC = "medic"
    SPY = "spy"
    DECOY = "decoy"
    SCORCH = "scorch"
    HORN = "horn"
    WEATHER = "weather"
    HERO = "hero"
    MUSTER = "muster"

    # Extra effects from your dataset
    AGILE = "agile"
    AVENGER = "avenger"
    BERSERKER = "berserker"
    MARDROEME = "mardroeme"

    NONE = "none"

    @classmethod
    def from_label(cls, label: str | None):
        """Convert raw text from JSON to correct enum ability."""
        if not label:
            return []
        key = label.lower().strip()

        mapping = {
            "bond": cls.TIGHT_BOND,
            "morale": cls.MORALE_BOOST,
            "medic": cls.MEDIC,
            "spy": cls.SPY,
            "scorch": cls.SCORCH,
            "horn": cls.HORN,
            "weather": cls.WEATHER,
            "muster": cls.MUSTER,
            "decoy": cls.DECOY,
            "agile": cls.AGILE,
            "avenger": cls.AVENGER,
            "berserker": cls.BERSERKER,
            "mardroeme": cls.MARDROEME,
        }

        return [mapping[key]] if key in mapping else []


# ============================================================
# BASE CARD CLASS
# ============================================================

@dataclass
class Card:
    """
    Base Card representation. All other card types inherit from this.
    DO NOT instantiate Card directly — use subclasses.
    """

    id: str
    name: str
    faction: Faction
    type: CardType
    row: Row
    power: int = 0
    hero: bool = False
    abilities: List[Ability] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    # ---------------------------------------------------------
    # Convenience Properties
    # ---------------------------------------------------------

    def base_power(self) -> int:
        return self.power

    @property
    def is_unit(self) -> bool:
        return self.type == CardType.UNIT

    @property
    def is_weather(self) -> bool:
        return self.type == CardType.WEATHER

    @property
    def is_special(self) -> bool:
        return self.type == CardType.SPECIAL

    @property
    def is_leader(self) -> bool:
        return self.type == CardType.LEADER

    @property
    def is_hero(self) -> bool:
        return self.hero or Ability.HERO in self.abilities

    def has_ability(self, ability: Ability) -> bool:
        return ability in self.abilities

    # ---------------------------------------------------------
    # Serialization
    # ---------------------------------------------------------

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Card":
        """
        This is the *generic* loader. Subclasses should override this.
        """
        return cls(
            id=data["id"],
            name=data["name"],
            faction=Faction(data["faction"]),
            type=CardType(data["type"]),
            row=Row(data["row"]),
            power=data.get("power", 0),
            hero=data.get("hero", False),
            abilities=[Ability(a) for a in data.get("abilities", [])],
            tags=data.get("tags", []),
            meta=data.get("meta", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert card into JSON-friendly dict."""
        return {
            "id": self.id,
            "name": self.name,
            "faction": self.faction.value,
            "type": self.type.value,
            "row": self.row.value,
            "power": self.power,
            "hero": self.hero,
            "abilities": [a.value for a in self.abilities],
            "tags": self.tags,
            "meta": self.meta,
        }
