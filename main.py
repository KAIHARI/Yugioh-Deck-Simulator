import tkinter as tk
from tkinter import ttk, messagebox, filedialog # Added filedialog
import os
import json
import random # Needed for AB Test hand generation and shuffling
from collections import Counter # Needed for AB Test report and potentially main
import re
import threading
import queue
import subprocess # For opening folder
import sys # For platform check

# Required for image handling
try:
    from PIL import Image, ImageTk
except ImportError:
    # Attempt to show Tkinter message box if possible, otherwise print critical error
    try:
        temp_root = tk.Tk(); temp_root.withdraw()
        messagebox.showerror("Missing Library", "Pillow library not found.\nPlease install it using 'pip install Pillow'")
        temp_root.destroy()
    except tk.TclError:
        print("CRITICAL ERROR: Pillow library not found. Please install it using 'pip install Pillow'")
    exit() # Exit if Pillow is missing

# Print statements for debugging environment - can be removed later
print("Python path:", sys.path)
print("Python version:", sys.version)
print("Current working directory:", os.getcwd())

# --- Reportlab and Analysis Engine Import Handling ---
try:
    import reportlab
    print("Reportlab version:", reportlab.__version__)
except ImportError as e:
    print("Detailed error:", str(e))
    script_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
        print(f"Added script directory to path: {script_dir}")
    try:
        import reportlab
        print("Reportlab version:", reportlab.__version__)
    except ImportError as e2:
         print("Detailed error after path modification:", str(e2))
         try:
             temp_root = tk.Tk(); temp_root.withdraw()
             messagebox.showerror("Import Error", f"Could not import required library 'reportlab'.\nPlease install it using 'pip install reportlab'.\n\nError: {str(e2)}\nCurrent directory: {os.getcwd()}\nPython Path: {sys.path}", parent=None)
             temp_root.destroy()
         except tk.TclError:
             print(f"CRITICAL ERROR: Could not import required library 'reportlab'. Please install it using 'pip install reportlab'.\nError: {str(e2)}")
         exit()

# --- Local Imports (Card Database, Analysis Engine) ---
try:
    import analysis_engine
except ImportError as e:
    print(f"Detailed error importing analysis_engine: {str(e)}")
    try:
        temp_root = tk.Tk(); temp_root.withdraw()
        messagebox.showerror("Import Error", f"Could not find analysis_engine.py\nCheck it exists in the same directory as main.py.\n\nError: {e}\nCurrent directory: {os.getcwd()}\nSearch path: {sys.path}", parent=None)
        temp_root.destroy()
    except tk.TclError:
        print(f"CRITICAL ERROR: Could not find analysis_engine.py. Error: {e}")
    exit()

try:
    from card_database import CARD_POOL, CARD_TYPES
except ImportError:
    try:
        temp_root = tk.Tk(); temp_root.withdraw()
        messagebox.showerror("Import Error", f"Could not find card_database.py.\nCheck it exists.\n\nSearch path: {sys.path}", parent=None)
        temp_root.destroy()
    except tk.TclError:
         print(f"CRITICAL ERROR: Could not find card_database.py.")
    exit()
# --------------------------------------

# --- Constants ---
DEFAULT_SIMULATIONS = 100000
MIN_DECK_SIZE = 40
MAX_DECK_SIZE = 60
MAX_CARD_COPIES = 3
DECKS_DIR = "decks"
CARD_IMAGES_DIR = "card_images" # Directory for card images
NO_DECK_A = "No Deck Selected (A)"
NO_DECK_B = "No Deck Selected (B)"
CATEGORY_FILE = "card_categories.json"
APP_STATE_FILE = "app_state.json"
CUSTOM_COMBO_FILE = "custom_combos.json"
USER_DB_FILE = "user_card_database.json" # Now includes image paths
STATUS_CLEAR_DELAY = 4000

# Ensure card images directory exists
if not os.path.exists(CARD_IMAGES_DIR):
    try:
        os.makedirs(CARD_IMAGES_DIR)
        print(f"Created card images directory: {CARD_IMAGES_DIR}")
    except OSError as e:
        messagebox.showwarning("Directory Error", f"Could not create card images directory '{CARD_IMAGES_DIR}'.\nImage loading may fail.\nError: {e}")


