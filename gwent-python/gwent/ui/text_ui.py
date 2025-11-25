from __future__ import annotations

import random
from typing import List, Dict, Optional

from gwent.cards import load_cards
from gwent.cards.base_card import Card, CardType, Ability, Row
from gwent.game.player import Player
from gwent.game.match import Match
from gwent.game.effects import activate_leader

# Numeric row shortcuts for quicker play input
ROW_INDEX_MAP = {
    "0": Row.MELEE,
    "1": Row.RANGED,
    "2": Row.SIEGE,
}


class TextUI:
    """Simple terminal UI for a Gwent Match.

    Commands:
      hand                Show current player's hand
      play <index> [row]  Play card at hand index; optional target row for Horn/agile
      pass                Pass the turn
      board               Show board rows and strengths
      graveyard           Show your graveyard
      leader              Activate leader ability (once)
      help                Show commands
      quit                Exit immediately
    """

    def __init__(self, match: Match, leaders: Dict[str, Card]):
        self.match = match
        self.leaders = leaders  # player_id -> leader card

    def _render_hand(self, player: Player) -> None:
        print(f"\n{player.id} Hand:")
        if not player.hand:
            print("  (empty)")
            return
        for i, c in enumerate(player.hand):
            abil = ",".join(a.value for a in c.abilities) or "-"
            print(f"  [{i}] {c.name} (P{c.power} {c.row.value} {abil})")

    def _render_board(self, perspective: Player) -> None:
        """Render each player; opponent rows shown far-to-near (siege,ranged,melee),
        perspective rows near-to-far (melee,ranged,siege)."""
        board = self.match.board
        you = perspective.id
        opp = board.get_opponent(you)
        print("\nBoard:")
        # Opponent
        print(f" Player {opp} total={board.total_strength(opp)}")
        for r in (Row.SIEGE, Row.RANGED, Row.MELEE):
            rs = board.rows[opp][r]
            mods = []
            if rs.weather_active:
                mods.append("weather")
            if rs.horn_active:
                mods.append("horn")
            mod_txt = f" ({','.join(mods)})" if mods else ""
            row_cards = " | ".join(f"{c.name}:{c.power}{'H' if c.is_hero else ''}" for c in rs.cards) or "(empty)"
            print(f"   {r.value:<6} [{board.row_strength(opp, r)}]{mod_txt}: {row_cards}")
        # You
        print(f" Player {you} total={board.total_strength(you)}")
        for idx, r in enumerate((Row.MELEE, Row.RANGED, Row.SIEGE)):
            rs = board.rows[you][r]
            mods = []
            if rs.weather_active:
                mods.append("weather")
            if rs.horn_active:
                mods.append("horn")
            mod_txt = f" ({','.join(mods)})" if mods else ""
            row_cards = " | ".join(f"{c.name}:{c.power}{'H' if c.is_hero else ''}" for c in rs.cards) or "(empty)"
            print(f"   [{idx}] {r.value:<6} [{board.row_strength(you, r)}]{mod_txt}: {row_cards}")

    def _render_status(self, player: Player) -> None:
        """Render combined status: board, active player's hand, row index legend."""
        self._render_board(player)
        self._render_hand(player)
        # Lives display (best-of-three)
        lives = getattr(self.match, 'lives', None)
        if lives:
            pids = [p.id for p in self.match.players]
            print("\nLives: " + " | ".join(f"{pid}:{lives.get(pid, 0)}" for pid in pids))
        print("\nRow Indices: 0=melee 1=ranged 2=siege")
        print("Play Syntax: play <hand_index> [row_label|row_index]")

    def _render_graveyard(self, player: Player) -> None:
        gy = self.match.board.get_graveyard(player.id)
        print(f"\nGraveyard {player.id} ({len(gy)} cards):")
        for c in gy:
            print(f"  {c.name} ({c.power})")

    def _activate_leader(self, player: Player) -> None:
        if player.leader_used:
            print("Leader already used.")
            return
        leader = self.leaders.get(player.id)
        if not leader:
            print("No leader assigned.")
            return
        applied = activate_leader(self.match.board, player.id, getattr(leader, 'leader_ability', ''))
        if applied:
            player.leader_used = True
            print(f"Leader ability activated: {leader.leader_ability}")
        else:
            print("Leader ability had no effect.")

    def run(self) -> None:
        print("\n=== Starting Gwent Match ===")
        self.match.start_round()
        while True:
            if self.match.match_winner():
                print(f"\nMatch winner: {self.match.match_winner().id}")
                break
            rnd = self.match.current_round
            if rnd.finished:
                print(f"\nRound {self.match.round_number} finished.")
                if self.match.match_winner():
                    continue
                print("Starting next round...")
                continue
            player = rnd.active_player
            # Always show current board + hand before input
            self._render_status(player)
            print(f"\nTurn: {player.id} (Total {self.match.board.total_strength(player.id)})")
            cmd = input("Command (help): ").strip().lower()
            if not cmd:
                continue
            if cmd == "quit":
                print("Exiting match.")
                break
            if cmd == "help":
                print("Commands: hand, play <index> [row], pass, board, graveyard, leader, quit")
                continue
            if cmd == "hand":
                self._render_hand(player)
                continue
            if cmd.startswith("play"):
                parts = cmd.split()
                if len(parts) < 2:
                    print("Usage: play <index> [row]")
                    continue
                try:
                    idx = int(parts[1])
                except ValueError:
                    print("Invalid index.")
                    continue
                if idx < 0 or idx >= len(player.hand):
                    print("Index out of range.")
                    continue
                card = player.hand[idx]
                target_row: Optional[Row] = None
                if len(parts) >= 3:
                    row_token = parts[2]
                    # Accept numeric index or text label
                    if row_token in ROW_INDEX_MAP:
                        target_row = ROW_INDEX_MAP[row_token]
                    else:
                        try:
                            target_row = Row.from_label(row_token)
                        except ValueError:
                            print("Invalid row label/index; ignoring.")
                            target_row = None
                target_unit: Optional[Card] = None
                if Ability.DECOY in card.abilities or Ability.MARDROEME in card.abilities:
                    targets: List[Card] = []
                    for r in (Row.MELEE, Row.RANGED, Row.SIEGE):
                        targets.extend(self.match.board.rows[player.id][r].cards)
                    if not targets:
                        print("No targets available on your board.")
                        continue
                    for i, t in enumerate(targets):
                        print(f"  [{i}] {t.name} (P{t.power})")
                    ti = input("Target index: ").strip()
                    try:
                        ti_int = int(ti)
                        target_unit = targets[ti_int]
                    except (ValueError, IndexError):
                        print("Invalid target.")
                        continue
                try:
                    self.match.play_card(player, card, target_row=target_row, target_unit=target_unit)
                except (ValueError, RuntimeError) as e:
                    print(f"Play error: {e}")
                continue
            if cmd == "pass":
                self.match.pass_turn(player)
                print(f"{player.id} passes.")
                continue
            if cmd == "board":
                self._render_board(player)
                continue
            if cmd == "graveyard":
                self._render_graveyard(player)
                continue
            if cmd == "leader":
                self._activate_leader(player)
                continue
            print("Unknown command. Type 'help'.")


