from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import random

import pygame

from gwent.cards import load_cards
from gwent.cards.base_card import Card, CardType, Row
from gwent.game.match import Match
from gwent.game.player import Player
from gwent.ai.hybrid_ai import HybridAI


WINDOW_SIZE = (1600, 900)
FPS = 60


# ---------------------------------
# Palette & subtle style constants
# ---------------------------------
WOOD_DARK = (24, 17, 10)
WOOD_MID = (46, 32, 20)
WOOD_LIGHT = (73, 51, 32)

BRONZE_DARK = (80, 55, 30)
BRONZE_MID = (134, 96, 52)
BRONZE_LIGHT = (196, 160, 96)

PARCHMENT_LIGHT = (214, 199, 167)
PARCHMENT_MID = (191, 173, 138)

GLOW_GOLD = (255, 222, 140)
TURN_GLOW = (220, 200, 120)


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

        # Mulligan state (redraw up to 2 cards before first round)
        self.phase: str = "mulligan"  # "mulligan" or "play"
        self.mulligan_discards: int = 0
        self.mulligan_max_discards: int = 2
        self.mulligan_confirm_rect: Optional[pygame.Rect] = None
        # For hit-testing discard icons during mulligan: map card id to rect
        self.mulligan_discard_buttons: List[Tuple[Card, pygame.Rect]] = []
        self.hovered_hand_index: Optional[int] = None

        # Drag-and-drop state for cards in hand
        self.dragging_card: Optional[Card] = None
        self.drag_offset: Tuple[int, int] = (0, 0)
        self.drag_rect: Optional[pygame.Rect] = None

        # Cached lane rects for hit-testing drops: (player_id, row) -> Rect
        self.row_lane_rects: Dict[Tuple[str, Row], pygame.Rect] = {}
        # Cached rects of cards currently rendered on the board rows so we
        # can show info on right-click even after they are played
        self.board_card_rects: List[Tuple[Card, pygame.Rect]] = []
        # Deck UI / animation state
        self.deck_hover: bool = False
        self.deck_pile_rect: Optional[pygame.Rect] = None
        self.deck_draw_progress: float = 0.0
        self.deck_draw_card: Optional[Card] = None
        self.deck_draw_from: Optional[Tuple[int, int]] = None
        self.deck_draw_to: Optional[Tuple[int, int]] = None
        # Graveyard UI / animation state
        self.grave_hover: bool = False
        self.grave_pile_rect: Optional[pygame.Rect] = None
        self.grave_anim_progress: float = 0.0
        self.grave_anim_card: Optional[Card] = None
        self.grave_anim_from: Optional[Tuple[int, int]] = None
        self.grave_anim_to: Optional[Tuple[int, int]] = None

    # -----------------------
    # Drawing helpers
    # -----------------------
    def draw(self) -> None:
        # Layered wood background with subtle vignette
        full_rect = self.screen.get_rect()
        for i in range(full_rect.height):
            t = i / max(1, full_rect.height - 1)
            r = int(WOOD_MID[0] + (WOOD_LIGHT[0] - WOOD_MID[0]) * t)
            g = int(WOOD_MID[1] + (WOOD_LIGHT[1] - WOOD_MID[1]) * t)
            b = int(WOOD_MID[2] + (WOOD_LIGHT[2] - WOOD_MID[2]) * t)
            pygame.draw.line(self.screen, (r, g, b), (0, i), (full_rect.width, i))

        # Simple vignette: darken edges slightly
        vignette = pygame.Surface(full_rect.size, pygame.SRCALPHA)  # type: ignore[attr-defined]
        for i in range(10):
            alpha = int(10 + i * 5)
            pygame.draw.rect(
                vignette,
                (0, 0, 0, alpha),
                full_rect.inflate(-i * 24, -i * 24),
                width=4,
            )
        self.screen.blit(vignette, (0, 0))
        board = self.match.board
        round_obj = self.match.current_round
        active_id = round_obj.active_player.id if round_obj else "?"

        # Main tavern table inset (center, leaving side panels)
        margin_x = 260  # leave room on left for portraits / scores
        margin_y = 40
        board_rect = pygame.Rect(
            margin_x,
            margin_y,
            self.screen.get_width() - 2 * margin_x,
            self.screen.get_height() - margin_y - 180,
        )

        # Outer board slab with bronze frame and recessed interior
        pygame.draw.rect(self.screen, WOOD_MID, board_rect)
        pygame.draw.rect(self.screen, BRONZE_DARK, board_rect, 6)
        pygame.draw.rect(self.screen, BRONZE_MID, board_rect.inflate(-6, -6), 4)
        inner = board_rect.inflate(-18, -18)
        pygame.draw.rect(self.screen, WOOD_DARK, inner)
        pygame.draw.rect(self.screen, BRONZE_LIGHT, inner, 1)

        # Divide board into 7 horizontal bands (3 opp rows, thin weather, 3 player rows)
        row_h = int(board_rect.height // 7 * 0.95)

        # Clear per-frame board card hit-test cache
        self.board_card_rects = []

        # Weather/effects strip in the middle (very slim)
        self._draw_weather_strip(board_rect, row_h)

        # Opponent rows (top): siege, ranged, melee
        opp_id = board.get_opponent("P1")
        self._draw_combat_rows(opp_id, board_rect, row_h, top=True)

        # Player rows (bottom): melee, ranged, siege
        self._draw_combat_rows("P1", board_rect, row_h, top=False)

        # Left and right side panels (portraits / extra slots)
        self._draw_side_panels(board_rect)

        # Leaders and scores overlaid near left portraits
        self._draw_leaders_and_scores(board_rect)

        # PASS button and simple status anchored near bottom-right of board
        self._draw_status_bar(active_id, board_rect)

        # Player hand / mulligan (now sits directly under board)
        if self.phase == "mulligan":
            self._draw_mulligan_hand("P1")
        else:
            self._draw_hand("P1")

        # Deck draw animation overlay (card sliding into hand)
        if self.deck_draw_card is not None and self.deck_draw_from and self.deck_draw_to:
            t = max(0.0, min(1.0, self.deck_draw_progress))
            sx, sy = self.deck_draw_from
            ex, ey = self.deck_draw_to
            cx = int(sx + (ex - sx) * t)
            cy = int(sy + (ey - sy) * t)
            w, h = 80, 110
            surf = self._render_card_surface(self.deck_draw_card, (w, h))
            rect = surf.get_rect(center=(cx, cy))
            # Slight shadow under flying card
            shadow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect().inflate(8, 18))
            self.screen.blit(shadow, (rect.x, rect.y + rect.height // 2))
            self.screen.blit(surf, rect.topleft)

        # Graveyard discard animation overlay (card sliding into graveyard pile)
        if self.grave_anim_card is not None and self.grave_anim_from and self.grave_anim_to:
            t = max(0.0, min(1.0, self.grave_anim_progress))
            sx, sy = self.grave_anim_from
            ex, ey = self.grave_anim_to
            cx = int(sx + (ex - sx) * t)
            cy = int(sy + (ey - sy) * t)
            w, h = 72, 102
            surf = self._render_card_back_surface((w, h), muted=True)
            rect = surf.get_rect(center=(cx, cy))
            shadow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, 120), shadow.get_rect().inflate(10, 22))
            self.screen.blit(shadow, (rect.x, rect.y + rect.height // 2))
            self.screen.blit(surf, rect.topleft)

        # Optional card info overlay
        if self.info_card is not None:
            self._draw_card_info(self.info_card)

        # Row choice overlay if we're choosing for a multi-row card
        if self.pending_row_choice is not None:
            self._draw_row_choice()

        pygame.display.flip()

    def _draw_weather_strip(self, board_rect: pygame.Rect, row_h: int) -> None:
        # Dark, foggy banner strip between rows
        y = board_rect.y + 3 * row_h + row_h // 2 - row_h // 4
        h = row_h // 2
        rect = pygame.Rect(board_rect.x + 32, y, board_rect.width - 64, h)

        banner = pygame.Surface(rect.size, pygame.SRCALPHA)  # type: ignore[attr-defined]
        for i in range(rect.height):
            t = i / max(1, rect.height - 1)
            col = (18 + int(30 * t), 20 + int(35 * t), 30 + int(40 * t))
            pygame.draw.line(banner, col, (0, i), (rect.width, i))

        # Swirling mist / rain lines
        for i in range(6):
            line_y = int((i + 1) * rect.height / 8)
            color = (140, 150, 170, 38)
            pygame.draw.line(banner, color, (10, line_y), (rect.width - 10, line_y))

        pygame.draw.rect(banner, BRONZE_DARK + (200,), banner.get_rect(), 3)  # type: ignore[operator]
        pygame.draw.rect(banner, BRONZE_LIGHT + (180,), banner.get_rect().inflate(-6, -6), 1)  # type: ignore[operator]
        self.screen.blit(banner, rect.topleft)

        # Active weather summary text with faint glow
        weather = self.match.board.active_weather
        parts = []
        if weather.get(Row.MELEE):
            parts.append("Biting Frost")
        if weather.get(Row.RANGED):
            parts.append("Impenetrable Fog")
        if weather.get(Row.SIEGE):
            parts.append("Torrential Rain")
        text = ", ".join(parts) if parts else "No active weather"

        text_surf = self.font_medium.render(text, True, (225, 235, 245))
        glow_surf = self.font_medium.render(text, True, (160, 190, 230))
        tx = rect.x + (rect.width - text_surf.get_width()) // 2
        ty = rect.y + (rect.height - text_surf.get_height()) // 2
        self.screen.blit(glow_surf, (tx, ty + 1))
        self.screen.blit(text_surf, (tx, ty))

    def _draw_combat_rows(self, player_id: str, board_rect: pygame.Rect, row_h: int, top: bool) -> None:
        board = self.match.board
        rows_order = (Row.SIEGE, Row.RANGED, Row.MELEE) if top else (Row.MELEE, Row.RANGED, Row.SIEGE)

        start_index = 0 if top else 4
        for i, row in enumerate(rows_order):
            band_index = start_index + i
            band_y = board_rect.y + band_index * row_h

            # Row lane – recessed wooden trough, with a bit more breathing room
            row_rect = pygame.Rect(
                board_rect.x + 90,
                band_y + 8,
                board_rect.width - 140,
                row_h - 16,
            )
            pygame.draw.rect(self.screen, WOOD_MID, row_rect)
            inner_row = row_rect.inflate(-8, -8)
            pygame.draw.rect(self.screen, WOOD_DARK, inner_row)
            pygame.draw.rect(self.screen, BRONZE_DARK, row_rect, 4)
            pygame.draw.rect(self.screen, BRONZE_LIGHT, inner_row, 1)

            # Cache lane rect for drag-and-drop hit testing (only for P1 side)
            if not top:
                self.row_lane_rects[(player_id, row)] = row_rect.copy()

            rs = board.rows[player_id][row]

            # Effect / row icon slot on the left of the lane
            effect_rect = pygame.Rect(
                board_rect.x + 30,
                row_rect.y + (row_rect.height - 52) // 2,
                44,
                52,
            )
            pygame.draw.rect(self.screen, WOOD_DARK, effect_rect)
            inner_eff = effect_rect.inflate(-6, -6)
            pygame.draw.rect(self.screen, BRONZE_MID, effect_rect, 3)
            pygame.draw.rect(self.screen, BRONZE_LIGHT, inner_eff, 1)

            # Row icon watermark instead of text label
            icon = "⚔"
            if row == Row.RANGED:
                icon = "🏹"
            elif row == Row.SIEGE:
                icon = "⛨"
            icon_surf = self.font_medium.render(icon, True, (240, 230, 215))
            ix = effect_rect.x + (effect_rect.width - icon_surf.get_width()) // 2
            iy = effect_rect.y + (effect_rect.height - icon_surf.get_height()) // 2
            self.screen.blit(icon_surf, (ix, iy))

            # Row strength in a bronze medallion on the far left
            strength = board.row_strength(player_id, row)
            badge_r = 20
            badge_center = (board_rect.x - 16, row_rect.y + row_rect.height // 2)
            med = pygame.Surface((badge_r * 2, badge_r * 2), pygame.SRCALPHA)  # type: ignore[attr-defined]
            center = (badge_r, badge_r)
            pygame.draw.circle(med, BRONZE_MID + (255,), center, badge_r)
            pygame.draw.circle(med, BRONZE_LIGHT + (255,), center, badge_r - 3)
            pygame.draw.circle(med, BRONZE_DARK + (255,), center, badge_r, 2)
            str_surf = self.font_small.render(str(strength), True, (15, 8, 0))
            med.blit(
                str_surf,
                (center[0] - str_surf.get_width() // 2, center[1] - str_surf.get_height() // 2),
            )
            self.screen.blit(med, (badge_center[0] - badge_r, badge_center[1] - badge_r))

            # Row effect runes in effect slot
            badge_y = effect_rect.y + effect_rect.height - 18
            badge_x = effect_rect.x + 6
            if rs.weather_active:
                weather_badge = self.font_small.render("☁", True, (190, 220, 255))
                self.screen.blit(weather_badge, (badge_x, badge_y))
                badge_x += 16
            if rs.horn_active:
                horn_badge = self.font_small.render("❖", True, (255, 235, 190))
                self.screen.blit(horn_badge, (badge_x, badge_y))

            # Draw cards in row as boxes with power and name
            # Draw row cards using shared card renderer, slightly overlapped
            cards_in_row = list(rs.cards)
            if cards_in_row:
                base_w = 70
                base_h = row_rect.height - 14
                overlap = 22
                total_w = base_w + overlap * (len(cards_in_row) - 1)
                start_x = row_rect.x + (row_rect.width - total_w) // 2
                y = row_rect.y + 7
                for idx, c in enumerate(cards_in_row):
                    cx = start_x + idx * overlap
                    rect = pygame.Rect(cx, y, base_w, base_h)
                    surf = self._render_card_surface(c, (base_w, base_h))
                    self.screen.blit(surf, rect.topleft)
                    # Remember this rect for right-click info lookup
                    self.board_card_rects.append((c, rect))

    def _draw_side_panels(self, board_rect: pygame.Rect) -> None:
        """Draw carved portrait panels on the left and deck/graveyard shelves on the right.

        Right stacks show P2 (top) and P1 (bottom) deck/graveyard
        separately, mirroring the board layout.
        """
        screen_h = self.screen.get_height()

        # Left vertical carved wood panel. Height chosen so bottom leader panel
        # sits above the hand tray instead of being covered by it.
        left_rect = pygame.Rect(20, 20, board_rect.x - 40, screen_h - 220)
        pygame.draw.rect(self.screen, WOOD_MID, left_rect)
        pygame.draw.rect(self.screen, BRONZE_DARK, left_rect, 4)
        pygame.draw.rect(self.screen, BRONZE_LIGHT, left_rect.inflate(-6, -6), 1)

        # Top and bottom frames for the leader panels (P2 and P1) so they
        # share the same outer carved box. Both use the same 26px vertical
        # inset from the top/bottom of the carved column for symmetry.
        frame_h = 130
        opp_frame = pygame.Rect(left_rect.x + 24, left_rect.y + 26, left_rect.width - 48, frame_h)
        # Drop the bottom frame so it hugs the dark backing box
        p1_frame_top = left_rect.bottom - frame_h - 46
        p1_frame = pygame.Rect(left_rect.x + 24, p1_frame_top, left_rect.width - 48, frame_h)
        for frame in (opp_frame, p1_frame):
            pygame.draw.rect(self.screen, WOOD_DARK, frame)
            pygame.draw.rect(self.screen, BRONZE_MID, frame, 4)
            pygame.draw.rect(self.screen, BRONZE_LIGHT, frame.inflate(-6, -6), 1)

        # Right vertical panel for deck / graveyard stacked slots (covers both players)
        right_rect = pygame.Rect(board_rect.right + 20, 20, self.screen.get_width() - board_rect.right - 40, screen_h - 40)
        pygame.draw.rect(self.screen, WOOD_MID, right_rect)
        pygame.draw.rect(self.screen, BRONZE_DARK, right_rect, 4)
        pygame.draw.rect(self.screen, BRONZE_LIGHT, right_rect.inflate(-6, -6), 1)
        # Shared geometry
        slot_w = right_rect.width - 48
        slot_h = 110
        mouse_pos = pygame.mouse.get_pos()

        def draw_deck_and_grave_for(player_id: str, top_side: bool) -> None:
            """Draw a deck + graveyard pair for the given player.

            top_side=True → P2 (top of board), False → P1 (bottom).
            """
            # Vertical anchor: tuck near that player's rows
            if top_side:
                base_y = right_rect.y + 28
            else:
                # Anchor P1 stacks even higher so they clear the hand tray.
                base_y = right_rect.bottom - (slot_h * 2 + 190)

            # Deck slot (closer to the board edge), then graveyard beneath
            deck_slot = pygame.Rect(right_rect.x + 24, base_y, slot_w, slot_h)
            pygame.draw.rect(self.screen, WOOD_DARK, deck_slot)
            deck_inner = deck_slot.inflate(-8, -8)
            pygame.draw.rect(self.screen, BRONZE_MID, deck_slot, 3)
            pygame.draw.rect(self.screen, BRONZE_LIGHT, deck_inner, 1)

            # For P1, also expose hover rect / state so we can animate draws
            if not top_side:
                self.deck_pile_rect = deck_inner.copy()
                self.deck_hover = self.deck_pile_rect.collidepoint(mouse_pos)

            # Deck stack
            player = next(p for p in self.match.players if p.id == player_id)
            remaining = len(getattr(player, "deck", []) or [])
            stack_layers = min(5, max(1, remaining // 3 + 1)) if remaining > 0 else 1

            base_w = 56
            base_h = 84
            center_x = deck_inner.centerx
            base_y = deck_inner.y + 10

            for i in range(stack_layers):
                offset_x = -8 + i * 4
                offset_y = i * 4
                rect = pygame.Rect(0, 0, base_w, base_h)
                rect.centerx = center_x + offset_x
                rect.y = base_y + offset_y

                back_surf = self._render_card_back_surface((rect.width, rect.height))
                # Hover glow only for the active human player's deck
                if not top_side and self.deck_hover:
                    glow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    glow.fill(TURN_GLOW + (45,))  # type: ignore[operator]
                    back_surf.blit(glow, (0, 0))
                self.screen.blit(back_surf, rect.topleft)

            # Deck counter badge
            badge_r = 16
            badge_center = (deck_inner.right - badge_r - 4, deck_inner.top + badge_r + 2)
            med = pygame.Surface((badge_r * 2, badge_r * 2), pygame.SRCALPHA)
            center = (badge_r, badge_r)
            pygame.draw.circle(med, (155, 120, 70, 255), center, badge_r)
            pygame.draw.circle(med, (210, 180, 110, 255), center, badge_r - 3)
            pygame.draw.circle(med, (70, 50, 30, 255), center, badge_r, 2)
            num_txt = self.font_small.render(str(remaining), True, (20, 10, 0))
            med.blit(num_txt, (center[0] - num_txt.get_width() // 2, center[1] - num_txt.get_height() // 2))
            self.screen.blit(med, (badge_center[0] - badge_r, badge_center[1] - badge_r))

            # Graveyard slot just below deck
            grave_y = deck_slot.bottom + 12
            grave_slot = pygame.Rect(right_rect.x + 24, grave_y, slot_w, slot_h)
            pygame.draw.rect(self.screen, WOOD_DARK, grave_slot)
            grave_inner = grave_slot.inflate(-8, -8)
            pygame.draw.rect(self.screen, BRONZE_MID, grave_slot, 3)
            pygame.draw.rect(self.screen, BRONZE_LIGHT, grave_inner, 1)

            # For P1, track hover / rect for tooltip + animation target
            if not top_side:
                self.grave_pile_rect = grave_inner.copy()
                self.grave_hover = self.grave_pile_rect.collidepoint(mouse_pos)

            board = self.match.board
            grave_cards = getattr(board, "graveyards", {}).get(player_id, [])
            grave_count = len(grave_cards)

            grave_layers = min(6, max(1, grave_count // 2 + 1)) if grave_count > 0 else 1
            g_base_w = 56
            g_base_h = 84
            g_center_x = grave_inner.centerx
            g_base_y = grave_inner.y + 12

            for i in range(grave_layers):
                offset_x = -10 + (i * 5 if i % 2 == 0 else -i * 3)
                offset_y = i * 5
                rect = pygame.Rect(0, 0, g_base_w, g_base_h)
                rect.centerx = g_center_x + offset_x
                rect.y = g_base_y + offset_y

                back_surf = self._render_card_back_surface((rect.width, rect.height), muted=True)
                if not top_side and self.grave_hover:
                    glow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    glow.fill((220, 210, 160, 35))
                    back_surf.blit(glow, (0, 0))
                self.screen.blit(back_surf, rect.topleft)

            # Graveyard counter
            g_badge_r = 16
            g_badge_center = (grave_inner.right - g_badge_r - 4, grave_inner.top + g_badge_r + 2)
            g_med = pygame.Surface((g_badge_r * 2, g_badge_r * 2), pygame.SRCALPHA)
            g_center = (g_badge_r, g_badge_r)
            pygame.draw.circle(g_med, (115, 95, 70, 255), g_center, g_badge_r)
            pygame.draw.circle(g_med, (170, 145, 105, 255), g_center, g_badge_r - 3)
            pygame.draw.circle(g_med, (40, 30, 20, 255), g_center, g_badge_r, 2)
            g_num = self.font_small.render(str(grave_count), True, (15, 8, 0))
            g_med.blit(g_num, (g_center[0] - g_num.get_width() // 2, g_center[1] - g_num.get_height() // 2))
            self.screen.blit(g_med, (g_badge_center[0] - g_badge_r, g_badge_center[1] - g_badge_r))

            # Simple hover label only for the local player's graveyard
            if not top_side and self.grave_hover:
                tip = self.font_small.render("Graveyard", True, (235, 230, 220))
                tx = grave_inner.x + (grave_inner.width - tip.get_width()) // 2
                ty = grave_inner.bottom + 4
                self.screen.blit(tip, (tx, ty))

        # P2 (opponent) at top, P1 at bottom
        opp_id = self.match.board.get_opponent("P1")
        draw_deck_and_grave_for(opp_id, top_side=True)
        draw_deck_and_grave_for("P1", top_side=False)

    def _draw_leaders_and_scores(self, board_rect: pygame.Rect) -> None:
        # Opponent and player summaries anchored inside the left side panel,
        # not overlapping the main board area.
        opp = self.match.board.get_opponent("P1")
        p1 = "P1"

        # Mirror _draw_side_panels left layout for leader plaques and reuse
        # the same frame geometry so P2 and P1 are identical.
        left_panel_x = 20
        left_panel_y = 20
        left_panel_w = board_rect.x - 40
        screen_h = self.screen.get_height()

        # Rebuild the same outer frames used in _draw_side_panels with
        # identical insets (26px from top/bottom of the carved column).
        frame_h = 130
        opp_frame = pygame.Rect(left_panel_x + 24, left_panel_y + 26, left_panel_w - 48, frame_h)
        p1_frame_top = screen_h - 220 - frame_h - 26
        p1_frame = pygame.Rect(left_panel_x + 24, p1_frame_top, left_panel_w - 48, frame_h)

        # Inner banner rects inset from the frames; keep alignment identical
        inset = 8
        # Both plaques have identical insets so they sit flush
        opp_leader_rect = opp_frame.inflate(-inset * 2, -inset * 2)
        p1_leader_rect = p1_frame.inflate(-inset * 2, -inset * 2)

        def draw_leader_block(player_id: str, rect: pygame.Rect) -> None:
            # Carved leader plaque with leader card, faction stripe and score medallions
            pygame.draw.rect(self.screen, WOOD_DARK, rect)
            pygame.draw.rect(self.screen, BRONZE_MID, rect, 4)
            pygame.draw.rect(self.screen, BRONZE_LIGHT, rect.inflate(-6, -6), 1)

            player = next(p for p in self.match.players if p.id == player_id)

            # Left: miniature leader card portrait inside the plaque
            leader_card = getattr(player, "leader", None)
            card_area_width = rect.width // 4
            card_margin = 6
            card_rect = pygame.Rect(
                rect.x + card_margin,
                rect.y + card_margin + 6,
                card_area_width - card_margin * 2,
                rect.height - card_margin * 2 - 8,
            )
            if leader_card is not None:
                surf = self._render_card_surface(leader_card, (card_rect.width, card_rect.height))
                self.screen.blit(surf, card_rect.topleft)
            else:
                # Fallback simple wood if no leader set
                pygame.draw.rect(self.screen, WOOD_MID, card_rect)
                pygame.draw.rect(self.screen, BRONZE_DARK, card_rect, 2)

            # Faction stripe at top of the right info area
            info_rect = pygame.Rect(
                card_rect.right + 6,
                rect.y + 4,
                rect.right - (card_rect.right + 10),
                rect.height - 8,
            )
            faction_color = (100, 100, 100)
            if leader_card is not None:
                faction_color = self._card_color(leader_card)
            stripe = pygame.Rect(info_rect.x, info_rect.y, info_rect.width, 12)
            pygame.draw.rect(self.screen, faction_color, stripe)

            # Score / rounds and labels inside the right info block
            score_rect = pygame.Rect(
                info_rect.x + 4,
                stripe.bottom + 4,
                info_rect.width - 8,
                info_rect.height - (stripe.height + 10),
            )
            pygame.draw.rect(self.screen, WOOD_MID, score_rect)
            pygame.draw.rect(self.screen, BRONZE_DARK, score_rect, 2)
            pygame.draw.rect(self.screen, BRONZE_LIGHT, score_rect.inflate(-4, -4), 1)

            # Totals
            total = self.match.board.total_strength(player_id)
            lives = getattr(self.match, "lives", {}).get(player_id, 0)
            wins = getattr(self.match, "wins", {}).get(player_id, 0)

            # Score medallion – emphasize total on the far right like the reference
            med_r = 20
            med_center = (score_rect.right - med_r - 6, score_rect.y + score_rect.height // 2)
            med = pygame.Surface((med_r * 2, med_r * 2), pygame.SRCALPHA)  # type: ignore[attr-defined]
            center = (med_r, med_r)
            pygame.draw.circle(med, BRONZE_MID + (255,), center, med_r)
            pygame.draw.circle(med, BRONZE_LIGHT + (255,), center, med_r - 3)
            pygame.draw.circle(med, BRONZE_DARK + (255,), center, med_r, 2)
            score_text = self.font_small.render(str(total), True, (15, 8, 0))
            med.blit(
                score_text,
                (center[0] - score_text.get_width() // 2, center[1] - score_text.get_height() // 2),
            )
            self.screen.blit(med, (med_center[0] - med_r, med_center[1] - med_r))

            # Round wins, lives and hand size as badges inside the box
            label_x = score_rect.x + 8
            label_y = score_rect.y + 6
            # Player id label
            label = self.font_small.render(player_id, True, (235, 225, 205))
            self.screen.blit(label, (label_x, label_y))

            # Hand size just below the id
            hand_size = len(player.hand)
            hand_text = self.font_small.render(f"Hand: {hand_size}", True, (235, 225, 205))
            self.screen.blit(hand_text, (label_x, label_y + label.get_height() + 2))

            # Wins (rounds) – small gold shields
            shield_y = label_y + label.get_height() + hand_text.get_height() + 6
            for i in range(wins):
                sx = label_x + i * 20
                shield = pygame.Rect(sx, shield_y, 14, 16)
                pygame.draw.rect(self.screen, (170, 140, 80), shield)
                pygame.draw.rect(self.screen, (90, 70, 40), shield, 1)

            # Lives – small gem circles
            gem_y = shield_y + 22
            for i in range(lives):
                gx = label_x + i * 20 + 8
                pygame.draw.circle(self.screen, (120, 210, 210), (gx, gem_y), 6)
                pygame.draw.circle(self.screen, (20, 40, 40), (gx, gem_y), 6, 1)

            # Visual cue when a player has passed this round – kept inside rect
            if getattr(player, "passed", False):
                passed_text = self.font_small.render("PASSED", True, (0, 0, 0))
                px = score_rect.right - passed_text.get_width() - 4
                py = score_rect.y + 4
                self.screen.blit(passed_text, (px, py))

        draw_leader_block(opp, opp_leader_rect)
        draw_leader_block(p1, p1_leader_rect)

    def _draw_status_bar(self, active_id: str, board_rect: pygame.Rect) -> None:
        """PASS button plus a small turn/AI status indicator.

        The PASS button is anchored to the bottom-right of the playfield,
        similar to Witcher 3, and we show whose turn it is so it's clear when
        the AI is thinking or playing.
        """
        btn_w, btn_h = 110, 32
        # Position comfortably inside the lower-right of the board,
        # high enough to avoid overlapping the hand tray.
        x = board_rect.right - btn_w - 14
        # Nudge down so it sits just above the hand tray
        y = board_rect.bottom - btn_h - 20
        self.pass_rect = pygame.Rect(x, y, btn_w, btn_h)
        pygame.draw.rect(self.screen, (130, 40, 40), self.pass_rect)
        pygame.draw.rect(self.screen, BRONZE_LIGHT, self.pass_rect, 1)
        ptxt = self.font_medium.render("PASS", True, (255, 255, 255))
        self.screen.blit(ptxt, (self.pass_rect.x + (btn_w - ptxt.get_width()) // 2, self.pass_rect.y + 4))

        # Turn / AI status text just above the button
        rnd = self.match.current_round
        status = ""
        if rnd:
            if rnd.active_player.id == "P1":
                status = "Your turn"
            elif self.ai and rnd.active_player.id == self.ai_player_id:
                status = "Opponent thinking..."
            else:
                status = f"{rnd.active_player.id} turn"
        if status:
            st_surf = self.font_small.render(status, True, (240, 235, 220))
            sx = self.pass_rect.right - st_surf.get_width()
            sy = self.pass_rect.y - st_surf.get_height() - 4
            self.screen.blit(st_surf, (sx, sy))

    def _draw_hand(self, player_id: str) -> None:
        player = next(p for p in self.match.players if p.id == player_id)
        # Place hand slightly closer to the board
        y = self.screen.get_height() - 170
        tray_rect = pygame.Rect(0, y - 12, self.screen.get_width(), 190)
        pygame.draw.rect(self.screen, WOOD_DARK, tray_rect)
        pygame.draw.rect(self.screen, BRONZE_DARK, tray_rect, 2)
        pygame.draw.rect(self.screen, BRONZE_LIGHT, tray_rect.inflate(-6, -6), 1)
        label = self.font_medium.render(f"{player.id} Hand", True, (235, 230, 220))
        self.screen.blit(label, (40, y - 5))

        hand = list(player.hand)
        n = max(1, len(hand))
        max_width = self.screen.get_width() - 200
        # Slightly larger cards (~25-30% over original base) for readability
        card_width = 130
        card_height = 150
        # Light overlap: 10–20% of card width
        if n > 1:
            step = min(card_width * 0.8, max_width / (n - 0.2))
        else:
            step = card_width
        step = int(step)
        # Ensure some minimum spacing
        step = max(int(card_width * 0.5), step)
        total_w = card_width + step * (n - 1)
        start_x = (self.screen.get_width() - total_w) // 2

        mouse_pos = pygame.mouse.get_pos()
        self.hand_sprites = []
        self.hovered_hand_index = None

        for i, c in enumerate(hand):
            # If this card is currently being dragged, skip drawing it in the tray;
            # it will be drawn following the mouse instead.
            if self.dragging_card is c:
                continue

            x = start_x + i * step
            base_rect = pygame.Rect(x, y + 6, card_width, card_height)
            hovered = base_rect.collidepoint(mouse_pos) and self.dragging_card is None
            if hovered:
                self.hovered_hand_index = i
            # Slight lift and scale on hover; keep rect size for hit-testing
            draw_rect = base_rect.copy()
            if hovered:
                draw_rect.y -= 12
                draw_rect.inflate_ip(12, 12)

            # Store logical card rect for hit-testing / dragging
            self.hand_sprites.append(CardSprite(c, base_rect))

            # Draw non-hovered cards first, then hovered last so it appears on top
        hovered_card: Optional[Tuple[Card, pygame.Rect]] = None
        for sprite in self.hand_sprites:
            card = sprite.card
            rect = sprite.rect
            is_hovered = rect.collidepoint(mouse_pos) and self.dragging_card is None
            draw_rect = rect.copy()
            if is_hovered:
                draw_rect.y -= 12
                draw_rect.inflate_ip(12, 12)
                hovered_card = (card, draw_rect)
            else:
                surf = self._render_card_surface(card, (draw_rect.width, draw_rect.height), hovered=False, selected=(self.selected_from_hand is card))
                self.screen.blit(surf, draw_rect.topleft)

        if hovered_card is not None:
            card, draw_rect = hovered_card
            surf = self._render_card_surface(card, (draw_rect.width, draw_rect.height), hovered=True, selected=(self.selected_from_hand is card))
            self.screen.blit(surf, draw_rect.topleft)

        # If a card is being dragged, render it following the mouse using drag_rect
        if self.dragging_card is not None and self.drag_rect is not None:
            w, h = self.drag_rect.width, self.drag_rect.height
            surf = self._render_card_surface(self.dragging_card, (w, h), hovered=True, selected=True)
            self.screen.blit(surf, self.drag_rect.topleft)

    def _draw_mulligan_hand(self, player_id: str) -> None:
        """Enlarged hand with discard buttons and confirm for mulligan phase."""
        player = next(p for p in self.match.players if p.id == player_id)
        y = self.screen.get_height() - 220

        # Dim background slightly to focus on hand
        overlay = pygame.Surface((self.screen.get_width(), self.screen.get_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))

        pygame.draw.rect(self.screen, (30, 22, 16), (0, y - 20, self.screen.get_width(), 240))
        title = self.font_medium.render("Mulligan: redraw up to 2 cards", True, (230, 230, 230))
        self.screen.blit(title, (40, y - 16))

        hand = list(player.hand)
        n = max(1, len(hand))
        max_width = self.screen.get_width() - 80
        card_width = 100
        gap = min(30, (max_width - card_width) // max(1, n - 1)) if n > 1 else 0
        start_x = 40

        self.hand_sprites = []
        self.mulligan_discard_buttons = []
        for i, c in enumerate(hand):
            x = start_x + i * (card_width + gap)
            rect = pygame.Rect(x, y + 10, card_width, 150)
            self.hand_sprites.append(CardSprite(c, rect))
            surf = self._render_card_surface(c, (rect.width, rect.height))
            self.screen.blit(surf, rect.topleft)

            # Discard "X" button in top-right
            if self.mulligan_discards < self.mulligan_max_discards:
                x_rect = pygame.Rect(rect.right - 20, rect.y + 4, 16, 16)
                pygame.draw.rect(self.screen, (140, 40, 40), x_rect)
                pygame.draw.rect(self.screen, (0, 0, 0), x_rect, 1)
                x_txt = self.font_small.render("X", True, (255, 255, 255))
                self.screen.blit(x_txt, (x_rect.x + 3, x_rect.y + 1))
                self.mulligan_discard_buttons.append((c, x_rect))

        # Confirm button
        btn_w, btn_h = 160, 36
        btn_x = self.screen.get_width() - btn_w - 40
        btn_y = y - 10
        self.mulligan_confirm_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        can_confirm = True  # allow confirm anytime; adjust if you want at least one redraw
        bg = (80, 60, 40) if can_confirm else (50, 40, 30)
        pygame.draw.rect(self.screen, bg, self.mulligan_confirm_rect)
        pygame.draw.rect(self.screen, (140, 110, 60), self.mulligan_confirm_rect, 1)
        label = self.font_medium.render("Confirm Hand", True, (255, 255, 255))
        self.screen.blit(label, (btn_x + 10, btn_y + 6))

    def _render_card_surface(self, card: Card, size: Tuple[int, int], *, hovered: bool = False, selected: bool = False) -> pygame.Surface:
        """Render a single card as parchment on wood with medallions and icons.

        Unit cards have parchment frames; specials use darker mystical frames.
        """
        w, h = size
        surf = pygame.Surface((w, h), pygame.SRCALPHA)  # type: ignore[attr-defined]

        is_special = card.type in (CardType.SPECIAL, CardType.WEATHER)

        # Base frame
        rect = pygame.Rect(0, 0, w, h)
        if is_special:
            frame_col = (40, 46, 70)
            inner_col_top = (72, 80, 110)
            inner_col_bot = (40, 44, 70)
        else:
            frame_col = self._card_color(card)
            inner_col_top = PARCHMENT_LIGHT
            inner_col_bot = PARCHMENT_MID

        pygame.draw.rect(surf, frame_col, rect, border_radius=10)  # type: ignore[arg-type]
        inner_rect = rect.inflate(-6, -6)

        # Parchment / mystical interior gradient
        for i in range(inner_rect.height):
            t = i / max(1, inner_rect.height - 1)
            r = int(inner_col_top[0] + (inner_col_bot[0] - inner_col_top[0]) * t)
            g = int(inner_col_top[1] + (inner_col_bot[1] - inner_col_top[1]) * t)
            b = int(inner_col_top[2] + (inner_col_bot[2] - inner_col_top[2]) * t)
            pygame.draw.line(
                surf,
                (r, g, b),
                (inner_rect.x, inner_rect.y + i),
                (inner_rect.right, inner_rect.y + i),
            )

        # Worn edges
        pygame.draw.rect(surf, (150, 135, 110), inner_rect, 1)

        # Hover / selection glow
        if hovered:
            glow = pygame.Surface((w, h), pygame.SRCALPHA)  # type: ignore[attr-defined]
            glow.fill(GLOW_GOLD + (60,))  # type: ignore[operator]
            surf.blit(glow, (0, 0))
        if selected:
            pygame.draw.rect(surf, GLOW_GOLD, rect, 3, border_radius=12)  # type: ignore[arg-type]

        # Strength medallion (top-left) for units
        if card.type == CardType.UNIT:
            badge_r = max(10, h // 9)
            badge_center = (inner_rect.x + badge_r + 2, inner_rect.y + badge_r + 2)
            med = pygame.Surface((badge_r * 2, badge_r * 2), pygame.SRCALPHA)  # type: ignore[attr-defined]
            center = (badge_r, badge_r)
            pygame.draw.circle(med, BRONZE_MID + (255,), center, badge_r)
            pygame.draw.circle(med, BRONZE_LIGHT + (255,), center, badge_r - 2)
            pygame.draw.circle(med, BRONZE_DARK + (255,), center, badge_r, 2)
            pw_text = self.font_small.render(str(card.power), True, (20, 10, 0))
            med.blit(
                pw_text,
                (center[0] - pw_text.get_width() // 2, center[1] - pw_text.get_height() // 2),
            )
            surf.blit(med, (badge_center[0] - badge_r, badge_center[1] - badge_r))

        # Row icon (bottom-right)
        icon_size = max(14, h // 10)
        icon_rect = pygame.Rect(0, 0, icon_size, icon_size)
        icon_rect.bottom = inner_rect.bottom - 4
        icon_rect.right = inner_rect.right - 4
        pygame.draw.rect(surf, (95, 80, 60), icon_rect, border_radius=4)  # type: ignore[arg-type]
        row_symbol = "?"
        if card.row == Row.MELEE:
            row_symbol = "⚔"
        elif card.row == Row.RANGED:
            row_symbol = "🏹"
        elif card.row == Row.SIEGE:
            row_symbol = "⛨"
        icon_text = self.font_small.render(row_symbol, True, (235, 235, 230))
        surf.blit(
            icon_text,
            (
                icon_rect.x + (icon_rect.width - icon_text.get_width()) // 2,
                icon_rect.y + (icon_rect.height - icon_text.get_height()) // 2,
            ),
        )

        # Central art placeholder – slightly darker strip
        art_margin_y = inner_rect.height // 5
        art_rect = pygame.Rect(
            inner_rect.x + 6,
            inner_rect.y + art_margin_y,
            inner_rect.width - 12,
            inner_rect.height - art_margin_y * 2 - 22,
        )
        art_col = (170, 158, 132) if not is_special else (70, 80, 110)
        pygame.draw.rect(surf, art_col, art_rect, border_radius=6)  # type: ignore[arg-type]

        # Special symbol for specials/weather
        if is_special:
            symbol = "★"
            name_lower = card.name.lower()
            if "frost" in name_lower or "fog" in name_lower or "rain" in name_lower or "storm" in name_lower:
                symbol = "☁"
            elif "decoy" in name_lower:
                symbol = "♜"
            elif "horn" in name_lower:
                symbol = "♩"
            sym_surf = self.font_medium.render(symbol, True, (230, 235, 250))
            sx = art_rect.x + (art_rect.width - sym_surf.get_width()) // 2
            sy = art_rect.y + (art_rect.height - sym_surf.get_height()) // 2
            surf.blit(sym_surf, (sx, sy))

        # Name ribbon at bottom
        banner_h = 18
        banner_rect = pygame.Rect(
            inner_rect.x + 6,
            inner_rect.bottom - banner_h - 4,
            inner_rect.width - 12,
            banner_h,
        )
        pygame.draw.rect(surf, (166, 138, 96), banner_rect)
        pygame.draw.rect(surf, (110, 82, 52), banner_rect, 1)
        name = card.name if len(card.name) <= 16 else card.name[:15] + "…"
        name_surf = self.font_small.render(name, True, (30, 18, 4))
        surf.blit(
            name_surf,
            (
                banner_rect.x + (banner_rect.width - name_surf.get_width()) // 2,
                banner_rect.y + (banner_rect.height - name_surf.get_height()) // 2,
            ),
        )

        return surf

    def _render_card_back_surface(self, size: Tuple[int, int], *, muted: bool = False) -> pygame.Surface:
        """Render a generic card back reusing the front-frame style.

        This mirrors the hand card aesthetic but without text, so the deck
        pile looks like real Gwent cards from Witcher 3.
        """
        w, h = size
        surf = pygame.Surface((w, h), pygame.SRCALPHA)  # type: ignore[attr-defined]

        rect = pygame.Rect(0, 0, w, h)
        if muted:
            frame_col = (38, 32, 26)
            inner_top = (70, 62, 50)
            inner_bot = (46, 40, 32)
        else:
            frame_col = (52, 40, 26)
            inner_top = (92, 70, 46)
            inner_bot = (60, 45, 30)

        pygame.draw.rect(surf, frame_col, rect, border_radius=10)  # type: ignore[arg-type]
        inner_rect = rect.inflate(-6, -6)

        for i in range(inner_rect.height):
            t = i / max(1, inner_rect.height - 1)
            r = int(inner_top[0] + (inner_bot[0] - inner_top[0]) * t)
            g = int(inner_top[1] + (inner_bot[1] - inner_top[1]) * t)
            b = int(inner_top[2] + (inner_bot[2] - inner_top[2]) * t)
            pygame.draw.line(
                surf,
                (r, g, b),
                (inner_rect.x, inner_rect.y + i),
                (inner_rect.right, inner_rect.y + i),
            )

        pygame.draw.rect(surf, (150, 130, 90), inner_rect, 1)

        # Simple Gwent-like emblem in the center
        emblem_rect = inner_rect.inflate(-inner_rect.width // 3, -inner_rect.height // 3)
        pygame.draw.rect(surf, (40, 28, 16), emblem_rect, border_radius=6)  # type: ignore[arg-type]
        pygame.draw.rect(surf, (180, 150, 90), emblem_rect, 2, border_radius=6)  # type: ignore[arg-type]

        return surf

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
        # Start first round; mulligan happens before any turns are taken
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
                        # Start drag from hand if clicking a card; otherwise
                        # fall back to the old click behaviour (pass, overlays).
                        self._on_mouse_down(event.pos)
                    elif event.button == 3:
                        self._on_right_click(event.pos)
                elif event.type == pygame.MOUSEMOTION:  # type: ignore[attr-defined]
                    self._on_mouse_motion(event.pos, event.rel, event.buttons)
                elif event.type == pygame.MOUSEBUTTONUP:  # type: ignore[attr-defined]
                    if event.button == 1:
                        self._on_mouse_up(event.pos)

            # During mulligan, skip AI logic entirely
            if self.phase != "mulligan":
                # AI turn with small random delay between moves; once you pass,
                # the AI will continue taking turns until it also passes or round ends.
                rnd = self.match.current_round
                if self.ai and rnd and not rnd.finished and rnd.active_player.id == self.ai_player_id:
                    if self.ai_wait_timer <= 0:
                        # Start a new wait in frames (0.3-2.0 seconds)
                        delay_seconds = random.uniform(0.3, 2.0)
                        self.ai_wait_timer = delay_seconds * FPS
                    else:
                        self.ai_wait_timer -= 1
                        if self.ai_wait_timer <= 0:
                            # Re-check active player in case round ended or switched unexpectedly
                            rnd = self.match.current_round
                            if not rnd or rnd.finished or rnd.active_player.id != self.ai_player_id:
                                self.ai_wait_timer = 0
                            else:
                                action = self.ai.choose_action(self.match)
                                player = rnd.active_player
                                if action.kind == "pass":
                                    self.match.pass_turn(player)
                                elif action.kind == "play" and action.card is not None:
                                    # Guard AI play so engine errors don't close the UI
                                    try:
                                        self.match.play_card(
                                            player,
                                            action.card,
                                            target_row=action.target_row,
                                            target_unit=action.target_unit,
                                        )
                                    except Exception as exc:
                                        # For now just print; could render a small status message instead
                                        print(f"[AI ERROR] {type(exc).__name__}: {exc}")
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

    def _on_mouse_down(self, pos: Tuple[int, int]) -> None:
        # Mulligan phase: handle discards and confirm hand
        if self.phase == "mulligan":
            self._handle_mulligan_click(pos)
            return

        # If we're choosing a row for a card, clicks go to that handler
        if self.pending_row_choice is not None:
            self._handle_row_choice_click(pos)
            return
        # Clicking anywhere while info panel is open will close it first
        if self.info_card is not None:
            self.info_card = None
            return
        # PASS button (still reacts to simple click)
        if self.pass_rect and self.pass_rect.collidepoint(pos):
            rnd = self.match.current_round
            if rnd:
                player = rnd.active_player
                if player.id == "P1":
                    self.match.pass_turn(player)
            return

        # Start drag from hand for active human player who has not passed
        rnd = self.match.current_round
        if rnd and rnd.active_player.id == "P1" and not rnd.active_player.passed:
            for sprite in getattr(self, "hand_sprites", []):
                if sprite.rect.collidepoint(pos):
                    self.dragging_card = sprite.card
                    # Center drag rect on click position with same size as sprite
                    self.drag_rect = sprite.rect.copy()
                    dx = pos[0] - self.drag_rect.x
                    dy = pos[1] - self.drag_rect.y
                    self.drag_offset = (dx, dy)
                    # Do not immediately play the card; wait for drop.
                    return

    def _on_mouse_motion(self, pos: Tuple[int, int], rel: Tuple[int, int], buttons: Tuple[int, int, int]) -> None:
        # If dragging, update the drag rectangle to follow the cursor
        if self.dragging_card is not None and self.drag_rect is not None and buttons[0]:
            self.drag_rect.x = pos[0] - self.drag_offset[0]
            self.drag_rect.y = pos[1] - self.drag_offset[1]

    def _on_mouse_up(self, pos: Tuple[int, int]) -> None:
        # If we were dragging a card, resolve drop
        if self.dragging_card is not None:
            card = self.dragging_card
            drop_handled = False

            # Only allow playing on your own turn, and not after passing
            rnd = self.match.current_round
            if rnd and rnd.active_player.id == "P1" and not rnd.active_player.passed:
                # Determine which lane was targeted by the drop (if any)
                dropped_row: Optional[Row] = None
                for (pid, row), lane_rect in self.row_lane_rects.items():
                    if pid == "P1" and lane_rect.collidepoint(pos):
                        dropped_row = row
                        break

                if dropped_row is not None:
                    # Work out whether this card is allowed in the dropped row.
                    # Units may have a fixed row or multiple combat_rows; specials
                    # typically don't care about row so we let the engine handle those.
                    allowed_rows: Optional[List[Row]] = None
                    combat_rows = getattr(card, "combat_rows", None)
                    if combat_rows and getattr(card, "row", None) == Row.ALL:
                        allowed_rows = [r for r in combat_rows if r in (Row.MELEE, Row.RANGED, Row.SIEGE)]
                    else:
                        base_row = getattr(card, "row", None)
                        if base_row in (Row.MELEE, Row.RANGED, Row.SIEGE):
                            allowed_rows = [base_row]

                    # If allowed_rows is not None, enforce that the dropped row is valid
                    if allowed_rows is not None and dropped_row not in allowed_rows:
                        # Invalid row for this card; treat as cancelled drag
                        pass
                    else:
                        try:
                            self.match.play_card(rnd.active_player, card, target_row=dropped_row)
                            drop_handled = True
                        except Exception as exc:
                            print(f"[PLAY ERROR] {type(exc).__name__}: {exc}")

            # Reset drag state; if drop_handled is False, card simply remains in hand
            self.dragging_card = None
            self.drag_rect = None
            self.drag_offset = (0, 0)

            # If we didn't play the card, leave selection untouched
            if drop_handled:
                self.selected_from_hand = None

            return

    def _handle_mulligan_click(self, pos: Tuple[int, int]) -> None:
        # Confirm hand button
        if self.mulligan_confirm_rect and self.mulligan_confirm_rect.collidepoint(pos):
            # End mulligan and move to normal play
            self.phase = "play"
            return

        # Discard icons (limit by mulligan_max_discards)
        if self.mulligan_discards >= self.mulligan_max_discards:
            return

        player = next(p for p in self.match.players if p.id == "P1")
        for card, rect in self.mulligan_discard_buttons:
            if rect.collidepoint(pos) and card in player.hand:
                # Remove from hand and draw a replacement from deck if possible
                player.hand.remove(card)
                deck = getattr(player, "deck", None) or []
                if deck:
                    # Simple top-of-deck draw
                    new_card = deck.pop(0)
                    player.hand.append(new_card)
                self.mulligan_discards += 1
                break

    def _handle_row_choice_click(self, pos: Tuple[int, int]) -> None:
        if self.pending_row_choice is None:
            return
        card, _rows = self.pending_row_choice
        # If we somehow don't have buttons (e.g. first frame), just cancel
        for r, rect in self.row_choice_buttons:
            if rect.collidepoint(pos):
                rnd = self.match.current_round
                if rnd and rnd.active_player.id == "P1":
                    try:
                        self.match.play_card(rnd.active_player, card, target_row=r)
                    except Exception as exc:
                        print(f"[PLAY ERROR] {type(exc).__name__}: {exc}")
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

        # Right-click on a card already on the board to open description
        for card, rect in self.board_card_rects:
            if rect.collidepoint(pos):
                self.info_card = card
                return


def start_visual_ui() -> None:
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("Gwent - Setup")
    clock = pygame.time.Clock()

    font_title = pygame.font.SysFont("arial", 32, bold=True)
    font_label = pygame.font.SysFont("arial", 22)
    font_small = pygame.font.SysFont("arial", 18)

    cards = load_cards()
    all_leaders = [c for c in cards if c.type == CardType.LEADER]
    if not all_leaders:
        raise RuntimeError("No leader cards available.")

    factions = sorted({c.faction for c in all_leaders})

    def build_auto_deck(faction) -> Tuple[List[Card], Card]:
        leaders = [c for c in all_leaders if c.faction == faction] or all_leaders[:]
        leader = leaders[0]
        all_units = [c for c in cards if c.type == CardType.UNIT]
        all_specials = [c for c in cards if c.type in (CardType.SPECIAL, CardType.WEATHER)]
        units_pool = [c for c in all_units if c.faction == faction or c.faction.value == "neutral"]
        specials_pool = [c for c in all_specials if c.faction == faction or c.faction.value == "neutral"]
        random.shuffle(units_pool)
        random.shuffle(specials_pool)
        chosen_units = units_pool[:22]
        chosen_specials = specials_pool[:8]
        deck = chosen_units + chosen_specials
        random.shuffle(deck)
        return deck, leader

    selected_faction_index = 0
    deck_mode_index = 0  # 0 = Auto, 1 = Manual (NYI, treated as Auto)
    start_button_rect: Optional[pygame.Rect] = None

    running = True
    while running:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:  # type: ignore[attr-defined]
                pygame.quit()  # type: ignore[attr-defined]
                return
            elif event.type == pygame.KEYDOWN:  # type: ignore[attr-defined]
                if event.key == pygame.K_ESCAPE:  # type: ignore[attr-defined]
                    pygame.quit()  # type: ignore[attr-defined]
                    return
                if event.key in (pygame.K_LEFT, pygame.K_a):  # type: ignore[attr-defined]
                    selected_faction_index = (selected_faction_index - 1) % len(factions)
                if event.key in (pygame.K_RIGHT, pygame.K_d):  # type: ignore[attr-defined]
                    selected_faction_index = (selected_faction_index + 1) % len(factions)
                if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s):  # type: ignore[attr-defined]
                    deck_mode_index = 1 - deck_mode_index
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):  # type: ignore[attr-defined]
                    if start_button_rect and start_button_rect.collidepoint(pygame.mouse.get_pos()):
                        running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:  # type: ignore[attr-defined]
                if event.button == 1 and start_button_rect and start_button_rect.collidepoint(event.pos):
                    running = False

        screen.fill((10, 10, 20))

        title = font_title.render("Gwent - Pre-game Setup", True, (230, 230, 230))
        screen.blit(title, ((WINDOW_SIZE[0] - title.get_width()) // 2, 40))

        # Faction selection
        faction_label = font_label.render("Faction (P1):", True, (220, 220, 220))
        screen.blit(faction_label, (120, 140))
        cur_faction = factions[selected_faction_index]
        faction_text = font_label.render(cur_faction.value.capitalize(), True, (255, 235, 180))
        screen.blit(faction_text, (360, 140))
        hint = font_small.render("Use ← → to change faction", True, (200, 200, 200))
        screen.blit(hint, (120, 175))

        # Deck mode (currently only Auto is implemented)
        deck_label = font_label.render("Deck Mode:", True, (220, 220, 220))
        screen.blit(deck_label, (120, 230))
        modes = ["Auto (22 units / 8 specials)", "Manual (not yet implemented)"]
        for idx, txt in enumerate(modes):
            color = (255, 255, 255) if idx == deck_mode_index else (180, 180, 180)
            surf = font_small.render(txt, True, color)
            screen.blit(surf, (360, 230 + idx * 28))
        mode_hint = font_small.render("Use ↑ ↓ to toggle mode", True, (200, 200, 200))
        screen.blit(mode_hint, (120, 300))

        # Start button
        btn_w, btn_h = 220, 50
        btn_x = (WINDOW_SIZE[0] - btn_w) // 2
        btn_y = 360
        start_button_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        pygame.draw.rect(screen, (60, 100, 60), start_button_rect)
        pygame.draw.rect(screen, (200, 230, 200), start_button_rect, 2)
        start_txt = font_label.render("Start Match", True, (255, 255, 255))
        screen.blit(start_txt, (btn_x + (btn_w - start_txt.get_width()) // 2, btn_y + 10))

        info = font_small.render("Press Esc to quit", True, (200, 200, 200))
        screen.blit(info, (20, WINDOW_SIZE[1] - 30))

        pygame.display.flip()

    # Build players and match based on selected faction (P2 uses random faction auto deck)
    p1_faction = factions[selected_faction_index]
    p1_full_deck, _p1_leader = build_auto_deck(p1_faction)
    # Starting hand of 10
    tmp = list(p1_full_deck)
    random.shuffle(tmp)
    p1_hand = tmp[:10]
    p1_deck_rest = tmp[10:]

    # P2: pick a random faction and auto deck
    p2_faction = random.choice(factions)
    p2_full_deck, _p2_leader = build_auto_deck(p2_faction)
    tmp2 = list(p2_full_deck)
    random.shuffle(tmp2)
    p2_hand = tmp2[:10]
    p2_deck_rest = tmp2[10:]

    p1 = Player(id="P1", deck=p1_deck_rest, hand=p1_hand)
    p2 = Player(id="P2", deck=p2_deck_rest, hand=p2_hand)
    match = Match([p1, p2])
    match.board.decks[p1.id].extend(p1_full_deck)
    match.board.decks[p2.id].extend(p2_full_deck)

    # Now hand off to main Visual UI (P2 is AI)
    ui = VisualUI(match, ai_player_id="P2")
    ui.run()


__all__ = ["start_visual_ui", "VisualUI"]

