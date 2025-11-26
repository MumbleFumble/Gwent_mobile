from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional
import random

import pygame

from gwent.cards import load_cards
from gwent.cards.base_card import Card, Row
from gwent.game.match import Match
from gwent.ui.text_ui import setup_match_via_menu
from gwent.ai.hybrid_ai import HybridAI


WINDOW_SIZE = (1600, 900)
FPS = 60


@dataclass
class CardSprite:
    card: Card
    rect: pygame.Rect


class VisualUI:
    def __init__(self, match: Match, ai_player_id: Optional[str] = None):
        self.match = match
        self.ai_player_id = ai_player_id
        self.ai: Optional[HybridAI] = HybridAI(ai_player_id) if ai_player_id else None

        pygame.init()
        # Clamp window size so it doesn't exceed the current display
        display_info = pygame.display.Info()
        max_w = max(960, display_info.current_w - 100)
        max_h = max(540, display_info.current_h - 100)
        clamped_w = min(WINDOW_SIZE[0], max_w)
        clamped_h = min(WINDOW_SIZE[1], max_h)

        self.screen = pygame.display.set_mode((clamped_w, clamped_h))
        pygame.display.set_caption("Gwent (Visual UI)")
        self.clock = pygame.time.Clock()

        self.font_small = pygame.font.SysFont("arial", 16)
        self.font_medium = pygame.font.SysFont("arial", 20, bold=True)

        self.selected_from_hand: Optional[Card] = None
        self.info_card: Optional[Card] = None
        self.pending_row_choice: Optional[Tuple[Card, List[Row]]] = None
        self.pass_rect: Optional[pygame.Rect] = None
        self.hand_sprites: List[CardSprite] = []
        self.row_choice_buttons: List[Tuple[Row, pygame.Rect]] = []
        self.ai_wait_timer: float = 0.0

    # -----------------------
    # Drawing helpers
    # -----------------------
    def draw(self) -> None:
        self.screen.fill((40, 28, 18))  # tavern background
        board = self.match.board
        round_obj = self.match.current_round
        active_id = round_obj.active_player.id if round_obj else "?"

        # Main board area inset
        margin_x = 40
        margin_y = 40
        board_rect = pygame.Rect(
            margin_x,
            margin_y,
            self.screen.get_width() - 2 * margin_x,
            self.screen.get_height() - margin_y - 180,
        )

        # Outer board
        pygame.draw.rect(self.screen, (70, 50, 30), board_rect)
        pygame.draw.rect(self.screen, (140, 110, 60), board_rect, 3)

        # Divide board into 7 horizontal bands (3 opp rows, weather, 3 player rows)
        row_h = board_rect.height // 7

        # Weather/effects strip in the middle
        self._draw_weather_strip(board_rect, row_h)

        # Opponent rows (top): siege, ranged, melee
        opp_id = board.get_opponent("P1")
        self._draw_combat_rows(opp_id, board_rect, row_h, top=True)

        # Player rows (bottom): melee, ranged, siege
        self._draw_combat_rows("P1", board_rect, row_h, top=False)

        # Leaders and scores
        self._draw_leaders_and_scores(board_rect)

        # Status / round info
        self._draw_status_bar(active_id)

        # Player hand area (with potential for scrolling later)
        self._draw_hand("P1")

        # Optional card info overlay
        if self.info_card is not None:
            self._draw_card_info(self.info_card)

        # Row choice overlay if we're choosing for a multi-row card
        if self.pending_row_choice is not None:
            self._draw_row_choice()

        pygame.display.flip()

    def _draw_weather_strip(self, board_rect: pygame.Rect, row_h: int) -> None:
        # Central weather/effects band
        y = board_rect.y + 3 * row_h + 4
        h = row_h - 8
        rect = pygame.Rect(board_rect.x + 20, y, board_rect.width - 40, h)
        pygame.draw.rect(self.screen, (35, 45, 70), rect)
        pygame.draw.rect(self.screen, (140, 110, 60), rect, 2)

        # Show active weather summary
        weather = self.match.board.active_weather
        parts = []
        if weather.get(Row.MELEE):
            parts.append("Frost (Melee)")
        if weather.get(Row.RANGED):
            parts.append("Fog (Ranged)")
        if weather.get(Row.SIEGE):
            parts.append("Rain (Siege)")
        text = ", ".join(parts) if parts else "No active weather"
        surf = self.font_small.render(text, True, (230, 230, 230))
        tx = rect.x + (rect.width - surf.get_width()) // 2
        ty = rect.y + (rect.height - surf.get_height()) // 2
        self.screen.blit(surf, (tx, ty))

    def _draw_combat_rows(self, player_id: str, board_rect: pygame.Rect, row_h: int, top: bool) -> None:
        board = self.match.board
        rows_order = (Row.SIEGE, Row.RANGED, Row.MELEE) if top else (Row.MELEE, Row.RANGED, Row.SIEGE)

        # Total strength label per side
        total = board.total_strength(player_id)
        label = f"{player_id} total: {total}"
        label_surf = self.font_medium.render(label, True, (230, 230, 230))
        if top:
            lx = board_rect.x + (board_rect.width - label_surf.get_width()) // 2
            ly = board_rect.y - 30
        else:
            lx = board_rect.x + (board_rect.width - label_surf.get_width()) // 2
            ly = board_rect.bottom + 5
        self.screen.blit(label_surf, (lx, ly))

        start_index = 0 if top else 4
        for i, row in enumerate(rows_order):
            band_index = start_index + i
            band_y = board_rect.y + band_index * row_h

            # Row lane
            row_rect = pygame.Rect(
                board_rect.x + 80,
                band_y + 6,
                board_rect.width - 120,
                row_h - 12,
            )
            pygame.draw.rect(self.screen, (55, 40, 26), row_rect)
            pygame.draw.rect(self.screen, (140, 110, 60), row_rect, 1)

            rs = board.rows[player_id][row]

            # Effect slot on the left of the lane
            effect_rect = pygame.Rect(
                board_rect.x + 30,
                row_rect.y + (row_rect.height - 40) // 2,
                40,
                40,
            )
            pygame.draw.rect(self.screen, (90, 70, 40), effect_rect)
            pygame.draw.rect(self.screen, (140, 110, 60), effect_rect, 1)

            # Row label and strength
            strength = board.row_strength(player_id, row)
            row_label = f"{row.value}"
            txt = self.font_small.render(row_label, True, (230, 230, 210))
            self.screen.blit(txt, (effect_rect.x + 4, effect_rect.y + 4))

            str_surf = self.font_small.render(str(strength), True, (255, 245, 220))
            self.screen.blit(str_surf, (row_rect.right - str_surf.get_width() - 8, row_rect.y + 4))

            # Row effect icons in effect slot
            badge_y = effect_rect.y + effect_rect.height - 18
            badge_x = effect_rect.x + 4
            if rs.weather_active:
                weather_badge = self.font_small.render("W", True, (180, 220, 255))
                self.screen.blit(weather_badge, (badge_x, badge_y))
                badge_x += 14
            if rs.horn_active:
                horn_badge = self.font_small.render("x2", True, (255, 230, 180))
                self.screen.blit(horn_badge, (badge_x, badge_y))

            # Draw cards in row as boxes with power and name
            x = row_rect.x + 8
            card_w, card_h = 60, row_rect.height - 12
            for c in rs.cards:
                color = self._card_color(c)
                rect = pygame.Rect(x, row_rect.y + 6, card_w, card_h)
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, (0, 0, 0), rect, 1)
                # Power at top-left
                text = self.font_small.render(str(c.power), True, (0, 0, 0))
                self.screen.blit(text, (rect.x + 3, rect.y + 3))
                # Truncated name along the bottom
                name = c.name if len(c.name) <= 10 else c.name[:9] + "…"
                name_surf = self.font_small.render(name, True, (0, 0, 0))
                name_x = rect.x + max(2, (rect.width - name_surf.get_width()) // 2)
                name_y = rect.y + rect.height - 16
                self.screen.blit(name_surf, (name_x, name_y))
                x += card_w + 8

    def _draw_leaders_and_scores(self, board_rect: pygame.Rect) -> None:
        # Opponent leader and score
        opp = self.match.board.get_opponent("P1")
        p1 = "P1"
        opp_leader_rect = pygame.Rect(board_rect.x - 10, board_rect.y + board_rect.height // 8, 72, 72)
        p1_leader_rect = pygame.Rect(board_rect.x - 10, board_rect.y + board_rect.height * 5 // 8, 72, 72)

        def draw_leader_block(player_id: str, rect: pygame.Rect) -> None:
            pygame.draw.rect(self.screen, (50, 40, 30), rect)
            pygame.draw.rect(self.screen, (160, 130, 70), rect, 2)
            # Simple faction color stripe
            player = next(p for p in self.match.players if p.id == player_id)
            faction_color = (100, 100, 100)
            if hasattr(player, "leader") and player.leader is not None:
                faction_color = self._card_color(player.leader)
            stripe = pygame.Rect(rect.x + 4, rect.y + 4, rect.width - 8, 14)
            pygame.draw.rect(self.screen, faction_color, stripe)

            # Score / rounds next to leader
            score_rect = pygame.Rect(rect.right + 8, rect.y, 150, rect.height)
            pygame.draw.rect(self.screen, (30, 22, 16), score_rect)
            pygame.draw.rect(self.screen, (140, 110, 60), score_rect, 1)

            total = self.match.board.total_strength(player_id)
            lives = getattr(self.match, "lives", {}).get(player_id, 0)
            wins = getattr(self.match, "wins", {}).get(player_id, 0)

            line1 = self.font_small.render(f"{player_id} Score: {total}", True, (230, 220, 200))
            line2 = self.font_small.render(f"Wins: {wins}  Lives: {lives}", True, (210, 200, 180))
            self.screen.blit(line1, (score_rect.x + 6, score_rect.y + 8))
            self.screen.blit(line2, (score_rect.x + 6, score_rect.y + 8 + 20))

        draw_leader_block(opp, opp_leader_rect)
        draw_leader_block(p1, p1_leader_rect)

    def _draw_status_bar(self, active_id: str) -> None:
        # Bar with active player and round number along bottom of board
        y = self.screen.get_height() - 180 - 36
        rect = pygame.Rect(0, y, self.screen.get_width(), 36)
        pygame.draw.rect(self.screen, (25, 20, 18), rect)
        pygame.draw.rect(self.screen, (80, 60, 40), rect, 1)

        lives = getattr(self.match, "lives", {})
        wins = getattr(self.match, "wins", {})
        txt = f"Round {self.match.round_number} | Active: {active_id} | "
        txt += "  ".join(f"{pid} L={lives.get(pid, 0)} W={wins.get(pid, 0)}" for pid in lives)
        surf = self.font_medium.render(txt, True, (230, 230, 230))
        self.screen.blit(surf, (40, y + 6))

        # PASS button on the right
        self.pass_rect = pygame.Rect(self.screen.get_width() - 140, y + 4, 100, 28)
        pygame.draw.rect(self.screen, (120, 40, 40), self.pass_rect)
        ptxt = self.font_medium.render("PASS", True, (255, 255, 255))
        self.screen.blit(ptxt, (self.pass_rect.x + 18, self.pass_rect.y + 2))

    def _draw_hand(self, player_id: str) -> None:
        player = next(p for p in self.match.players if p.id == player_id)
        y = self.screen.get_height() - 160
        pygame.draw.rect(self.screen, (30, 22, 16), (0, y - 10, self.screen.get_width(), 170))
        label = self.font_medium.render(f"{player.id} Hand", True, (230, 230, 230))
        self.screen.blit(label, (40, y - 5))

        hand = list(player.hand)
        n = max(1, len(hand))
        max_width = self.screen.get_width() - 80
        card_width = 80
        gap = min(20, (max_width - card_width) // max(1, n - 1)) if n > 1 else 0
        start_x = 40

        self.hand_sprites = []
        for i, c in enumerate(hand):
            x = start_x + i * (card_width + gap)
            rect = pygame.Rect(x, y + 10, card_width, 120)
            self.hand_sprites.append(CardSprite(c, rect))
            color = self._card_color(c)
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, (0, 0, 0), rect, 2)

            if self.selected_from_hand is c:
                pygame.draw.rect(self.screen, (255, 215, 0), rect, 3)

            # Power and name
            pw = self.font_small.render(str(c.power), True, (0, 0, 0))
            self.screen.blit(pw, (rect.x + 3, rect.y + 3))
            name = c.name if len(c.name) <= 12 else c.name[:11] + "…"
            nm = self.font_small.render(name, True, (0, 0, 0))
            self.screen.blit(nm, (rect.x + 3, rect.y + rect.height - 18))

    def _card_color(self, c: Card) -> Tuple[int, int, int]:
        # Simple faction-based coloring
        f = c.faction.value
        if f == "northern_realms":
            return (70, 100, 180)
        if f == "nilfgaardian_empire":
            return (60, 60, 60)
        if f == "scoiatael":
            return (40, 130, 60)
        if f == "monsters":
            return (130, 40, 40)
        if f == "skellige":
            return (40, 100, 120)
        return (160, 160, 160)

    def _draw_card_info(self, card: Card) -> None:
        # Simple centered tooltip panel with card name, power, row, abilities, and description/quote
        panel_width = 480
        panel_height = 220
        x = (WINDOW_SIZE[0] - panel_width) // 2
        y = (WINDOW_SIZE[1] - panel_height) // 2

        # Background
        panel_rect = pygame.Rect(x, y, panel_width, panel_height)
        pygame.draw.rect(self.screen, (15, 15, 25), panel_rect)
        pygame.draw.rect(self.screen, (220, 220, 220), panel_rect, 2)

        lines: List[str] = []
        lines.append(f"{card.name} ({card.faction.value})")
        lines.append(f"Power: {card.power} | Row: {card.row.value}")
        if card.abilities:
            abil = ", ".join(a.value for a in card.abilities)
            lines.append(f"Abilities: {abil}")
        desc = (card.meta or {}).get("description") or (card.meta or {}).get("quote")
        if desc:
            lines.append("")
            # Basic manual wrapping
            words = desc.split()
            cur = ""
            for w in words:
                test = (cur + " " + w).strip()
                if len(test) > 60:
                    lines.append(cur)
                    cur = w
                else:
                    cur = test
            if cur:
                lines.append(cur)

        lines.append("")
        lines.append("Right-click anywhere to close")

        dy = y + 15
        for ln in lines:
            surf = self.font_small.render(ln, True, (230, 230, 230))
            self.screen.blit(surf, (x + 15, dy))
            dy += 22

    def _draw_row_choice(self) -> None:
        if self.pending_row_choice is None:
            return

        card, rows = self.pending_row_choice

        panel_width = 360
        panel_height = 180
        x = (WINDOW_SIZE[0] - panel_width) // 2
        y = (WINDOW_SIZE[1] - panel_height) // 2

        panel_rect = pygame.Rect(x, y, panel_width, panel_height)
        pygame.draw.rect(self.screen, (20, 20, 35), panel_rect)
        pygame.draw.rect(self.screen, (220, 220, 220), panel_rect, 2)

        title = self.font_medium.render("Choose row", True, (230, 230, 230))
        self.screen.blit(title, (x + 15, y + 10))

        subtitle = self.font_small.render(card.name, True, (230, 230, 230))
        self.screen.blit(subtitle, (x + 15, y + 40))

        # Simple vertical list of row buttons
        self.row_choice_buttons: List[Tuple[Row, pygame.Rect]] = []
        by = y + 70
        for r in rows:
            btn_rect = pygame.Rect(x + 30, by, panel_width - 60, 30)
            pygame.draw.rect(self.screen, (60, 60, 90), btn_rect)
            pygame.draw.rect(self.screen, (200, 200, 230), btn_rect, 1)
            label = self.font_small.render(r.value.capitalize(), True, (230, 230, 230))
            lx = btn_rect.x + (btn_rect.width - label.get_width()) // 2
            ly = btn_rect.y + (btn_rect.height - label.get_height()) // 2
            self.screen.blit(label, (lx, ly))
            self.row_choice_buttons.append((r, btn_rect))
            by += 40

    # -----------------------
    # Main loop
    # -----------------------
    def run(self) -> None:
        self.match.start_round()
        running = True
        while running:
            self.clock.tick(FPS)

            for event in pygame.event.get():
                # type: ignore[attr-defined] is for static checkers; pygame provides these at runtime
                if event.type == pygame.QUIT:  # type: ignore[attr-defined]
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:  # type: ignore[attr-defined]
                    if event.button == 1:
                        self._on_click(event.pos)
                    elif event.button == 3:
                        self._on_right_click(event.pos)

            # AI turn with small random delay between moves; once you pass,
            # the AI will continue taking turns until it also passes or round ends.
            rnd = self.match.current_round
            if self.ai and rnd and not rnd.finished and rnd.active_player.id == self.ai_player_id:
                if self.ai_wait_timer <= 0:
                    # Start a new wait in frames (1-5 seconds)
                    delay_seconds = random.uniform(1.0, 5.0)
                    self.ai_wait_timer = delay_seconds * FPS
                else:
                    self.ai_wait_timer -= 1
                    if self.ai_wait_timer <= 0:
                        action = self.ai.choose_action(self.match)
                        player = rnd.active_player
                        if action.kind == "pass":
                            self.match.pass_turn(player)
                        elif action.kind == "play" and action.card is not None:
                            # Let engine raise if something is invalid; we don't silently catch here
                            self.match.play_card(player, action.card, target_row=action.target_row, target_unit=action.target_unit)
                        # After an AI move, immediately prepare the next delay so it
                        # will keep going on its subsequent turns.
                        self.ai_wait_timer = 0

            if self.match.match_winner():
                # Simple end condition: pause briefly then exit
                self.draw()
                pygame.time.delay(1500)
                running = False
                continue

            self.draw()

        pygame.quit()  # type: ignore[attr-defined]

    def _on_click(self, pos: Tuple[int, int]) -> None:
        # If we're choosing a row for a card, clicks go to that handler
        if self.pending_row_choice is not None:
            self._handle_row_choice_click(pos)
            return
        # Clicking anywhere while info panel is open will close it first
        if self.info_card is not None:
            self.info_card = None
            return
        # PASS button
        if self.pass_rect and self.pass_rect.collidepoint(pos):
            rnd = self.match.current_round
            if rnd:
                player = rnd.active_player
                if player.id == "P1":
                    self.match.pass_turn(player)
            return

        # Hand cards
        for sprite in getattr(self, "hand_sprites", []):
            if sprite.rect.collidepoint(pos):
                # Select or play immediately / with row selection
                self.selected_from_hand = sprite.card
                rnd = self.match.current_round
                if rnd and rnd.active_player.id == "P1":
                    card = sprite.card
                    combat_rows = getattr(card, "combat_rows", None)
                    if combat_rows and card.row == Row.ALL:
                        # Multi-row unit: ask player to choose
                        rows = [r for r in combat_rows if r in (Row.MELEE, Row.RANGED, Row.SIEGE)]
                        if len(rows) == 1:
                            # Only one valid row, just play it
                            self.match.play_card(rnd.active_player, card, target_row=rows[0])
                            self.selected_from_hand = None
                        elif rows:
                            self.pending_row_choice = (card, rows)
                        else:
                            # Fallback: let engine decide
                            self.match.play_card(rnd.active_player, card, target_row=None)
                            self.selected_from_hand = None
                    else:
                        target_row = card.row if card.row in (Row.MELEE, Row.RANGED, Row.SIEGE) else None
                        self.match.play_card(rnd.active_player, card, target_row=target_row)
                        self.selected_from_hand = None
                return

    def _handle_row_choice_click(self, pos: Tuple[int, int]) -> None:
        if self.pending_row_choice is None:
            return
        card, _rows = self.pending_row_choice
        # If we somehow don't have buttons (e.g. first frame), just cancel
        for r, rect in self.row_choice_buttons:
            if rect.collidepoint(pos):
                rnd = self.match.current_round
                if rnd and rnd.active_player.id == "P1":
                    self.match.play_card(rnd.active_player, card, target_row=r)
                self.pending_row_choice = None
                self.selected_from_hand = None
                return
        # Clicked outside: cancel selection
        self.pending_row_choice = None
        self.selected_from_hand = None

    def _on_right_click(self, pos: Tuple[int, int]) -> None:
        # If an info panel is open, close it regardless of where we click
        if self.info_card is not None:
            self.info_card = None
            return

        # Right-click on a card in hand to open description panel
        for sprite in getattr(self, "hand_sprites", []):
            if sprite.rect.collidepoint(pos):
                self.info_card = sprite.card
                return


def start_visual_ui() -> None:
    cards = load_cards()
    # For first version, reuse text setup menu in console
    match, _leader_map = setup_match_via_menu(cards)

    # Simple choice: P1 human, P2 AI (can be extended later)
    ui = VisualUI(match, ai_player_id="P2")
    ui.run()


__all__ = ["start_visual_ui", "VisualUI"]

