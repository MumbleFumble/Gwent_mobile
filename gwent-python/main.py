"""
Entry point for the Gwent (Witcher 3 minigame) Python implementation.

For now this just runs a placeholder CLI loop.
Later, this should:
- create a Match object
- hook into a Text UI or Visual UI
"""

from typing import NoReturn


def main() -> NoReturn:
    print("=== Gwent (Witcher 3 Minigame) ===")
    print("Backend/engine not fully implemented yet.")
    print("Planned flow:")
    print("  1. Initialize decks for Player and AI")
    print("  2. Play best-of-three rounds")
    print("  3. Show final winner")

    # TODO:
    # from gwent.game.match import Match
    # from gwent.ui.text_ui import TextUI
    #
    # match = Match.new_default()
    # ui = TextUI(match)
    # ui.run()

    while True:
        choice = input("\nType 'q' to quit: ").strip().lower()
        if choice == "q":
            print("Goodbye, Gwent player.")
            break


if __name__ == "__main__":
    main()