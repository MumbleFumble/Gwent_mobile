from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional

from gwent.cards.base_card import Card, Ability, Row


@dataclass
class RowState:
    """Represents one combat row for a single player.

    Applies modifiers in order: Weather, Bond, Morale, Horn.
    """

    row: Row
    cards: List[Card] = field(default_factory=list)
    weather_active: bool = False
    horn_active: bool = False

    def add(self, card: Card) -> None:
        self.cards.append(card)
        if Ability.HORN in card.abilities:
            self.horn_active = True

    def remove(self, card: Card) -> bool:
        try:
            self.cards.remove(card)
            return True
        except ValueError:
            return False

    def preview_added_strength(self, card: Card) -> int:
        before = self.effective_strength()
        self.cards.append(card)
        try:
            after = self.effective_strength()
        finally:
            self.cards.pop()
        return after - before

    def _bond_groups(self) -> Dict[str, int]:
        groups: Dict[str, int] = {}
        for c in self.cards:
            if Ability.TIGHT_BOND in c.abilities:
                groups[c.name] = groups.get(c.name, 0) + 1
        return groups

    def effective_strength(self) -> int:
        if not self.cards:
            return 0
        bond = self._bond_groups()
        morale_sources = [c for c in self.cards if Ability.MORALE_BOOST in c.abilities]
        morale_count = len(morale_sources)
        total = 0
        for c in self.cards:
            if self.weather_active and not c.is_hero:
                base = 1 if c.is_unit else 0
            else:
                base = c.base_power()
            if Ability.TIGHT_BOND in c.abilities:
                base *= bond.get(c.name, 1)
            if morale_count and Ability.MORALE_BOOST not in c.abilities and c.is_unit:
                base += morale_count
            if self.horn_active and c.is_unit and not c.is_hero:
                base *= 2
            total += base
        return total


