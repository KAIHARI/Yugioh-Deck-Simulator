# Yugioh-Deck-Simulator

This Python program provides a graphical user interface (GUI) built with Tkinter for building and analyzing Yu-Gi-Oh! decks, specifically focusing on opening hand probabilities and consistency to aid in optimizing card ratios.

Core Functionality:

Deck Building:

Allows users to build two decks (Deck A and Deck B) side-by-side.

Provides a searchable list of available cards (the "card pool").

Users can add cards (up to 3 copies) and remove cards from each deck list.

Displays running counts for each deck (Total cards, Monsters, Spells, Traps).

Supports saving and loading deck lists to/from JSON files stored in a decks folder.

Simulation:

Users can submit Deck A (for single analysis) or both Deck A and Deck B (for comparison).

The application remembers the last submitted decks and attempts to preload them on startup.

Users specify the number of simulations (opening hands to draw) to perform.

Simulations run in a background thread to keep the GUI responsive, with status updates shown in a status bar.

Analysis & Reporting (analysis_engine.py):

Performs Monte Carlo simulation by repeatedly shuffling the submitted deck(s) and drawing an opening hand (5 cards).

Calculates various statistics based on the simulated hands:

Individual Card Frequency: How often each card appears in the opening hand (count and percentage).

Combo Frequency: How often predefined (hardcoded) and user-defined (custom) combos are achievable with the opening hand.

Duplicate Card Frequency: How often 2 or more copies of the same card appear.

Hand Composition (M/S/T): Frequencies of different Monster/Spell/Trap count combinations in the opening hand.

Category Frequency: Average number of cards belonging to each user-defined category per hand.

Hand Category Composition: Frequencies of different combinations of card categories appearing in the opening hand.

Generates a detailed PDF report (saved in analysis_reports) summarizing these statistics, comparing Deck A and Deck B if applicable.

Includes an "Insights" section in the comparison report, highlighting differences in combo frequencies and providing basic recommendations for card ratio adjustments based on hardcoded combo definitions.

Customization & Management:

Card Database Editor: Allows users to modify the effective card pool used by the application. Users can add new cards (defining name and type), "remove" (hide) default cards, and override the type (Monster/Spell/Trap) of default cards. These changes are saved persistently in user_card_database.json and merged with the base data from card_database.py on startup.

Category Manager: Provides a window to define custom categories (e.g., "Starter", "Extender", "Hand Trap", "Garnet") and assign cards to one or more categories. Assignments are saved in card_categories.json and used in the analysis.

Combo Editor: Allows users to define complex custom combos using a structured format (requiring specific cards AND/OR requiring at least one card from defined groups). Users can also view the structure of hardcoded combos as examples and save their custom definitions to custom_combos.json. The analysis engine evaluates both hardcoded and custom combos.

User Experience:

Starts in comparison mode by default.

Uses status bar messages for confirmations (loading/saving/submitting decks) instead of pop-up windows.

After a simulation finishes and the PDF is generated, it prompts the user via the status bar to press Spacebar to open the report folder or X to dismiss the prompt.

In essence, it's a tool to build decks, simulate opening hands thousands or millions of times very quickly, and get statistical feedback on consistency, combo potential, and hand structure, with significant customization options for cards, categories, and combos.
