from __future__ import annotations

from typing import List, Optional

from gwent.game.round import Round
from gwent.game.board import Board
from gwent.game.player import Player


class Match:
	"""Best-of-three style match controller (first to two round wins)."""

	def __init__(self, players: List[Player]):
		self.players = players
		self.board = Board([p.id for p in players])
		self.round_number = 0
		self.wins = {p.id: 0 for p in players}
		self.current_round: Optional[Round] = None

	def start_round(self) -> None:
		for p in self.players:
			p.reset_for_new_round()
		self.board.active_weather = {r: False for r in self.board.active_weather}
		self.board._sync_weather_flags()
		self.round_number += 1
		self.current_round = Round(self.players, self.board)

	def play_card(self, player: Player, card) -> None:
		if not self.current_round:
			raise RuntimeError("No active round")
		self.current_round.play_card(player, card)
		self._check_round_end()

	def pass_turn(self, player: Player) -> None:
		if not self.current_round:
			raise RuntimeError("No active round")
		self.current_round.pass_turn(player)
		self._check_round_end()

	def _check_round_end(self) -> None:
		if self.current_round and self.current_round.finished:
			winner = self.current_round.winner()
			if winner:
				self.wins[winner.id] += 1
			if any(w >= 2 for w in self.wins.values()) or self.round_number >= 3:
				return
			self.start_round()

	def match_winner(self) -> Optional[Player]:
		for p in self.players:
			if self.wins[p.id] >= 2:
				return p
		return None