# --- Category Management Window ---
# (No changes needed in this class for image support)
class CategoryManagerWindow(tk.Toplevel):
    """A Toplevel window for managing card categories."""
    def __init__(self, parent, card_pool):
        super().__init__(parent)
        self.parent_app = parent # Reference to the main DeckSimulatorApp
        self.card_pool = card_pool # Store the passed card_pool
        self.card_categories = self._load_categories() # Load initial data
        self.selected_card = tk.StringVar()
        self.selected_category = tk.StringVar()
        self.new_category_var = tk.StringVar()
        self.title("Card Category Manager")
        self.geometry("700x550")
        self.transient(parent) # Keep on top of parent
        self.grab_set() # Make modal
        self._setup_category_gui()
        self._populate_lists()

    def _load_categories(self):
        """Loads categories from file, filtering by the current effective card pool."""
        categories = {}
        try:
            if os.path.exists(CATEGORY_FILE):
                with open(CATEGORY_FILE, 'r') as f: data = json.load(f)
                if isinstance(data, dict):
                    for card, value in data.items():
                        if card not in self.card_pool: continue # Filter by pool
                        if isinstance(value, list):
                            valid_cats = sorted(list(set(str(cat) for cat in value if isinstance(cat, str))))
                            if valid_cats: categories[card] = valid_cats
                        elif isinstance(value, str):
                            print(f"Info: Converting old category format for '{card}'.")
                            categories[card] = [value]
                        else: print(f"Warn: Invalid category data type for '{card}' in {CATEGORY_FILE}")
                    return categories
                else: print(f"Warn: {CATEGORY_FILE} content is not a dictionary. Ignoring."); return {}
            else: return {} # File not found
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error loading categories: {e}")
            messagebox.showerror("Load Error", f"Failed to load categories from {CATEGORY_FILE}:\n{e}", parent=self)
            return {}

    def _save_categories(self):
        """Saves categories to file, ensuring only cards from the current pool are included."""
        try:
            cleaned_categories = {card: cats for card, cats in self.card_categories.items() if card in self.card_pool and cats}
            with open(CATEGORY_FILE, 'w') as f:
                json.dump(cleaned_categories, f, indent=4, sort_keys=True)
            print(f"Categories saved to {CATEGORY_FILE}")
            if hasattr(self.parent_app, 'load_card_categories'):
                self.parent_app.load_card_categories()
            messagebox.showinfo("Saved", f"Categories saved to {CATEGORY_FILE}.\nMain application reloaded categories.", parent=self)
        except Exception as e:
            print(f"Error saving categories: {e}")
            messagebox.showerror("Save Error", f"Failed to save categories to {CATEGORY_FILE}:\n{e}", parent=self)

    def _setup_category_gui(self):
        """Creates the GUI elements for the category manager."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(expand=True, fill="both")
        main_frame.columnconfigure(1, weight=1); main_frame.columnconfigure(3, weight=1)
        main_frame.rowconfigure(1, weight=1)

        ttk.Label(main_frame, text="Available Cards (in current pool):").grid(row=0, column=0, columnspan=2, pady=(0, 5), sticky="w")
        self.card_listbox = tk.Listbox(main_frame, width=40, exportselection=False)
        self.card_listbox.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        card_scroll = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.card_listbox.yview)
        card_scroll.grid(row=1, column=1, padx=(0,5), pady=5, sticky="nse")
        self.card_listbox.config(yscrollcommand=card_scroll.set)
        self.card_listbox.bind('<<ListboxSelect>>', self._on_card_select)

        ttk.Label(main_frame, text="Defined Categories:").grid(row=0, column=2, columnspan=2, pady=(0, 5), sticky="w")
        self.category_listbox = tk.Listbox(main_frame, width=30, exportselection=False)
        self.category_listbox.grid(row=1, column=2, columnspan=2, padx=5, pady=5, sticky="nsew")
        cat_scroll = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.category_listbox.yview)
        cat_scroll.grid(row=1, column=3, padx=(0,5), pady=5, sticky="nse")
        self.category_listbox.config(yscrollcommand=cat_scroll.set)
        self.category_listbox.bind('<<ListboxSelect>>', self._on_category_select)

        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=4, pady=10, sticky="ew")
        control_frame.columnconfigure(1, weight=1)
        ttk.Label(control_frame, text="New Category:").pack(side="left", padx=(0, 5))
        new_cat_entry = ttk.Entry(control_frame, textvariable=self.new_category_var, width=20)
        new_cat_entry.pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(control_frame, text="Add Cat", command=self._add_category, width=8).pack(side="left", padx=5)
        ttk.Button(control_frame, text="Del Cat", command=self._remove_category, width=8).pack(side="left", padx=(5, 20))

        assign_frame = ttk.Frame(main_frame)
        assign_frame.grid(row=3, column=0, columnspan=4, pady=5, sticky="ew")
        self.assign_button = ttk.Button(assign_frame, text="Assign Card to Category", command=self._assign_card, state="disabled", width=25)
        self.assign_button.pack(side="left", padx=5)
        self.unassign_button = ttk.Button(assign_frame, text="Unassign Card from Category", command=self._unassign_card, state="disabled", width=25)
        self.unassign_button.pack(side="left", padx=5)

        self.selection_label = ttk.Label(main_frame, text="Select a card and a category.", anchor="w")
        self.selection_label.grid(row=4, column=0, columnspan=4, pady=5, sticky="ew")

        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=5, column=0, columnspan=4, pady=10, sticky="e")
        ttk.Button(bottom_frame, text="Save Categories", command=self._save_categories).pack(side="left", padx=10)
        ttk.Button(bottom_frame, text="Close", command=self.destroy).pack(side="left", padx=10)

    def _populate_lists(self):
        """Populates the card and category listboxes."""
        self.card_listbox.delete(0, tk.END)
        for card in self.card_pool:
            categories = self.card_categories.get(card, [])
            cat_string = ", ".join(categories)
            display_text = f"{card}" + (f" [{cat_string}]" if cat_string else "")
            self.card_listbox.insert(tk.END, display_text)

        self.category_listbox.delete(0, tk.END)
        all_assigned_cats = set(cat for cats in self.card_categories.values() for cat in cats)
        for category in sorted(list(all_assigned_cats)):
            self.category_listbox.insert(tk.END, category)

        self.selected_card.set("")
        self.selected_category.set("")
        self._update_selection_status()

    def _on_card_select(self, event=None):
        """Handles selection in the card listbox."""
        selection = self.card_listbox.curselection()
        if selection:
            selected_text = self.card_listbox.get(selection[0])
            card_name = selected_text.split(" [")[0]
            self.selected_card.set(card_name)
        else: self.selected_card.set("")
        self._update_selection_status()

    def _on_category_select(self, event=None):
        """Handles selection in the category listbox."""
        selection = self.category_listbox.curselection()
        if selection: self.selected_category.set(self.category_listbox.get(selection[0]))
        else: self.selected_category.set("")
        self._update_selection_status()

    def _update_selection_status(self):
        """Updates the status label and button states based on current selections."""
        card = self.selected_card.get(); category = self.selected_category.get()
        status_text = "Selection: "; can_assign, can_unassign = False, False
        if card:
            status_text += f"Card='{card}'"; current_cats = self.card_categories.get(card, [])
            if category:
                status_text += f", Category='{category}'"
                if category not in current_cats: can_assign = True
                if category in current_cats: can_unassign = True
                self.unassign_button.config(text="Unassign Card from Category")
            else:
                 status_text += ", Category=None"
                 if current_cats: can_unassign = True; self.unassign_button.config(text="Unassign ALL from Card")
                 else: self.unassign_button.config(text="Unassign Card from Category")
        elif category: status_text += f"Card=None, Category='{category}'"; self.unassign_button.config(text="Unassign Card from Category")
        else: status_text = "Select a card and/or category."; self.unassign_button.config(text="Unassign Card from Category")
        self.selection_label.config(text=status_text)
        self.assign_button.config(state="normal" if can_assign else "disabled")
        self.unassign_button.config(state="normal" if can_unassign else "disabled")

    def _add_category(self):
        """Adds a new category name to the list of defined categories."""
        new_cat = self.new_category_var.get().strip()
        if not new_cat: messagebox.showwarning("Invalid Name", "Category name cannot be empty.", parent=self); return
        if new_cat in self.category_listbox.get(0, tk.END): messagebox.showwarning("Duplicate", f"Category '{new_cat}' already exists.", parent=self); return
        self.category_listbox.insert(tk.END, new_cat)
        items = list(self.category_listbox.get(0, tk.END))
        self.category_listbox.delete(0, tk.END)
        for item in sorted(items): self.category_listbox.insert(tk.END, item)
        self.new_category_var.set("")

    def _remove_category(self):
        """Removes a category definition and unassigns it from all cards."""
        selection = self.category_listbox.curselection()
        if not selection: messagebox.showwarning("No Selection", "Select a category from the list to delete.", parent=self); return
        category_to_delete = self.category_listbox.get(selection[0])
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the category '{category_to_delete}'?\nThis will unassign it from ALL cards.", parent=self):
            cards_to_update = [card for card, cat_list in self.card_categories.items() if category_to_delete in cat_list]
            for card in cards_to_update:
                cats = self.card_categories.get(card, [])
                if category_to_delete in cats: cats.remove(category_to_delete)
                if not cats: del self.card_categories[card]
                else: self.card_categories[card] = sorted(cats)
            self.category_listbox.delete(selection[0])
            self.selected_category.set("")
            self._populate_lists()

    def _assign_card(self):
        """Assigns the selected category to the selected card."""
        card = self.selected_card.get(); category = self.selected_category.get()
        if not card or not category: return
        current_cats = self.card_categories.get(card, [])
        if category not in current_cats:
            current_cats.append(category)
            self.card_categories[card] = sorted(current_cats)
        else: messagebox.showinfo("Info", f"Card '{card}' already has category '{category}'.", parent=self); return
        self._sync_card_list_display(card)
        self._update_selection_status()

    def _unassign_card(self):
        """Unassigns the selected category from the selected card, or all categories."""
        card = self.selected_card.get(); category = self.selected_category.get()
        if not card: return
        card_updated = False
        if category:
            current_cats = self.card_categories.get(card, [])
            if category in current_cats:
                current_cats.remove(category)
                if not current_cats:
                    if card in self.card_categories: del self.card_categories[card]
                else: self.card_categories[card] = sorted(current_cats)
                card_updated = True
            else: messagebox.showinfo("Info", f"Card '{card}' is not assigned to category '{category}'.", parent=self); return
        else:
            if card in self.card_categories:
                if messagebox.askyesno("Confirm Unassign All", f"Unassign ALL categories from '{card}'?", parent=self):
                    del self.card_categories[card]
                    card_updated = True
                else: return
            else: messagebox.showinfo("Info", f"Card '{card}' has no categories assigned.", parent=self); return
        if card_updated:
            self._sync_card_list_display(card)
            self._update_selection_status()

    def _sync_card_list_display(self, card_name_to_update):
         """Updates the display text for a specific card in the card listbox."""
         items = list(self.card_listbox.get(0, tk.END))
         for i, item in enumerate(items):
             if item.startswith(card_name_to_update):
                 new_categories = self.card_categories.get(card_name_to_update, [])
                 new_cat_string = ", ".join(new_categories)
                 new_display_text = f"{card_name_to_update}" + (f" [{new_cat_string}]" if new_cat_string else "")
                 self.card_listbox.delete(i)
                 self.card_listbox.insert(i, new_display_text)
                 self.card_listbox.selection_set(i)
                 self.card_listbox.see(i)
                 break
# --- End of CategoryManagerWindow ---


# --- Combo Editor Window ---
# (No changes needed in this class for image support)
class ComboEditorWindow(tk.Toplevel):
    """Toplevel window for creating and editing custom combos."""
    def __init__(self, parent, card_pool, initial_custom_combos, hardcoded_combo_definitions):
        super().__init__(parent)
        self.parent_app = parent
        self.card_pool = card_pool
        self.custom_combos = {name: definition.copy() for name, definition in initial_custom_combos.items()}
        self.hardcoded_combos = hardcoded_combo_definitions
        self.is_editing_default = False
        self.original_loaded_name = None

        self.current_combo_name = tk.StringVar()
        self.selected_combo_in_list = tk.StringVar()
        self.selected_card_from_pool = tk.StringVar()
        self.selected_card_in_must_have = tk.StringVar()
        self.selected_card_in_need_one = tk.StringVar()
        self.selected_need_one_group_index = -1

        self.title("Custom Combo Editor")
        self.geometry("900x650")
        self.transient(parent)
        self.grab_set()

        self._setup_combo_gui()
        self._populate_combo_list()

    def _load_combos_from_file(self):
        """Loads custom combos directly from the JSON file."""
        try:
            if os.path.exists(CUSTOM_COMBO_FILE):
                with open(CUSTOM_COMBO_FILE, 'r') as f: data = json.load(f)
                if isinstance(data, dict): return data
                else: print(f"Warn: {CUSTOM_COMBO_FILE} invalid format."); return {}
            else: return {}
        except Exception as e:
            print(f"Error loading combos from file: {e}")
            if self.winfo_exists(): messagebox.showerror("Load Error", f"Failed to load combos from {CUSTOM_COMBO_FILE}:\n{e}", parent=self)
            return {}

    def _save_combos_to_file(self):
        """Saves the current state of self.custom_combos to the JSON file."""
        try:
            cleaned_combos = {}
            for name, definition in self.custom_combos.items():
                 must_have = definition.get("must_have", [])
                 need_one = [group for group in definition.get("need_one_groups", []) if group]
                 if must_have or need_one:
                     cleaned_must_have = [str(c) for c in must_have]
                     cleaned_need_one = [[str(c) for c in group] for group in need_one]
                     cleaned_combos[name] = {"must_have": cleaned_must_have, "need_one_groups": cleaned_need_one}

            with open(CUSTOM_COMBO_FILE, 'w') as f:
                json.dump(cleaned_combos, f, indent=4, sort_keys=True)

            if hasattr(self.parent_app, 'load_custom_combos'):
                self.parent_app.load_custom_combos()
            else: print("Warn: Main app missing 'load_custom_combos' method.")

            self.update_status("Custom combos saved to file.")
            self._populate_combo_list()

        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save combos to {CUSTOM_COMBO_FILE}:\n{e}", parent=self)
            self.update_status(f"Error saving: {e}", True)

    def _setup_combo_gui(self):
        """Creates the GUI elements for the combo editor."""
        paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(paned_window, padding=5)
        left_frame.columnconfigure(0, weight=1); left_frame.rowconfigure(1, weight=1)
        paned_window.add(left_frame, width=250)
        ttk.Label(left_frame, text="Available Combos").grid(row=0, column=0, sticky="w")
        self.combo_listbox = tk.Listbox(left_frame, exportselection=False)
        self.combo_listbox.grid(row=1, column=0, sticky="nsew", pady=5)
        combo_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.combo_listbox.yview)
        combo_scroll.grid(row=1, column=1, sticky="ns", pady=5)
        self.combo_listbox.config(yscrollcommand=combo_scroll.set)
        self.combo_listbox.bind("<<ListboxSelect>>", self._on_combo_select_from_list)
        combo_buttons_frame = ttk.Frame(left_frame)
        combo_buttons_frame.grid(row=2, column=0, columnspan=2, pady=5)
        ttk.Button(combo_buttons_frame, text="Load/View", command=self._load_selected_combo_to_editor).pack(side="left", padx=2)
        ttk.Button(combo_buttons_frame, text="New Combo", command=self._clear_editor).pack(side="left", padx=2)
        self.delete_combo_button = ttk.Button(combo_buttons_frame, text="Delete Custom", command=self._delete_selected_combo, state="disabled")
        self.delete_combo_button.pack(side="left", padx=2)

        right_frame = ttk.Frame(paned_window, padding=5)
        right_frame.columnconfigure(0, weight=1); right_frame.columnconfigure(1, weight=1)
        right_frame.columnconfigure(2, weight=1); right_frame.columnconfigure(3, weight=1)
        right_frame.rowconfigure(3, weight=1); right_frame.rowconfigure(5, weight=1)
        paned_window.add(right_frame)
        ttk.Label(right_frame, text="Combo Name:").grid(row=0, column=0, sticky="w", pady=2)
        self.combo_name_entry = ttk.Entry(right_frame, textvariable=self.current_combo_name, width=40)
        self.combo_name_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=2, padx=5)
        self.save_update_button = ttk.Button(right_frame, text="Save/Update Definition", command=self._save_editor_combo, width=25, state="disabled")
        self.save_update_button.grid(row=0, column=3, padx=10, sticky="e")
        ttk.Label(right_frame, text="Available Cards Pool:").grid(row=4, column=2, columnspan=2, sticky="sw", pady=(10, 2))
        self.pool_listbox = tk.Listbox(right_frame, width=35, height=10, exportselection=False)
        self.pool_listbox.grid(row=5, column=2, columnspan=2, sticky="nsew", padx=5, pady=5)
        pool_scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.pool_listbox.yview)
        pool_scrollbar.grid(row=5, column=3, sticky="nse", padx=(0,5), pady=5)
        self.pool_listbox.config(yscrollcommand=pool_scrollbar.set)
        self.pool_listbox.bind("<<ListboxSelect>>", self._on_pool_select)
        for card in self.card_pool: self.pool_listbox.insert(tk.END, card)

        must_have_frame = ttk.LabelFrame(right_frame, text="Must Have ALL These Cards (AND)")
        must_have_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=5, padx=5)
        must_have_frame.columnconfigure(0, weight=1); must_have_frame.rowconfigure(0, weight=1)
        self.must_have_listbox = tk.Listbox(must_have_frame, height=5, exportselection=False)
        self.must_have_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        must_have_scroll = ttk.Scrollbar(must_have_frame, orient=tk.VERTICAL, command=self.must_have_listbox.yview)
        must_have_scroll.grid(row=0, column=1, sticky="ns", padx=(0,5), pady=5)
        self.must_have_listbox.config(yscrollcommand=must_have_scroll.set)
        self.must_have_listbox.bind("<<ListboxSelect>>", self._on_must_have_select)
        must_have_buttons = ttk.Frame(must_have_frame)
        must_have_buttons.grid(row=1, column=0, columnspan=2, pady=2)
        self.must_have_add_button = ttk.Button(must_have_buttons, text="Add Selected Card", command=self._add_to_must_have, state="disabled")
        self.must_have_add_button.pack(side="left", padx=5)
        self.must_have_remove_button = ttk.Button(must_have_buttons, text="Remove Selected", command=self._remove_from_must_have, state="disabled")
        self.must_have_remove_button.pack(side="left", padx=5)

        need_one_main_frame = ttk.LabelFrame(right_frame, text="Need AT LEAST ONE From EACH Group Below (AND Groups, OR Cards within Group)")
        need_one_main_frame.grid(row=2, column=0, columnspan=2, rowspan=3, sticky="nsew", pady=5, padx=5)
        need_one_main_frame.columnconfigure(0, weight=1); need_one_main_frame.rowconfigure(1, weight=1)
        need_one_buttons_top = ttk.Frame(need_one_main_frame)
        need_one_buttons_top.grid(row=0, column=0, pady=5, sticky="ew")
        self.need_one_add_group_button = ttk.Button(need_one_buttons_top, text="Add New 'Need One' Group", command=self._add_need_one_group, state="disabled")
        self.need_one_add_group_button.pack(side="left", padx=5)
        self.need_one_remove_group_button = ttk.Button(need_one_buttons_top, text="Remove Selected Group", command=self._remove_selected_need_one_group, state="disabled")
        self.need_one_remove_group_button.pack(side="left", padx=5)
        self.need_one_groups_frame = ttk.Frame(need_one_main_frame)
        self.need_one_groups_frame.grid(row=1, column=0, sticky="nsew")
        self.need_one_groups_frame.columnconfigure(0, weight=1)
        self.need_one_group_listboxes = []
        self.need_one_group_frames = []

        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        ttk.Button(bottom_frame, text="Save All Custom Combos to File", command=self._save_combos_to_file).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="Close Editor", command=self.destroy).pack(side="right", padx=5)
        self.status_label = ttk.Label(bottom_frame, text="Status: Ready", anchor="w")
        self.status_label.pack(side="left", padx=10, fill="x", expand=True)
        self._set_editor_state("disabled")

    def _on_combo_select_from_list(self, event=None):
        """Handles selection in the main combo list."""
        selection = self.combo_listbox.curselection()
        if selection:
            selected_item = self.combo_listbox.get(selection[0])
            self.selected_combo_in_list.set(selected_item)
            is_default = selected_item.endswith(" [Default]")
            self.delete_combo_button.config(state="disabled" if is_default else "normal")
            self.update_status(f"Selected '{selected_item}' from list.")
        else:
            self.selected_combo_in_list.set("")
            self.delete_combo_button.config(state="disabled")
            self.update_status("Combo list selection cleared.")

    def _on_pool_select(self, event=None):
        """Handles selection in the card pool list."""
        selection = self.pool_listbox.curselection()
        if selection:
            self.selected_card_from_pool.set(self.pool_listbox.get(selection[0]))
            if self.save_update_button['state'] == 'normal':
                 self.must_have_add_button.config(state="normal")
                 if self.selected_need_one_group_index != -1:
                      group_frame = self.need_one_group_frames[self.selected_need_one_group_index]
                      add_btn = next((w for w in group_frame.winfo_children() if isinstance(w, ttk.Frame) for w2 in w.winfo_children() if isinstance(w2, ttk.Button) and w2.cget("text")=="Add Card"), None)
                      if add_btn: add_btn.config(state="normal")
        else:
            self.selected_card_from_pool.set("")
            self.must_have_add_button.config(state="disabled")
            for frame in self.need_one_group_frames:
                 add_btn = next((w for w in frame.winfo_children() if isinstance(w, ttk.Frame) for w2 in w.winfo_children() if isinstance(w2, ttk.Button) and w2.cget("text")=="Add Card"), None)
                 if add_btn: add_btn.config(state="disabled")

    def _on_must_have_select(self, event=None):
        """Handles selection in the 'Must Have' list."""
        selection = self.must_have_listbox.curselection()
        if selection:
            self.selected_card_in_must_have.set(self.must_have_listbox.get(selection[0]))
            self.must_have_remove_button.config(state="normal")
        else:
            self.selected_card_in_must_have.set("")
            self.must_have_remove_button.config(state="disabled")

    def _on_need_one_select(self, event, group_index):
        """Handles selection within a 'Need One' group listbox."""
        listbox = event.widget; selection = listbox.curselection()
        for i, lb in enumerate(self.need_one_group_listboxes):
            if i != group_index:
                lb.selection_clear(0, tk.END)
                other_frame = self.need_one_group_frames[i]
                remove_btn = next((w for w in other_frame.winfo_children() if isinstance(w, ttk.Frame) for w2 in w.winfo_children() if isinstance(w2, ttk.Button) and w2.cget("text")=="Remove Card"), None)
                if remove_btn: remove_btn.config(state="disabled")
        current_frame = self.need_one_group_frames[group_index]
        current_remove_btn = next((w for w in current_frame.winfo_children() if isinstance(w, ttk.Frame) for w2 in w.winfo_children() if isinstance(w2, ttk.Button) and w2.cget("text")=="Remove Card"), None)
        if selection:
            self.selected_card_in_need_one.set(listbox.get(selection[0]))
            self.selected_need_one_group_index = group_index
            if current_remove_btn: current_remove_btn.config(state="normal")
            self.need_one_remove_group_button.config(state="normal")
        else:
            self.selected_card_in_need_one.set("")
            self.selected_need_one_group_index = -1
            if current_remove_btn: current_remove_btn.config(state="disabled")
            self.need_one_remove_group_button.config(state="disabled")

    def _clear_editor(self):
        """Clears the editor fields to start defining a new combo."""
        self.current_combo_name.set(""); self.original_loaded_name = None
        self.must_have_listbox.delete(0, tk.END)
        for frame in self.need_one_group_frames: frame.destroy()
        self.need_one_group_frames = []; self.need_one_group_listboxes = []
        self.selected_need_one_group_index = -1
        self.selected_card_in_must_have.set(""); self.selected_card_in_need_one.set("")
        self.selected_card_from_pool.set("")
        self.is_editing_default = False
        self._set_editor_state("normal")
        self.combo_name_entry.focus_set()
        self.update_status("Editor cleared. Ready for new combo definition.")

    def _load_selected_combo_to_editor(self):
        """Loads the definition of the selected combo into the editor fields."""
        selected_item = self.selected_combo_in_list.get()
        if not selected_item: messagebox.showwarning("Load Error", "Select a combo from the list first.", parent=self); return
        is_default = selected_item.endswith(" [Default]")
        combo_name = selected_item.replace(" [Default]", "").strip() if is_default else selected_item
        definition = self.hardcoded_combos.get(combo_name) if is_default else self.custom_combos.get(combo_name)
        if not definition: messagebox.showerror("Load Error", f"Could not find definition for '{combo_name}'.", parent=self); self._clear_editor(); return
        self._clear_editor()
        self.current_combo_name.set(combo_name); self.original_loaded_name = combo_name
        self.is_editing_default = is_default
        for card in definition.get("must_have", []):
            if card in self.card_pool: self.must_have_listbox.insert(tk.END, card)
            else: print(f"Warning: Card '{card}' in combo '{combo_name}' (Must Have) not found in pool, skipping.")
        for group in definition.get("need_one_groups", []):
            valid_group_cards = [c for c in group if c in self.card_pool]
            if valid_group_cards: self._add_need_one_group(populate_list=valid_group_cards)
            elif group: print(f"Warning: Need one group {group} in combo '{combo_name}' has no valid cards in pool, skipping group.")
        self._set_editor_state("normal")
        status_prefix = "Viewing/Editing Default" if self.is_editing_default else "Editing Custom"
        self.update_status(f"{status_prefix}: {combo_name}")

    def _set_editor_state(self, state):
         """Enables or disables the editor widgets."""
         entry_state = "normal"; button_state = state
         self.combo_name_entry.config(state=entry_state)
         self.save_update_button.config(state=button_state)
         self.must_have_listbox.config(state=button_state)
         self.must_have_add_button.config(state="disabled")
         self.must_have_remove_button.config(state="disabled")
         self.need_one_add_group_button.config(state=button_state)
         self.need_one_remove_group_button.config(state="disabled")
         for frame in self.need_one_group_frames:
              listbox = next((w for w in frame.winfo_children() if isinstance(w, tk.Listbox)), None)
              button_frame = next((w for w in frame.winfo_children() if isinstance(w, ttk.Frame)), None)
              if listbox: listbox.config(state=button_state)
              if button_frame:
                  add_card_btn = next((w for w in button_frame.winfo_children() if isinstance(w, ttk.Button) and w.cget("text")=="Add Card"), None)
                  remove_card_btn = next((w for w in button_frame.winfo_children() if isinstance(w, ttk.Button) and w.cget("text")=="Remove Card"), None)
                  if add_card_btn: add_card_btn.config(state="disabled")
                  if remove_card_btn: remove_card_btn.config(state="disabled")
         if state == "disabled":
              self.pool_listbox.selection_clear(0, tk.END)
              self.must_have_listbox.selection_clear(0, tk.END)
              for lb in self.need_one_group_listboxes: lb.selection_clear(0, tk.END)
              self._on_pool_select(); self._on_must_have_select()
              if self.selected_need_one_group_index != -1:
                   fake_event = tk.Event(); fake_event.widget = self.need_one_group_listboxes[self.selected_need_one_group_index]
                   self._on_need_one_select(fake_event, self.selected_need_one_group_index)

    def _save_editor_combo(self):
        """Saves the current editor definition to the self.custom_combos dictionary."""
        combo_name = self.current_combo_name.get().strip()
        if not combo_name: messagebox.showerror("Save Error", "Combo Name cannot be empty.", parent=self); return
        # --- Validation and Confirmation ---
        if self.original_loaded_name and self.original_loaded_name != combo_name and self.original_loaded_name in self.custom_combos:
             if combo_name in self.custom_combos:
                  if not messagebox.askyesno("Confirm Overwrite", f"A custom combo named '{combo_name}' already exists.\nOverwrite it?", parent=self): return
             elif combo_name in self.hardcoded_combos:
                  if not messagebox.askyesno("Confirm Name Conflict", f"New name '{combo_name}' conflicts with a default combo.\nSave anyway?", parent=self): return
        elif combo_name in self.custom_combos and not self.is_editing_default and self.original_loaded_name == combo_name:
             if not messagebox.askyesno("Confirm Update", f"Update the custom combo '{combo_name}'?", parent=self): return
        elif combo_name in self.hardcoded_combos:
             if self.is_editing_default:
                  if combo_name in self.custom_combos:
                       if not messagebox.askyesno("Confirm Overwrite", f"Custom definition for '{combo_name}' exists.\nOverwrite it?", parent=self): return
             elif self.original_loaded_name != combo_name:
                  if not messagebox.askyesno("Confirm Name Conflict", f"Name '{combo_name}' conflicts with a default combo.\nSave anyway?", parent=self): return
        # --- Prepare Definition ---
        must_have = list(self.must_have_listbox.get(0, tk.END))
        need_one = [list(lb.get(0, tk.END)) for lb in self.need_one_group_listboxes if lb.size() > 0]
        if not must_have and not need_one: messagebox.showerror("Save Error", "Combo definition cannot be empty.", parent=self); return
        new_definition = {"must_have": must_have, "need_one_groups": need_one}
        # --- Update Dictionary ---
        if self.original_loaded_name and self.original_loaded_name != combo_name and self.original_loaded_name in self.custom_combos:
             del self.custom_combos[self.original_loaded_name]
        self.custom_combos[combo_name] = new_definition
        # --- Post-Save Updates ---
        self.original_loaded_name = combo_name; self.is_editing_default = False
        self._populate_combo_list()
        try:
             items = list(self.combo_listbox.get(0, tk.END)); idx = items.index(combo_name)
             self.combo_listbox.selection_clear(0, tk.END); self.combo_listbox.selection_set(idx); self.combo_listbox.see(idx)
             self._on_combo_select_from_list()
        except ValueError: print(f"Info: Could not re-select '{combo_name}' in list after save.")
        self.update_status(f"Definition for '{combo_name}' updated in custom list. (Save to file separately)")

    def _delete_selected_combo(self):
        """Deletes the selected custom combo definition."""
        selected_item = self.selected_combo_in_list.get()
        is_default = selected_item.endswith(" [Default]")
        combo_name = selected_item.replace(" [Default]", "").strip() if is_default else selected_item
        if is_default: messagebox.showerror("Delete Error", "Cannot delete default combo definitions.", parent=self); return
        if not combo_name or combo_name not in self.custom_combos: messagebox.showwarning("Delete Error", "Select a custom combo to delete.", parent=self); return
        if messagebox.askyesno("Confirm Delete", f"Delete the custom combo definition for '{combo_name}'?", parent=self):
            del self.custom_combos[combo_name]; self._populate_combo_list()
            if self.current_combo_name.get() == combo_name: self._clear_editor(); self._set_editor_state("disabled")
            self.update_status(f"Deleted custom combo '{combo_name}'. (Save to file separately)")

    def _add_to_must_have(self):
        """Adds the selected card from the pool to the 'Must Have' list."""
        card = self.selected_card_from_pool.get()
        if not card: return
        if card in self.must_have_listbox.get(0, tk.END): messagebox.showinfo("Info", f"'{card}' is already in 'Must Have'.", parent=self); return
        self.must_have_listbox.insert(tk.END, card)

    def _remove_from_must_have(self):
        """Removes the selected card from the 'Must Have' list."""
        selection = self.must_have_listbox.curselection()
        if not selection: return
        self.must_have_listbox.delete(selection[0])
        self.selected_card_in_must_have.set(""); self.must_have_remove_button.config(state="disabled")

    def _add_need_one_group(self, populate_list=None):
        """Adds a new, empty 'Need One' group frame and listbox to the editor."""
        group_index = len(self.need_one_group_frames)
        group_frame = ttk.Frame(self.need_one_groups_frame, borderwidth=1, relief="sunken")
        group_frame.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.BOTH, expand=True)
        self.need_one_group_frames.append(group_frame)
        ttk.Label(group_frame, text=f"Group {group_index + 1} (Need 1+)").pack(anchor="w")
        listbox_frame = ttk.Frame(group_frame); listbox_frame.pack(fill=tk.BOTH, expand=True)
        listbox_frame.rowconfigure(0, weight=1); listbox_frame.columnconfigure(0, weight=1)
        listbox = tk.Listbox(listbox_frame, height=5, width=25, exportselection=False)
        listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        listbox.config(yscrollcommand=scrollbar.set)
        listbox.bind("<<ListboxSelect>>", lambda e, idx=group_index: self._on_need_one_select(e, idx))
        self.need_one_group_listboxes.append(listbox)
        button_frame = ttk.Frame(group_frame); button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=2)
        add_button = ttk.Button(button_frame, text="Add Card", command=lambda idx=group_index: self._add_to_need_one(idx), state="disabled")
        add_button.pack(side="left", padx=2)
        remove_button = ttk.Button(button_frame, text="Remove Card", command=lambda idx=group_index: self._remove_from_need_one(idx), state="disabled")
        remove_button.pack(side="left", padx=2)
        if populate_list:
            for card in populate_list: listbox.insert(tk.END, card)
        editor_state = self.save_update_button['state']
        listbox.config(state=editor_state)

    def _remove_selected_need_one_group(self):
        """Removes the currently selected 'Need One' group."""
        if self.selected_need_one_group_index < 0 or self.selected_need_one_group_index >= len(self.need_one_group_frames): messagebox.showwarning("Selection Error", "Select a card within the group to remove.", parent=self); return
        group_to_remove_index = self.selected_need_one_group_index
        if messagebox.askyesno("Confirm Remove Group", f"Remove 'Need One' Group {group_to_remove_index + 1}?", parent=self):
            self.need_one_group_frames[group_to_remove_index].destroy()
            del self.need_one_group_frames[group_to_remove_index]; del self.need_one_group_listboxes[group_to_remove_index]
            # --- Renumber subsequent groups ---
            for i, frame in enumerate(self.need_one_group_frames[group_to_remove_index:], start=group_to_remove_index):
                 label = next((w for w in frame.winfo_children() if isinstance(w, ttk.Label)), None)
                 if label: label.config(text=f"Group {i + 1} (Need 1+)")
                 listbox = next((w for w in frame.winfo_children() if isinstance(w, ttk.Frame) for w2 in w.winfo_children() if isinstance(w2, tk.Listbox)), None)
                 if listbox: listbox.unbind("<<ListboxSelect>>"); listbox.bind("<<ListboxSelect>>", lambda e, idx=i: self._on_need_one_select(e, idx))
                 button_frame = next((w for w in frame.winfo_children() if isinstance(w, ttk.Frame) and not any(isinstance(w2, tk.Listbox) for w2 in w.winfo_children())), None)
                 if button_frame:
                     add_button = next((w for w in button_frame.winfo_children() if isinstance(w, ttk.Button) and w.cget("text")=="Add Card"), None)
                     remove_button = next((w for w in button_frame.winfo_children() if isinstance(w, ttk.Button) and w.cget("text")=="Remove Card"), None)
                     if add_button: add_button.config(command=lambda idx=i: self._add_to_need_one(idx))
                     if remove_button: remove_button.config(command=lambda idx=i: self._remove_from_need_one(idx))
            # --- End Renumbering ---
            self.selected_need_one_group_index = -1; self.selected_card_in_need_one.set("")
            self.need_one_remove_group_button.config(state="disabled")
            self.update_status("Removed 'Need One' group.")

    def _add_to_need_one(self, group_index):
        """Adds the selected card from the pool to the specified 'Need One' group."""
        card = self.selected_card_from_pool.get();
        if not card: return
        if group_index < 0 or group_index >= len(self.need_one_group_listboxes): print(f"Error: Invalid group index {group_index} for add."); return
        listbox = self.need_one_group_listboxes[group_index]
        if card in listbox.get(0, tk.END): messagebox.showinfo("Info", f"'{card}' is already in this group.", parent=self); return
        listbox.insert(tk.END, card)

    def _remove_from_need_one(self, group_index):
        """Removes the selected card from the specified 'Need One' group list."""
        if group_index < 0 or group_index >= len(self.need_one_group_listboxes): print(f"Error: Invalid group index {group_index} for remove."); return
        listbox = self.need_one_group_listboxes[group_index]; selection = listbox.curselection()
        if not selection: return
        listbox.delete(selection[0]); self.selected_card_in_need_one.set("")
        frame = self.need_one_group_frames[group_index]
        remove_btn = next((w for w in frame.winfo_children() if isinstance(w, ttk.Frame) for w2 in w.winfo_children() if isinstance(w2, ttk.Button) and w2.cget("text")=="Remove Card"), None)
        if remove_btn: remove_btn.config(state="disabled")
        if self.selected_need_one_group_index == group_index: self.need_one_remove_group_button.config(state="disabled"); self.selected_need_one_group_index = -1

    def _populate_combo_list(self):
        """Populates the listbox with available default and custom combos."""
        self.combo_listbox.delete(0, tk.END); added_names = set()
        for name in sorted(self.hardcoded_combos.keys()):
            display_name = f"{name} [Default]"; self.combo_listbox.insert(tk.END, display_name)
            self.combo_listbox.itemconfig(tk.END, {'fg': 'grey'}); added_names.add(name)
        for name in sorted(self.custom_combos.keys()):
            if name in self.hardcoded_combos:
                default_display_name = f"{name} [Default]"
                try:
                    idx = list(self.combo_listbox.get(0, tk.END)).index(default_display_name)
                    self.combo_listbox.delete(idx); self.combo_listbox.insert(idx, name)
                except ValueError:
                    if name not in added_names: self.combo_listbox.insert(tk.END, name); added_names.add(name)
            else:
                if name not in added_names: self.combo_listbox.insert(tk.END, name); added_names.add(name)
        self.selected_combo_in_list.set(""); self.delete_combo_button.config(state="disabled")

    def update_status(self, message, error=False):
        """Updates the status label at the bottom of the editor."""
        prefix = "Error: " if error else "Status: "; self.status_label.config(text=f"{prefix}{message}")
        if error: print(f"COMBO EDITOR ERROR: {message}")
        else: print(f"COMBO EDITOR STATUS: {message}")
# --- End of ComboEditorWindow ---


# --- Card Database Editor Window ---
# Modified to include image path assignment
class CardDatabaseEditorWindow(tk.Toplevel):
    """Toplevel window for editing the effective card database, including image paths."""
    def __init__(self, parent_app):
        super().__init__(parent_app.root)
        self.parent_app = parent_app

        self.base_pool = self.parent_app.base_card_pool
        self.base_types = self.parent_app.base_card_types # Correctly assigned in init
        # Load user data fresh, including image paths
        self.user_data = self._load_user_db()
        self.added_cards = self.user_data.get("added_cards", {})
        self.removed_cards = set(self.user_data.get("removed_cards", []))
        self.type_overrides = self.user_data.get("type_overrides", {})
        self.image_paths = self.user_data.get("image_paths", {}) # Load image paths

        self._calculate_effective_db()

        # UI Variables
        self.selected_card_var = tk.StringVar()
        self.new_card_name_var = tk.StringVar()
        self.new_card_type_var = tk.StringVar(value="MONSTER")
        self.current_image_path_var = tk.StringVar(value="No image set") # Variable for image path label

        self.title("Card Database Editor")
        self.geometry("700x680") # Increased height slightly for scan button
        self.transient(parent_app.root)
        self.grab_set()

        self._setup_editor_gui()
        self._populate_card_list()

    def _load_user_db(self):
        """Loads user additions/removals/overrides/image_paths from JSON."""
        # (Identical to previous version)
        try:
            if os.path.exists(USER_DB_FILE):
                with open(USER_DB_FILE, 'r') as f: data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("added_cards", {}); data.setdefault("removed_cards", [])
                    data.setdefault("type_overrides", {}); data.setdefault("image_paths", {})
                    if not isinstance(data["added_cards"], dict): data["added_cards"] = {}
                    if not isinstance(data["removed_cards"], list): data["removed_cards"] = []
                    if not isinstance(data["type_overrides"], dict): data["type_overrides"] = {}
                    if not isinstance(data["image_paths"], dict): data["image_paths"] = {}
                    data["added_cards"] = {str(k): str(v) for k, v in data["added_cards"].items()}
                    data["removed_cards"] = [str(c) for c in data["removed_cards"]]
                    data["type_overrides"] = {str(k): str(v) for k, v in data["type_overrides"].items()}
                    data["image_paths"] = {str(k): str(v) for k, v in data["image_paths"].items()}
                    return data
                else: print(f"Warn: {USER_DB_FILE} invalid format."); return {"added_cards": {}, "removed_cards": [], "type_overrides": {}, "image_paths": {}}
            else: return {"added_cards": {}, "removed_cards": [], "type_overrides": {}, "image_paths": {}}
        except Exception as e:
            print(f"Error loading user DB from {USER_DB_FILE}: {e}")
            messagebox.showerror("Load Error", f"Failed to load user card data from {USER_DB_FILE}:\n{e}", parent=self)
            return {"added_cards": {}, "removed_cards": [], "type_overrides": {}, "image_paths": {}}

    def _save_user_db(self):
        """Saves current user changes (added, removed, overrides, image_paths) to JSON."""
        # (Identical to previous version)
        self.user_data["added_cards"] = self.added_cards
        self.user_data["removed_cards"] = sorted(list(self.removed_cards))
        self.user_data["type_overrides"] = self.type_overrides
        self.user_data["image_paths"] = self.image_paths # Save image paths
        try:
            with open(USER_DB_FILE, 'w') as f:
                json.dump(self.user_data, f, indent=4, sort_keys=True)
            print(f"User card database changes saved to {USER_DB_FILE}")
            if hasattr(self.parent_app, 'reload_card_database'):
                 self.parent_app.reload_card_database()
                 messagebox.showinfo("Saved", f"Changes saved to {USER_DB_FILE}.\nMain application database reloaded.", parent=self)
            else: messagebox.showwarning("Saved (Warning)", f"Changes saved to {USER_DB_FILE}, but could not trigger automatic reload in main app.", parent=self)
        except Exception as e:
            print(f"Error saving user DB: {e}")
            messagebox.showerror("Save Error", f"Failed to save changes to {USER_DB_FILE}:\n{e}", parent=self)

    def _calculate_effective_db(self):
        """Calculates the effective card pool, types, and image paths."""
        # Pool calculation
        effective_pool_set = self.base_pool.copy(); effective_pool_set.update(self.added_cards.keys())
        effective_pool_set -= self.removed_cards
        self.effective_pool_list = sorted(list(effective_pool_set))

        # Type calculation - uses self.base_types (correctly assigned in __init__)
        effective_types_dict = self.base_types.copy(); effective_types_dict.update(self.added_cards) # <<< CORRECTED LINE
        effective_types_dict.update(self.type_overrides)
        final_types = {}
        for card in self.effective_pool_list:
            if card in effective_types_dict: final_types[card] = effective_types_dict[card]
            else: print(f"Warning: Card '{card}' missing type. Defaulting to MONSTER."); final_types[card] = "MONSTER"
        self.effective_types = final_types

        # Image path calculation
        self.effective_image_paths = {card: path for card, path in self.image_paths.items() if card in self.effective_pool_list}

    def _setup_editor_gui(self):
        """Creates the GUI elements for the database editor."""
        main_frame = ttk.Frame(self, padding="10"); main_frame.pack(expand=True, fill="both")
        main_frame.rowconfigure(1, weight=1); main_frame.columnconfigure(0, weight=1)

        # --- Add Card Frame ---
        add_frame = ttk.LabelFrame(main_frame, text="Add New Card")
        add_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        add_frame.columnconfigure(1, weight=1)
        ttk.Label(add_frame, text="Name:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(add_frame, textvariable=self.new_card_name_var, width=40).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(add_frame, text="Type:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        card_type_values = sorted(list(set(self.base_types.values()) | {"MONSTER", "SPELL", "TRAP"}))
        ttk.Combobox(add_frame, textvariable=self.new_card_type_var, values=card_type_values, state="readonly", width=12).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(add_frame, text="Add Card", command=self._add_card).grid(row=0, column=2, rowspan=2, padx=10, pady=5, sticky="ns")

        # --- List Frame ---
        list_frame = ttk.LabelFrame(main_frame, text="Effective Card Pool (Base + Your Changes)")
        list_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        list_frame.rowconfigure(0, weight=1); list_frame.columnconfigure(0, weight=1)
        self.card_listbox = tk.Listbox(list_frame, exportselection=False)
        self.card_listbox.grid(row=0, column=0, sticky="nsew", pady=5, padx=5)
        card_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.card_listbox.yview)
        card_scroll.grid(row=0, column=1, sticky="ns", pady=5, padx=(0,5))
        self.card_listbox.config(yscrollcommand=card_scroll.set)
        self.card_listbox.bind("<<ListboxSelect>>", self._on_card_select)

        # --- Action Frame ---
        action_frame = ttk.LabelFrame(main_frame, text="Edit Selected Card")
        action_frame.grid(row=2, column=0, pady=5, sticky="ew", padx=5)
        action_frame.columnconfigure(1, weight=1)
        self.selected_card_label = ttk.Label(action_frame, text="Selected: None", anchor='w', font=('TkDefaultFont', 10, 'bold'))
        self.selected_card_label.grid(row=0, column=0, columnspan=3, padx=5, pady=(5,10), sticky='ew')
        self.edit_type_button = ttk.Button(action_frame, text="Change Type To:", command=self._edit_card_type, state="disabled")
        self.edit_type_button.grid(row=1, column=0, padx=(5, 2), pady=2, sticky='w')
        self.edit_type_combo = ttk.Combobox(action_frame, values=card_type_values, state="disabled", width=12)
        self.edit_type_combo.grid(row=1, column=1, padx=(0, 10), pady=2, sticky='w')
        self.remove_restore_button = ttk.Button(action_frame, text="Remove/Restore", command=self._toggle_remove_restore_card, state="disabled")
        self.remove_restore_button.grid(row=1, column=2, padx=10, pady=2, sticky='e')
        ttk.Label(action_frame, text="Image Path:").grid(row=2, column=0, padx=5, pady=2, sticky='w')
        self.image_path_label = ttk.Label(action_frame, textvariable=self.current_image_path_var, relief="sunken", anchor="w", width=40)
        self.image_path_label.grid(row=2, column=1, padx=0, pady=2, sticky='ew')
        self.browse_image_button = ttk.Button(action_frame, text="Browse...", command=self._browse_image, state="disabled")
        self.browse_image_button.grid(row=2, column=2, padx=10, pady=2, sticky='e')

        # --- Auto-Scan Frame ---
        scan_frame = ttk.Frame(main_frame)
        scan_frame.grid(row=3, column=0, pady=5, sticky="ew", padx=5)
        scan_frame.columnconfigure(0, weight=1) # Allow button to center using grid
        self.scan_button = ttk.Button(scan_frame, text=f"Scan '{CARD_IMAGES_DIR}' & Assign Missing Images", command=self._scan_and_assign_images)
        self.scan_button.grid(row=0, column=0, pady=5) # Use grid instead of pack

        # --- Bottom Frame ---
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=4, column=0, pady=(5,0), sticky="e")
        ttk.Button(bottom_frame, text="Save Changes", command=self._save_user_db).pack(side="left", padx=10)
        ttk.Button(bottom_frame, text="Close", command=self.destroy).pack(side="left", padx=10)

    def _populate_card_list(self):
        """Populates the listbox with cards from the effective pool, indicating status."""
        # (Identical to previous version)
        self.card_listbox.delete(0, tk.END)
        current_selection_name = self.selected_card_var.get()
        new_selection_index = -1
        for i, card in enumerate(self.effective_pool_list):
            card_type = self.effective_types.get(card, "???"); status = ""; color = "black"
            is_added = card in self.added_cards; is_removed = card in self.removed_cards
            is_overridden = card in self.type_overrides; is_base_unmodified = card in self.base_pool and not is_overridden and not is_removed
            if is_added: status = "[Added]"; color = "blue"
            elif is_overridden: base_type = self.base_types.get(card, "???"); status = f"[Type Override: {base_type} -> {card_type}]"; color = "purple"
            elif is_base_unmodified: status = "[Base]"; color = "grey40"
            display_text = f"{card} ({card_type}) {status}".strip()
            self.card_listbox.insert(tk.END, display_text)
            self.card_listbox.itemconfig(tk.END, {'fg': color})
            if card == current_selection_name: new_selection_index = i
        if new_selection_index != -1:
            self.card_listbox.selection_set(new_selection_index); self.card_listbox.see(new_selection_index)
            self._update_action_buttons(current_selection_name)
        else: self.selected_card_var.set(""); self._update_action_buttons(None)
        self._update_image_path_display(self.selected_card_var.get())


    def _on_card_select(self, event):
        """Handles selection changes in the card listbox, updates action buttons and image path."""
        # (Identical to previous version)
        selection = self.card_listbox.curselection()
        selected_card_name = None
        if selection:
            selected_display = self.card_listbox.get(selection[0])
            match = re.match(r"^(.*?)\s+\(", selected_display)
            if match: selected_card_name = match.group(1).strip(); self.selected_card_var.set(selected_card_name); self.selected_card_label.config(text=f"Selected: {selected_card_name}")
            else: print(f"Warning: Could not parse card name: {selected_display}"); self.selected_card_var.set(""); self.selected_card_label.config(text="Selected: Error parsing")
        else: self.selected_card_var.set(""); self.selected_card_label.config(text="Selected: None")
        self._update_action_buttons(selected_card_name); self._update_image_path_display(selected_card_name)

    def _update_action_buttons(self, card_name):
        """Updates the state and text of action buttons based on the selected card."""
        # (Identical to previous version)
        if card_name and card_name in self.effective_pool_list:
            current_type = self.effective_types.get(card_name); is_added = card_name in self.added_cards; is_base = card_name in self.base_pool
            if current_type: self.edit_type_combo.config(state="readonly"); self.edit_type_combo.set(current_type); self.edit_type_button.config(state="normal")
            else: self.edit_type_combo.config(state="disabled"); self.edit_type_combo.set(""); self.edit_type_button.config(state="disabled")
            self.remove_restore_button.config(state="normal")
            if is_added: self.remove_restore_button.config(text="Delete Added Card")
            elif is_base: self.remove_restore_button.config(text="Remove from Pool")
            else: self.remove_restore_button.config(text="Invalid State", state="disabled"); print(f"Warning: Card '{card_name}' has unexpected state.")
            self.browse_image_button.config(state="normal")
        else:
            self.remove_restore_button.config(state="disabled", text="Remove/Restore"); self.edit_type_button.config(state="disabled")
            self.edit_type_combo.config(state="disabled"); self.edit_type_combo.set(""); self.browse_image_button.config(state="disabled")

    def _update_image_path_display(self, card_name):
         """Updates the image path label based on the selected card."""
         # (Identical to previous version)
         if card_name and card_name in self.image_paths: # Check internal dict directly
              relative_path = self.image_paths[card_name]
              self.current_image_path_var.set(relative_path)
         elif card_name: self.current_image_path_var.set("No image set")
         else: self.current_image_path_var.set("")

    def _add_card(self):
        """Adds a new card to the user's added_cards list."""
        # (Identical to previous version)
        name = self.new_card_name_var.get().strip(); ctype = self.new_card_type_var.get()
        if not name: messagebox.showerror("Error", "Card name cannot be empty.", parent=self); return
        if not ctype: messagebox.showerror("Error", "Card type must be selected.", parent=self); return
        if name in self.added_cards: messagebox.showerror("Error", f"Card '{name}' has already been added.", parent=self); return
        if name in self.base_pool and name not in self.removed_cards: messagebox.showerror("Error", f"Card '{name}' exists in base pool.", parent=self); return
        if name in self.base_pool and name in self.removed_cards:
             if not messagebox.askyesno("Confirm Add", f"Card '{name}' exists in base pool but is marked for removal.\nAdding it now will restore it with type '{ctype}'.\nProceed?", parent=self): return
        self.added_cards[name] = ctype; self.removed_cards.discard(name)
        if name in self.type_overrides: del self.type_overrides[name]
        if name in self.image_paths: del self.image_paths[name]
        print(f"Added new card: {name} ({ctype})"); self.new_card_name_var.set("")
        self._calculate_effective_db(); self._populate_card_list()
        try: idx = self.effective_pool_list.index(name); self.card_listbox.selection_clear(0, tk.END); self.card_listbox.selection_set(idx); self.card_listbox.see(idx); self._on_card_select(None)
        except ValueError: print(f"Info: Could not auto-select newly added card '{name}'.")

    def _toggle_remove_restore_card(self):
        """Handles removing/deleting the selected card based on its state."""
        # (Identical to previous version)
        card = self.selected_card_var.get();
        if not card: return
        is_added = card in self.added_cards; is_base = card in self.base_pool
        action_taken = None
        if is_added:
            if messagebox.askyesno("Confirm Delete", f"Permanently delete user-added card '{card}'?", parent=self):
                del self.added_cards[card]
                if card in self.type_overrides: del self.type_overrides[card]
                if card in self.image_paths: del self.image_paths[card]
                action_taken = f"Deleted added card: {card}"
        elif is_base:
             if messagebox.askyesno("Confirm Remove", f"Mark base card '{card}' for removal?", parent=self):
                 self.removed_cards.add(card)
                 if card in self.type_overrides: del self.type_overrides[card]
                 if card in self.image_paths: del self.image_paths[card]
                 action_taken = f"Marked base card for removal: {card}"
        else: messagebox.showerror("Error", f"Cannot determine state of card '{card}'.", parent=self); return
        if action_taken:
            print(action_taken); self.selected_card_var.set("")
            self._calculate_effective_db(); self._populate_card_list()

    def _edit_card_type(self):
        """Changes the type of the selected card (override base or update added)."""
        # (Identical to previous version)
        card = self.selected_card_var.get(); new_type = self.edit_type_combo.get()
        if not card or not new_type: return
        current_effective_type = self.effective_types.get(card)
        if new_type == current_effective_type: messagebox.showinfo("Info", f"Card '{card}' already type '{new_type}'.", parent=self); return
        is_added = card in self.added_cards; is_base = card in self.base_pool; base_type = self.base_types.get(card)
        action_taken = None
        if is_added: self.added_cards[card] = new_type; action_taken = f"Changed type of added card '{card}' to {new_type}"
        elif is_base:
            if new_type == base_type:
                if card in self.type_overrides: del self.type_overrides[card]; action_taken = f"Reverted type of base card '{card}' to default ({new_type})"
                else: action_taken = f"Type of base card '{card}' confirmed as default ({new_type})"
            else: self.type_overrides[card] = new_type; action_taken = f"Overrode type of base card '{card}' to {new_type}"
        else: messagebox.showerror("Error", f"Cannot edit type for card '{card}': Unknown state.", parent=self); return
        if action_taken:
            print(action_taken); self._calculate_effective_db(); self._populate_card_list()
            try: idx = self.effective_pool_list.index(card); self.card_listbox.selection_clear(0, tk.END); self.card_listbox.selection_set(idx); self.card_listbox.see(idx); self._on_card_select(None)
            except ValueError: self._update_action_buttons(None); print(f"Warning: Card '{card}' not found after type edit.")

    def _browse_image(self):
        """Opens a file dialog to select an image for the selected card."""
        # (Identical to previous version)
        selected_card = self.selected_card_var.get()
        if not selected_card: messagebox.showwarning("No Card Selected", "Please select a card first.", parent=self); return
        filetypes = [("Image Files", "*.png *.jpg *.jpeg *.gif *.bmp *.ico"), ("All Files", "*.*")]; initial_dir = CARD_IMAGES_DIR
        filepath = filedialog.askopenfilename(title=f"Select Image for {selected_card}", initialdir=initial_dir, filetypes=filetypes)
        if filepath:
            try:
                base_path = os.path.abspath(CARD_IMAGES_DIR); selected_path = os.path.abspath(filepath)
                relative_path = os.path.relpath(selected_path, base_path)
                if os.path.isabs(relative_path) and not selected_path.startswith(base_path):
                     print(f"Warning: Selected image '{filepath}' outside '{CARD_IMAGES_DIR}'. Storing potentially complex relative path: '{relative_path}'")
                self.image_paths[selected_card] = relative_path # Update internal dict
                print(f"Set image for '{selected_card}' to '{relative_path}'")
                self.current_image_path_var.set(relative_path) # Update display
            except Exception as e: messagebox.showerror("Error Processing Path", f"Could not process path:\n{e}", parent=self); print(f"Error processing image path: {e}")

    def _scan_and_assign_images(self):
        """Scans CARD_IMAGES_DIR and assigns images to cards missing paths."""
        if not os.path.isdir(CARD_IMAGES_DIR):
            messagebox.showerror("Error", f"Image directory '{CARD_IMAGES_DIR}' not found.", parent=self)
            return

        print(f"Scanning '{CARD_IMAGES_DIR}' for missing card images...")
        assigned_count = 0
        skipped_count = 0
        not_found_count = 0
        image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico')

        # Use sets for efficient lookup
        effective_card_set = set(self.effective_pool_list)
        cards_with_paths = set(self.image_paths.keys())

        try:
            for filename in os.listdir(CARD_IMAGES_DIR):
                if filename.lower().endswith(image_extensions):
                    # Extract potential card name from filename (remove extension)
                    card_name_from_file = os.path.splitext(filename)[0]

                    # Check if it's a valid card in the pool AND doesn't have a path yet
                    if card_name_from_file in effective_card_set:
                        if card_name_from_file not in cards_with_paths:
                            # Assign the relative path (which is just the filename)
                            self.image_paths[card_name_from_file] = filename
                            assigned_count += 1
                            print(f"  Assigned '{filename}' to '{card_name_from_file}'")
                        else:
                            # Card found, but already has a path assigned
                            skipped_count += 1
                    else:
                        # Image file doesn't match a card in the effective pool
                        not_found_count +=1
                        # print(f"  Info: Image '{filename}' does not match any known card.")

        except Exception as e:
             messagebox.showerror("Scan Error", f"An error occurred while scanning:\n{e}", parent=self)
             print(f"ERROR during image scan: {e}")
             return

        # Report results
        message = f"Scan complete.\n\nNewly assigned images: {assigned_count}\nSkipped (already assigned): {skipped_count}"
        if not_found_count > 0:
             message += f"\nImage files not matching known cards: {not_found_count}"
        messagebox.showinfo("Scan Results", message, parent=self)

        # Update display if the currently selected card got assigned an image
        current_selection = self.selected_card_var.get()
        self._update_image_path_display(current_selection)
