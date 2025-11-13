from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict

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

	def play_card(self, player: str, card: Card) -> None:
		target_row = card.row
		if target_row not in self.rows[player]:
			raise ValueError(f"Invalid row {target_row} for player {player}")
		if Ability.WEATHER in card.abilities:
			self._apply_weather(card)
			return
		self.rows[player][target_row].add(card)
		self._sync_weather_flags()

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

	def row_strength(self, player: str, row: Row) -> int:
		return self.rows[player][row].effective_strength()

	def total_strength(self, player: str) -> int:
		return sum(self.row_strength(player, r) for r in (Row.MELEE, Row.RANGED, Row.SIEGE))

	def snapshot(self) -> Dict[str, Dict[str, int]]:
		return {p: {r.value: self.row_strength(p, r) for r in (Row.MELEE, Row.RANGED, Row.SIEGE)} for p in self.players}

