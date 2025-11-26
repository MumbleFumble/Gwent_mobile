"""
Entry point for the Gwent (Witcher 3 minigame) Python implementation.

For now this just runs a placeholder CLI loop.
Later, this should:
- create a Match object
- hook into a Text UI or Visual UI
"""

from typing import NoReturn

from gwent.ui.text_ui import start_text_ui
from gwent.ui.visual_ui import start_visual_ui


def main() -> NoReturn:
    print("=== Gwent (Witcher 3 Minigame) ===")
    print("Select UI mode:")
    print("  1) Text UI (terminal)")
    print("  2) Visual UI (PyGame)")

    choice = input("Enter 1 or 2: ").strip()
    if choice == "2":
        start_visual_ui()
    else:
        print("Launching Text UI. Type 'help' for commands.")
        start_text_ui()
    print("Goodbye, Gwent player.")


if __name__ == "__main__":
    main()