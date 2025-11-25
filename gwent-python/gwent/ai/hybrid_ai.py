from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

from gwent.game.match import Match
from gwent.game.player import Player
from gwent.cards.base_card import Card, Row, Ability


@dataclass
class Action:
    kind: str  # "play" or "pass"
    card: Optional[Card] = None
    target_row: Optional[Row] = None
    target_unit: Optional[Card] = None


class HybridAI:
    """Medium-strength AI: rule-guided candidate set + shallow evaluation.

    This does a 1-ply lookahead over a filtered set of actions
    and uses a heuristic evaluation of the resulting state.
    """

    def __init__(self, player_id: str):
        self.player_id = player_id

    # ------------------------
    # Public API
    # ------------------------
    def choose_action(self, match: Match) -> Action:
        rnd = match.current_round
        if not rnd:
            raise RuntimeError("No active round for AI")
        player = next(p for p in match.players if p.id == self.player_id)

        # Generate and filter candidate actions
        candidates = self._generate_candidate_actions(match, player)
        if not candidates:
            return Action("pass")

        # Always consider passing as an option
        candidates.append(Action("pass"))

        # Simple rule: if clearly ahead and no strong reason to keep playing, pass
        if self._should_consider_immediate_pass(match, player):
            return Action("pass")

        # Evaluate each candidate with a 1-ply simulation
        best_score = float("-inf")
        best_action = candidates[0]
        for action in candidates:
            score = self._evaluate_after_action(match, player, action)
            if score > best_score:
                best_score = score
                best_action = action
        return best_action

    # ------------------------
    # Candidate generation
    # ------------------------
    def _generate_candidate_actions(self, match: Match, player: Player) -> List[Action]:
        actions: List[Action] = []
        hand = list(player.hand)
        if not hand:
            return actions

        # Always include special cards and a few representative units (low/mid/high)
        specials: List[Card] = []
        units: List[Card] = []
        for c in hand:
            if any(a in c.abilities for a in (Ability.SPY, Ability.SCORCH, Ability.MEDIC, Ability.HORN, Ability.WEATHER, Ability.DECOY)):
                specials.append(c)
            else:
                units.append(c)

        units_sorted = sorted(units, key=lambda c: c.power)
        unit_reprs: List[Card] = []
        if units_sorted:
            unit_reprs.append(units_sorted[0])
            if len(units_sorted) > 2:
                unit_reprs.append(units_sorted[len(units_sorted) // 2])
            if len(units_sorted) > 1:
                unit_reprs.append(units_sorted[-1])

        considered: List[Card] = []
        considered.extend(specials)
        for u in unit_reprs:
            if u not in considered:
                considered.append(u)

        for card in considered:
            if card in player.hand:
                actions.extend(self._card_actions(match, player, card))

        return actions

    def _card_actions(self, match: Match, player: Player, card: Card) -> List[Action]:
        actions: List[Action] = []

        # Decoy / Mardroeme require a target unit; pick the highest-power valid unit
        if Ability.DECOY in card.abilities or Ability.MARDROEME in card.abilities:
            targets: List[Card] = []
            for r in (Row.MELEE, Row.RANGED, Row.SIEGE):
                targets.extend(match.board.rows[player.id][r].cards)
            if not targets:
                return actions
            target = max(targets, key=lambda c: c.power)
            actions.append(Action("play", card=card, target_unit=target))
            return actions

        # Spy should target opponent's side; board logic handles placement
        if Ability.SPY in card.abilities:
            actions.append(Action("play", card=card))
            return actions

        # Weather and Scorch don't need row targeting from AI
        if Ability.WEATHER in card.abilities or (Ability.SCORCH in card.abilities and not card.is_unit):
            actions.append(Action("play", card=card))
            return actions

        # Horn: pick best row by previewing strength gain
        if Ability.HORN in card.abilities and not card.is_unit:
            best_row = None
            best_gain = 0
            for r in (Row.MELEE, Row.RANGED, Row.SIEGE):
                before = match.board.row_strength(player.id, r)
                # Simple approximation: horn doubles non-hero units on row
                row_state = match.board.rows[player.id][r]
                non_hero = [c for c in row_state.cards if not c.is_hero]
                gain = sum(c.power for c in non_hero)
                if gain > best_gain:
                    best_gain = gain
                    best_row = r
            if best_row is not None and best_gain > 0:
                actions.append(Action("play", card=card, target_row=best_row))
            return actions

        # Units (including Agile units): choose the row that maximizes immediate strength
        rows_to_try: List[Row] = []
        if getattr(card, "combat_rows", None):
            for r in card.combat_rows:
                if r in (Row.MELEE, Row.RANGED, Row.SIEGE):
                    rows_to_try.append(r)
        else:
            rows_to_try.append(card.row)

        best_row = None
        best_score = float("-inf")
        for r in rows_to_try:
            before = match.board.row_strength(player.id, r)
            # approximate additional strength
            approx = before + card.power
            if approx > best_score:
                best_score = approx
                best_row = r

        actions.append(Action("play", card=card, target_row=best_row))
        return actions

    # ------------------------
    # Heuristics
    # ------------------------
    def _should_consider_immediate_pass(self, match: Match, player: Player) -> bool:
        board = match.board
        my = board.total_strength(player.id)
        opp_id = board.get_opponent(player.id)
        opp = board.total_strength(opp_id)
        lead = my - opp

        # Only think about auto-pass if we are leading by a safe margin
        SAFE_LEAD = 10
        if lead < SAFE_LEAD:
            return False

        # Don't pass if we're already behind in lives in a decisive round
        my_lives = match.lives.get(player.id, 0)
        opp_lives = match.lives.get(opp_id, 0)
        if my_lives < opp_lives and match.round_number >= 2:
            return False

        return True

    def _evaluate_after_action(self, match: Match, player: Player, action: Action) -> float:
        """Quick heuristic based on board and resources after one move.

        For now we approximate by applying the action conceptually:
        - If action is play: assume card's nominal value is realized.
        - If pass: rely on current board state and card advantage.
        """
        board = match.board
        me = player.id
        opp = board.get_opponent(me)

        # Base metrics
        my_score = board.total_strength(me)
        opp_score = board.total_strength(opp)
        score_diff = my_score - opp_score

        # Card advantage (hand + remaining deck)
        my_cards = len(player.hand) + len(board.decks.get(me, []))
        opp_player = next(p for p in match.players if p.id == opp)
        opp_cards = len(opp_player.hand) + len(board.decks.get(opp, []))
        card_advantage = my_cards - opp_cards

        # Life / round context
        life_adv = match.lives.get(me, 0) - match.lives.get(opp, 0)
        round_bonus = 0
        my_wins = match.wins.get(me, 0)
        opp_wins = match.wins.get(opp, 0)
        if my_wins > opp_wins:
            round_bonus = 3
        elif my_wins < opp_wins:
            round_bonus = -3

        # Rough ability value of card we are about to play
        ability_bonus = 0
        if action.kind == "play" and action.card is not None:
            c = action.card
            if Ability.SPY in c.abilities:
                ability_bonus += 8
            if Ability.SCORCH in c.abilities:
                ability_bonus += 6
            if Ability.MEDIC in c.abilities:
                ability_bonus += 5
            if Ability.HORN in c.abilities:
                ability_bonus += 4
            if Ability.WEATHER in c.abilities:
                ability_bonus += 3

        # Weights tuned loosely for "medium" play
        return (
            1.0 * score_diff
            + 0.7 * card_advantage
            + 1.5 * life_adv
            + 1.0 * round_bonus
            + 0.5 * ability_bonus
        )