# --- End CardDatabaseEditorWindow ---

# --- A/B Hand Test Window (Card Evaluation with Images) ---
class ABTestWindow(tk.Toplevel):
    """
    Toplevel window for manually comparing opening hands based on adding
    Card A vs Card B to the same initial 4 random cards drawn from the deck.
    Displays card images instead of text. Also shows theoretical next draws
    and allows viewing the remaining deck.
    """

    def __init__(self, parent_app, saved_deck_files):
        super().__init__(parent_app.root)
        self.parent_app = parent_app # Reference to the main app
        self.saved_deck_files = saved_deck_files
        # Assume DECKS_DIR and CARD_IMAGES_DIR are accessible globals or defined in parent_app
        global DECKS_DIR, CARD_IMAGES_DIR
        self.decks_dir = DECKS_DIR
        self.card_images_dir = CARD_IMAGES_DIR

        self.title("Card Evaluation Test (Images)") # Updated title
        self.geometry("850x800") # Adjusted size for images
        self.transient(parent_app.root)
        self.grab_set()

        # --- State Variables ---
        self.deck_name = tk.StringVar()
        self.card_a_name = tk.StringVar() # Test Card 1
        self.card_b_name = tk.StringVar() # Test Card 2
        self.num_trials_var = tk.IntVar(value=16)

        self.deck_list = {} # The loaded deck {card_name: count}
        self.valid_cards = [] # List of card names in the loaded deck

        self.is_testing = False
        self.current_trial = 0
        self.total_trials = 0
        self.wins_a = 0
        self.wins_b = 0
        self.ties = 0
        # History: [trial_num, hand_a_list, hand_b_list, pot_draws, bj_reveals, rest_of_deck, result]
        self.trial_history = []

        # Thumbnail size
        self.thumbnail_size = (60, 88) # Adjust as needed (width, height)
        # Placeholder for missing images
        self.placeholder_image = None # Will be created in setup_gui
        # Cache for loaded/resized images to avoid reloading/leaking memory
        self._image_cache = {}
        # References to PhotoImage objects to prevent garbage collection
        self._image_references = []

        # Bind Escape key to close the window
        self.bind('<Escape>', lambda e: self.destroy())

        self._setup_gui()
        self._update_ui_state() # Initial state

    def _setup_gui(self):
        """Sets up the GUI, replacing listboxes with frames for images."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(expand=True, fill="both")
        # Configure rows: 0=Setup, 1=Hands (expand), 2=Extra Draws, 3=View Deck Btn, 4=Bottom
        main_frame.rowconfigure(1, weight=1) # Hand display area expands
        main_frame.rowconfigure(2, weight=0)
        main_frame.rowconfigure(3, weight=0)
        main_frame.columnconfigure(0, weight=1)

        # --- Setup Frame (Row 0) ---
        # (Identical setup controls as before)
        setup_frame = ttk.LabelFrame(main_frame, text="Setup Test")
        setup_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        setup_frame.columnconfigure(1, weight=1); setup_frame.columnconfigure(3, weight=1)
        ttk.Label(setup_frame, text="Selected Deck:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.deck_combo = ttk.Combobox(setup_frame, textvariable=self.deck_name, values=self.saved_deck_files, state="readonly", width=30)
        self.deck_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.deck_combo.bind("<<ComboboxSelected>>", lambda e: self._load_deck())
        ttk.Label(setup_frame, text="Card A (Test Card 1):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.card_a_combo = ttk.Combobox(setup_frame, textvariable=self.card_a_name, state="disabled", width=30)
        self.card_a_combo.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.card_a_combo.bind("<<ComboboxSelected>>", lambda e: self._validate_inputs_for_start())
        ttk.Label(setup_frame, text="Card B (Test Card 2):").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.card_b_combo = ttk.Combobox(setup_frame, textvariable=self.card_b_name, state="disabled", width=30)
        self.card_b_combo.grid(row=1, column=3, padx=5, pady=5, sticky="ew")
        self.card_b_combo.bind("<<ComboboxSelected>>", lambda e: self._validate_inputs_for_start())
        ttk.Label(setup_frame, text="Trials (1-162):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.trials_spinbox = tk.Spinbox(setup_frame, from_=1, to=162, textvariable=self.num_trials_var, width=5, justify=tk.RIGHT)
        self.trials_spinbox.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.start_button = ttk.Button(setup_frame, text="Start Test", command=self._start_ab_test, state="disabled")
        self.start_button.grid(row=2, column=3, padx=5, pady=10, sticky="e")

        # --- Testing Frame (Row 1) ---
        testing_frame = ttk.Frame(main_frame)
        testing_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        testing_frame.rowconfigure(1, weight=1) # Hand frames row expands if needed
        testing_frame.columnconfigure(0, weight=1) # Hand A frame
        testing_frame.columnconfigure(1, weight=1) # Hand B frame

        # Progress and Score Display
        progress_frame = ttk.Frame(testing_frame)
        progress_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=(5, 2), sticky="ew")
        self.progress_label = ttk.Label(progress_frame, text="Trial: - / -")
        self.progress_label.pack(side="left", padx=10)
        self.score_label = ttk.Label(progress_frame, text="Score: A: 0 (0.0%) | B: 0 (0.0%) | Ties: 0 (0.0%)")
        self.score_label.pack(side="left", padx=10)

        # --- Hand Display Frames (Replacing Listboxes) ---
        hand_a_outer_frame = ttk.LabelFrame(testing_frame, text="Hand A (Draw 4 + Card A)")
        hand_a_outer_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        # Create a frame inside for packing the image labels horizontally
        self.hand_a_image_frame = ttk.Frame(hand_a_outer_frame)
        self.hand_a_image_frame.pack(padx=5, pady=5) # Pack labels inside this

        hand_b_outer_frame = ttk.LabelFrame(testing_frame, text="Hand B (Draw 4 + Card B)")
        hand_b_outer_frame.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")
        # Create a frame inside for packing the image labels horizontally
        self.hand_b_image_frame = ttk.Frame(hand_b_outer_frame)
        self.hand_b_image_frame.pack(padx=5, pady=5) # Pack labels inside this

        # Instructions
        self.instruction_label = ttk.Label(testing_frame, text="Left Arrow = Hand A Better | Right Arrow = Hand B Better | Down Arrow = Equal | Up Arrow = Undo Last", font=("TkDefaultFont", 10, "italic"))
        self.instruction_label.grid(row=2, column=0, columnspan=2, padx=5, pady=5)


        # --- Extra Draws Frame (Row 2) ---
        # (Using Listboxes here for simplicity, could be changed to images too)
        extra_draws_frame = ttk.LabelFrame(main_frame, text="Theoretical Next Draws")
        extra_draws_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        extra_draws_frame.columnconfigure(0, weight=1); extra_draws_frame.columnconfigure(1, weight=1)

        pot_frame = ttk.LabelFrame(extra_draws_frame, text="Pot of Extravagance (Next 3)")
        pot_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        pot_frame.rowconfigure(0, weight=1); pot_frame.columnconfigure(0, weight=1);
        self.pot_listbox = tk.Listbox(pot_frame, height=3, width=35)
        self.pot_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        pot_scroll = ttk.Scrollbar(pot_frame, orient=tk.VERTICAL, command=self.pot_listbox.yview)
        pot_scroll.grid(row=0, column=1, sticky="ns", padx=(0,5), pady=5)
        self.pot_listbox.config(yscrollcommand=pot_scroll.set)

        bj_frame = ttk.LabelFrame(extra_draws_frame, text="Back Jack Reveal (BWL + Next 3)")
        bj_frame.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")
        bj_frame.rowconfigure(0, weight=1); bj_frame.columnconfigure(0, weight=1);
        self.bj_listbox = tk.Listbox(bj_frame, height=4, width=35)
        self.bj_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        bj_scroll = ttk.Scrollbar(bj_frame, orient=tk.VERTICAL, command=self.bj_listbox.yview)
        bj_scroll.grid(row=0, column=1, sticky="ns", padx=(0,5), pady=5)
        self.bj_listbox.config(yscrollcommand=bj_scroll.set)


        # --- View Deck Button Frame (Row 3) ---
        view_deck_frame = ttk.Frame(main_frame)
        view_deck_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        self.view_deck_button = ttk.Button(view_deck_frame, text="View Remaining Deck", command=self._show_remaining_deck, state="disabled")
        self.view_deck_button.pack(pady=5)


        # --- Bottom Frame (Row 4) ---
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        self.status_label_ab = ttk.Label(bottom_frame, text="Status: Select deck and two different cards.")
        self.status_label_ab.pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="Close", command=self.destroy).pack(side="right", padx=5)

        # --- Create Placeholder Image ---
        try:
            # Create a simple grey image with text
            ph_img = Image.new('RGB', self.thumbnail_size, color = 'grey')
            # To add text requires ImageDraw, let's skip for simplicity now
            # Could draw a '?' or 'N/A'
            self.placeholder_image = ImageTk.PhotoImage(ph_img)
        except Exception as e:
            print(f"Error creating placeholder image: {e}")
            self.placeholder_image = None # Fallback if Pillow fails unexpectedly

        # --- End GUI Setup ---

    def _update_status(self, msg):
        # (Identical to previous versions)
        self.status_label_ab.config(text=f"Status: {msg}")
        print(f"A/B Test Status: {msg}")

    def _load_deck(self):
        """Loads the selected single deck file."""
        # (Identical to previous versions)
        filename = self.deck_combo.get()
        if not filename:
            self.deck_list = {}; self.valid_cards = []
            self.card_a_combo.config(values=[], state="disabled")
            self.card_b_combo.config(values=[], state="disabled")
            self.card_a_name.set(""); self.card_b_name.set("")
            self._validate_inputs_for_start(); return

        filepath = os.path.join(self.decks_dir, filename)
        try:
            with open(filepath, 'r') as f: loaded_deck = json.load(f)
            if not isinstance(loaded_deck, dict) or not all(isinstance(k, str) and isinstance(v, int) and v > 0 for k, v in loaded_deck.items()):
                raise ValueError("Invalid deck format (must be dict of card:count > 0).")
            effective_loaded_deck = {}; unknown_cards = []
            for card, count in loaded_deck.items():
                if card in self.parent_app.card_pool: effective_loaded_deck[card] = count
                else: unknown_cards.append(card)
            if unknown_cards: messagebox.showwarning("Load Warning", f"Deck '{filename}' loaded, but some cards ignored (not in DB):\n- " + "\n- ".join(unknown_cards), parent=self)
            if not effective_loaded_deck: raise ValueError("Deck contains no valid cards found in the current database.")
            total_cards = sum(effective_loaded_deck.values())
            if total_cards < 5: raise ValueError(f"Deck must have at least 5 valid cards (has {total_cards}).")
            valid_cards = sorted(list(effective_loaded_deck.keys()))
            self.deck_list = effective_loaded_deck; self.valid_cards = valid_cards
            self.card_a_combo.config(values=valid_cards, state="readonly")
            self.card_b_combo.config(values=valid_cards, state="readonly")
            self.card_a_name.set(""); self.card_b_name.set("")
            self._update_status(f"Deck '{filename}' loaded ({total_cards} cards). Select two different cards.")
        except FileNotFoundError:
             messagebox.showerror("Deck Load Error", f"Deck file not found: '{filename}'", parent=self)
             self.deck_list = {}; self.valid_cards = []
             self.card_a_combo.config(values=[], state="disabled"); self.card_b_combo.config(values=[], state="disabled")
             self.deck_name.set(""); self.card_a_name.set(""); self.card_b_name.set("")
        except Exception as e:
            messagebox.showerror("Deck Load Error", f"Failed to load or validate deck '{filename}':\n{e}", parent=self)
            self.deck_list = {}; self.valid_cards = []
            self.card_a_combo.config(values=[], state="disabled"); self.card_b_combo.config(values=[], state="disabled")
            self.deck_name.set(""); self.card_a_name.set(""); self.card_b_name.set("")
        self._validate_inputs_for_start()

    def _validate_inputs_for_start(self):
        """Checks if a deck and two DIFFERENT cards are selected."""
        # (Identical to previous versions)
        deck_ok = bool(self.deck_list)
        card_a_selected = self.card_a_name.get(); card_b_selected = self.card_b_name.get()
        cards_ok = bool(card_a_selected and card_b_selected and card_a_selected != card_b_selected)
        cards_in_deck = cards_ok and card_a_selected in self.deck_list and card_b_selected in self.deck_list
        if deck_ok and cards_ok and cards_in_deck:
            self.start_button.config(state="normal"); self._update_status("Ready to start test.")
        else:
            self.start_button.config(state="disabled"); status_msg = "Status: "
            if not deck_ok: status_msg += "Select a valid Deck. "
            elif not card_a_selected or not card_b_selected: status_msg += "Select both Card A and Card B. "
            elif card_a_selected == card_b_selected: status_msg += "Card A and Card B must be different. "
            elif not cards_in_deck: status_msg += "One or both selected cards not found in the loaded deck. "
            else: status_msg += "Setup incomplete."
            self._update_status(status_msg.replace("Status: ", ""))

    def _update_ui_state(self):
        """Enable/disable parts of the UI based on whether testing is active."""
        setup_state = "disabled" if self.is_testing else "normal"
        testing_state = "normal" if self.is_testing else "disabled"

        # Setup Frame Widgets
        self.deck_combo.config(state="disabled" if self.is_testing else "readonly")
        self.card_a_combo.config(state="disabled" if self.is_testing or not self.deck_list else "readonly")
        self.card_b_combo.config(state="disabled" if self.is_testing or not self.deck_list else "readonly")
        self.trials_spinbox.config(state=setup_state)
        self.start_button.config(state="disabled" if self.is_testing else "normal")
        if not self.is_testing: self._validate_inputs_for_start()

        # Testing Frame Widgets
        # Hand frames are always visible, but content is cleared/added
        # Extra Draw Listboxes
        self.pot_listbox.config(state=testing_state)
        self.bj_listbox.config(state=testing_state)
        # View Deck Button
        self.view_deck_button.config(state=testing_state if self.current_trial > 0 else "disabled") # Enable only if a trial is displayed

        # Labels
        self.progress_label.config(text="Trial: - / -" if not self.is_testing else self.progress_label.cget("text"))
        self.score_label.config(text="Score: A: 0 (0.0%) | B: 0 (0.0%) | Ties: 0 (0.0%)" if not self.is_testing else self.score_label.cget("text"))
        self.instruction_label.config(foreground="black" if self.is_testing else "grey")

        # Clear image frames if not testing
        if not self.is_testing:
            self._clear_image_frame(self.hand_a_image_frame)
            self._clear_image_frame(self.hand_b_image_frame)
            self.pot_listbox.delete(0, tk.END)
            self.bj_listbox.delete(0, tk.END)


    def _clear_image_frame(self, frame):
        """Removes all child widgets (image labels) from a frame."""
        for widget in frame.winfo_children():
            widget.destroy()
        # Clear references associated with this frame if needed (handled globally now)

    def _get_card_image(self, card_name):
        """Loads, resizes, and caches an image for a given card name."""
        # Check cache first
        if card_name in self._image_cache:
            return self._image_cache[card_name]

        # Get image path from main app's data (via parent_app reference)
        image_path_relative = self.parent_app.card_images.get(card_name) # Use effective paths from main app

        if not image_path_relative:
            # print(f"No image path found for card: {card_name}")
            return self.placeholder_image # Return placeholder if no path defined

        # Construct full path
        # Assumes CARD_IMAGES_DIR is relative to the script's execution directory
        image_path_full = os.path.join(self.card_images_dir, image_path_relative)

        try:
            # Open, resize, convert
            img = Image.open(image_path_full)
            img.thumbnail(self.thumbnail_size) # Resize in-place maintaining aspect ratio
            photo_img = ImageTk.PhotoImage(img)

            # Store in cache
            self._image_cache[card_name] = photo_img
            return photo_img

        except FileNotFoundError:
            print(f"Image file not found: {image_path_full}")
            # Cache the placeholder for this missing card to avoid repeated attempts
            self._image_cache[card_name] = self.placeholder_image
            return self.placeholder_image
        except Exception as e:
            print(f"Error loading image for {card_name} at {image_path_full}: {e}")
            # Cache the placeholder on error
            self._image_cache[card_name] = self.placeholder_image
            return self.placeholder_image

    def _start_ab_test(self):
        """Validates inputs and begins the testing sequence."""
        # --- Start Test Logic ---
        # (Identical to previous versions)
        card_a = self.card_a_name.get()
        card_b = self.card_b_name.get()
        if not (self.deck_list and card_a and card_b and card_a != card_b):
            messagebox.showerror("Setup Error", "Ensure a valid deck and two different cards are selected.", parent=self)
            return
        if card_a not in self.deck_list or card_b not in self.deck_list:
             messagebox.showerror("Setup Error", "Selected card(s) not found in loaded deck.", parent=self)
             return
        # Deck size check happens in load_deck

        try:
            self.total_trials = self.num_trials_var.get()
            if not (1 <= self.total_trials <= 162):
                raise ValueError("Trials must be between 1 and 162.")
        except (tk.TclError, ValueError) as e:
            messagebox.showerror("Input Error", f"Invalid number of trials: {e}", parent=self)
            return

        # Reset state
        self.is_testing = True
        self.current_trial = 0
        self.wins_a = 0; self.wins_b = 0; self.ties = 0
        self.trial_history = []
        self._image_references = [] # Clear image references from previous test
        # Note: _image_cache persists between tests for efficiency, could be cleared if needed
        self._update_status(f"Starting test for {self.total_trials} trials...")
        self._update_ui_state()
        self._update_live_scores()
        self._prepare_next_trial()
        # --- End Start Test ---

    def _display_trial(self, trial_num):
        """Displays the hands (as images) and extra draws for a given trial number."""
        # Clear previous displays
        self._clear_image_frame(self.hand_a_image_frame)
        self._clear_image_frame(self.hand_b_image_frame)
        self.pot_listbox.delete(0, tk.END)
        self.bj_listbox.delete(0, tk.END)
        self.view_deck_button.config(state="disabled")
        self._image_references = [] # Clear references for the new trial

        if not self.trial_history or trial_num < 1 or trial_num > len(self.trial_history):
            return # Invalid trial number or history empty

        # History: [trial_num, hand_a_list, hand_b_list, pot_draws, bj_reveals, rest_of_deck, result]
        trial_data = self.trial_history[trial_num - 1]
        hand_a_list = trial_data[1]
        hand_b_list = trial_data[2]
        pot_draws = trial_data[3]
        bj_reveals = trial_data[4]

        # --- Display Hand A Images ---
        for card_name in hand_a_list:
            photo_img = self._get_card_image(card_name)
            if photo_img:
                img_label = ttk.Label(self.hand_a_image_frame, image=photo_img)
                img_label.image = photo_img # Keep reference! Crucial for Tkinter
                img_label.pack(side=tk.LEFT, padx=2)
                self._image_references.append(photo_img) # Add to list to prevent GC
            else: # Fallback if placeholder also failed
                ttk.Label(self.hand_a_image_frame, text=card_name, relief="solid", padding=2).pack(side=tk.LEFT, padx=2)

        # --- Display Hand B Images ---
        for card_name in hand_b_list:
            photo_img = self._get_card_image(card_name)
            if photo_img:
                img_label = ttk.Label(self.hand_b_image_frame, image=photo_img)
                img_label.image = photo_img # Keep reference!
                img_label.pack(side=tk.LEFT, padx=2)
                self._image_references.append(photo_img) # Add to list to prevent GC
            else: # Fallback
                ttk.Label(self.hand_b_image_frame, text=card_name, relief="solid", padding=2).pack(side=tk.LEFT, padx=2)


        # Display extra draws (still using Listbox for these)
        for card in pot_draws: self.pot_listbox.insert(tk.END, card)
        for card in bj_reveals: self.bj_listbox.insert(tk.END, card)

        # Update progress label
        self.progress_label.config(text=f"Trial: {trial_num} / {self.total_trials}")
        # Enable view deck button now that data is loaded
        self.view_deck_button.config(state="normal")


    def _prepare_next_trial(self):
        """Generates hands (Draw 4 + Test Card) and extra draws, stores state, updates UI, binds keys."""
        self.current_trial += 1
        if self.current_trial > self.total_trials:
            self._finish_ab_test()
            return

        self._update_status(f"Running Trial {self.current_trial} / {self.total_trials}. Waiting for input...")

        card_a = self.card_a_name.get()
        card_b = self.card_b_name.get()

        try:
            # --- Hand and Draw Generation (Draw 4 + Test Card) ---
            full_deck_list = []
            for card, count in self.deck_list.items():
                full_deck_list.extend([card] * count)

            if len(full_deck_list) < 4:
                 raise ValueError(f"Deck size ({len(full_deck_list)}) is too small to draw 4 common cards.")

            random.shuffle(full_deck_list)
            common_cards = full_deck_list[:4]
            rest_of_deck = full_deck_list[4:]

            hand_a_list = common_cards + [card_a]
            hand_b_list = common_cards + [card_b]
            current_hand_a = sorted(hand_a_list)
            current_hand_b = sorted(hand_b_list)

            pot_draws = rest_of_deck[:3]

            bwl_card_name = "Big Welcome Labrynth"
            if bwl_card_name not in self.deck_list:
                bj_reveals = ["N/A (BWL not in deck)"]
            else:
                next_3_for_bj = rest_of_deck[:3]
                bj_reveals = [bwl_card_name] + next_3_for_bj
            # --- End Hand and Draw Generation ---

        except ValueError as e:
             messagebox.showerror("Hand Generation Error", f"Error during trial {self.current_trial}:\n{e}", parent=self)
             self._abort_test(); return
        except Exception as e:
             messagebox.showerror("Error", f"An unexpected error occurred generating data for trial {self.current_trial}:\n{e}", parent=self)
             import traceback; traceback.print_exc()
             self._abort_test(); return

        # Store state for this trial including rest_of_deck
        self.trial_history.append([
            self.current_trial, current_hand_a, current_hand_b,
            pot_draws, bj_reveals, rest_of_deck, None # Result is None initially (index 6)
        ])

        # Display the hands (as images) and update progress
        self._display_trial(self.current_trial)

        # Bind keys for user input for THIS trial
        self._bind_evaluation_keys()

    def _bind_evaluation_keys(self):
        """Binds Left, Right, Down, Up arrow keys for evaluation and undo."""
        # (Identical to previous versions)
        self.unbind("<Left>"); self.unbind("<Right>"); self.unbind("<Down>"); self.unbind("<Up>")
        self.bind("<Left>", lambda e: self._record_result('A'))
        self.bind("<Right>", lambda e: self._record_result('B'))
        self.bind("<Down>", lambda e: self._record_result('Tie'))
        self.bind("<Up>", lambda e: self._undo_last_trial())
        self.focus_set()

    def _unbind_evaluation_keys(self):
        """Unbinds evaluation keys."""
        # (Identical to previous versions)
        self.unbind("<Left>")
        self.unbind("<Right>")
        self.unbind("<Down>")
        self.unbind("<Up>")

    def _record_result(self, result):
        """Records the user's evaluation for the current trial and prepares the next."""
        # (Identical to previous versions, index adjusted)
        if not self.trial_history or self.trial_history[-1][0] != self.current_trial:
            print(f"Error: History mismatch when recording result for trial {self.current_trial}")
            self._abort_test(); return
        self.trial_history[-1][6] = result # Update result at index 6

        if result == 'A': self.wins_a += 1
        elif result == 'B': self.wins_b += 1
        else: self.ties += 1
        self._update_live_scores()

        self._unbind_evaluation_keys()
        self._update_status(f"Trial {self.current_trial}: Result '{result}' recorded. Preparing next...")

        self.after(50, self._prepare_next_trial)

    def _undo_last_trial(self):
        """Reverts the last recorded evaluation and goes back one trial."""
        # (Identical to previous versions, index adjusted)
        if self.current_trial <= 1 or not self.trial_history:
            self._update_status("Cannot undo the first trial."); return

        if len(self.trial_history) < self.current_trial:
             print(f"Error: History length invalid during undo."); return
        if self.trial_history[-1][0] != self.current_trial:
             print(f"Error: History mismatch during undo."); return

        self.trial_history.pop() # Remove current (unevaluated) trial state

        if not self.trial_history:
             print("Error: History empty after pop during undo."); self.current_trial = 0; self._abort_test(); return

        last_completed_trial_data = self.trial_history[-1]
        last_result = last_completed_trial_data[6] # Result is at index 6

        if last_result == 'A': self.wins_a -= 1
        elif last_result == 'B': self.wins_b -= 1
        elif last_result == 'Tie': self.ties -= 1

        last_completed_trial_data[6] = None # Clear result at index 6

        self.current_trial -= 1

        self._display_trial(self.current_trial) # Display previous trial's state (incl images)
        self._update_live_scores()
        self._update_status(f"Undo successful. Re-evaluating Trial {self.current_trial}.")

        self._bind_evaluation_keys()

    def _update_live_scores(self):
        """Updates the score display label."""
        # (Identical to previous versions)
        evaluated_count = self.wins_a + self.wins_b + self.ties
        if evaluated_count == 0: perc_a = perc_b = perc_tie = 0.0
        else:
            perc_a = (self.wins_a / evaluated_count) * 100
            perc_b = (self.wins_b / evaluated_count) * 100
            perc_tie = (self.ties / evaluated_count) * 100
        score_text = f"Score: A: {self.wins_a} ({perc_a:.1f}%) | B: {self.wins_b} ({perc_b:.1f}%) | Ties: {self.ties} ({perc_tie:.1f}%)"
        self.score_label.config(text=score_text)

    def _abort_test(self):
        """Called if a fatal error occurs during testing."""
        # (Identical to previous versions)
        self.is_testing = False
        self._update_ui_state()
        self._update_status("Test aborted due to error.")
        self._unbind_evaluation_keys()

    def _finish_ab_test(self):
        """Called when all trials are complete."""
        # (Identical to previous versions)
        self.is_testing = False
        final_evaluated = self.wins_a + self.wins_b + self.ties
        self._update_status(f"Test Finished. {final_evaluated} trials evaluated.")
        self.progress_label.config(text=f"Trial: {self.total_trials} / {self.total_trials}")
        self._update_ui_state()
        self._unbind_evaluation_keys()
        messagebox.showinfo("Test Complete", f"Card Evaluation finished.\n\nFinal Score:\n{self.score_label.cget('text')}\n\nGenerating report details...", parent=self)
        self._generate_report()

    def _generate_report(self):
        """Analyzes results and generates the final report."""
        # (Identical to previous versions, index adjusted)
        final_wins_a = self.wins_a; final_wins_b = self.wins_b; final_ties = self.ties
        total_evaluated = final_wins_a + final_wins_b + final_ties
        evaluated_trials_history = [data for data in self.trial_history if data[6] is not None] # Check result at index 6
        if total_evaluated == 0 or not evaluated_trials_history:
            self._update_status("No trials evaluated to generate report.")
            if self.total_trials > 0: messagebox.showwarning("Report Error", "No trials were successfully evaluated.", parent=self)
            return
        card_a = self.card_a_name.get(); card_b = self.card_b_name.get()
        perc_a = (final_wins_a / total_evaluated) * 100; perc_b = (final_wins_b / total_evaluated) * 100; perc_tie = (final_ties / total_evaluated) * 100
        draw4_when_a_preferred = Counter(); draw4_when_b_preferred = Counter()
        for trial_data in evaluated_trials_history:
            initial_draw4 = [c for c in trial_data[1] if c != card_a]
            if len(initial_draw4) != 4: print(f"Warning: Invalid common cards in trial {trial_data[0]}. Skipping."); continue
            result = trial_data[6] # Result at index 6
            if result == 'A': draw4_when_a_preferred.update(initial_draw4)
            elif result == 'B': draw4_when_b_preferred.update(initial_draw4)
        report = f"--- Card Evaluation Report (Draw 4 + Test Card) ---\n\n"; report += f"Deck: {self.deck_name.get()}\n"; report += f"Card A: {card_a}\n"; report += f"Card B: {card_b}\n"
        report += f"Total Trials Evaluated: {total_evaluated}\n\n"; report += "--- Overall Results ---\n"; report += f"Hand A (Draw 4 + {card_a}) Preferred: {final_wins_a} ({perc_a:.1f}%)\n"
        report += f"Hand B (Draw 4 + {card_b}) Preferred: {final_wins_b} ({perc_b:.1f}%)\n"; report += f"Equal Value / Tie:                   {final_ties} ({perc_tie:.1f}%)\n\n"
        report += f"--- Initial Draw 4 Analysis ---\n"; report += "Top Cards in Initial Draw 4 (When Hand A Preferred):\n"
        if draw4_when_a_preferred:
            for card, count in draw4_when_a_preferred.most_common(5): report += f"  - {card} (Seen in {count} initial draws)\n"
        else: report += "  - N/A (Hand A never preferred)\n"
        report += "\n"; report += "Top Cards in Initial Draw 4 (When Hand B Preferred):\n"
        if draw4_when_b_preferred:
            for card, count in draw4_when_b_preferred.most_common(5): report += f"  - {card} (Seen in {count} initial draws)\n"
        else: report += "  - N/A (Hand B never preferred)\n"
        report += "\n--- End of Report ---"
        self._display_report_window(report); self._update_status("Report generated and displayed.")

    def _display_report_window(self, report_text):
        """Shows the generated report in a scrollable text window."""
        # (Identical to previous versions)
        report_win = tk.Toplevel(self); report_win.title("Card Evaluation Report"); report_win.geometry("600x550"); report_win.transient(self); report_win.grab_set(); report_win.bind('<Escape>', lambda e: report_win.destroy())
        text_frame = ttk.Frame(report_win, padding=5); text_frame.pack(expand=True, fill="both"); text_frame.rowconfigure(0, weight=1); text_frame.columnconfigure(0, weight=1)
        report_widget = tk.Text(text_frame, wrap="word", height=25, width=70, font=("Courier New", 9)); report_widget.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=report_widget.yview); scrollbar.grid(row=0, column=1, sticky="ns", padx=(0,5)); report_widget.config(yscrollcommand=scrollbar.set)
        report_widget.insert(tk.END, report_text); report_widget.config(state="disabled")
        button_frame = ttk.Frame(report_win, padding=(0, 5, 0, 5)); button_frame.pack(fill="x"); ttk.Button(button_frame, text="Close Report (Esc)", command=report_win.destroy).pack()

    def _show_remaining_deck(self):
        """Displays the rest of the shuffled deck for the current trial in a new window."""
        # (Identical to previous versions, index adjusted)
        if not self.is_testing or not self.trial_history or self.current_trial < 1 or self.current_trial > len(self.trial_history):
            messagebox.showinfo("No Data", "No trial data available to view remaining deck.", parent=self); return
        trial_data = self.trial_history[self.current_trial - 1]
        rest_of_deck = trial_data[5] # Remaining deck is at index 5
        deck_view_win = tk.Toplevel(self); deck_view_win.title(f"Remaining Deck - Trial {self.current_trial}"); deck_view_win.geometry("350x450"); deck_view_win.transient(self)
        label_text = f"Cards remaining after drawing 4 for Trial {self.current_trial}: ({len(rest_of_deck)} cards)"; ttk.Label(deck_view_win, text=label_text, wraplength=330).pack(padx=10, pady=(10, 5))
        list_frame = ttk.Frame(deck_view_win); list_frame.pack(expand=True, fill="both", padx=10, pady=5); list_frame.rowconfigure(0, weight=1); list_frame.columnconfigure(0, weight=1)
        deck_listbox = tk.Listbox(list_frame); deck_listbox.grid(row=0, column=0, sticky="nsew"); scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=deck_listbox.yview); scrollbar.grid(row=0, column=1, sticky="ns"); deck_listbox.config(yscrollcommand=scrollbar.set)
        if not rest_of_deck: deck_listbox.insert(tk.END, "(No cards remaining)")
        else:
            for i, card in enumerate(rest_of_deck): deck_listbox.insert(tk.END, f"{i+1}. {card}") # Show order
        ttk.Button(deck_view_win, text="Close", command=deck_view_win.destroy).pack(pady=(5, 10))

