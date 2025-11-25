# Gwent (Witcher 3 Minigame) — Python Implementation

A fully playable Python recreation of **Gwent**, the card game from *The Witcher 3: Wild Hunt*.  
This project aims to rebuild the **minigame version**, not the standalone Gwent mobile game.

The project progresses through three phases:

1. **Backend logic** – cards, board, rounds, rules  
2. **AI opponent** – simple heuristics, later a smarter agent  
3. **Visual interface** – text UI first, then graphical version  

---

## ✨ Features (Planned)

### ✔ Core Game Mechanics
- Decks, hands, graveyards  
- Melee / Ranged / Siege rows  
- Heroes, specials, weather, Tight Bond, Morale Boost  
- Round system (best of two victories)

### ✔ AI Opponent
- Basic AI (rule-based heuristics)  
- Optional upgrade: Monte-Carlo or Minimax AI  

### ✔ UI Options
- CLI text-only mode  
- Later: graphical interface (likely PyGame)


# Gwent (Witcher 3 Minigame) — Rules Overview

This document describes the rules used by this project.  
It is based on the **Gwent minigame** inside *The Witcher 3: Wild Hunt* (not the standalone Gwent game), but written and organized in my own words.

---

## 1. Objective

- Two players compete over **up to three rounds**.
- Each round, players play cards to their side of the board and try to have **more total strength** than the opponent when both pass.
- The first player to win **two rounds** wins the match.

---

## 2. Decks and Starting Hand

- Each player chooses a **faction deck** (e.g. Northern Realms, Nilfgaard, Scoia'tael, Monsters).
- Decks contain:
  - **Unit cards** (with a strength value and a row: melee / ranged / siege)
  - **Special cards** (e.g. Commander's Horn, Decoy, Scorch)
  - **Weather cards** (e.g. Biting Frost, Impenetrable Fog, Torrential Rain)
  - **Leader card** with a once-per-match special ability
- At the start of the match:
  - Each player draws a **starting hand** (fixed size, e.g. 10 cards).
  - Players may **redraw** a small number of cards (mulligan) depending on faction rules.

> Important: You do **not** draw a full new hand each round.  
> Most of the strategy is about managing a limited hand over multiple rounds.

---

## 3. Board Layout

Each player’s side of the board has three rows:

1. **Melee row**
2. **Ranged row**
3. **Siege row**

Each row has:

- A set of **unit cards** placed there.
- Optional **row modifiers**, such as:
  - Weather cards (debuff)
  - Commander's Horn (buff)

The total **round strength** for a player is the sum of the strengths of all units on all three rows (after all modifiers).

---

## 4. Turn Structure

- Players take turns, starting with one player (based on rules/faction or random).
- On your turn you must **either**:
  1. **Play a card** from your hand, or
  2. **Pass**.

Once you pass:

- You cannot play more cards this round.
- Your opponent may continue to play cards until they also pass, or run out of cards.

The round ends when **both players have passed**.

---

## 5. Winning a Round

- Compare total strength (all three rows) for both players.
- The player with the **higher total strength** wins the round.
- On a tie:
  - Some factions (e.g. Nilfgaard) have a special rule and win ties.
  - Otherwise, both players may be treated as winning/losing depending on implementation; this project can model the Nilfgaard tiebreaker.

After the round:

- Each player’s **round token** (lives) is updated.
  - Typically best-of-three: each player starts with 2 lives, and losing a round costs 1 life.
- Cards on the board generally go to the **graveyard**.
- Weather effects are cleared.

Players usually **do not draw many new cards**. Some abilities and faction bonuses allow extra draws between rounds.

---

## 6. Card Types and Effects

### 6.1 Unit Cards

- Have:
  - Strength (power)
  - Row: melee, ranged, or siege
  - Optional abilities

Common unit abilities:

- **Tight Bond**:  
  - When multiple cards with the same name and Tight Bond are on the same row on your side, each gets its strength multiplied (usually ×2 for each duplicate).
- **Morale Boost**:  
  - Gives +1 strength to all other unit cards on the same row.
- **Medic**:  
  - Lets you take a unit card from your graveyard and play it immediately.
- **Muster**:  
  - When you play one unit in a group, all matching units from your deck (and possibly hand) with the same muster group name are played automatically.
- **Hero**:
  - High-strength hero units.
  - Immune to most effects (weather, Scorch, etc.).

### 6.2 Special Cards

Examples:

- **Commander's Horn**:
  - Doubles the strength of all non-hero unit cards in a chosen row.
- **Decoy**:
  - Replace a unit card on your side of the board with Decoy, returning the unit to your hand.
- **Scorch**:
  - Destroys the strongest non-hero unit card(s) on the board (across both players), according to specific rules.

### 6.3 Weather Cards

- **Biting Frost**:
  - Reduces the strength of all melee units (non-hero) to 1.
- **Impenetrable Fog**:
  - Reduces the strength of all ranged units (non-hero) to 1.
- **Torrential Rain**:
  - Reduces the strength of all siege units (non-hero) to 1.
- **Clear Weather**:
  - Removes all active weather effects from the board.

---

## 7. Leader Abilities

- Each faction has multiple possible leader cards.
- A leader ability can usually be used **once per match**.
- Example effects:
  - Play a weather card from your deck.
  - Restore a unit from the graveyard.
  - Cancel a weather effect on your side.

Implementation detail for this project:

- Leader abilities can be represented as special actions tied to the faction/leader card, separate from normal card play.

---

## 8. Faction Perks (Minigame Version)

Each faction in the minigame has a passive perk, such as:

- **Northern Realms**:
  - Example behavior: Draw a card after winning a round.
- **Nilfgaardian Empire**:
  - Wins the round in case of a **tie**.
- **Scoia'tael**:
  - Can choose who goes first.
- **Monsters**:
  - Keeps a random unit card on the board after each round.

Your implementation can model these perks via:

- Hooks at end-of-round
- Hooks at start-of-match
- Tie-resolution logic

---

## 9. Strategy Considerations

Some intended depth for the AI and player:

- Intentionally **throwing a round** to preserve cards for later.
- Baiting out opponent’s strong cards or weather.
- Passing at the right time when ahead on points.
- Managing hero cards and Commander's Horn for maximum impact.
- Leveraging faction perk synergies.

---

## 10. Implementation Notes for This Project

In code, we will roughly map rules to:

- `Card` objects with:
  - faction, row, power, abilities, hero flag
- A `Board` object with:
  - three rows per player
  - active weather effects and row buffs
- A `Round` / `Match` controller that:
  - manages turns, passing, and score evaluation
  - applies faction perks and leader abilities
- An AI agent that:
  - estimates whether to play or pass
  - picks “good enough” cards based on heuristics

This document is meant to guide implementation, not serve as an official rulebook.