class Board:
    """Board containing rows for players and global weather state."""

    def __init__(self, players: List[str]):
        self.players = players
        self.rows: Dict[str, Dict[Row, RowState]] = {
            p: {Row.MELEE: RowState(Row.MELEE), Row.RANGED: RowState(Row.RANGED), Row.SIEGE: RowState(Row.SIEGE)}
            for p in players
        }
        self.active_weather: Dict[Row, bool] = {Row.MELEE: False, Row.RANGED: False, Row.SIEGE: False}
        # Optional simple deck stores for muster support in tests/integration
        self.decks: Dict[str, List[Card]] = {p: [] for p in players}
        # Simple per-player graveyard to store destroyed/discarded units
        self.graveyards: Dict[str, List[Card]] = {p: [] for p in players}

    def add_to_deck(self, player: str, cards: List[Card]) -> None:
        self.decks[player].extend(cards)

    def get_opponent(self, player: str) -> str:
        for p in self.players:
            if p != player:
                return p
        return player

    def play_card(self, player: str, card: Card, target_row: Optional[Row] = None, target_unit: Optional[Card] = None, suppress_muster: bool = False) -> Dict[str, Optional[Card]]:
        events: Dict[str, Optional[Card]] = {"decoy_returned": None, "resurrected": None, "spy_played": None, "transformed": None}
        chosen_row = target_row or card.row
        # Weather specials ignore row targeting entirely
        if Ability.WEATHER in card.abilities:
            self._apply_weather(card)
            self.graveyards[player].append(card)
            return events
        # Scorch: remove strongest non-hero units from board
        if Ability.SCORCH in card.abilities and not card.is_unit:
            self._apply_scorch()
            self.graveyards[player].append(card)
            return events
        # Decoy: return a unit from your board to hand (requires target_unit)
        if Ability.DECOY in card.abilities and not card.is_unit:
            if target_unit is None:
                raise ValueError("Decoy requires target_unit")
            for rs in self.rows[player].values():
                if target_unit in rs.cards:
                    rs.remove(target_unit)
                    # Place the decoy on the specified or unit's row (0 strength placeholder)
                    place_row = chosen_row if chosen_row in self.rows[player] else rs.row
                    self.rows[player][place_row].add(card)
                    events["decoy_returned"] = target_unit
                    break
            return events
        # Mardroeme: transform berserker target into its transformed form
        if Ability.MARDROEME in card.abilities and not card.is_unit:
            if target_unit is None:
                raise ValueError("Mardroeme requires target_unit (typically a Berserker)")
            # Find target on board and replace if eligible
            for r, rs in self.rows[player].items():
                if target_unit in rs.cards:
                    if Ability.BERSERKER in target_unit.abilities:
                        rs.remove(target_unit)
                        new_power = max(target_unit.base_power(), 8)
                        transformed = Card(
                            id=f"{target_unit.id}:t",
                            name=f"{target_unit.name} (Transformed)",
                            faction=target_unit.faction,
                            type=target_unit.type,
                            row=r,
                            power=new_power,
                            hero=target_unit.hero,
                            abilities=[a for a in target_unit.abilities if a != Ability.BERSERKER],
                            tags=list(target_unit.tags),
                            meta={**target_unit.meta, "transformed": True},
                        )
                        self.rows[player][r].add(transformed)
                        events["transformed"] = transformed
                    break
            self.graveyards[player].append(card)
            self._sync_weather_flags()
            return events
        # Spy: place this unit on opponent's board
        if Ability.SPY in card.abilities and card.is_unit:
            opp = self.get_opponent(player)
            if getattr(card, "combat_rows", None) and chosen_row == Row.ALL:
                chosen_row = self._best_row_for_unit(opp, card)
            if chosen_row not in self.rows[opp]:
                raise ValueError(f"Invalid row {chosen_row} for opponent {opp}")
            self.rows[opp][chosen_row].add(card)
            self._sync_weather_flags()
            events["spy_played"] = card
            return events
        # Commander's Horn can target any specific row of the player
        if Ability.HORN in card.abilities and not card.is_unit:
            if chosen_row not in self.rows[player]:
                raise ValueError(f"Invalid row {chosen_row} for player {player}")
            self.rows[player][chosen_row].horn_active = True
            self._sync_weather_flags()
            self.graveyards[player].append(card)
            return events
        # Agile or multi-row unit: choose best row when not specified (row==ALL)
        if getattr(card, "combat_rows", None) and chosen_row == Row.ALL:
            chosen_row = self._best_row_for_unit(player, card)
        # Validate final row for placement
        if chosen_row not in self.rows[player]:
            raise ValueError(f"Invalid row {chosen_row} for player {player}")
        self.rows[player][chosen_row].add(card)
        self._sync_weather_flags()
        # Medic: after placing the unit, resurrect best candidate from your graveyard
        if Ability.MEDIC in card.abilities and card.is_unit:
            gy = self.graveyards.get(player, [])
            best_score: int = -1
            res: Optional[Card] = None
            for c in gy:
                if c.is_unit and not c.is_hero:
                    score = c.base_power()
                    if score > best_score:
                        best_score = score
                        res = c
            if res is not None:
                gy.remove(res)
                # Place resurrected unit on its own row
                res_row = res.row
                if getattr(res, "combat_rows", None) and res_row == Row.ALL:
                    res_row = self._best_row_for_unit(player, res)
                self.rows[player][res_row].add(res)
                events["resurrected"] = res
        # Muster: after placing the primary card, pull matching group units from deck
        if Ability.MUSTER in card.abilities and not suppress_muster:
            group = card.meta.get("group") or card.name
            deck = self.decks.get(player, [])
            to_play: List[Card] = []
            for c in list(deck):
                if getattr(c, "meta", {}).get("group") == group and c.is_unit:
                    deck.remove(c)
                    to_play.append(c)
            for c in to_play:
                # Place each from deck; let agile logic pick if applicable
                self.play_card(player, c, target_row=None, suppress_muster=True)
        return events

    def _apply_weather(self, card: Card) -> None:
        name = card.name.lower()
        mapping = {
            "biting frost": [Row.MELEE],
            "impenetrable fog": [Row.RANGED],
            "torrential rain": [Row.SIEGE],
            "skellige storm": [Row.MELEE, Row.RANGED, Row.SIEGE],
            "clear weather": []
        }
        if name == "clear weather":
            for r in self.active_weather:
                self.active_weather[r] = False
        else:
            for r in mapping.get(name, []):
                self.active_weather[r] = True
        self._sync_weather_flags()

    def _sync_weather_flags(self) -> None:
        for p in self.players:
            for r, state in self.rows[p].items():
                state.weather_active = self.active_weather[r]

    def _best_row_for_unit(self, player: str, card: Card) -> Row:
        choices = list(getattr(card, "combat_rows", []) or [card.row])
        if not choices:
            return card.row
        best_row = choices[0]
        best_gain = -10**9
        for r in choices:
            rs = self.rows[player][r]
            gain = rs.preview_added_strength(card)
            if gain > best_gain:
                best_gain = gain
                best_row = r
        return best_row

    def _apply_scorch(self) -> None:
        highest = 0
        victims: List[Card] = []
        locations: List[tuple[str, Row]] = []
        for p in self.players:
            for r, rs in self.rows[p].items():
                for c in rs.cards:
                    if not c.is_unit or c.is_hero:
                        continue
                    before = rs.effective_strength()
                    rs.cards.remove(c)
                    after = rs.effective_strength()
                    rs.cards.insert(0, c)
                    value = before - after
                    if value > highest:
                        highest = value
                        victims = [c]
                        locations = [(p, r)]
                    elif value == highest and value > 0:
                        victims.append(c)
                        locations.append((p, r))
        for (c, (p, r)) in zip(victims, locations):
            removed = self.rows[p][r].remove(c)
            if removed:
                self._on_unit_removed(p, c, r)

    def row_strength(self, player: str, row: Row) -> int:
        return self.rows[player][row].effective_strength()

    def total_strength(self, player: str) -> int:
        return sum(self.row_strength(player, r) for r in (Row.MELEE, Row.RANGED, Row.SIEGE))

    def snapshot(self) -> Dict[str, Dict[str, int]]:
        return {p: {r.value: self.row_strength(p, r) for r in (Row.MELEE, Row.RANGED, Row.SIEGE)} for p in self.players}

    def get_graveyard(self, player: str) -> List[Card]:
        return list(self.graveyards.get(player, []))

    def cleanup_after_round(self) -> None:
        # Move all cards from rows to graveyards and reset row state
        for p in self.players:
            for rs in self.rows[p].values():
                # Move units and specials from board to graveyard
                if rs.cards:
                    self.graveyards[p].extend(rs.cards)
                    rs.cards = []
                rs.horn_active = False
                rs.weather_active = False

    def _on_unit_removed(self, player: str, card: Card, row: Row) -> None:
        # Push to graveyard and process on-death triggers
        self.graveyards[player].append(card)
        # Avenger: immediately return to the same row once
        if Ability.AVENGER in card.abilities and not card.meta.get("avenged"):
            card.meta["avenged"] = True
            # Bring back from graveyard to the same row
            try:
                self.graveyards[player].remove(card)
            except ValueError:
                pass
            self.rows[player][row].add(card)
            self._sync_weather_flags()