# --- End of ABTestWindow ---

# --- Main Application Class ---
class DeckSimulatorApp:
    def __init__(self, root):
        """Initialize the Deck Simulator App."""
        self.root = root
        self.root.title("Yu-Gi-Oh! Deck Simulator & Analyzer")
        self.root.geometry("1050x750") # Adjusted default size maybe

        # --- App State and Data Initialization ---
        if not os.path.exists(DECKS_DIR):
            try: os.makedirs(DECKS_DIR)
            except OSError as e: messagebox.showerror("Directory Error", f"Cannot create decks directory '{DECKS_DIR}': {e}"); self.root.quit()
        if not os.path.exists(CARD_IMAGES_DIR): # Ensure images dir exists too
            try: os.makedirs(CARD_IMAGES_DIR)
            except OSError as e: messagebox.showwarning("Directory Error", f"Cannot create card images directory '{CARD_IMAGES_DIR}'.\nImage loading may fail.\nError: {e}")


        # Load base card data first (these should not change during runtime)
        self.base_card_pool = set(CARD_POOL)
        self.base_card_types = CARD_TYPES.copy()
        # Load user modifications (these can change via editor)
        self.user_card_data = self._load_user_card_db()
        # Calculate the effective database the app will use initially
        # Initializes self.card_pool, self.card_types, self.card_images
        self._calculate_effective_card_db()

        # Deck building state
        self.deck_list_a = {}
        self.deck_list_b = {}
        self.current_deck_name_a = NO_DECK_A
        self.current_deck_name_b = NO_DECK_B

        # Simulation state (uses copies of decks at time of submission)
        self.current_submitted_deck_a = ""
        self.current_submitted_deck_b = ""
        self.submitted_deck_list_a = {}
        self.submitted_deck_list_b = {}
        self.submitted_stats_a = {}
        self.submitted_stats_b = {}
        self.submitted_is_comparison = False # Track if comparison was active at submission

        # UI Variables
        self.num_simulations = tk.IntVar(value=DEFAULT_SIMULATIONS)
        self.comparison_mode = tk.BooleanVar(value=True) # Default to True
        self.simulation_status_var = tk.StringVar(value="Status: Idle")

        # Simulation Threading & Communication
        self.simulation_queue = queue.Queue()
        self.last_pdf_path = None # Store path to generated PDF
        self._after_id_status_clear = None # ID for status bar clear timer

        # Load combo definitions (hardcoded and custom)
        self.hardcoded_combo_definitions = analysis_engine._get_hardcoded_combo_definitions()
        self.custom_combos = self._load_initial_custom_combos()

        # Load categories (these can change via editor)
        self.card_categories = self._load_initial_categories()

        # --- Setup GUI ---
        self._setup_gui()
        self.update_load_deck_dropdown() # Populate dropdowns initially
        self._load_last_submitted_decks() # Attempt to preload decks from state
        self.toggle_comparison_mode() # Set initial UI state based on comparison mode
        self.root.after(100, self._check_simulation_queue) # Start queue checker

    # --- Card DB Loading/Merging Methods ---
    def _load_user_card_db(self):
        """Loads user additions/removals/overrides/image_paths from USER_DB_FILE."""
        try:
            if os.path.exists(USER_DB_FILE):
                with open(USER_DB_FILE, 'r') as f: data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("added_cards", {}); data.setdefault("removed_cards", [])
                    data.setdefault("type_overrides", {}); data.setdefault("image_paths", {}) # Add image_paths default
                    if not isinstance(data["added_cards"], dict): data["added_cards"] = {}
                    if not isinstance(data["removed_cards"], list): data["removed_cards"] = []
                    if not isinstance(data["type_overrides"], dict): data["type_overrides"] = {}
                    if not isinstance(data["image_paths"], dict): data["image_paths"] = {} # Validate image_paths
                    # Ensure keys/values are strings
                    data["added_cards"] = {str(k): str(v) for k, v in data["added_cards"].items()}
                    data["removed_cards"] = [str(c) for c in data["removed_cards"]]
                    data["type_overrides"] = {str(k): str(v) for k, v in data["type_overrides"].items()}
                    data["image_paths"] = {str(k): str(v) for k, v in data["image_paths"].items()} # Clean image_paths
                    print(f"Loaded user card DB changes from {USER_DB_FILE}")
                    return data
                else:
                    print(f"Warn: {USER_DB_FILE} invalid format. Loading defaults."); return {}
            else:
                print(f"Info: User card DB file '{USER_DB_FILE}' not found. Using base data only.")
                return {"added_cards": {}, "removed_cards": [], "type_overrides": {}, "image_paths": {}} # Return empty defaults
        except Exception as e:
            self.update_status(f"Error loading user card DB ({USER_DB_FILE}): {e}", True)
            return {"added_cards": {}, "removed_cards": [], "type_overrides": {}, "image_paths": {}} # Return empty defaults on error

    def _calculate_effective_card_db(self):
        """
        Calculates the effective card pool, types, and image paths used by the application.
        Initializes/updates self.card_pool (list), self.card_types (dict), and self.card_images (dict).
        """
        added = self.user_card_data.get("added_cards", {})
        removed = set(self.user_card_data.get("removed_cards", []))
        overrides = self.user_card_data.get("type_overrides", {})
        image_paths = self.user_card_data.get("image_paths", {}) # Get user image paths

        # Calculate effective pool
        effective_pool_set = self.base_card_pool.copy()
        effective_pool_set.update(added.keys())
        effective_pool_set -= removed
        self.card_pool = sorted(list(effective_pool_set)) # Update main app's pool (SORTED LIST)

        # Calculate effective types
        effective_types_dict = self.base_card_types.copy()
        effective_types_dict.update(added)
        effective_types_dict.update(overrides)
        final_types = {}
        for card in self.card_pool:
            if card in effective_types_dict: final_types[card] = effective_types_dict[card]
            else: print(f"Warning: Card '{card}' missing type. Defaulting to MONSTER."); final_types[card] = "MONSTER"
        self.card_types = final_types # Final effective types dictionary

        # Calculate effective image paths (only include paths for cards in the effective pool)
        self.card_images = {card: path for card, path in image_paths.items() if card in self.card_pool}
        print(f"Calculated effective card database: {len(self.card_pool)} cards, {len(self.card_images)} image paths.")


    def reload_card_database(self):
        """Reloads user DB changes, recalculates effective DB, and updates relevant UI."""
        print("Reloading card database...")
        self.user_card_data = self._load_user_card_db()
        self._calculate_effective_card_db() # Recalculates pool, types, and images

        # Update card lists in deck builders
        self.update_card_list('a'); self.update_card_list('b')
        # Reload categories (filtered by new pool)
        self.load_card_categories()
        # Reload custom combos
        self.load_custom_combos()
        # Validate currently loaded decks against new pool
        self._validate_current_decks_against_pool('a')
        self._validate_current_decks_against_pool('b')
        # Update Open Editor Windows
        if hasattr(self, '_category_window') and self._category_window and self._category_window.winfo_exists():
             self._category_window.card_pool = self.card_pool; self._category_window._populate_lists()
        if hasattr(self, '_combo_editor_window') and self._combo_editor_window and self._combo_editor_window.winfo_exists():
             self._combo_editor_window.card_pool = self.card_pool
             pool_lb = getattr(self._combo_editor_window, 'pool_listbox', None)
             if pool_lb:
                 pool_lb.delete(0, tk.END);
                 for card in self.card_pool: pool_lb.insert(tk.END, card)

        self.update_status("Card database reloaded. UI and decks updated.", temporary=True)

    def _validate_current_decks_against_pool(self, deck_id):
         """Checks loaded deck against current pool, removes invalid cards, updates UI."""
         deck_list = self._get_deck_list(deck_id);
         if not deck_list: return
         invalid_cards = [card for card in list(deck_list.keys()) if card not in self.card_pool]
         if invalid_cards:
             removed_info = []; deck_name_var = self.current_deck_name_a if deck_id == 'a' else self.current_deck_name_b
             deck_label = deck_name_var if deck_name_var not in [NO_DECK_A, NO_DECK_B] else f"Deck {deck_id.upper()}"
             for card in invalid_cards: removed_info.append(f"- {card} (x{deck_list[card]})"); del deck_list[card]
             messagebox.showwarning("Deck Updated", f"Card DB changed. Invalid cards removed from '{deck_label}':\n" + "\n".join(removed_info), parent=self.root)
             self.update_deck_listbox(deck_id); self.update_deck_counts(deck_id)
             if self.comparison_mode.get(): self.update_deck_differences()
             self.validate_decks_for_submission()

    # --- GUI Setup Methods ---
    def _setup_gui(self):
        """Sets up the main application window layout and widgets."""
        self.root.columnconfigure(0, weight=1); self.root.rowconfigure(1, weight=1)
        self.deck_builder_frame = ttk.Frame(self.root); self.deck_builder_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.deck_builder_frame.columnconfigure(0, weight=1); self.deck_builder_frame.columnconfigure(1, weight=1); self.deck_builder_frame.rowconfigure(0, weight=1)
        self.deck_a_frame = self._create_deck_frame(self.deck_builder_frame, "Deck A"); self.deck_a_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.deck_b_frame = self._create_deck_frame(self.deck_builder_frame, "Deck B"); self.deck_b_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.file_frame = ttk.LabelFrame(self.root, text="File Operations & Tools"); self.file_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew"); self._setup_file_ops()
        self.current_deck_frame = ttk.Frame(self.root); self.current_deck_frame.grid(row=3, column=0, padx=10, pady=2, sticky="ew")
        self.current_deck_label_a = ttk.Label(self.current_deck_frame, text=f"Submitted A: {self.current_submitted_deck_a}"); self.current_deck_label_a.pack(side="left", padx=5)
        self.current_deck_label_b = ttk.Label(self.current_deck_frame, text=f"Submitted B: {self.current_submitted_deck_b}"); self.current_deck_label_b.pack(side="left", padx=5)
        self.simulation_frame = ttk.Frame(self.root); self.simulation_frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew"); self._setup_simulation_controls()
        self.deck_differences_frame = ttk.LabelFrame(self.root, text="Deck Differences (B vs A)"); self.deck_differences_frame.grid(row=5, column=0, padx=10, pady=5, sticky="ew"); self.deck_differences_frame.grid_remove()
        self.deck_differences_label = ttk.Label(self.deck_differences_frame, text="", justify=tk.LEFT, wraplength=900); self.deck_differences_label.pack(padx=5, pady=5, anchor="w", fill="x")
        self.status_bar = ttk.Label(self.root, textvariable=self.simulation_status_var, relief=tk.SUNKEN, anchor=tk.W); self.status_bar.grid(row=6, column=0, sticky="ew", padx=1, pady=1)

    def _create_deck_frame(self, parent, deck_label):
        """Helper method to create the frame and widgets for one deck builder (A or B)."""
        # (Identical to Part 2)
        is_deck_a = (deck_label == "Deck A"); deck_char = 'a' if is_deck_a else 'b'
        frame = ttk.LabelFrame(parent, text=deck_label); frame.columnconfigure(2, weight=1); frame.rowconfigure(1, weight=1)
        widgets = {}
        widgets['search_var'] = tk.StringVar(); widgets['search_var'].trace_add("write", lambda *args, d=deck_char: self.update_card_list(deck=d))
        search_label = ttk.Label(frame, text="Search Pool:"); search_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        widgets['search_entry'] = ttk.Entry(frame, textvariable=widgets['search_var']); widgets['search_entry'].grid(row=0, column=1, columnspan=1, padx=5, pady=2, sticky="ew")
        widgets['card_listbox'] = tk.Listbox(frame, width=35, height=10, exportselection=False); widgets['card_listbox'].grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        widgets['card_listbox'].bind("<Double-Button-1>", lambda event, d=deck_char: self.add_card(deck=d, quantity=1))
        pool_scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=widgets['card_listbox'].yview); pool_scrollbar.grid(row=1, column=1, padx=(0,5), pady=5, sticky="nse"); widgets['card_listbox'].config(yscrollcommand=pool_scrollbar.set)
        qty_label = ttk.Label(frame, text="Qty:"); qty_label.grid(row=2, column=0, padx=5, pady=2, sticky="e")
        widgets['quantity_var'] = tk.StringVar(value="1"); widgets['quantity_dropdown'] = ttk.Combobox(frame, textvariable=widgets['quantity_var'], values=["1", "2", "3"], state="readonly", width=5); widgets['quantity_dropdown'].grid(row=2, column=1, padx=5, pady=2, sticky="w")
        button_frame = ttk.Frame(frame); button_frame.grid(row=3, column=0, columnspan=2, pady=2)
        widgets['add_button'] = ttk.Button(button_frame, text="Add", width=8, command=lambda d=deck_char: self.add_card(deck=d)); widgets['add_button'].pack(side="left", padx=2)
        widgets['remove_button'] = ttk.Button(button_frame, text="Remove", width=8, command=lambda d=deck_char: self.remove_card(deck=d)); widgets['remove_button'].pack(side="left", padx=2)
        deck_list_label = ttk.Label(frame, text="Current Deck:"); deck_list_label.grid(row=0, column=2, padx=5, pady=2, sticky="w")
        widgets['deck_listbox'] = tk.Listbox(frame, width=40, height=15, exportselection=False); widgets['deck_listbox'].grid(row=1, column=2, rowspan=3, padx=5, pady=5, sticky="nsew")
        widgets['deck_listbox'].bind("<Double-Button-1>", lambda event, d=deck_char: self.remove_card(deck=d, quantity=1))
        deck_scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=widgets['deck_listbox'].yview); deck_scrollbar.grid(row=1, column=3, rowspan=3, padx=(0,5), pady=5, sticky="ns"); widgets['deck_listbox'].config(yscrollcommand=deck_scrollbar.set)
        widgets['total_count'] = tk.IntVar(value=0); widgets['monster_count'] = tk.IntVar(value=0); widgets['spell_count'] = tk.IntVar(value=0); widgets['trap_count'] = tk.IntVar(value=0)
        count_frame = ttk.LabelFrame(frame, text="Counts"); count_frame.grid(row=4, column=2, padx=5, pady=5, sticky="ew")
        count_frame.columnconfigure(0, weight=1); count_frame.columnconfigure(1, weight=1); count_frame.columnconfigure(2, weight=1); count_frame.columnconfigure(3, weight=1)
        ttk.Label(count_frame, text="Total:").grid(row=0, column=0, sticky="e"); ttk.Label(count_frame, textvariable=widgets['total_count']).grid(row=0, column=1, sticky="w", padx=2)
        ttk.Label(count_frame, text="M:").grid(row=0, column=2, sticky="e"); ttk.Label(count_frame, textvariable=widgets['monster_count']).grid(row=0, column=3, sticky="w", padx=2)
        ttk.Label(count_frame, text="S:").grid(row=1, column=0, sticky="e"); ttk.Label(count_frame, textvariable=widgets['spell_count']).grid(row=1, column=1, sticky="w", padx=2)
        ttk.Label(count_frame, text="T:").grid(row=1, column=2, sticky="e"); ttk.Label(count_frame, textvariable=widgets['trap_count']).grid(row=1, column=3, sticky="w", padx=2)
        frame.widgets = widgets; self.update_card_list(deck=deck_char, frame_widgets=widgets)
        return frame

    def _setup_file_ops(self):
        """Sets up the buttons and dropdowns for file operations and tools."""
        # (Identical to Part 2)
        self.load_deck_button_a = ttk.Button(self.file_frame, text="Load A", command=lambda: self.load_deck(deck='a'), width=8); self.load_deck_button_a.pack(side="left", padx=(5,2), pady=5)
        self.load_deck_dropdown_a = ttk.Combobox(self.file_frame, values=[], state="readonly", width=20); self.load_deck_dropdown_a.pack(side="left", padx=(0,5), pady=5)
        self.load_deck_dropdown_a.bind("<<ComboboxSelected>>", lambda event: self.load_deck(deck='a'))
        self.save_button_a = ttk.Button(self.file_frame, text="Save A", command=lambda: self.save_deck(deck='a'), width=8); self.save_button_a.pack(side="left", padx=5, pady=5)
        self.save_as_button_a = ttk.Button(self.file_frame, text="Save A As...", command=lambda: self.save_deck_as(deck='a'), width=10); self.save_as_button_a.pack(side="left", padx=(0,15), pady=5)
        self.load_deck_button_b = ttk.Button(self.file_frame, text="Load B", command=lambda: self.load_deck(deck='b'), width=8); self.load_deck_button_b.pack(side="left", padx=(5,2), pady=5)
        self.load_deck_dropdown_b = ttk.Combobox(self.file_frame, values=[], state="readonly", width=20); self.load_deck_dropdown_b.pack(side="left", padx=(0,5), pady=5)
        self.load_deck_dropdown_b.bind("<<ComboboxSelected>>", lambda event: self.load_deck(deck='b'))
        self.save_button_b = ttk.Button(self.file_frame, text="Save B", command=lambda: self.save_deck(deck='b'), width=8); self.save_button_b.pack(side="left", padx=5, pady=5)
        self.save_as_button_b = ttk.Button(self.file_frame, text="Save B As...", command=lambda: self.save_deck_as(deck='b'), width=10); self.save_as_button_b.pack(side="left", padx=5, pady=5)
        self.manage_categories_button = ttk.Button(self.file_frame, text="Manage Categories", command=self._open_category_manager); self.manage_categories_button.pack(side="right", padx=5, pady=5)
        self.manage_combos_button = ttk.Button(self.file_frame, text="Manage Combos", command=self._open_combo_editor); self.manage_combos_button.pack(side="right", padx=5, pady=5)
        self.manage_db_button = ttk.Button(self.file_frame, text="Manage Card DB", command=self._open_db_editor); self.manage_db_button.pack(side="right", padx=5, pady=5)
        self.ab_test_button = ttk.Button(self.file_frame, text="Card Evaluation Test", command=self._open_ab_test_window); self.ab_test_button.pack(side="right", padx=5, pady=5)

    def _setup_simulation_controls(self):
        """Sets up the widgets for controlling the simulation."""
        # (Identical to Part 2)
        self.submit_button = ttk.Button(self.simulation_frame, text="Submit Deck(s)", command=self.submit_decks, state="disabled"); self.submit_button.pack(side="left", padx=5, pady=5)
        num_sim_label = ttk.Label(self.simulation_frame, text="Simulations:"); num_sim_label.pack(side="left", padx=(10, 2), pady=5)
        validate_cmd = self.root.register(self._validate_simulation_entry); self.num_sim_entry = ttk.Entry(self.simulation_frame, textvariable=self.num_simulations, width=10, validate="key", validatecommand=(validate_cmd, '%P')); self.num_sim_entry.pack(side="left", padx=(0, 5), pady=5)
        self.start_simulation_button = ttk.Button(self.simulation_frame, text="Start Simulation", command=self.start_simulation_thread, state="disabled"); self.start_simulation_button.pack(side="left", padx=5, pady=5)
        self.comparison_mode_check = ttk.Checkbutton(self.simulation_frame, text="Comparison Mode", variable=self.comparison_mode, command=self.toggle_comparison_mode); self.comparison_mode_check.pack(side="left", padx=15, pady=5)

    def _validate_simulation_entry(self, value_if_allowed):
        """Validation function for the simulation number entry."""
        # (Identical to Part 2)
        if value_if_allowed == "": return True
        try: int(value_if_allowed); return True
        except ValueError: return False

    # --- GUI Update Methods ---
    def _get_deck_widgets(self, deck):
        """Helper to get the widgets dictionary for Deck A or B's frame."""
        # (Identical to Part 2)
        frame = self.deck_a_frame if deck == 'a' else self.deck_b_frame; return getattr(frame, 'widgets', None)

    def _get_deck_list(self, deck):
        """Helper to get the internal deck list dictionary for Deck A or B."""
        # (Identical to Part 2)
        if deck == 'a': return self.deck_list_a
        elif deck == 'b': return self.deck_list_b
        else: self.update_status(f"Invalid deck identifier '{deck}'", True); return None

    def update_card_list(self, deck, frame_widgets=None):
        """Updates the card pool listbox based on search term and effective pool."""
        # (Identical to Part 2)
        widgets = frame_widgets or self._get_deck_widgets(deck);
        if not widgets: return
        search_term = widgets['search_var'].get().lower(); listbox = widgets['card_listbox']
        current_selection_indices = listbox.curselection(); selected_card = listbox.get(current_selection_indices[0]) if current_selection_indices else None
        listbox.delete(0, tk.END); new_selection_index = -1
        for i, card in enumerate(self.card_pool):
            if search_term in card.lower(): listbox.insert(tk.END, card);
            if card == selected_card: new_selection_index = listbox.size() - 1
        if new_selection_index != -1: listbox.selection_set(new_selection_index); listbox.see(new_selection_index)

    def update_deck_listbox(self, deck):
        """Updates the deck listbox to show current cards and quantities."""
        # (Identical to Part 2)
        widgets = self._get_deck_widgets(deck); deck_list = self._get_deck_list(deck);
        if not widgets or deck_list is None: return
        listbox = widgets['deck_listbox']; current_selection_indices = listbox.curselection()
        selected_item_text = listbox.get(current_selection_indices[0]) if current_selection_indices else None
        listbox.delete(0, tk.END); new_selection_index = -1
        for i, (card, quantity) in enumerate(sorted(deck_list.items())):
            display_text = f"{card} x{quantity}"; listbox.insert(tk.END, display_text)
            if display_text == selected_item_text: new_selection_index = i
        if new_selection_index != -1: listbox.selection_set(new_selection_index); listbox.see(new_selection_index)

    def update_deck_counts(self, deck):
        """Updates the Monster/Spell/Trap/Total counts for a deck."""
        # (Identical to Part 2)
        widgets = self._get_deck_widgets(deck); deck_list = self._get_deck_list(deck);
        if not widgets or deck_list is None: return
        m_count, s_count, t_count, total_count = 0, 0, 0, 0
        for card, quantity in deck_list.items():
            card_type = self.card_types.get(card, "UNKNOWN"); total_count += quantity
            if card_type == "MONSTER": m_count += quantity
            elif card_type == "SPELL": s_count += quantity
            elif card_type == "TRAP": t_count += quantity
        widgets['total_count'].set(total_count); widgets['monster_count'].set(m_count)
        widgets['spell_count'].set(s_count); widgets['trap_count'].set(t_count)
        self.validate_decks_for_submission()

    def update_load_deck_dropdown(self):
        """Refreshes the list of saved decks in the dropdown menus."""
        # (Identical to Part 2)
        try:
            saved_decks = self.get_saved_decks(); self.load_deck_dropdown_a["values"] = saved_decks; self.load_deck_dropdown_b["values"] = saved_decks
            current_a = self.load_deck_dropdown_a.get();
            if current_a and current_a not in saved_decks: self.load_deck_dropdown_a.set("")
            current_b = self.load_deck_dropdown_b.get();
            if current_b and current_b not in saved_decks: self.load_deck_dropdown_b.set("")
        except Exception as e: self.update_status(f"Error updating deck dropdown lists: {e}", True)

    def update_deck_differences(self):
        """Calculates and displays differences between Deck A and B."""
        # (Identical to Part 2)
        if not self.comparison_mode.get():
             if self.deck_differences_frame.winfo_viewable(): self.deck_differences_frame.grid_remove(); return
        if not self.deck_differences_frame.winfo_viewable(): self.deck_differences_frame.grid()
        diff_lines = []; all_cards = set(self.deck_list_a.keys()) | set(self.deck_list_b.keys())
        for card in sorted(list(all_cards)):
            count_a = self.deck_list_a.get(card, 0); count_b = self.deck_list_b.get(card, 0); difference = count_b - count_a
            if difference > 0: diff_lines.append(f"+{difference} {card} (B has more)")
            elif difference < 0: diff_lines.append(f"{difference} {card} (A has more)")
        diff_text = "\n".join(diff_lines) if diff_lines else "No differences found between loaded decks."; self.deck_differences_label.config(text=diff_text)

    def toggle_comparison_mode(self):
        """Handles switching between single deck (A) and comparison (A vs B) mode."""
        # (Identical to Part 2)
        is_comparing = self.comparison_mode.get(); widgets_b = self._get_deck_widgets('b')
        if is_comparing:
            self.deck_b_frame.grid(); self.deck_differences_frame.grid(); self.submit_button.config(text="Submit Decks")
            self.load_deck_button_b.config(state="normal"); self.load_deck_dropdown_b.config(state="readonly"); self.save_button_b.config(state="normal"); self.save_as_button_b.config(state="normal")
            if widgets_b:
                for widget in widgets_b.values():
                    if hasattr(widget, 'config'):
                         if isinstance(widget, ttk.Combobox) and widget == widgets_b.get('quantity_dropdown'): widget.config(state="readonly")
                         elif hasattr(widget, 'config'): widget.config(state="normal")
            self.update_deck_differences()
        else:
            self.deck_b_frame.grid_remove(); self.deck_differences_frame.grid_remove(); self.submit_button.config(text="Submit Deck A")
            self.load_deck_button_b.config(state="disabled"); self.load_deck_dropdown_b.config(state="disabled"); self.save_button_b.config(state="disabled"); self.save_as_button_b.config(state="disabled")
            if widgets_b:
                for name, widget in widgets_b.items():
                    if name not in ['search_var', 'quantity_var', 'total_count', 'monster_count', 'spell_count', 'trap_count']:
                        if hasattr(widget, 'config'): widget.config(state="disabled")
            self.current_submitted_deck_b = ""; self.current_deck_label_b.config(text="Submitted B: "); self.submitted_deck_list_b = {}; self.submitted_stats_b = {}
        self.validate_decks_for_submission()

    def update_status(self, message, error=False, temporary=False):
        """Updates the status bar text, optionally logging errors and setting a clear timer."""
        # (Identical to Part 2)
        if self._after_id_status_clear: self.root.after_cancel(self._after_id_status_clear); self._after_id_status_clear = None
        prefix = "ERROR: " if error else "Status: "; self.simulation_status_var.set(f"{prefix}{message}")
        if error: print(f"ERROR: {message}")
        else: print(f"STATUS: {message}")
        if temporary and not error: self._after_id_status_clear = self.root.after(STATUS_CLEAR_DELAY, lambda: self.update_status("Idle"))

    # --- Deck Manipulation Methods ---
    def add_card(self, deck, quantity=None):
        """Adds the selected card from the pool to the specified deck."""
        # (Identical to Part 2)
        widgets = self._get_deck_widgets(deck); deck_list = self._get_deck_list(deck);
        if not widgets or deck_list is None: return
        pool_listbox = widgets['card_listbox']; selected_index = pool_listbox.curselection();
        if not selected_index: messagebox.showwarning("No Card Selected", "Please select a card from the pool list first.", parent=self.root); return
        card_to_add = pool_listbox.get(selected_index[0])
        if quantity is None:
            try: quantity_to_add = int(widgets['quantity_var'].get())
            except ValueError: messagebox.showerror("Invalid Quantity", "Quantity must be a number.", parent=self.root); return
        else: quantity_to_add = quantity
        current_quantity = deck_list.get(card_to_add, 0); current_total_cards = sum(deck_list.values())
        if current_quantity + quantity_to_add > MAX_CARD_COPIES: messagebox.showwarning("Card Limit Exceeded", f"Max {MAX_CARD_COPIES} copies of '{card_to_add}'. You have {current_quantity}.", parent=self.root); return
        if current_total_cards + quantity_to_add > MAX_DECK_SIZE: messagebox.showwarning("Deck Size Limit Exceeded", f"Max deck size is {MAX_DECK_SIZE}. Adding {quantity_to_add} would exceed limit.", parent=self.root); return
        deck_list[card_to_add] = current_quantity + quantity_to_add
        self.update_deck_listbox(deck); self.update_deck_counts(deck);
        if self.comparison_mode.get(): self.update_deck_differences()

    def remove_card(self, deck, quantity=None):
        """Removes the selected card from the specified deck."""
        # (Identical to Part 2)
        widgets = self._get_deck_widgets(deck); deck_list = self._get_deck_list(deck);
        if not widgets or deck_list is None: return
        deck_listbox = widgets['deck_listbox']; selected_index = deck_listbox.curselection();
        if not selected_index: messagebox.showwarning("No Card Selected", f"Select card from Deck {deck.upper()} list to remove.", parent=self.root); return
        selected_item_text = deck_listbox.get(selected_index[0]); match = re.match(r"^(.*)\s+x\d+$", selected_item_text);
        if not match: messagebox.showerror("Parse Error", f"Could not parse card name from '{selected_item_text}'.", parent=self.root); return
        card_to_remove = match.group(1).strip()
        if quantity is None:
            try: quantity_to_remove = int(widgets['quantity_var'].get())
            except ValueError: messagebox.showerror("Invalid Quantity", "Quantity must be a number.", parent=self.root); return
        else: quantity_to_remove = quantity
        current_quantity = deck_list.get(card_to_remove, 0)
        if current_quantity == 0: messagebox.showwarning("Card Not Found", f"Card '{card_to_remove}' not in Deck {deck.upper()}.", parent=self.root); return
        if quantity_to_remove > current_quantity: messagebox.showwarning("Invalid Quantity", f"Cannot remove {quantity_to_remove} copies of '{card_to_remove}', you only have {current_quantity}.", parent=self.root); return
        new_quantity = current_quantity - quantity_to_remove
        if new_quantity <= 0: del deck_list[card_to_remove]
        else: deck_list[card_to_remove] = new_quantity
        self.update_deck_listbox(deck); self.update_deck_counts(deck);
        if self.comparison_mode.get(): self.update_deck_differences()

    def get_total_cards(self, deck):
        """Calculates the total number of cards in the specified deck's list."""
        # (Identical to Part 2)
        deck_list = self._get_deck_list(deck); return sum(deck_list.values()) if deck_list else 0

    # --- File Operations ---
    def get_saved_decks(self):
        """Returns a sorted list of '.json' filenames in the decks directory."""
        # (Identical to Part 2)
        try:
            if not os.path.exists(DECKS_DIR): os.makedirs(DECKS_DIR); return []
            files = [f for f in os.listdir(DECKS_DIR) if f.lower().endswith(".json") and os.path.isfile(os.path.join(DECKS_DIR, f))]
            return sorted(files, key=str.lower)
        except Exception as e: self.update_status(f"Error accessing decks directory '{DECKS_DIR}': {e}", True); return []

    def save_deck_as(self, deck):
        """Prompts the user for a filename and saves the specified deck."""
        # (Identical to Part 2)
        deck_list = self._get_deck_list(deck); current_name_var = self.current_deck_name_a if deck == 'a' else self.current_deck_name_b; no_deck_name = NO_DECK_A if deck == 'a' else NO_DECK_B
        if not deck_list: messagebox.showwarning("Empty Deck", f"Deck {deck.upper()} is empty.", parent=self.root); return
        initial_filename = current_name_var if current_name_var != no_deck_name else f"new_deck_{deck}.json"
        file_path = filedialog.asksaveasfilename(initialdir=DECKS_DIR, initialfile=initial_filename, defaultextension=".json", filetypes=[("JSON Deck Files", "*.json"), ("All Files", "*.*")], title=f"Save Deck {deck.upper()} As...")
        if file_path:
            filename = os.path.basename(file_path)
            if deck == 'a': self.current_deck_name_a = filename
            else: self.current_deck_name_b = filename
            if self.save_deck(file_path=file_path, deck=deck):
                self.update_load_deck_dropdown()
                dropdown = self.load_deck_dropdown_a if deck == 'a' else self.load_deck_dropdown_b; dropdown.set(filename)

    def save_deck(self, file_path=None, deck=None):
        """Saves the specified deck list to a file (JSON format)."""
        # (Identical to Part 2)
        deck_list = self._get_deck_list(deck); current_name_var = self.current_deck_name_a if deck == 'a' else self.current_deck_name_b; no_deck_name = NO_DECK_A if deck == 'a' else NO_DECK_B
        if not deck_list:
            if file_path is None: messagebox.showwarning("Empty Deck", f"Deck {deck.upper()} is empty.", parent=self.root)
            return False
        if file_path is None:
            if current_name_var == no_deck_name: self.save_deck_as(deck=deck); return False
            else: file_path = os.path.join(DECKS_DIR, current_name_var)
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f: json.dump(deck_list, f, indent=4, sort_keys=True)
            if file_path.endswith(os.path.basename(file_path)): self.update_status(f"Deck {deck.upper()} saved as {os.path.basename(file_path)}", temporary=True)
            return True
        except Exception as e: self.update_status(f"Failed to save deck to '{os.path.basename(file_path)}': {e}", True); messagebox.showerror("Save Error", f"Could not save deck:\n{e}", parent=self.root); return False

    def load_deck(self, deck, deck_filename=None):
        """Loads a deck from a selected JSON file into Deck A or B."""
        # (Identical to Part 2)
        if deck_filename is None:
             dropdown = self.load_deck_dropdown_a if deck == 'a' else self.load_deck_dropdown_b; deck_filename = dropdown.get()
             if not deck_filename: return False
        path = os.path.join(DECKS_DIR, deck_filename)
        try:
            with open(path, "r") as f: loaded_data = json.load(f)
            if not isinstance(loaded_data, dict): raise TypeError("Invalid deck file format.")
            loaded_deck_list = {}; invalid_cards_found = []; invalid_format_entries = []; total_cards = 0
            for card, count in loaded_data.items():
                if not isinstance(card, str) or not isinstance(count, int) or count < 1 or count > MAX_CARD_COPIES: invalid_format_entries.append(f"'{card}': {count}"); continue
                if card not in self.card_pool: invalid_cards_found.append(f"{card} (x{count})"); continue
                loaded_deck_list[card] = count; total_cards += count
            min_size_warning = False
            if total_cards < MIN_DECK_SIZE: min_size_warning = True
            if total_cards > MAX_DECK_SIZE: raise ValueError(f"Deck size ({total_cards}) exceeds max {MAX_DECK_SIZE}.")
            warning_messages = []
            if invalid_format_entries: warning_messages.append("Invalid format entries ignored:\n- " + "\n- ".join(invalid_format_entries))
            if invalid_cards_found: warning_messages.append("Cards not in DB ignored:\n- " + "\n- ".join(invalid_cards_found))
            if min_size_warning: warning_messages.append(f"Deck has only {total_cards} valid cards (min {MIN_DECK_SIZE}).")
            if warning_messages: messagebox.showwarning("Load Issues", f"Issues loading '{deck_filename}':\n\n" + "\n\n".join(warning_messages), parent=self.root)
            if deck == 'a': self.deck_list_a = loaded_deck_list; self.current_deck_name_a = deck_filename
            else: self.deck_list_b = loaded_deck_list; self.current_deck_name_b = deck_filename
            self.update_deck_listbox(deck); self.update_deck_counts(deck)
            if self.comparison_mode.get(): self.update_deck_differences()
            self.update_status(f"Deck '{deck_filename}' loaded into Deck {deck.upper()}.", temporary=True)
            dropdown = self.load_deck_dropdown_a if deck == 'a' else self.load_deck_dropdown_b; dropdown.set(deck_filename)
            return True
        except FileNotFoundError: self.update_status(f"Deck file not found: {deck_filename}", True); messagebox.showerror("Load Error", f"Could not find deck file:\n{path}", parent=self.root); self.update_load_deck_dropdown(); return False
        except (json.JSONDecodeError, ValueError, TypeError) as e: self.update_status(f"Invalid deck file '{deck_filename}': {e}", True); messagebox.showerror("Load Error", f"Failed to load deck '{deck_filename}':\n{e}", parent=self.root); return False
        except Exception as e: self.update_status(f"Unexpected error loading '{deck_filename}': {e}", True); import traceback; traceback.print_exc(); messagebox.showerror("Load Error", f"Unexpected error loading '{deck_filename}':\n{e}", parent=self.root); return False

    # --- Category Management Methods ---
    def _load_initial_categories(self):
        """Loads card categories from CATEGORY_FILE, filtering by effective pool."""
        # (Identical to Part 1)
        categories = {};
        try:
            if os.path.exists(CATEGORY_FILE):
                with open(CATEGORY_FILE, 'r') as f: data = json.load(f)
                if not isinstance(data, dict): print(f"Warning: {CATEGORY_FILE} not a dictionary."); return {}
                converted_data = {}; needs_resave = False
                for card, value in data.items():
                    if card not in self.card_pool: continue
                    if isinstance(value, str): converted_data[card] = [value]; needs_resave = True
                    elif isinstance(value, list):
                        valid_cats = sorted(list(set(str(cat) for cat in value if isinstance(cat, str))))
                        if valid_cats: converted_data[card] = valid_cats
                if needs_resave:
                    print(f"Info: Converting category file '{CATEGORY_FILE}'.")
                    try:
                        with open(CATEGORY_FILE, 'w') as wf: json.dump(converted_data, wf, indent=4, sort_keys=True)
                    except Exception as save_err: print(f"Error saving converted categories: {save_err}")
                print(f"Loaded {len(converted_data)} category assignments."); return converted_data
            else: print(f"Info: Category file '{CATEGORY_FILE}' not found."); return {}
        except (json.JSONDecodeError, Exception) as e: print(f"ERROR loading categories: {e}"); return {}

    def load_card_categories(self):
         """Reloads categories from file."""
         # (Identical to Part 1)
         self.card_categories = self._load_initial_categories()

    def _open_category_manager(self):
        """Opens the Toplevel window for managing card categories."""
        # (Identical to Part 1)
        if hasattr(self, '_category_window') and self._category_window and self._category_window.winfo_exists(): self._category_window.lift(); return
        self._category_window = CategoryManagerWindow(self.root, self.card_pool)

    # --- App State Persistence ---
    def _load_app_state(self):
        """Loads the last used deck filenames from APP_STATE_FILE."""
        # (Identical to Part 1)
        try:
            if os.path.exists(APP_STATE_FILE):
                with open(APP_STATE_FILE, 'r') as f: state = json.load(f)
                return state.get("last_deck_a"), state.get("last_deck_b")
        except (json.JSONDecodeError, Exception) as e: print(f"Warning: Could not load app state: {e}")
        return None, None

    def _save_app_state(self, deck_a_name, deck_b_name):
        """Saves the submitted deck filenames to APP_STATE_FILE."""
        # (Identical to Part 1)
        state = {"last_deck_a": deck_a_name if deck_a_name != NO_DECK_A else None, "last_deck_b": deck_b_name if deck_b_name != NO_DECK_B else None}
        try:
            with open(APP_STATE_FILE, 'w') as f: json.dump(state, f, indent=4)
        except Exception as e: print(f"Warning: Could not save app state: {e}")

    def _load_last_submitted_decks(self):
         """Attempts to load the decks saved in the app state on startup."""
         # (Identical to Part 1)
         last_a_name, last_b_name = self._load_app_state(); loaded_any = False
         if last_a_name and os.path.exists(os.path.join(DECKS_DIR, last_a_name)):
              print(f"Attempting preload A: {last_a_name}")
              if self.load_deck(deck='a', deck_filename=last_a_name): loaded_any = True
         elif last_a_name: print(f"Info: Last Deck A file '{last_a_name}' not found.")
         if self.comparison_mode.get() and last_b_name and os.path.exists(os.path.join(DECKS_DIR, last_b_name)):
              print(f"Attempting preload B: {last_b_name}")
              if self.load_deck(deck='b', deck_filename=last_b_name): loaded_any = True
         elif last_b_name: print(f"Info: Last Deck B file '{last_b_name}' not found.")
         if loaded_any: self.update_status("Loaded last used deck(s).", temporary=True)
         else: self.update_status("No previous decks found or loaded.")
         if not self.deck_list_a: self.current_deck_name_a = NO_DECK_A
         if not self.deck_list_b: self.current_deck_name_b = NO_DECK_B

    # --- Simulation & Analysis Trigger Methods ---
    def validate_decks_for_submission(self):
        """Checks if the loaded decks meet requirements for simulation."""
        # (Identical to Part 1)
        total_a = sum(self.deck_list_a.values()); valid_a = total_a >= MIN_DECK_SIZE and total_a <= MAX_DECK_SIZE
        valid_b = True
        if self.comparison_mode.get(): total_b = sum(self.deck_list_b.values()); valid_b = total_b >= MIN_DECK_SIZE and total_b <= MAX_DECK_SIZE
        can_submit = valid_a and valid_b; self.submit_button.config(state="normal" if can_submit else "disabled")
        if not can_submit: self.start_simulation_button.config(state="disabled")
        return can_submit

    def submit_decks(self):
        """Copies the current deck states for simulation and enables Start."""
        # (Identical to Part 1)
        if not self.validate_decks_for_submission():
            msg = []; total_a = sum(self.deck_list_a.values())
            if total_a < MIN_DECK_SIZE: msg.append(f"Deck A < {MIN_DECK_SIZE} cards.")
            if total_a > MAX_DECK_SIZE: msg.append(f"Deck A > {MAX_DECK_SIZE} cards.")
            if self.comparison_mode.get():
                total_b = sum(self.deck_list_b.values())
                if total_b < MIN_DECK_SIZE: msg.append(f"Deck B < {MIN_DECK_SIZE} cards.")
                if total_b > MAX_DECK_SIZE: msg.append(f"Deck B > {MAX_DECK_SIZE} cards.")
            messagebox.showwarning("Invalid Deck(s)", "Cannot submit:\n" + "\n".join(msg), parent=self.root); return
        self.submitted_deck_list_a = self.deck_list_a.copy(); self.current_submitted_deck_a = self.current_deck_name_a
        widgets_a = self._get_deck_widgets('a'); self.submitted_stats_a = {'total': widgets_a['total_count'].get(), 'M': widgets_a['monster_count'].get(), 'S': widgets_a['spell_count'].get(), 'T': widgets_a['trap_count'].get()} if widgets_a else {}
        self.current_deck_label_a.config(text=f"Submitted A: {self.current_submitted_deck_a}")
        self.submitted_is_comparison = self.comparison_mode.get()
        if self.submitted_is_comparison:
            self.submitted_deck_list_b = self.deck_list_b.copy(); self.current_submitted_deck_b = self.current_deck_name_b
            widgets_b = self._get_deck_widgets('b'); self.submitted_stats_b = {'total': widgets_b['total_count'].get(), 'M': widgets_b['monster_count'].get(), 'S': widgets_b['spell_count'].get(), 'T': widgets_b['trap_count'].get()} if widgets_b else {}
            self.current_deck_label_b.config(text=f"Submitted B: {self.current_submitted_deck_b}")
        else: self.submitted_deck_list_b = {}; self.current_submitted_deck_b = ""; self.submitted_stats_b = {}; self.current_deck_label_b.config(text="Submitted B: ")
        self._save_app_state(self.current_submitted_deck_a, self.current_submitted_deck_b)
        self.start_simulation_button.config(state="normal"); self.update_status("Deck(s) submitted. Ready for simulation.", temporary=True)

    def start_simulation_thread(self):
        """Starts the simulation process in a separate thread."""
        # (Identical to Part 1)
        self.update_status("Starting simulation..."); self.start_simulation_button.config(state="disabled"); self.submit_button.config(state="disabled")
        try: 
            num_sim = self.num_simulations.get()
            if num_sim <= 0: raise ValueError("Simulations must be positive.")
        except (ValueError, tk.TclError) as e: 
            self.update_status(f"Invalid simulation number: {e}", True); messagebox.showerror("Input Error", f"Enter valid positive number for simulations.", parent=self.root); self.validate_decks_for_submission(); return
        deck_a_to_sim = self.submitted_deck_list_a; is_comp_to_sim = self.submitted_is_comparison; deck_b_to_sim = self.submitted_deck_list_b if is_comp_to_sim else None
        name_a_to_sim = self.current_submitted_deck_a; name_b_to_sim = self.current_submitted_deck_b if is_comp_to_sim else ""; stats_a_to_sim = self.submitted_stats_a; stats_b_to_sim = self.submitted_stats_b if is_comp_to_sim else None
        cats_copy = self.card_categories.copy()
        all_combos_to_pass = analysis_engine._define_combos(); all_combos_to_pass.update(self.custom_combos)
        combo_map_to_pass = analysis_engine._define_combo_card_map()
        sim_thread = threading.Thread(target=self._run_simulation_task, args=(num_sim, is_comp_to_sim, deck_a_to_sim, deck_b_to_sim, name_a_to_sim, name_b_to_sim, stats_a_to_sim, stats_b_to_sim, cats_copy, all_combos_to_pass, combo_map_to_pass), daemon=True); sim_thread.start()

    def _run_simulation_task(self, num_sim, is_comp, deck_a, deck_b, name_a, name_b, stats_a, stats_b, card_categories, card_combos, combo_card_map):
        """The actual simulation logic executed in a separate thread."""
        # (Identical to Part 1)
        try:
            self.simulation_queue.put(("status", f"Simulating Deck A ('{name_a}')...")); results_a = analysis_engine.run_simulation(num_sim, deck_a, "A", card_combos, card_categories, self.simulation_queue)
            if not results_a: return
            results_b = None
            if is_comp: self.simulation_queue.put(("status", f"Simulating Deck B ('{name_b}')...")); results_b = analysis_engine.run_simulation(num_sim, deck_b, "B", card_combos, card_categories, self.simulation_queue) # Continue even if B fails
            self.simulation_queue.put(("status", "Analyzing results and generating PDF report..."))
            pdf_filename = analysis_engine.analyze_and_generate_pdf(results_a, results_b, deck_a, deck_b, name_a, name_b, is_comp, card_combos, combo_card_map, card_categories, self.simulation_queue, stats_a, stats_b)
            if pdf_filename: self.simulation_queue.put(("pdf_ready", pdf_filename))
            else: self.simulation_queue.put(("error", "PDF generation failed."))
        except Exception as e: import traceback; traceback.print_exc(); self.simulation_queue.put(("error", f"Simulation task failed: {e}"))
        finally: self.simulation_queue.put(("simulation_complete", None))

    def _check_simulation_queue(self):
        """Periodically checks the queue for messages from the simulation thread."""
        # (Identical to Part 1)
        try:
            while True:
                msg_type, msg_data = self.simulation_queue.get_nowait()
                if msg_type == "status": self.update_status(msg_data)
                elif msg_type == "error": self.update_status(msg_data, error=True); self.validate_decks_for_submission(); self._unbind_pdf_prompt_keys()
                elif msg_type == "pdf_ready":
                    pdf_path = msg_data; self.last_pdf_path = pdf_path; base_filename = os.path.basename(pdf_path)
                    status_msg = f"PDF Ready: {base_filename}. Space=Open Folder, X=Dismiss."; self.update_status(status_msg); self._bind_pdf_prompt_keys(); self.validate_decks_for_submission()
                elif msg_type == "simulation_complete": self.validate_decks_for_submission()
                self.simulation_queue.task_done()
        except queue.Empty: self.root.after(100, self._check_simulation_queue)
        except Exception as e: print(f"Error processing simulation queue: {e}"); import traceback; traceback.print_exc(); self.update_status(f"Queue processing error: {e}", True); self.root.after(100, self._check_simulation_queue)

    # --- PDF Prompt Handlers ---
    def _bind_pdf_prompt_keys(self):
        """Binds Space and X keys for the PDF ready prompt."""
        # (Identical to Part 1)
        self._unbind_pdf_prompt_keys(); self.root.bind("<space>", self._handle_open_pdf_prompt); self.root.bind("<KeyPress-x>", self._handle_dismiss_pdf_prompt); self.root.bind("<KeyPress-X>", self._handle_dismiss_pdf_prompt); self.root.focus_set()

    def _unbind_pdf_prompt_keys(self):
        """Unbinds keys used for the PDF prompt."""
        # (Identical to Part 1)
        self.root.unbind("<space>"); self.root.unbind("<KeyPress-x>"); self.root.unbind("<KeyPress-X>")

    def _handle_open_pdf_prompt(self, event=None):
        """Handles the Space key press: opens the PDF output folder."""
        # (Identical to Part 1)
        if self.last_pdf_path and os.path.exists(self.last_pdf_path):
            folder_path = os.path.dirname(self.last_pdf_path)
            try:
                if sys.platform == "win32": os.startfile(folder_path)
                elif sys.platform == "darwin": subprocess.run(["open", folder_path], check=True)
                else: subprocess.run(["xdg-open", folder_path], check=True)
                self.update_status(f"Opened folder: {folder_path}", temporary=True)
            except Exception as e: self.update_status(f"Error opening folder '{folder_path}': {e}", error=True); messagebox.showerror("Error", f"Could not open folder:\n{e}", parent=self.root)
        else: self.update_status("PDF path not found or invalid.", error=True)
        self._unbind_pdf_prompt_keys(); self.last_pdf_path = None

    def _handle_dismiss_pdf_prompt(self, event=None):
        """Handles the X key press: dismisses the prompt."""
        # (Identical to Part 1)
        self._unbind_pdf_prompt_keys(); self.last_pdf_path = None; self.update_status("Idle")

    # --- Custom Combo Methods ---
    def _load_initial_custom_combos(self):
        """Loads custom combo definitions from CUSTOM_COMBO_FILE."""
        # (Identical to Part 1)
        try:
            if os.path.exists(CUSTOM_COMBO_FILE):
                with open(CUSTOM_COMBO_FILE, 'r') as f: data = json.load(f)
                if isinstance(data, dict): print(f"Loaded {len(data)} custom combos."); return data
                else: print(f"Warning: {CUSTOM_COMBO_FILE} invalid format."); return {}
            else: print(f"Info: Custom combo file '{CUSTOM_COMBO_FILE}' not found."); return {}
        except (json.JSONDecodeError, Exception) as e: print(f"ERROR loading custom combos: {e}"); return {}

    def load_custom_combos(self):
        """Reloads custom combos."""
        # (Identical to Part 1)
        self.custom_combos = self._load_initial_custom_combos()

    def _open_combo_editor(self):
        """Opens the Toplevel window for managing custom combos."""
        # (Identical to Part 1)
        if hasattr(self, '_combo_editor_window') and self._combo_editor_window and self._combo_editor_window.winfo_exists(): self._combo_editor_window.lift(); return
        self._combo_editor_window = ComboEditorWindow(self.root, self.card_pool, self.custom_combos, self.hardcoded_combo_definitions)

    # --- Card DB Editor Methods ---
    def _open_db_editor(self):
         """Opens the Toplevel window for managing the card database."""
         # (Identical to Part 1)
         if hasattr(self, '_db_editor_window') and self._db_editor_window and self._db_editor_window.winfo_exists(): self._db_editor_window.lift(); return
         self._db_editor_window = CardDatabaseEditorWindow(self)

    # --- A/B Hand Test (Card Evaluation) Methods ---
    def _open_ab_test_window(self):
        """Opens the Toplevel window for A/B Hand Testing (Card Evaluation)."""
        # (Identical to Part 1)
        if hasattr(self, '_ab_test_window') and self._ab_test_window and self._ab_test_window.winfo_exists(): self._ab_test_window.lift(); return
        saved_decks = self.get_saved_decks()
        if not saved_decks: messagebox.showwarning("No Saved Decks", "Card Evaluation Test requires saved decks. Please save a deck first.", parent=self.root); return
        self._ab_test_window = ABTestWindow(self, saved_decks)

# --- End of DeckSimulatorApp Class ---


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    # Set a theme (optional)
    try:
        style = ttk.Style(root); available_themes = style.theme_names(); print("Available themes:", available_themes)
        if 'vista' in available_themes: style.theme_use('vista')
        elif 'aqua' in available_themes: style.theme_use('aqua')
        elif 'clam' in available_themes: style.theme_use('clam')
        print(f"Using theme: {style.theme_use()}")
    except tk.TclError: print("ttk themes not available.")

    app = DeckSimulatorApp(root)
    root.mainloop()
