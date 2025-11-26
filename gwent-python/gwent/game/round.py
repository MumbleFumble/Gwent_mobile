from __future__ import annotations

from typing import List, Optional

from gwent.game.board import Board
from gwent.game.player import Player
from gwent.cards.base_card import Card


class Round:
	"""Controls a single round: turn order, passing, scoring."""

	def __init__(self, players: List[Player], board: Board):
		self.players = players
		self.board = board
		self.turn_index = 0
		self.finished = False

	@property
	def active_player(self) -> Player:
		return self.players[self.turn_index]

	def next_player(self) -> None:
		# Do not advance turns if the round is already finished.
		if self.finished:
			return

		start_index = self.turn_index
		while True:
			self.turn_index = (self.turn_index + 1) % len(self.players)
			# If we've come full circle, let _check_auto_end decide about finishing.
			if self.turn_index == start_index:
				break
			candidate = self.players[self.turn_index]
			# Only stop on a player who has not passed and still has cards.
			if not candidate.passed and candidate.hand:
				break


	def play_card(self, player: Player, card: Card, target_row=None, target_unit: Optional[Card] = None) -> None:
		placed = player.play_from_hand(card)
		events = self.board.play_card(player.id, placed, target_row=target_row, target_unit=target_unit)
		# Spy: playing player draws 2
		if events.get("spy_played") is not None:
			player.draw(2)
		# Decoy: return selected unit to player's hand
		returned = events.get("decoy_returned")
		if returned is not None:
			player.add_to_hand(returned)
		self._check_auto_end()
		self.next_player()

	def pass_turn(self, player: Player) -> None:
		player.pass_round()
		self._check_auto_end()
		if not self.finished:
			self.next_player()

	def _check_auto_end(self) -> None:
		if all(p.passed or not p.hand for p in self.players):
			self.finished = True

	def winner(self) -> Optional[Player]:
		if not self.finished:
			return None
		scores = {p.id: self.board.total_strength(p.id) for p in self.players}
		ids = list(scores.keys())
		if scores[ids[0]] == scores[ids[1]]:
			return None
		return self.players[0] if scores[ids[0]] > scores[ids[1]] else self.players[1]
