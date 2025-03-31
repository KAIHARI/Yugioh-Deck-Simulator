import os
import random
import re
from collections import Counter

# ReportLab Imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch

# Local Import (Requires card_database.py)
try:
    from card_database import CARD_POOL, CARD_TYPES
except ImportError:
    # If run directly, this error might show. It's okay if main.py imports it.
    print("Warning: card_database.py not found. Analysis engine relies on it.")
    CARD_POOL = []
    CARD_TYPES = {}

# --- Constants (Mirrored from main for standalone use if needed) ---
MIN_DECK_SIZE = 40
MAX_DECK_SIZE = 60
MAX_CARD_COPIES = 3

# --- Helper Functions ---

def get_unique_filename(base_filename):
    """Generates a unique filename by appending _N if the file exists."""
    directory = os.path.dirname(base_filename)
    name_part, ext = os.path.splitext(os.path.basename(base_filename))

    # Ensure directory exists
    if directory and not os.path.exists(directory):
        try:
            os.makedirs(directory)
        except OSError as e:
            print(f"Error creating directory {directory}: {e}")
            directory = "" # Fallback to current dir

    counter = 0
    new_filename = base_filename
    while os.path.exists(new_filename):
        counter += 1
        new_filename = os.path.join(directory, f"{name_part}_{counter}{ext}")
    return new_filename

def _define_combos():
    """Defines the hardcoded combo checking logic (lambdas)."""
    # These serve as defaults if no custom combos are loaded or defined
    furniture_cards = {"Labrynth Stovie Torbie", "Labrynth Chandraglier"}
    welcome_cards = {"Welcome Labrynth", "Big Welcome Labrynth"}
    disruption_traps = {"Trap Trick", "Destructive Daruma Karma Cannon", "Dimensional Barrier"}

    return {
        "Furniture + Back Jack": lambda hand_set: ( # Lambdas now accept hand_set
            any(card in furniture_cards for card in hand_set) and "Absolute King Back Jack" in hand_set
        ),
        "Arias + Disruption Trap": lambda hand_set: (
            "Arias the Labrynth Butler" in hand_set and any(card in disruption_traps for card in hand_set)
        ),
        "Rollback Combo": lambda hand_set: (
            "Dominus Impulse" in hand_set and "Transaction Rollback" in hand_set and any(card in furniture_cards for card in hand_set)
        ),
        "Access to Furniture + Back Jack": lambda hand_set: (
            "Arias the Labrynth Butler" in hand_set and
            ("Arianna the Labrynth Servant" in hand_set or any(card in welcome_cards for card in hand_set)) and
            "Absolute King Back Jack" in hand_set
        ),
        "Furniture Combo": lambda hand_set: (
            any(card in furniture_cards for card in hand_set) and "Labrynth Cooclock" in hand_set
        ),
        "Lady Combo": lambda hand_set: (
            "Lady Labrynth of the Silver Castle" in hand_set and "Arias the Labrynth Butler" in hand_set and any(card in welcome_cards for card in hand_set)
        ),
    }

def _define_combo_card_map():
    """Maps HARDCODED combo names to the set of cards involved for recommendations."""
    # NOTE: This currently only maps hardcoded combos. Recommendations for custom combos are not generated.
    return {
        "Furniture + Back Jack": {"Labrynth Stovie Torbie", "Labrynth Chandraglier", "Absolute King Back Jack"},
        "Arias + Disruption Trap": {"Arias the Labrynth Butler", "Trap Trick", "Destructive Daruma Karma Cannon", "Dimensional Barrier"},
        "Rollback Combo": {"Dominus Impulse", "Transaction Rollback", "Labrynth Stovie Torbie", "Labrynth Chandraglier"},
        "Access to Furniture + Back Jack": {"Arias the Labrynth Butler", "Arianna the Labrynth Servant", "Welcome Labrynth", "Big Welcome Labrynth", "Absolute King Back Jack"},
        "Furniture Combo": {"Labrynth Stovie Torbie", "Labrynth Chandraglier", "Labrynth Cooclock"},
        "Lady Combo": {"Lady Labrynth of the Silver Castle", "Arias the Labrynth Butler", "Welcome Labrynth", "Big Welcome Labrynth"}
    }

