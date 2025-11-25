"""
Entry point for the Gwent (Witcher 3 minigame) Python implementation.

For now this just runs a placeholder CLI loop.
Later, this should:
- create a Match object
- hook into a Text UI or Visual UI
"""

from typing import NoReturn

from gwent.ui.text_ui import start_text_ui


def main() -> NoReturn:
    print("=== Gwent (Witcher 3 Minigame) ===")
    print("Launching demo Text UI. Type 'help' for commands.")
    start_text_ui()
    print("Goodbye, Gwent player.")


if __name__ == "__main__":
    main()