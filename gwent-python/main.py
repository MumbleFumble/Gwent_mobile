"""
Entry point for the Gwent (Witcher 3 minigame) Python implementation.

For now this just runs a placeholder CLI loop.
Later, this should:
- create a Match object
- hook into a Text UI or Visual UI
"""

from typing import NoReturn

from gwent.ui.visual_ui import start_visual_ui


def main() -> NoReturn:
    """Launch the visual PyGame UI directly.

    Text UI is still available via gwent.ui.text_ui:start_text_ui if needed,
    but running this script will go straight into the graphical client.
    """
    print("=== Gwent (Witcher 3 Minigame) ===")
    print("Launching Visual UI...")
    start_visual_ui()
    print("Goodbye, Gwent player.")


if __name__ == "__main__":
    main()