def build_demo_players(card_pool: List[Card]) -> Match:
    """Create two players with small demo decks from the loaded card pool."""
    units = [c for c in card_pool if c.type == CardType.UNIT]
    specials = [c for c in card_pool if c.type == CardType.SPECIAL or c.type == CardType.WEATHER]
    leaders = [c for c in card_pool if c.type == CardType.LEADER]
    random.shuffle(units)
    random.shuffle(specials)
    p1_units = units[:10]
    p2_units = units[10:20]
    p1_specials = specials[:3]
    p2_specials = specials[3:6]
    p1_deck = p1_units + p1_specials
    p2_deck = p2_units + p2_specials
    p1 = Player(id="P1", deck=p1_deck[10:], hand=p1_deck[:10])
    p2 = Player(id="P2", deck=p2_deck[10:], hand=p2_deck[:10])
    match = Match([p1, p2])
    match.board.decks["P1"].extend(p1_deck)
    match.board.decks["P2"].extend(p2_deck)
    leader_map: Dict[str, Card] = {}
    if leaders:
        leader_map["P1"] = leaders[0]
        if len(leaders) > 1:
            leader_map["P2"] = leaders[1]
    return match, leader_map


def start_text_ui() -> None:
    cards = load_cards()
    # Offer setup menu to pick factions/leaders/decks
    match, leader_map = setup_match_via_menu(cards)
    ui = TextUI(match, leader_map)
    ui.run()


