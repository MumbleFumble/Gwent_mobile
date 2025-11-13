from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from gwent.cards.base_card import Card


@dataclass
class Player:
	"""Represents player state: deck, hand, graveyard."""

	id: str
	deck: List[Card]
	hand: List[Card] = field(default_factory=list)
	graveyard: List[Card] = field(default_factory=list)
	passed: bool = False
	leader_used: bool = False

	def draw(self, count: int = 1) -> List[Card]:
		drawn: List[Card] = []
		for _ in range(count):
			if not self.deck:
				break
			drawn.append(self.deck.pop(0))
		self.hand.extend(drawn)
		return drawn

	def play_from_hand(self, card: Card) -> Card:
		self.hand.remove(card)
		return card

	def find_in_hand(self, name: str) -> Optional[Card]:
		for c in self.hand:
			if c.name == name:
				return c
		return None

	def pass_round(self) -> None:
		self.passed = True

	def reset_for_new_round(self) -> None:
		self.passed = False