def _get_hardcoded_combo_definitions():
    """Returns the hardcoded combo logic in the structured dictionary format."""
    # Manual translation of the lambda logic from _define_combos()
    return {
        "Furniture + Back Jack": {
            "must_have": ["Absolute King Back Jack"],
            "need_one_groups": [
                ["Labrynth Stovie Torbie", "Labrynth Chandraglier"] # Need one of these
            ]
        },
        "Arias + Disruption Trap": {
            "must_have": ["Arias the Labrynth Butler"],
            "need_one_groups": [
                ["Trap Trick", "Destructive Daruma Karma Cannon", "Dimensional Barrier"] # Need one of these
            ]
        },
        "Rollback Combo": {
            "must_have": ["Dominus Impulse", "Transaction Rollback"],
            "need_one_groups": [
                ["Labrynth Stovie Torbie", "Labrynth Chandraglier"] # Need one of these
            ]
        },
        "Access to Furniture + Back Jack": {
            "must_have": ["Arias the Labrynth Butler", "Absolute King Back Jack"],
            "need_one_groups": [
                 ["Arianna the Labrynth Servant", "Welcome Labrynth", "Big Welcome Labrynth"] # Need one of these
            ]
        },
        "Furniture Combo": {
            "must_have": ["Labrynth Cooclock"],
            "need_one_groups": [
                ["Labrynth Stovie Torbie", "Labrynth Chandraglier"] # Need one of these
            ]
        },
        "Lady Combo": {
            "must_have": ["Lady Labrynth of the Silver Castle", "Arias the Labrynth Butler"],
            "need_one_groups": [
                ["Welcome Labrynth", "Big Welcome Labrynth"] # Need one of these
            ]
        },
    }

# <<< NEW FUNCTION for evaluating custom combo structure >>>
def evaluate_custom_combo(hand_set, combo_definition):
    """
    Evaluates if a hand satisfies a structured custom combo definition.

    Args:
        hand_set (set): A set of card names in the current hand.
        combo_definition (dict): The combo definition dictionary with
                                 'must_have' (list) and 'need_one_groups' (list of lists).

    Returns:
        bool: True if the combo conditions are met, False otherwise.
    """
    # 1. Check "Must Have" cards (AND logic)
    must_have_cards = combo_definition.get("must_have", [])
    if not hand_set.issuperset(must_have_cards):
        return False # Missing a required card

    # 2. Check "Need One Groups" (AND logic between groups, OR logic within groups)
    need_one_groups = combo_definition.get("need_one_groups", [])
    for group in need_one_groups:
        # Check if at least one card from this group is in the hand
        found_one_in_group = False
        for card in group:
            if card in hand_set:
                found_one_in_group = True
                break # Found one, no need to check rest of this group
        if not found_one_in_group:
            return False # This group's requirement (at least one) was not met

    # 3. If all checks passed
    return True
# <<< END NEW FUNCTION >>>


# --- Simulation Core ---