__all__ = ["TextUI", "start_text_ui"]

# ------------------------------
# Setup Menu Helpers
# ------------------------------

def setup_match_via_menu(card_pool: List[Card]):
    """Interactive pre-game setup for two players.

    Adds Manual mode: pick exactly 30 non-leader cards before playing.
    """
    print("\n=== Gwent Setup ===")
    # Partition cards
    all_units = [c for c in card_pool if c.type == CardType.UNIT]
    all_specials = [c for c in card_pool if c.type in (CardType.SPECIAL, CardType.WEATHER)]
    all_non_leader = [c for c in card_pool if c.type != CardType.LEADER]
    all_leaders = [c for c in card_pool if c.type == CardType.LEADER]

    # Available factions come from leaders to ensure a leader exists
    factions = sorted({c.faction for c in all_leaders})

    def prompt_choice(title: str, options: List[str]) -> int:
        while True:
            print(f"\n{title}")
            for i, opt in enumerate(options):
                print(f"  [{i}] {opt}")
            raw = input("Choose index: ").strip()
            try:
                idx = int(raw)
                if 0 <= idx < len(options):
                    return idx
            except ValueError:
                pass
            print("Invalid choice. Try again.")

    def select_leader_any(pid: str) -> Card:
        if not all_leaders:
            raise RuntimeError("No leaders available.")
        idx = prompt_choice(f"{pid} Leader", [f"{c.name} ({c.faction.value})" for c in all_leaders])
        return all_leaders[idx]

    def manual_pick_deck(pid: str, count: int = 30) -> List[Card]:
        pool = list(all_non_leader)
        # Stable, readable ordering: by type, then name, then power desc
        type_order = {CardType.UNIT: 0, CardType.SPECIAL: 1, CardType.WEATHER: 2}
        pool.sort(key=lambda c: (type_order.get(c.type, 9), c.name.lower(), -c.power))
        selected: List[Card] = []
        page = 0
        page_size = 20
        filter_text: Optional[str] = None

        def filtered() -> List[Card]:
            if not filter_text:
                return [c for c in pool if c not in selected]
            ft = filter_text.lower()
            return [c for c in pool if c not in selected and (ft in c.name.lower())]

        def confirm_selection() -> bool:
            print("\nSelected (30):")
            for i, c in enumerate(selected):
                print(f"  ({i+1}) {c.name}")
            while True:
                ans = input("Confirm deck? [y]es / [u]ndo last / [c]lear: ").strip().lower()
                if ans in ('y', 'yes'):  # lock in
                    return True
                if ans in ('u', 'undo'):
                    if selected:
                        rem = selected.pop()
                        print(f"Removed: {rem.name}")
                    return False
                if ans in ('c', 'clear'):
                    selected.clear()
                    return False
                print("Please answer y, u, or c.")

        while True:
            while len(selected) < count:
                remaining = filtered()
                total_pages = max(1, (len(remaining) + page_size - 1) // page_size)
                page = max(0, min(page, total_pages - 1))
                start = page * page_size
                end = start + page_size
                view = remaining[start:end]
                print(f"\n{pid} Manual Deck: {len(selected)}/{count} selected")
                if filter_text:
                    print(f" Filter: '{filter_text}'  (clear with 'f')")
                print(" Commands: indices e.g. 0,3  | n | p | s <text> | f | u | show | done")
                for i, c in enumerate(view):
                    tag = 'H' if getattr(c, 'hero', False) else ''
                    typ = 'U' if c.type == CardType.UNIT else ('S' if c.type == CardType.SPECIAL else 'W')
                    row = getattr(c, 'row', Row.ALL).value
                    print(f"  [{i}] {c.name} ({typ} {row} P{c.power}{tag})")
                raw = input("Pick: ").strip()
                if not raw:
                    continue
                if raw == 'n':
                    page = min(page + 1, total_pages - 1)
                    continue
                if raw == 'p':
                    page = max(page - 1, 0)
                    continue
                if raw.startswith('s '):
                    filter_text = raw[2:].strip() or None
                    page = 0
                    continue
                if raw == 'f':
                    filter_text = None
                    page = 0
                    continue
                if raw == 'u':
                    if selected:
                        removed = selected.pop()
                        print(f"Removed: {removed.name}")
                    continue
                if raw == 'show':
                    print(" Selected:")
                    for i, c in enumerate(selected):
                        print(f"  ({i+1}) {c.name}")
                    continue
                if raw == 'done':
                    if len(selected) < count:
                        print(f"Need {count - len(selected)} more to reach {count}.")
                        continue
                    # Already have count, skip directly to confirmation
                    break
                else:
                    # indices input
                    parts = [p for p in raw.replace(',', ' ').split() if p]
                    added_any = False
                    for p in parts:
                        try:
                            idx = int(p)
                            if 0 <= idx < len(view):
                                selected.append(view[idx])
                                added_any = True
                                if len(selected) >= count:
                                    break
                        except ValueError:
                            pass
                    if not added_any and parts:
                        print("No cards added. Use indices shown on the page.")
                # loop back; inner while will exit when len==count
            # Reached 30: confirm
            if confirm_selection():
                return selected
            # If not confirmed, continue loop to allow undo/clear and further picks

    players_cfg = []
    for pid in ("P1", "P2"):
        print(f"\n-- Configure {pid} --")
        mode = prompt_choice(
            "Deck build mode",
            [
                "Auto (faction-based quick build)",
                "Manual (pick any 30 cards)",
            ],
        )
        if mode == 1:
            # Manual mode: pick any 30 non-leader cards, then any leader
            leader = select_leader_any(pid)
            deck30 = manual_pick_deck(pid, 30)
            # Draw starting hand of 10 from chosen 30
            tmp = list(deck30)
            random.shuffle(tmp)
            hand = tmp[:10]
            rest_deck = tmp[10:]
            players_cfg.append((pid, hand, rest_deck, leader))
            continue

        # Auto (legacy) flow: faction -> leader -> deck counts
        f_idx = prompt_choice("Faction", [f.value for f in factions])
        faction = factions[f_idx]
        leaders = [c for c in all_leaders if c.faction == faction] or all_leaders[:]
        l_idx = prompt_choice("Leader", [c.name for c in leaders])
        leader = leaders[l_idx]

        def prompt_int(msg: str, default: int) -> int:
            raw = input(f"{msg} [{default}]: ").strip()
            if not raw:
                return default
            try:
                v = int(raw)
                return max(0, v)
            except ValueError:
                return default

        unit_count = prompt_int("Number of unit cards in deck", 22)
        special_count = prompt_int("Number of special/weather cards in deck", 8)
        units_pool = [c for c in all_units if c.faction == faction or c.faction.value == "neutral"]
        specials_pool = [c for c in all_specials if c.faction == faction or c.faction.value == "neutral"]
        random.shuffle(units_pool)
        random.shuffle(specials_pool)
        chosen_units = units_pool[: min(unit_count, len(units_pool))]
        chosen_specials = specials_pool[: min(special_count, len(specials_pool))]
        deck = chosen_units + chosen_specials
        random.shuffle(deck)
        hand = deck[: min(10, len(deck))]
        rest_deck = deck[len(hand) :]
        players_cfg.append((pid, hand, rest_deck, leader))

    # Create players and match
    p1 = Player(id=players_cfg[0][0], deck=players_cfg[0][2], hand=players_cfg[0][1])
    p2 = Player(id=players_cfg[1][0], deck=players_cfg[1][2], hand=players_cfg[1][1])
    match = Match([p1, p2])
    match.board.decks[p1.id].extend(players_cfg[0][1] + players_cfg[0][2])
    match.board.decks[p2.id].extend(players_cfg[1][1] + players_cfg[1][2])
    leader_map: Dict[str, Card] = {p1.id: players_cfg[0][3], p2.id: players_cfg[1][3]}
    print("\nSetup complete. Starting match...\n")
    return match, leader_map
