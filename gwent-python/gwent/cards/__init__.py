import json
from pathlib import Path

from .card_factory import CardFactory


def load_json(name: str):
    """Load any JSON file relative to this directory."""
    path = Path(__file__).with_name(name)
    if not path.exists():
        raise FileNotFoundError(f"Cannot find JSON file: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_cards() -> list:
    """
    Load ALL cards from:
      - units.json
      - leaders.json
      - effects.json (special rules)
    and automatically build proper Card subclass objects.

    Output: List[Card]
    """
    cards = []

    units = load_json("units.json")
    leaders = load_json("leaders.json")

    # effects are only needed for matching names to abilities if desired
    try:
        effects = load_json("effects.json")
    except FileNotFoundError:
        effects = []

    uid_counter = 1

    # -------------------------------------------------------
    # LOAD UNITS (with occurrences)
    # -------------------------------------------------------
    for entry in units:
        count = entry.get("Occurrences", 1)
        for _ in range(count):
            uid = f"CARD_{uid_counter:03d}"
            cards.append(CardFactory.make(entry, uid))
            uid_counter += 1

    # -------------------------------------------------------
    # LOAD LEADERS (always unique)
    # -------------------------------------------------------
    for entry in leaders:
        uid = f"CARD_{uid_counter:03d}"
        cards.append(CardFactory.make(entry, uid))
        uid_counter += 1

    # (Optionally add weather/special standalone cards from effects.json)

    return cards