def run_simulation(num_simulations, deck_list, deck_label, card_combos, card_categories, simulation_queue):
    """Performs the Monte Carlo simulation for a given deck list."""
    if not deck_list or sum(deck_list.values()) < MIN_DECK_SIZE:
        simulation_queue.put(("error", f"Deck {deck_label} invalid for simulation."))
        return None

    cards = []
    for card, quantity in deck_list.items():
        if card not in CARD_POOL:
            print(f"Warning (Sim {deck_label}): Card '{card}' not in CARD_POOL.")
        cards.extend([card] * quantity)

    if len(cards) < 5:
        simulation_queue.put(("error", f"Deck {deck_label} has only {len(cards)} cards, cannot draw 5."))
        return None

    all_results = {
        "hands": [], "card_counts": Counter(), "combo_counts": Counter(),
        "duplicate_counts": Counter(), "hand_composition_counts": Counter(),
        "category_counts": Counter(),
        "hand_category_composition_counts": Counter(),
    }
    sim_count = 0
    update_interval = max(1, num_simulations // 100)

    for i in range(num_simulations):
        try:
            random.shuffle(cards)
            hand = cards[:5]
            hand_set = set(hand) # Use set for efficient checking
            all_results["hands"].append(hand)
            all_results["card_counts"].update(hand)

            # --- Combo Checking (Handles hardcoded lambdas and custom dicts) ---
            for combo_name, definition in card_combos.items():
                combo_success = False
                try:
                    if callable(definition): # Hardcoded lambda function
                        combo_success = definition(hand_set)
                    elif isinstance(definition, dict): # Custom structured combo
                        combo_success = evaluate_custom_combo(hand_set, definition)
                    else:
                        print(f"Warning: Unknown combo definition type for '{combo_name}'")

                    if combo_success:
                        all_results["combo_counts"][combo_name] += 1
                except Exception as e:
                    print(f"Error evaluating combo '{combo_name}': {e}")
            # --- End Combo Checking ---

            hand_counts = Counter(hand)
            all_results["duplicate_counts"].update(c for c, count in hand_counts.items() if count > 1)

            m, s, t = 0, 0, 0
            for card_in_hand in hand:
                card_type = CARD_TYPES.get(card_in_hand, "UNKNOWN")
                if card_type == "MONSTER": m += 1
                elif card_type == "SPELL": s += 1
                elif card_type == "TRAP": t += 1
            all_results["hand_composition_counts"][f"M:{m} S:{s} T:{t}"] += 1

            # --- Category Analysis (Corrected Logic) ---
            hand_categories_found = []
            category_composition_counter = Counter()
            uncategorized_count = 0
            for card_in_hand in hand:
                categories_for_card = card_categories.get(card_in_hand, [])
                if categories_for_card:
                    hand_categories_found.extend(categories_for_card)
                    for category in categories_for_card:
                         category_composition_counter[category] += 1
                else: uncategorized_count += 1
            all_results["category_counts"].update(hand_categories_found)
            comp_parts = [f"{cat}:{count}" for cat, count in sorted(category_composition_counter.items())]
            if uncategorized_count > 0: comp_parts.append(f"Uncategorized:{uncategorized_count}")
            composition_key = ", ".join(comp_parts) if comp_parts else "Uncategorized Hand"
            all_results["hand_category_composition_counts"][composition_key] += 1
            # --- End Category Analysis ---

            sim_count += 1
            if (i + 1) % update_interval == 0:
                progress = ((i + 1) / num_simulations) * 100
                simulation_queue.put(("status", f"Simulating Deck {deck_label}... {progress:.0f}%"))

        except Exception as e:
            print(f"Error during simulation {i+1} for deck {deck_label}: {e}")

    if sim_count == 0:
        simulation_queue.put(("error", f"No simulations completed for Deck {deck_label}."))
        return None
    return all_results

# --- PDF Generation Core ---

def _create_pdf_table(data, col_widths, style):
    """Helper to create a ReportLab Table, handling empty data."""
    if not data or len(data) <= 1:
        return Paragraph("No data available.", getSampleStyleSheet()['Italic'])
    try:
        table = Table(data, colWidths=col_widths)
        table.setStyle(style)
        return table
    except Exception as e:
        print(f"Error creating PDF table: {e}")
        return Paragraph(f"Error creating table: {e}", getSampleStyleSheet()['Normal'])

def _add_pdf_section(elements, title, data, col_widths, style, styles):
    """Adds a standard section (title, table, spacer) to PDF elements."""
    elements.append(Paragraph(title, styles['h2']))
    table = _create_pdf_table(data, col_widths, style)
    elements.append(table)
    elements.append(Spacer(1, 0.3 * inch))

def analyze_and_generate_pdf(
    results_a, results_b, deck_list_a, deck_list_b,
    submitted_name_a, submitted_name_b, is_comparison,
    # Note: card_combos now contains BOTH hardcoded lambdas and custom dicts
    card_combos, combo_card_map, card_categories, simulation_queue,
    deck_stats_a, deck_stats_b
):
    """Analyzes results and generates PDF. Returns filename or None on failure."""
    if not results_a: simulation_queue.put(("error", "Analysis failed: Missing results A.")); return None
    if is_comparison and not results_b: simulation_queue.put(("error", "Analysis failed: Missing results B.")); return None
    total_simulations = len(results_a.get("hands", []))
    if total_simulations == 0: simulation_queue.put(("error", "Analysis failed: Zero simulations recorded.")); return None

    # --- Filename Setup ---
    no_deck_a_placeholder = "deck_a"; no_deck_b_placeholder = "deck_b"
    name_a = os.path.splitext(submitted_name_a)[0] if submitted_name_a != "No Deck Selected (A)" else no_deck_a_placeholder
    base_filename = f"analysis_{name_a}"
    if is_comparison:
        name_b = os.path.splitext(submitted_name_b)[0] if submitted_name_b != "No Deck Selected (B)" else no_deck_b_placeholder
        base_filename = f"comparison_{name_a}_vs_{name_b}"
    try:
        output_dir = "analysis_reports"; os.makedirs(output_dir, exist_ok=True)
        full_base_path = os.path.join(output_dir, base_filename)
        filename = get_unique_filename(full_base_path + ".pdf")
        doc = SimpleDocTemplate(filename, pagesize=letter)
    except Exception as e: simulation_queue.put(("error", f"Failed PDF setup '{base_filename}.pdf': {e}")); return None

    # --- PDF Content ---
    styles = getSampleStyleSheet(); elements = []
    elements.append(Paragraph("Deck Analysis - Comparison" if is_comparison else "Deck Analysis", styles['h1']))
    elements.append(Paragraph(f"Deck A: {submitted_name_a}", styles['Normal']))
    if is_comparison: elements.append(Paragraph(f"Deck B: {submitted_name_b}", styles['Normal']))
    elements.append(Paragraph(f"Simulations: {total_simulations:,}", styles['h3']))
    elements.append(Spacer(1, 0.2 * inch))

    # --- Table Style and Widths ---
    common_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkslategray), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey), ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8), ('LEFTPADDING', (0,0), (-1,-1), 4), ('RIGHTPADDING', (0,0),(-1,-1),4),
    ])
    comp_cols = [2.5*inch, 0.8*inch, 0.7*inch, 0.8*inch, 0.7*inch]
    single_cols = [3.5*inch, 1.0*inch, 1.2*inch]
    comp_comp_cols = [1.5*inch, 0.9*inch, 0.8*inch, 0.9*inch, 0.8*inch]
    single_comp_cols = [2.0*inch, 1.5*inch, 1.5*inch]
    cat_freq_comp_cols = [2.5*inch, 0.8*inch, 0.7*inch, 0.8*inch, 0.7*inch]
    cat_freq_single_cols = [3.5*inch, 1.0*inch, 1.2*inch]
    cat_comp_comp_cols = [3.0*inch, 0.8*inch, 0.7*inch, 0.8*inch, 0.7*inch]
    cat_comp_single_cols = [4.0*inch, 1.0*inch, 1.2*inch]

    # --- Generate Tables ---
    try:
        # Card Frequency (Unchanged)
        data = [("Card", "Count (A)", "% (A)", "Count (B)", "% (B)")] if is_comparison else [("Card", "Count", "Percentage")]
        counts_a = results_a.get("card_counts", Counter()); all_cards = set(deck_list_a.keys())
        if is_comparison: all_cards.update(deck_list_b.keys())
        temp_data = []
        for card in sorted(list(all_cards)):
            c_a = counts_a.get(card, 0); p_a = (c_a / total_simulations) * 100
            if is_comparison:
                counts_b = results_b.get("card_counts", Counter()); c_b = counts_b.get(card, 0); p_b = (c_b / total_simulations) * 100
                temp_data.append((card, str(c_a), f"{p_a:.2f}%", str(c_b), f"{p_b:.2f}%"))
            else: temp_data.append((card, str(c_a), f"{p_a:.2f}%"))
        temp_data.sort(key=lambda x: float(x[2].rstrip('%')), reverse=True); data.extend(temp_data)
        _add_pdf_section(elements, "Individual Card Frequency", data, comp_cols if is_comparison else single_cols, common_style, styles)

        # Combo Frequency (Now includes custom combos passed in card_combos)
        data = [("Combo", "Count (A)", "% (A)", "Count (B)", "% (B)")] if is_comparison else [("Combo", "Count", "Percentage")]
        combos_a = results_a.get("combo_counts", Counter())
        all_defined = set(card_combos.keys()) # Use keys from the passed dict
        all_defined.update(combos_a.keys())
        if is_comparison: all_defined.update(results_b.get("combo_counts", Counter()).keys())
        temp_data = []
        for combo in sorted(list(all_defined)):
            c_a = combos_a.get(combo, 0); p_a = (c_a / total_simulations) * 100
            if is_comparison:
                combos_b = results_b.get("combo_counts", Counter()); c_b = combos_b.get(combo, 0); p_b = (c_b / total_simulations) * 100
                temp_data.append((combo, str(c_a), f"{p_a:.2f}%", str(c_b), f"{p_b:.2f}%"))
            else: temp_data.append((combo, str(c_a), f"{p_a:.2f}%"))
        temp_data.sort(key=lambda x: float(x[2].rstrip('%')), reverse=True); data.extend(temp_data)
        _add_pdf_section(elements, "Combo Frequency", data, comp_cols if is_comparison else single_cols, common_style, styles)

        # Duplicate Frequency (Unchanged)
        data = [("Card", "Count (A)", "% (A)", "Count (B)", "% (B)")] if is_comparison else [("Card", "Count", "Percentage")]
        dupes_a = results_a.get("duplicate_counts", Counter()); all_dupes = set(dupes_a.keys())
        if is_comparison: all_dupes.update(results_b.get("duplicate_counts", Counter()).keys())
        temp_data = []
        for card in sorted(list(all_dupes)):
            c_a = dupes_a.get(card, 0); p_a = (c_a / total_simulations) * 100
            if is_comparison:
                dupes_b = results_b.get("duplicate_counts", Counter()); c_b = dupes_b.get(card, 0); p_b = (c_b / total_simulations) * 100
                temp_data.append((card, str(c_a), f"{p_a:.2f}%", str(c_b), f"{p_b:.2f}%"))
            else: temp_data.append((card, str(c_a), f"{p_a:.2f}%"))
        temp_data.sort(key=lambda x: float(x[2].rstrip('%')), reverse=True); data.extend(temp_data)
        _add_pdf_section(elements, "Duplicate Card Frequency (Opening Hand)", data, comp_cols if is_comparison else single_cols, common_style, styles)

        # Hand Composition (M/S/T) (Unchanged)
        data = [("Composition", "Count (A)", "% (A)", "Count (B)", "% (B)")] if is_comparison else [("Composition", "Count", "Percentage")]
        comp_a = results_a.get("hand_composition_counts", Counter()); all_comps = set(comp_a.keys())
        if is_comparison: all_comps.update(results_b.get("hand_composition_counts", Counter()).keys())
        temp_data = []
        for comp in sorted(list(all_comps)):
            c_a = comp_a.get(comp, 0); p_a = (c_a / total_simulations) * 100
            if is_comparison:
                comp_b = results_b.get("hand_composition_counts", Counter()); c_b = comp_b.get(comp, 0); p_b = (c_b / total_simulations) * 100
                temp_data.append((comp, str(c_a), f"{p_a:.2f}%", str(c_b), f"{p_b:.2f}%"))
            else: temp_data.append((comp, str(c_a), f"{p_a:.2f}%"))
        temp_data.sort(key=lambda x: float(x[2].rstrip('%')), reverse=True); data.extend(temp_data)
        _add_pdf_section(elements, "Opening Hand Composition (M/S/T)", data, comp_comp_cols if is_comparison else single_comp_cols, common_style, styles)

        # Individual Category Frequency (Unchanged)
        data = [("Category", "Count (A)", "% (A)", "Count (B)", "% (B)")] if is_comparison else [("Category", "Count", "Percentage")]
        cats_a = results_a.get("category_counts", Counter()); all_cats = set(cats_a.keys())
        if is_comparison: all_cats.update(results_b.get("category_counts", Counter()).keys())
        temp_data = []
        for cat in sorted(list(all_cats)):
            c_a = cats_a.get(cat, 0); p_a = (c_a / total_simulations) * 100
            if is_comparison:
                cats_b = results_b.get("category_counts", Counter()); c_b = cats_b.get(cat, 0); p_b = (c_b / total_simulations) * 100
                temp_data.append((cat, str(c_a), f"{p_a:.2f}%", str(c_b), f"{p_b:.2f}%"))
            else: temp_data.append((cat, str(c_a), f"{p_a:.2f}%"))
        temp_data.sort(key=lambda x: x[0]); data.extend(temp_data)
        _add_pdf_section(elements, "Individual Category Frequency (Avg per Hand)", data, cat_freq_comp_cols if is_comparison else cat_freq_single_cols, common_style, styles)

        # Hand Category Composition (Unchanged)
        data = [("Category Composition", "Count (A)", "% (A)", "Count (B)", "% (B)")] if is_comparison else [("Category Composition", "Count", "Percentage")]
        cat_comp_a = results_a.get("hand_category_composition_counts", Counter()); all_cat_comps = set(cat_comp_a.keys())
        if is_comparison: all_cat_comps.update(results_b.get("hand_category_composition_counts", Counter()).keys())
        temp_data = []
        for comp_key in sorted(list(all_cat_comps)):
            c_a = cat_comp_a.get(comp_key, 0); p_a = (c_a / total_simulations) * 100
            if is_comparison:
                cat_comp_b = results_b.get("hand_category_composition_counts", Counter()); c_b = cat_comp_b.get(comp_key, 0); p_b = (c_b / total_simulations) * 100
                temp_data.append((comp_key, str(c_a), f"{p_a:.2f}%", str(c_b), f"{p_b:.2f}%"))
            else: temp_data.append((comp_key, str(c_a), f"{p_a:.2f}%"))
        temp_data.sort(key=lambda x: float(x[2].rstrip('%')), reverse=True); data.extend(temp_data)
        _add_pdf_section(elements, "Hand Category Composition", data, cat_comp_comp_cols if is_comparison else cat_comp_single_cols, common_style, styles)

    except Exception as e:
        elements.append(Paragraph(f"Error generating report tables: {e}", styles['Normal']))
        print(f"Error during PDF table generation: {e}")

    # --- Insights ---
    if is_comparison:
        elements.append(Paragraph("Insights and Analysis", styles['h2']))
        try:
            # Pass deck_stats_a and deck_stats_b here
            insights = generate_insights(results_a, results_b, deck_list_a, deck_list_b, total_simulations, card_combos, combo_card_map, card_categories, deck_stats_a, deck_stats_b)
            if insights:
                for insight in insights:
                    if isinstance(insight, str):
                        if insight == "--- Deck Composition Ratios ---": elements.append(Spacer(1, 0.2 * inch)); elements.append(Paragraph(insight, styles['h3']))
                        elif insight == "--- Category Frequency Comparison (Avg per Hand) ---": elements.append(Spacer(1, 0.2 * inch)); elements.append(Paragraph(insight, styles['h3']))
                        elif insight.strip().startswith("->"): elements.append(Paragraph(insight, styles['Bullet'], bulletText='• '))
                        else: elements.append(Paragraph(insight, styles['Normal'])); elements.append(Spacer(1, 0.1 * inch))
            else: elements.append(Paragraph("No insights generated.", styles['Normal']))
        except Exception as e:
            elements.append(Paragraph(f"Error generating insights section: {e}", styles['Normal']))
            print(f"Error during insight generation/processing: {e}")
        elements.append(Spacer(1, 0.2*inch))

    # --- Build PDF ---
    try:
        doc.build(elements)
        return filename # Return filename on success
    except Exception as e:
        simulation_queue.put(("error", f"Failed to build PDF document '{filename}': {e}"))
        return None # Return None on failure

# --- Insight Generation Logic ---

def generate_insights(results_a, results_b, deck_list_a, deck_list_b, total_simulations, card_combos, combo_card_map, card_categories, deck_stats_a, deck_stats_b):
    """Generates textual insights comparing two simulation results."""
    insights = [];
    if total_simulations == 0: return ["No simulations run."]
    results_a_combos = results_a.get("combo_counts", Counter()); results_b_combos = results_b.get("combo_counts", Counter())

    # --- Combo Insights (Uses combined hardcoded + custom combo keys) ---
    all_defined_combos = set(card_combos.keys()); all_found_combos = set(results_a_combos.keys()) | set(results_b_combos.keys())
    combos_to_analyze = sorted(list(all_defined_combos | all_found_combos))
    for combo in combos_to_analyze:
        count_a = results_a_combos.get(combo, 0); percentage_a = (count_a / total_simulations) * 100
        count_b = results_b_combos.get(combo, 0); percentage_b = (count_b / total_simulations) * 100
        better_list, worse_list, better_label, worse_label = None, None, None, None
        if abs(percentage_a - percentage_b) < 0.01: insights.append(f"'{combo}': Similar draw chance ({percentage_a:.2f}%).")
        elif percentage_a > percentage_b: better_list, worse_list, better_label, worse_label = deck_list_a, deck_list_b, "A", "B"; insights.append(f"'{combo}': Deck A higher ({percentage_a:.2f}%) vs Deck B ({percentage_b:.2f}%).")
        else: better_list, worse_list, better_label, worse_label = deck_list_b, deck_list_a, "B", "A"; insights.append(f"'{combo}': Deck B higher ({percentage_b:.2f}%) vs Deck A ({percentage_a:.2f}%).")
        # Recommendations only work for hardcoded combos until combo_card_map is dynamic
        if better_list is not None and combo in combo_card_map:
            recs = get_combo_recommendations(combo, better_list, worse_list, better_label, worse_label, combo_card_map)
            insights.extend(recs)
    insights.append("")

    # --- Category Insights ---
    insights.append("--- Category Frequency Comparison (Avg per Hand) ---")
    results_a_cats = results_a.get("category_counts", Counter()); results_b_cats = results_b.get("category_counts", Counter())
    all_cats = sorted(list(set(results_a_cats.keys()) | set(results_b_cats.keys())))
    for cat in all_cats:
        count_a = results_a_cats.get(cat, 0); percentage_a = (count_a / total_simulations) * 100
        count_b = results_b_cats.get(cat, 0); percentage_b = (count_b / total_simulations) * 100
        if abs(percentage_a - percentage_b) < 0.1: insights.append(f"'{cat}': Similar avg frequency (~{percentage_a:.2f}%).")
        elif percentage_a > percentage_b: insights.append(f"'{cat}': Deck A higher avg ({percentage_a:.2f}%) vs Deck B ({percentage_b:.2f}%).")
        else: insights.append(f"'{cat}': Deck B higher avg ({percentage_b:.2f}%) vs Deck A ({percentage_a:.2f}%).")

    # --- Composition Insights ---
    insights.append("--- Deck Composition Ratios ---")
    total_a, m_a, s_a, t_a = deck_stats_a.get('total',0), deck_stats_a.get('M',0), deck_stats_a.get('S',0), deck_stats_a.get('T',0)
    if deck_stats_b and isinstance(deck_stats_b, dict): total_b, m_b, s_b, t_b = deck_stats_b.get('total',0), deck_stats_b.get('M',0), deck_stats_b.get('S',0), deck_stats_b.get('T',0)
    else: total_b, m_b, s_b, t_b = 0, 0, 0, 0
    r_m_a=(m_a/total_a*100) if total_a else 0; r_s_a=(s_a/total_a*100) if total_a else 0; r_t_a=(t_a/total_a*100) if total_a else 0
    r_m_b=(m_b/total_b*100) if total_b else 0; r_s_b=(s_b/total_b*100) if total_b else 0; r_t_b=(t_b/total_b*100) if total_b else 0
    insights.append(f"Deck A ({total_a} cards): {m_a} M ({r_m_a:.1f}%) / {s_a} S ({r_s_a:.1f}%) / {t_a} T ({r_t_a:.1f}%)")
    insights.append(f"Deck B ({total_b} cards): {m_b} M ({r_m_b:.1f}%) / {s_b} S ({r_s_b:.1f}%) / {t_b} T ({r_t_b:.1f}%)")
    return insights

def get_combo_recommendations(combo_name, better_list, worse_list, better_label, worse_label, combo_card_map):
    """Generates recommendations based on card counts for a combo."""
    recommendations = []; involved_cards = combo_card_map.get(combo_name)
    if not involved_cards: return []
    for card in involved_cards:
        if card not in CARD_POOL: continue
        count_better = better_list.get(card, 0); count_worse = worse_list.get(card, 0); diff = count_better - count_worse
        if diff > 0: recommendations.append(f"-> Consider +{diff} '{card}' in Deck {worse_label} (has {count_worse}, Deck {better_label} has {count_better}) for '{combo_name}'.")
        elif diff < 0: recommendations.append(f"-> Note: Deck {better_label} (better for '{combo_name}') uses {abs(diff)} fewer '{card}' ({count_better}) than Deck {worse_label} ({count_worse}).")
    return recommendations

# Example test call
if __name__ == '__main__':
    print("Analysis engine module. Run main.py to use the GUI.")

