import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
import random # Still needed? Maybe not directly, but keep for now.
from collections import Counter # Keep for potential future use in main
import re
import threading
import queue
import subprocess # For opening folder
import sys # For platform check

# Local Imports
try:
    from card_database import CARD_POOL, CARD_TYPES
except ImportError:
    messagebox.showerror("Import Error", "Could not find card_database.py.")
    exit()
try:
    import analysis_engine # Assumes analysis_engine.py exists
except ImportError:
    messagebox.showerror("Import Error", "Could not find analysis_engine.py.")
    exit()
# --------------------------------------

# --- Constants ---
DEFAULT_SIMULATIONS = 100000
MIN_DECK_SIZE = 40
MAX_DECK_SIZE = 60
MAX_CARD_COPIES = 3
DECKS_DIR = "decks"
NO_DECK_A = "No Deck Selected (A)"
NO_DECK_B = "No Deck Selected (B)"
CATEGORY_FILE = "card_categories.json"
APP_STATE_FILE = "app_state.json" # For saving last loaded decks
CUSTOM_COMBO_FILE = "custom_combos.json"
USER_DB_FILE = "user_card_database.json" # For user DB changes
STATUS_CLEAR_DELAY = 4000 # Milliseconds to show status messages

# --- Category Management Window ---
class CategoryManagerWindow(tk.Toplevel):
    """A Toplevel window for managing card categories."""
    # ... (Code for CategoryManagerWindow - Assuming unchanged from previous correct version) ...
    def __init__(self, parent, card_pool):
        super().__init__(parent)
        self.parent_app = parent # Reference to the main DeckSimulatorApp
        self.card_pool = card_pool # Store the passed card_pool
        self.card_categories = self._load_categories() # Load initial data
        self.selected_card = tk.StringVar()
        self.selected_category = tk.StringVar()
        self.new_category_var = tk.StringVar()
        self.title("Card Category Manager"); self.geometry("700x550"); self.transient(parent); self.grab_set()
        self._setup_category_gui(); self._populate_lists()
    def _load_categories(self):
        categories = {}; 
        try:
            if os.path.exists(CATEGORY_FILE):
                with open(CATEGORY_FILE, 'r') as f: data = json.load(f)
                if isinstance(data, dict):
                    for card, value in data.items():
                        if card not in self.card_pool: print(f"Warn: Cat card '{card}' not in pool."); continue
                        if isinstance(value, list): categories[card] = sorted(list(set(value)))
                        elif isinstance(value, str): print(f"Info: Converting old cat format for '{card}'."); categories[card] = [value]
                        else: print(f"Warn: Invalid cat data for '{card}'")
                    return categories
                else: print(f"Warn: {CATEGORY_FILE} invalid."); return {}
            else: return {}
        except (json.JSONDecodeError, Exception) as e: print(f"Error loading cats: {e}"); messagebox.showerror("Load Error", f"Failed cats: {e}", parent=self); return {}
    def _save_categories(self):
        try:
            cleaned_categories = {card: cats for card, cats in self.card_categories.items() if card in self.card_pool}
            with open(CATEGORY_FILE, 'w') as f: json.dump(cleaned_categories, f, indent=4, sort_keys=True)
            print(f"Cats saved to {CATEGORY_FILE}")
            if hasattr(self.parent_app, 'load_card_categories'): self.parent_app.load_card_categories()
        except Exception as e: print(f"Error saving cats: {e}"); messagebox.showerror("Save Error", f"Failed cats: {e}", parent=self)
    def _setup_category_gui(self):
        main_frame = ttk.Frame(self, padding="10"); main_frame.pack(expand=True, fill="both")
        main_frame.columnconfigure(1, weight=1); main_frame.columnconfigure(3, weight=1); main_frame.rowconfigure(1, weight=1)
        ttk.Label(main_frame, text="Available Cards:").grid(row=0, column=0, columnspan=2, pady=(0, 5), sticky="w")
        self.card_listbox = tk.Listbox(main_frame, width=40, exportselection=False); self.card_listbox.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        card_scroll = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.card_listbox.yview); card_scroll.grid(row=1, column=1, padx=(0,5), pady=5, sticky="nse"); self.card_listbox.config(yscrollcommand=card_scroll.set)
        self.card_listbox.bind('<<ListboxSelect>>', self._on_card_select)
        ttk.Label(main_frame, text="Categories:").grid(row=0, column=2, columnspan=2, pady=(0, 5), sticky="w")
        self.category_listbox = tk.Listbox(main_frame, width=30, exportselection=False); self.category_listbox.grid(row=1, column=2, columnspan=2, padx=5, pady=5, sticky="nsew")
        cat_scroll = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.category_listbox.yview); cat_scroll.grid(row=1, column=3, padx=(0,5), pady=5, sticky="nse"); self.category_listbox.config(yscrollcommand=cat_scroll.set)
        self.category_listbox.bind('<<ListboxSelect>>', self._on_category_select)
        control_frame = ttk.Frame(main_frame); control_frame.grid(row=2, column=0, columnspan=4, pady=10)
        ttk.Label(control_frame, text="New Category:").pack(side="left", padx=(0, 5))
        new_cat_entry = ttk.Entry(control_frame, textvariable=self.new_category_var, width=15); new_cat_entry.pack(side="left", padx=5)
        ttk.Button(control_frame, text="Add Cat", command=self._add_category, width=8).pack(side="left", padx=5)
        ttk.Button(control_frame, text="Del Cat", command=self._remove_category, width=8).pack(side="left", padx=(5, 20))
        self.assign_button = ttk.Button(control_frame, text="Assign Card", command=self._assign_card, state="disabled", width=12); self.assign_button.pack(side="left", padx=5)
        self.unassign_button = ttk.Button(control_frame, text="Unassign Card", command=self._unassign_card, state="disabled", width=12); self.unassign_button.pack(side="left", padx=5)
        bottom_frame = ttk.Frame(main_frame); bottom_frame.grid(row=3, column=0, columnspan=4, pady=10)
        ttk.Button(bottom_frame, text="Save Categories", command=self._save_categories).pack(side="left", padx=10)
        ttk.Button(bottom_frame, text="Close", command=self.destroy).pack(side="left", padx=10)
        self.selection_label = ttk.Label(main_frame, text="Select a card and a category."); self.selection_label.grid(row=4, column=0, columnspan=4, pady=5)
    def _populate_lists(self):
        self.card_listbox.delete(0, tk.END)
        for card in self.card_pool:
            categories = self.card_categories.get(card, []); cat_string = ", ".join(categories)
            display_text = f"{card}" + (f" [{cat_string}]" if cat_string else "")
            self.card_listbox.insert(tk.END, display_text)
        self.category_listbox.delete(0, tk.END)
        all_assigned_cats = set(cat for cats in self.card_categories.values() for cat in cats)
        for category in sorted(list(all_assigned_cats)): self.category_listbox.insert(tk.END, category)
    def _on_card_select(self, event):
        selection = self.card_listbox.curselection()
        if selection: card_name = self.card_listbox.get(selection[0]).split(" [")[0]; self.selected_card.set(card_name)
        else: self.selected_card.set("")
        self._update_selection_status()
    def _on_category_select(self, event):
        selection = self.category_listbox.curselection()
        if selection: self.selected_category.set(self.category_listbox.get(selection[0]))
        else: self.selected_category.set("")
        self._update_selection_status()
    def _update_selection_status(self):
        card = self.selected_card.get(); category = self.selected_category.get(); status_text = "Selection: "
        can_assign, can_unassign = False, False
        if card:
            status_text += f"Card='{card}'"; current_cats = self.card_categories.get(card, [])
            if category:
                status_text += f", Category='{category}'"
                if category not in current_cats: can_assign = True
                if category in current_cats: can_unassign = True
            else:
                 status_text += ", Category=None"
                 if current_cats: can_unassign = True; self.unassign_button.config(text="Unassign All")
                 else: self.unassign_button.config(text="Unassign Card")
        elif category: status_text += f"Card=None, Category='{category}'"; self.unassign_button.config(text="Unassign Card")
        else: status_text = "Select a card and/or category."; self.unassign_button.config(text="Unassign Card")
        self.selection_label.config(text=status_text)
        self.assign_button.config(state="normal" if can_assign else "disabled")
        self.unassign_button.config(state="normal" if can_unassign else "disabled")
    def _add_category(self):
        new_cat = self.new_category_var.get().strip()
        if not new_cat: messagebox.showwarning("Invalid Name", "Category name empty.", parent=self); return
        if new_cat in self.category_listbox.get(0, tk.END): messagebox.showwarning("Duplicate", f"'{new_cat}' exists.", parent=self); return
        self.category_listbox.insert(tk.END, new_cat); self.new_category_var.set("")
    def _remove_category(self):
        selection = self.category_listbox.curselection()
        if not selection: messagebox.showwarning("No Selection", "Select category to delete.", parent=self); return
        category_to_delete = self.category_listbox.get(selection[0])
        if messagebox.askyesno("Confirm", f"Delete category '{category_to_delete}'?\nCards will be unassigned.", parent=self):
            cards_to_update = [card for card, cat_list in self.card_categories.items() if category_to_delete in cat_list]
            for card in cards_to_update:
                cats = self.card_categories[card]; cats.remove(category_to_delete)
                if not cats: del self.card_categories[card]
                else: self.card_categories[card] = sorted(cats)
            self.category_listbox.delete(selection[0]); self.selected_category.set("")
            self._populate_lists(); self._update_selection_status()
    def _assign_card(self):
        card, category = self.selected_card.get(), self.selected_category.get()
        if not card or not category: return
        current_cats = self.card_categories.get(card, [])
        if category not in current_cats: current_cats.append(category); self.card_categories[card] = sorted(current_cats)
        else: messagebox.showinfo("Info", f"Already has category '{category}'.", parent=self); return
        self._populate_lists()
        try:
            text = f"{card} [{', '.join(self.card_categories[card])}]"; items = self.card_listbox.get(0, tk.END)
            for i, item in enumerate(items):
                if item == text: self.card_listbox.selection_clear(0, tk.END); self.card_listbox.selection_set(i); self.card_listbox.see(i); break
        except Exception: pass
        self._update_selection_status()
    def _unassign_card(self):
        card, category = self.selected_card.get(), self.selected_category.get()
        if not card: return
        if category:
            current_cats = self.card_categories.get(card, [])
            if category in current_cats:
                current_cats.remove(category)
                if current_cats: self.card_categories[card] = sorted(current_cats)
                else: del self.card_categories[card]
            else: messagebox.showinfo("Info", f"Not assigned to '{category}'.", parent=self); return
        else:
            if card in self.card_categories:
                if messagebox.askyesno("Confirm", f"Unassign ALL categories from '{card}'?", parent=self): del self.card_categories[card]
                else: return
            else: messagebox.showinfo("Info", "No categories assigned.", parent=self); return
        self._populate_lists()
        try:
            items = self.card_listbox.get(0, tk.END)
            for i, item in enumerate(items):
                if item.startswith(card + " [") or item == card: self.card_listbox.selection_clear(0, tk.END); self.card_listbox.selection_set(i); self.card_listbox.see(i); break
        except Exception: pass
        self._update_selection_status()
# --- End of CategoryManagerWindow ---


# --- Combo Editor Window ---
class ComboEditorWindow(tk.Toplevel):
    """Toplevel window for creating and editing custom combos."""
    # ... (Code for ComboEditorWindow - Assuming unchanged from previous correct version) ...
    def __init__(self, parent, card_pool, initial_custom_combos, hardcoded_combo_definitions):
        super().__init__(parent)
        self.parent_app = parent; self.card_pool = card_pool
        self.custom_combos = initial_custom_combos; self.hardcoded_combos = hardcoded_combo_definitions
        self.is_editing_default = False
        self.current_combo_name = tk.StringVar(); self.selected_combo_in_list = tk.StringVar()
        self.selected_card_from_pool = tk.StringVar(); self.selected_card_in_must_have = tk.StringVar()
        self.selected_card_in_need_one = tk.StringVar(); self.selected_need_one_group_index = -1
        self.title("Custom Combo Editor"); self.geometry("900x650"); self.transient(parent); self.grab_set()
        self._setup_combo_gui(); self._populate_combo_list()
    def _load_combos(self):
        try:
            if os.path.exists(CUSTOM_COMBO_FILE):
                with open(CUSTOM_COMBO_FILE, 'r') as f: data = json.load(f)
                if isinstance(data, dict): return data
                else: print(f"Warn: {CUSTOM_COMBO_FILE} invalid format."); return {}
            else: return {}
        except Exception as e:
            print(f"Error loading combos: {e}")
            if self.winfo_exists(): messagebox.showerror("Load Error", f"Failed combos: {e}", parent=self)
            return {}
    def _save_combos(self):
        try:
            cleaned_combos = {}
            for name, definition in self.custom_combos.items():
                 must_have = definition.get("must_have", []); need_one = [group for group in definition.get("need_one_groups", []) if group]
                 if must_have or need_one: cleaned_combos[name] = {"must_have": must_have, "need_one_groups": need_one}
            with open(CUSTOM_COMBO_FILE, 'w') as f: json.dump(cleaned_combos, f, indent=4, sort_keys=True)
            if hasattr(self.parent_app, 'load_custom_combos'): self.parent_app.load_custom_combos()
            else: print("Warn: Main app missing 'load_custom_combos'")
            self.update_status("Custom combos saved.")
        except Exception as e: messagebox.showerror("Save Error", f"Failed combos: {e}", parent=self); self.update_status(f"Error saving: {e}", True)
    def _setup_combo_gui(self):
        paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED); paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        left_frame = ttk.Frame(paned_window, padding=5); left_frame.columnconfigure(0, weight=1); left_frame.rowconfigure(1, weight=1); paned_window.add(left_frame, width=250)
        ttk.Label(left_frame, text="Available Combos").grid(row=0, column=0, sticky="w")
        self.combo_listbox = tk.Listbox(left_frame, exportselection=False); self.combo_listbox.grid(row=1, column=0, sticky="nsew", pady=5)
        combo_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.combo_listbox.yview); combo_scroll.grid(row=1, column=1, sticky="ns", pady=5)
        self.combo_listbox.config(yscrollcommand=combo_scroll.set); self.combo_listbox.bind("<<ListboxSelect>>", self._on_combo_select_from_list)
        combo_buttons_frame = ttk.Frame(left_frame); combo_buttons_frame.grid(row=2, column=0, columnspan=2, pady=5)
        ttk.Button(combo_buttons_frame, text="Load/View", command=self._load_selected_combo_to_editor).pack(side="left", padx=2)
        ttk.Button(combo_buttons_frame, text="New Combo", command=self._clear_editor).pack(side="left", padx=2)
        self.delete_combo_button = ttk.Button(combo_buttons_frame, text="Delete Custom", command=self._delete_selected_combo); self.delete_combo_button.pack(side="left", padx=2)
        right_frame = ttk.Frame(paned_window, padding=5); right_frame.columnconfigure(0, weight=1); right_frame.columnconfigure(1, weight=1); right_frame.columnconfigure(2, weight=1); right_frame.rowconfigure(3, weight=1); right_frame.rowconfigure(5, weight=1); paned_window.add(right_frame)
        ttk.Label(right_frame, text="Combo Name:").grid(row=0, column=0, sticky="w", pady=2)
        self.combo_name_entry = ttk.Entry(right_frame, textvariable=self.current_combo_name, width=40); self.combo_name_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=2)
        self.save_update_button = ttk.Button(right_frame, text="Save/Update Definition", command=self._save_editor_combo, width=25); self.save_update_button.grid(row=0, column=3, padx=10)
        ttk.Label(right_frame, text="Available Cards Pool:").grid(row=4, column=2, columnspan=2, sticky="sw", pady=(10, 2))
        self.pool_listbox = tk.Listbox(right_frame, width=35, height=10, exportselection=False); self.pool_listbox.grid(row=5, column=2, columnspan=2, sticky="nsew", padx=5, pady=5)
        pool_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.pool_listbox.yview); pool_scroll.grid(row=5, column=3, sticky="nse", padx=(0,5), pady=5)
        self.pool_listbox.config(yscrollcommand=pool_scrollbar.set); self.pool_listbox.bind("<<ListboxSelect>>", self._on_pool_select)
        for card in self.card_pool: self.pool_listbox.insert(tk.END, card)
        must_have_frame = ttk.LabelFrame(right_frame, text="Must Have ALL These Cards (AND)"); must_have_frame.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=5, padx=5); must_have_frame.columnconfigure(0, weight=1); must_have_frame.rowconfigure(0, weight=1)
        self.must_have_listbox = tk.Listbox(must_have_frame, height=5, exportselection=False); self.must_have_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        must_have_scroll = ttk.Scrollbar(must_have_frame, orient=tk.VERTICAL, command=self.must_have_listbox.yview); must_have_scroll.grid(row=0, column=1, sticky="ns", padx=(0,5), pady=5)
        self.must_have_listbox.config(yscrollcommand=must_have_scroll.set); self.must_have_listbox.bind("<<ListboxSelect>>", self._on_must_have_select)
        must_have_buttons = ttk.Frame(must_have_frame); must_have_buttons.grid(row=1, column=0, columnspan=2, pady=2)
        self.must_have_add_button = ttk.Button(must_have_buttons, text="Add Selected Card", command=self._add_to_must_have); self.must_have_add_button.pack(side="left", padx=5)
        self.must_have_remove_button = ttk.Button(must_have_buttons, text="Remove Selected", command=self._remove_from_must_have); self.must_have_remove_button.pack(side="left", padx=5)
        need_one_main_frame = ttk.LabelFrame(right_frame, text="Need AT LEAST ONE From EACH Group Below (AND Groups, OR Cards within Group)"); need_one_main_frame.grid(row=2, column=0, columnspan=4, rowspan=2, sticky="nsew", pady=5, padx=5); need_one_main_frame.columnconfigure(0, weight=1); need_one_main_frame.rowconfigure(1, weight=1)
        need_one_buttons_top = ttk.Frame(need_one_main_frame); need_one_buttons_top.grid(row=0, column=0, pady=5, sticky="ew")
        self.need_one_add_group_button = ttk.Button(need_one_buttons_top, text="Add New 'Need One' Group", command=self._add_need_one_group); self.need_one_add_group_button.pack(side="left", padx=5)
        self.need_one_remove_group_button = ttk.Button(need_one_buttons_top, text="Remove Selected Group", command=self._remove_selected_need_one_group); self.need_one_remove_group_button.pack(side="left", padx=5)
        self.need_one_groups_frame = ttk.Frame(need_one_main_frame); self.need_one_groups_frame.grid(row=1, column=0, sticky="nsew")
        self.need_one_group_listboxes = []; self.need_one_group_frames = []
        bottom_frame = ttk.Frame(self); bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        ttk.Button(bottom_frame, text="Save All Combos to File", command=self._save_combos).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="Close Editor", command=self.destroy).pack(side="right", padx=5)
        self.status_label = ttk.Label(bottom_frame, text="Status: Ready"); self.status_label.pack(side="left", padx=10)
    def _on_combo_select_from_list(self, event=None):
        selection = self.combo_listbox.curselection()
        if selection:
            selected_item = self.combo_listbox.get(selection[0]); self.selected_combo_in_list.set(selected_item)
            is_default = selected_item.endswith(" [Default]"); self.delete_combo_button.config(state="disabled" if is_default else "normal")
            self.update_status(f"Selected '{selected_item}'")
        else: self.selected_combo_in_list.set(""); self.delete_combo_button.config(state="disabled"); self.update_status("Selection cleared.")
    def _on_pool_select(self, event=None):
        selection = self.pool_listbox.curselection()
        if selection: self.selected_card_from_pool.set(self.pool_listbox.get(selection[0]))
        else: self.selected_card_from_pool.set("")
    def _on_must_have_select(self, event=None):
        selection = self.must_have_listbox.curselection()
        if selection: self.selected_card_in_must_have.set(self.must_have_listbox.get(selection[0]))
        else: self.selected_card_in_must_have.set("")
    def _on_need_one_select(self, event, group_index):
        listbox = event.widget; selection = listbox.curselection()
        self.selected_need_one_group_index = group_index
        for i, lb in enumerate(self.need_one_group_listboxes):
            if i != group_index: lb.selection_clear(0, tk.END)
        if selection: self.selected_card_in_need_one.set(listbox.get(selection[0]))
        else: self.selected_card_in_need_one.set("")
    def _clear_editor(self):
        self.current_combo_name.set(""); self.must_have_listbox.delete(0, tk.END)
        for frame in self.need_one_group_frames: frame.destroy()
        self.need_one_group_frames = []; self.need_one_group_listboxes = []
        self.selected_need_one_group_index = -1; self.selected_card_in_must_have.set(""); self.selected_card_in_need_one.set("")
        self.is_editing_default = False; self._set_editor_state("normal"); self.combo_name_entry.focus_set(); self.update_status("Editor cleared.")
    def _load_selected_combo_to_editor(self):
        selected_item = self.selected_combo_in_list.get();
        if not selected_item: messagebox.showwarning("Load Error", "Select combo first.", parent=self); return
        is_default = selected_item.endswith(" [Default]"); combo_name = selected_item.replace(" [Default]", "") if is_default else selected_item
        definition = self.hardcoded_combos.get(combo_name) if is_default else self.custom_combos.get(combo_name)
        self.is_editing_default = is_default
        if not definition: messagebox.showerror("Load Error", f"Cannot find definition for '{combo_name}'.", parent=self); self._clear_editor(); return
        self._clear_editor(); self.current_combo_name.set(combo_name)
        for card in definition.get("must_have", []): self.must_have_listbox.insert(tk.END, card)
        for group in definition.get("need_one_groups", []): self._add_need_one_group(populate_list=group)
        self._set_editor_state("normal") # Enable editing for both in Batch 2
        status_prefix = "Viewing/Editing Default" if self.is_editing_default else "Editing Custom"
        self.update_status(f"{status_prefix}: {combo_name}")
    def _set_editor_state(self, state):
         entry_state = "readonly" if state == "disabled" else "normal"
         self.combo_name_entry.config(state=entry_state) # Allow editing name even for defaults now
         self.must_have_listbox.config(state=state); self.must_have_add_button.config(state=state); self.must_have_remove_button.config(state=state)
         self.need_one_add_group_button.config(state=state); self.need_one_remove_group_button.config(state=state)
         for frame in self.need_one_group_frames:
              for widget in frame.winfo_children():
                   if isinstance(widget, tk.Listbox): widget.config(state=state)
                   elif isinstance(widget, ttk.Button): widget.config(state=state)
         self.save_update_button.config(state="normal") # Always allow saving (will save to custom)
    def _save_editor_combo(self):
        combo_name = self.current_combo_name.get().strip()
        if not combo_name: messagebox.showerror("Save Error", "Combo Name empty.", parent=self); return
        if combo_name in self.hardcoded_combos and self.is_editing_default: print(f"Info: Saving edited default combo '{combo_name}' as custom.")
        elif combo_name in self.hardcoded_combos and not self.is_editing_default: # Renaming a custom TO a default name
             if not messagebox.askyesno("Confirm Overwrite", f"Save as '{combo_name}'? This will override the default combo behavior.", parent=self): return
        must_have = list(self.must_have_listbox.get(0, tk.END)); need_one = [list(lb.get(0, tk.END)) for lb in self.need_one_group_listboxes if lb.size() > 0]
        if not must_have and not need_one: messagebox.showerror("Save Error", "Combo needs requirements.", parent=self); return
        new_definition = {"must_have": must_have, "need_one_groups": need_one}
        self.custom_combos[combo_name] = new_definition
        self._populate_combo_list(); self.update_status(f"Definition for '{combo_name}' saved to custom list.")
        self.is_editing_default = False; self._set_editor_state("normal")
    def _delete_selected_combo(self):
        selected_item = self.selected_combo_in_list.get(); is_default = selected_item.endswith(" [Default]")
        combo_name = selected_item.replace(" [Default]", "") if is_default else selected_item
        if is_default: messagebox.showerror("Delete Error", "Cannot delete defaults.", parent=self); return
        if not combo_name or combo_name not in self.custom_combos: messagebox.showwarning("Delete Error", "Select custom combo.", parent=self); return
        if messagebox.askyesno("Confirm Delete", f"Delete custom combo '{combo_name}'?", parent=self):
            del self.custom_combos[combo_name]; self._populate_combo_list()
            if self.current_combo_name.get() == combo_name: self._clear_editor()
            self.update_status(f"Deleted custom combo '{combo_name}'.")
    def _add_to_must_have(self):
        card = self.selected_card_from_pool.get()
        if not card: messagebox.showwarning("Selection Error", "Select card from pool.", parent=self); return
        if card in self.must_have_listbox.get(0, tk.END): messagebox.showinfo("Info", "Already in 'Must Have'.", parent=self); return
        self.must_have_listbox.insert(tk.END, card)
    def _remove_from_must_have(self):
        selection = self.must_have_listbox.curselection()
        if not selection: messagebox.showwarning("Selection Error", "Select card from 'Must Have'.", parent=self); return
        self.must_have_listbox.delete(selection[0]); self.selected_card_in_must_have.set("")
    def _add_need_one_group(self, populate_list=None):
        group_index = len(self.need_one_group_frames)
        group_frame = ttk.Frame(self.need_one_groups_frame, borderwidth=1, relief="sunken"); group_frame.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.BOTH, expand=True); self.need_one_group_frames.append(group_frame)
        ttk.Label(group_frame, text=f"Group {group_index + 1} (Need 1+)").pack(anchor="w")
        listbox = tk.Listbox(group_frame, height=5, width=25, exportselection=False); listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(group_frame, orient=tk.VERTICAL, command=listbox.yview); scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scrollbar.set); listbox.bind("<<ListboxSelect>>", lambda e, idx=group_index: self._on_need_one_select(e, idx))
        button_frame = ttk.Frame(group_frame); button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=2)
        ttk.Button(button_frame, text="Add Card", command=lambda idx=group_index: self._add_to_need_one(idx)).pack(side="left", padx=2)
        ttk.Button(button_frame, text="Remove Card", command=lambda idx=group_index: self._remove_from_need_one(idx)).pack(side="left", padx=2)
        self.need_one_group_listboxes.append(listbox)
        if populate_list:
            for card in populate_list: listbox.insert(tk.END, card)
    def _remove_selected_need_one_group(self):
        if self.selected_need_one_group_index < 0 or self.selected_need_one_group_index >= len(self.need_one_group_frames): messagebox.showwarning("Selection Error", "Select card in group to remove.", parent=self); return
        if messagebox.askyesno("Confirm Remove", f"Remove Group {self.selected_need_one_group_index + 1}?", parent=self):
            self.need_one_group_frames[self.selected_need_one_group_index].destroy()
            del self.need_one_group_frames[self.selected_need_one_group_index]; del self.need_one_group_listboxes[self.selected_need_one_group_index]
            self.selected_need_one_group_index = -1; self.selected_card_in_need_one.set("")
            for i, frame in enumerate(self.need_one_group_frames):
                 for widget in frame.winfo_children():
                      if isinstance(widget, ttk.Label): widget.config(text=f"Group {i + 1} (Need 1+)"); break
            self.update_status("Removed 'Need One' group.")
    def _add_to_need_one(self, group_index):
        card = self.selected_card_from_pool.get()
        if not card: messagebox.showwarning("Selection Error", "Select card from pool.", parent=self); return
        if group_index < 0 or group_index >= len(self.need_one_group_listboxes): return
        listbox = self.need_one_group_listboxes[group_index]
        if card in listbox.get(0, tk.END): messagebox.showinfo("Info", "Already in group.", parent=self); return
        listbox.insert(tk.END, card)
    def _remove_from_need_one(self, group_index):
        if group_index < 0 or group_index >= len(self.need_one_group_listboxes): return
        listbox = self.need_one_group_listboxes[group_index]; selection = listbox.curselection()
        if not selection: messagebox.showwarning("Selection Error", f"Select card from Group {group_index+1}.", parent=self); return
        listbox.delete(selection[0]); self.selected_card_in_need_one.set("")
    def _populate_combo_list(self):
        self.combo_listbox.delete(0, tk.END)
        for name in sorted(self.hardcoded_combos.keys()):
            if name not in self.custom_combos: self.combo_listbox.insert(tk.END, f"{name} [Default]"); self.combo_listbox.itemconfig(tk.END, {'fg': 'grey'})
        for name in sorted(self.custom_combos.keys()): self.combo_listbox.insert(tk.END, name)
        self.selected_combo_in_list.set(""); self.delete_combo_button.config(state="disabled")
    def update_status(self, message, error=False):
        prefix = "Error: " if error else "Status: "; self.status_label.config(text=f"{prefix}{message}")
        if error: print(f"COMBO EDITOR ERROR: {message}")
        else: print(f"COMBO EDITOR STATUS: {message}")
# --- End of ComboEditorWindow ---


# --- Card Database Editor Window ---
class CardDatabaseEditorWindow(tk.Toplevel):
    """Toplevel window for editing the effective card database."""
    def __init__(self, parent_app): # <<< Changed parent to parent_app for clarity >>>
        super().__init__(parent_app.root) # Pass the main tk root as parent
        self.parent_app = parent_app # Reference to DeckSimulatorApp

        # Use base data from parent app
        self.base_pool = self.parent_app.base_card_pool
        self.base_types = self.parent_app.base_card_types
        self.user_data = self._load_user_db() # Load user changes specific to this window
        self.added_cards = self.user_data.get("added_cards", {})
        self.removed_cards = set(self.user_data.get("removed_cards", []))
        self.type_overrides = self.user_data.get("type_overrides", {})

        self._calculate_effective_db() # Calculate initial effective pool/types for display

        # UI Variables
        self.selected_card_var = tk.StringVar()
        self.new_card_name_var = tk.StringVar()
        self.new_card_type_var = tk.StringVar(value="MONSTER") # Default type

        self.title("Card Database Editor")
        self.geometry("600x600")
        self.transient(parent_app.root) # Keep window on top of parent
        self.grab_set() # Modal behavior

        self._setup_editor_gui()
        self._populate_card_list() # Populate with effective list

    def _load_user_db(self):
        """Loads user additions/removals/overrides from JSON."""
        try:
            if os.path.exists(USER_DB_FILE):
                with open(USER_DB_FILE, 'r') as f: data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("added_cards", {}); data.setdefault("removed_cards", []); data.setdefault("type_overrides", {})
                    if not isinstance(data["added_cards"], dict): data["added_cards"] = {}
                    if not isinstance(data["removed_cards"], list): data["removed_cards"] = []
                    if not isinstance(data["type_overrides"], dict): data["type_overrides"] = {}
                    return data
                else: print(f"Warn: {USER_DB_FILE} invalid format."); return {}
            else: return {"added_cards": {}, "removed_cards": [], "type_overrides": {}}
        except Exception as e:
            print(f"Error loading user DB: {e}")
            messagebox.showerror("Load Error", f"Failed to load user card data: {e}", parent=self)
            return {"added_cards": {}, "removed_cards": [], "type_overrides": {}}

    def _save_user_db(self):
        """Saves user changes to JSON."""
        self.user_data["added_cards"] = self.added_cards
        self.user_data["removed_cards"] = sorted(list(self.removed_cards))
        self.user_data["type_overrides"] = self.type_overrides
        try:
            with open(USER_DB_FILE, 'w') as f: json.dump(self.user_data, f, indent=4, sort_keys=True)
            print(f"User card database saved to {USER_DB_FILE}")
            if hasattr(self.parent_app, 'reload_card_database'): self.parent_app.reload_card_database()
        except Exception as e: print(f"Error saving user DB: {e}"); messagebox.showerror("Save Error", f"Failed save: {e}", parent=self)

    def _calculate_effective_db(self):
        """Calculates the effective card pool and types based on user changes."""
        self.effective_pool = self.base_pool.copy() # Use base from parent
        self.effective_pool.update(self.added_cards.keys())
        self.effective_pool -= self.removed_cards
        self.effective_types = self.base_types.copy() # Use base from parent
        self.effective_types.update(self.added_cards)
        self.effective_types.update(self.type_overrides)
        final_types = {}
        for card in sorted(list(self.effective_pool)):
             if card in self.effective_types: final_types[card] = self.effective_types[card]
             else: print(f"Warn: Card '{card}' missing type. Defaulting."); final_types[card] = "MONSTER"
        self.effective_types = final_types
        self.effective_pool_list = sorted(list(self.effective_pool))

    def _setup_editor_gui(self):
        main_frame = ttk.Frame(self, padding="10"); main_frame.pack(expand=True, fill="both")
        main_frame.rowconfigure(1, weight=1); main_frame.columnconfigure(0, weight=1)
        list_frame = ttk.LabelFrame(main_frame, text="Effective Card Pool (Base + Your Changes)"); list_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
        list_frame.rowconfigure(0, weight=1); list_frame.columnconfigure(0, weight=1)
        self.card_listbox = tk.Listbox(list_frame, exportselection=False); self.card_listbox.grid(row=0, column=0, sticky="nsew", pady=5, padx=5)
        card_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.card_listbox.yview); card_scroll.grid(row=0, column=1, sticky="ns", pady=5)
        self.card_listbox.config(yscrollcommand=card_scroll.set); self.card_listbox.bind("<<ListboxSelect>>", self._on_card_select)
        add_frame = ttk.LabelFrame(main_frame, text="Add New Card"); add_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        ttk.Label(add_frame, text="Name:").grid(row=0, column=0, padx=5, pady=5)
        ttk.Entry(add_frame, textvariable=self.new_card_name_var, width=30).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(add_frame, text="Type:").grid(row=1, column=0, padx=5, pady=5)
        ttk.Combobox(add_frame, textvariable=self.new_card_type_var, values=["MONSTER", "SPELL", "TRAP"], state="readonly", width=10).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(add_frame, text="Add Card", command=self._add_card).grid(row=0, column=2, rowspan=2, padx=10, pady=5)
        action_frame = ttk.Frame(main_frame); action_frame.grid(row=2, column=0, columnspan=3, pady=10)
        self.selected_card_label = ttk.Label(action_frame, text="Selected: None"); self.selected_card_label.pack(side="left", padx=10)
        self.edit_type_button = ttk.Button(action_frame, text="Change Type To:", command=self._edit_card_type, state="disabled"); self.edit_type_button.pack(side="left", padx=5)
        self.edit_type_combo = ttk.Combobox(action_frame, values=["MONSTER", "SPELL", "TRAP"], state="readonly", width=10); self.edit_type_combo.pack(side="left", padx=5)
        self.remove_button = ttk.Button(action_frame, text="Remove Selected", command=self._remove_card, state="disabled"); self.remove_button.pack(side="left", padx=10)
        bottom_frame = ttk.Frame(main_frame); bottom_frame.grid(row=3, column=0, columnspan=3, pady=(10,0))
        ttk.Button(bottom_frame, text="Save Changes", command=self._save_user_db).pack(side="left", padx=10)
        ttk.Button(bottom_frame, text="Close", command=self.destroy).pack(side="right", padx=10)

    def _populate_card_list(self):
        self.card_listbox.delete(0, tk.END)
        for card in self.effective_pool_list:
            card_type = self.effective_types.get(card, "???"); is_added = card in self.added_cards; is_default = card in self.base_pool
            display_text = f"{card} ({card_type})"
            self.card_listbox.insert(tk.END, display_text)
            if is_added: self.card_listbox.itemconfig(tk.END, {'fg': 'blue'})
            elif card in self.type_overrides: self.card_listbox.itemconfig(tk.END, {'fg': 'purple'})

    def _on_card_select(self, event):
        selection = self.card_listbox.curselection()
        if selection:
            selected_display = self.card_listbox.get(selection[0]); card_name = selected_display.split(" (")[0]
            self.selected_card_var.set(card_name); self.selected_card_label.config(text=f"Selected: {card_name}")
            self.remove_button.config(state="normal"); self.edit_type_button.config(state="normal")
            current_type = self.effective_types.get(card_name)
            if current_type: self.edit_type_combo.set(current_type)
        else:
            self.selected_card_var.set(""); self.selected_card_label.config(text="Selected: None")
            self.remove_button.config(state="disabled"); self.edit_type_button.config(state="disabled")

    def _add_card(self):
        name = self.new_card_name_var.get().strip(); ctype = self.new_card_type_var.get()
        if not name: messagebox.showerror("Error", "Card name empty.", parent=self); return
        if not ctype: messagebox.showerror("Error", "Card type must be selected.", parent=self); return
        if name in self.base_pool and name not in self.removed_cards: messagebox.showerror("Error", f"'{name}' exists in base pool.", parent=self); return
        if name in self.added_cards: messagebox.showerror("Error", f"'{name}' already added.", parent=self); return
        self.added_cards[name] = ctype; self.removed_cards.discard(name)
        if name in self.type_overrides: del self.type_overrides[name]
        self.new_card_name_var.set(""); self._calculate_effective_db(); self._populate_card_list()
        print(f"Added new card: {name} ({ctype})")

    def _remove_card(self):
        card = self.selected_card_var.get()
        if not card: return
        if messagebox.askyesno("Confirm Remove", f"Remove '{card}' from effective pool?", parent=self):
            was_added = card in self.added_cards; was_default = card in self.base_pool
            if was_added: del self.added_cards[card]
            elif was_default:
                self.removed_cards.add(card)
                # Corrected Indentation
                if card in self.type_overrides:
                    del self.type_overrides[card]
            # End Corrected Indentation
            self.selected_card_var.set(""); self._calculate_effective_db(); self._populate_card_list(); self._on_card_select(None)
            print(f"Removed card: {card}")

    def _edit_card_type(self):
        card = self.selected_card_var.get(); new_type = self.edit_type_combo.get()
        if not card or not new_type: return
        current_type = self.effective_types.get(card)
        if new_type == current_type: messagebox.showinfo("Info", "Already has type.", parent=self); return
        was_added = card in self.added_cards; was_default = card in self.base_pool
        if was_added: self.added_cards[card] = new_type; print(f"Changed added card '{card}' to {new_type}")
        elif was_default:
            base_type = self.base_types.get(card)
            if new_type == base_type:
                 if card in self.type_overrides: del self.type_overrides[card]
                 print(f"Reverted '{card}' to default ({new_type})")
            else: self.type_overrides[card] = new_type; print(f"Overrode type of '{card}' to {new_type}")
        else: messagebox.showerror("Error", "Cannot edit type.", parent=self); return
        self._calculate_effective_db(); self._populate_card_list()
        try: # Reselect
            idx = self.effective_pool_list.index(card)
            self.card_listbox.selection_clear(0, tk.END); self.card_listbox.selection_set(idx); self.card_listbox.see(idx); self._on_card_select(None)
        except ValueError: pass
# --- End of CardDatabaseEditorWindow ---


class DeckSimulatorApp:
    def __init__(self, root):
        """Initialize the Deck Simulator App."""
        self.root = root
        self.root.title("Yu-Gi-Oh! Deck Simulator")
        self.root.geometry("1050x750")

        # --- App State ---
        if not os.path.exists(DECKS_DIR):
            try: os.makedirs(DECKS_DIR)
            except OSError as e: messagebox.showerror("Dir Error", f"Cannot create '{DECKS_DIR}': {e}"); self.root.quit()

        self.base_card_pool = set(CARD_POOL)
        self.base_card_types = CARD_TYPES.copy()
        self.user_card_data = self._load_user_card_db()
        self._calculate_effective_card_db() # Initializes self.card_pool and self.card_types

        self.deck_list_a = {}
        self.deck_list_b = {}
        self.current_deck_name_a = NO_DECK_A
        self.current_deck_name_b = NO_DECK_B
        self.current_submitted_deck_a = ""
        self.current_submitted_deck_b = ""
        self.num_simulations = tk.IntVar(value=DEFAULT_SIMULATIONS)
        self.comparison_mode = tk.BooleanVar(value=True) # Default to True

        self.submitted_deck_list_a = {}
        self.submitted_deck_list_b = {}
        self.submitted_stats_a = {}
        self.submitted_stats_b = {}
        self.submitted_is_comparison = False

        self.simulation_status_var = tk.StringVar(value="Status: Idle")
        self.simulation_queue = queue.Queue()
        self.last_pdf_path = None
        self._after_id_status_clear = None

        self._engine_card_combos = analysis_engine._define_combos()
        self._engine_combo_card_map = analysis_engine._define_combo_card_map()
        self.hardcoded_combo_definitions = analysis_engine._get_hardcoded_combo_definitions()
        self.custom_combos = self._load_initial_custom_combos()
        self.card_categories = self._load_initial_categories()

        # --- Setup ---
        self._setup_gui()
        self.update_load_deck_dropdown()
        self._load_last_submitted_decks()
        self.toggle_comparison_mode()
        self.root.after(100, self._check_simulation_queue)

    # --- Card DB Loading/Merging ---
    def _load_user_card_db(self):
        """Loads user additions/removals/overrides from JSON."""
        try:
            if os.path.exists(USER_DB_FILE):
                with open(USER_DB_FILE, 'r') as f: data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("added_cards", {}); data.setdefault("removed_cards", []); data.setdefault("type_overrides", {})
                    if not isinstance(data["added_cards"], dict): data["added_cards"] = {}
                    if not isinstance(data["removed_cards"], list): data["removed_cards"] = []
                    if not isinstance(data["type_overrides"], dict): data["type_overrides"] = {}
                    print(f"Loaded user card DB changes from {USER_DB_FILE}")
                    return data
                else: print(f"Warn: {USER_DB_FILE} invalid format."); return {}
            else: return {"added_cards": {}, "removed_cards": [], "type_overrides": {}}
        except Exception as e: self.update_status(f"Error loading user card DB: {e}", True); return {}

    def _calculate_effective_card_db(self):
        """Calculates self.card_pool and self.card_types from base + user data."""
        added = self.user_card_data.get("added_cards", {})
        removed = set(self.user_card_data.get("removed_cards", []))
        overrides = self.user_card_data.get("type_overrides", {})
        effective_pool_set = self.base_card_pool.copy()
        effective_pool_set.update(added.keys())
        effective_pool_set -= removed
        self.card_pool = sorted(list(effective_pool_set)) # Update main app's pool list
        self.card_types = self.base_card_types.copy()
        self.card_types.update(added)
        self.card_types.update(overrides)
        final_types = {card: self.card_types[card] for card in self.card_pool if card in self.card_types}
        for card in self.card_pool:
            if card not in final_types: print(f"Warning: Card '{card}' missing type. Defaulting."); final_types[card] = "MONSTER"
        self.card_types = final_types
        print(f"Calculated effective card database: {len(self.card_pool)} cards.")

    def reload_card_database(self):
        """Reloads user DB changes and recalculates effective DB."""
        print("Reloading card database...")
        self.user_card_data = self._load_user_card_db()
        self._calculate_effective_card_db()
        self.update_card_list('a'); self.update_card_list('b')
        if hasattr(self, '_category_window') and self._category_window.winfo_exists():
             self._category_window.card_pool = self.card_pool; self._category_window._populate_lists()
        if hasattr(self, '_combo_editor_window') and self._combo_editor_window.winfo_exists():
             self._combo_editor_window.card_pool = self.card_pool
             pool_lb = getattr(self._combo_editor_window, 'pool_listbox', None)
             if pool_lb: pool_lb.delete(0, tk.END);
             for card in self.card_pool: pool_lb.insert(tk.END, card)
        self.load_card_categories() # Uses updated self.card_pool
        self.update_status("Card database reloaded.", temporary=True)
    # --- End Card DB ---

    # --- GUI Setup Methods ---
    def _setup_gui(self):
        # ... (Same as before) ...
        self.root.columnconfigure(0, weight=1); self.root.rowconfigure(1, weight=1)
        self.deck_builder_frame = ttk.Frame(self.root); self.deck_builder_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.deck_builder_frame.columnconfigure(0, weight=1); self.deck_builder_frame.columnconfigure(1, weight=1); self.deck_builder_frame.rowconfigure(0, weight=1)
        self.deck_a_frame = self._create_deck_frame(self.deck_builder_frame, "Deck A"); self.deck_a_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.deck_b_frame = self._create_deck_frame(self.deck_builder_frame, "Deck B"); self.deck_b_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.file_frame = ttk.LabelFrame(self.root, text="File Operations"); self.file_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self._setup_file_ops()
        self.current_deck_frame = ttk.Frame(self.root); self.current_deck_frame.grid(row=3, column=0, padx=10, pady=2, sticky="ew")
        self.current_deck_label_a = ttk.Label(self.current_deck_frame, text=f"Submitted A: {self.current_submitted_deck_a}"); self.current_deck_label_a.pack(side="left", padx=5)
        self.current_deck_label_b = ttk.Label(self.current_deck_frame, text=f"Submitted B: {self.current_submitted_deck_b}"); self.current_deck_label_b.pack(side="left", padx=5)
        self.simulation_frame = ttk.Frame(self.root); self.simulation_frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")
        self._setup_simulation_controls()
        self.deck_differences_frame = ttk.LabelFrame(self.root, text="Deck Differences (B vs A)"); self.deck_differences_frame.grid(row=5, column=0, padx=10, pady=5, sticky="ew")
        self.deck_differences_label = ttk.Label(self.deck_differences_frame, text="", justify=tk.LEFT); self.deck_differences_label.pack(padx=5, pady=5, anchor="w")
        self.status_bar = ttk.Label(self.root, textvariable=self.simulation_status_var, relief=tk.SUNKEN, anchor=tk.W); self.status_bar.grid(row=6, column=0, sticky="ew", padx=1, pady=1)

    def _create_deck_frame(self, parent, deck_label):
        # ... (Same as before) ...
        is_deck_a = (deck_label == "Deck A"); deck_char = 'a' if is_deck_a else 'b'
        frame = ttk.LabelFrame(parent, text=deck_label); frame.columnconfigure(2, weight=1); frame.rowconfigure(1, weight=1)
        widgets = {}
        widgets['search_var'] = tk.StringVar(); widgets['search_var'].trace_add("write", lambda *args, d=deck_char: self.update_card_list(deck=d))
        search_label = ttk.Label(frame, text="Search Pool:"); search_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        widgets['search_entry'] = ttk.Entry(frame, textvariable=widgets['search_var']); widgets['search_entry'].grid(row=0, column=1, columnspan=1, padx=5, pady=2, sticky="ew")
        widgets['card_listbox'] = tk.Listbox(frame, width=35, height=10, exportselection=False); widgets['card_listbox'].grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        widgets['card_listbox'].bind("<<ListboxSelect>>", lambda event, d=deck_char: self.select_card(event, deck=d))
        pool_scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=widgets['card_listbox'].yview); pool_scrollbar.grid(row=1, column=1, padx=(0,5), pady=5, sticky="nse")
        widgets['card_listbox'].config(yscrollcommand=pool_scrollbar.set)
        qty_label = ttk.Label(frame, text="Qty:"); qty_label.grid(row=2, column=0, padx=5, pady=2, sticky="e")
        widgets['quantity_var'] = tk.StringVar(value="1"); widgets['quantity_dropdown'] = ttk.Combobox(frame, textvariable=widgets['quantity_var'], values=["1", "2", "3"], state="readonly", width=5); widgets['quantity_dropdown'].grid(row=2, column=1, padx=5, pady=2, sticky="w")
        button_frame = ttk.Frame(frame); button_frame.grid(row=3, column=0, columnspan=2, pady=2)
        widgets['add_button'] = ttk.Button(button_frame, text="Add", width=8, command=lambda d=deck_char: self.add_card(deck=d)); widgets['add_button'].pack(side="left", padx=2)
        widgets['remove_button'] = ttk.Button(button_frame, text="Remove", width=8, command=lambda d=deck_char: self.remove_card(deck=d)); widgets['remove_button'].pack(side="left", padx=2)
        deck_list_label = ttk.Label(frame, text="Current Deck:"); deck_list_label.grid(row=0, column=2, padx=5, pady=2, sticky="w")
        widgets['deck_listbox'] = tk.Listbox(frame, width=40, height=15, exportselection=False); widgets['deck_listbox'].grid(row=1, column=2, rowspan=3, padx=5, pady=5, sticky="nsew")
        deck_scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=widgets['deck_listbox'].yview); deck_scrollbar.grid(row=1, column=3, rowspan=3, padx=(0,5), pady=5, sticky="ns")
        widgets['deck_listbox'].config(yscrollcommand=deck_scrollbar.set)
        widgets['total_count'] = tk.IntVar(value=0); widgets['monster_count'] = tk.IntVar(value=0); widgets['spell_count'] = tk.IntVar(value=0); widgets['trap_count'] = tk.IntVar(value=0)
        count_frame = ttk.LabelFrame(frame, text="Counts"); count_frame.grid(row=4, column=2, padx=5, pady=5, sticky="ew")
        count_frame.columnconfigure(0, weight=1); count_frame.columnconfigure(1, weight=1); count_frame.columnconfigure(2, weight=1); count_frame.columnconfigure(3, weight=1)
        ttk.Label(count_frame, text="Total:").grid(row=0, column=0, sticky="e"); ttk.Label(count_frame, textvariable=widgets['total_count']).grid(row=0, column=1, sticky="w", padx=2)
        ttk.Label(count_frame, text="M:").grid(row=0, column=2, sticky="e"); ttk.Label(count_frame, textvariable=widgets['monster_count']).grid(row=0, column=3, sticky="w", padx=2)
        ttk.Label(count_frame, text="S:").grid(row=1, column=0, sticky="e"); ttk.Label(count_frame, textvariable=widgets['spell_count']).grid(row=1, column=1, sticky="w", padx=2)
        ttk.Label(count_frame, text="T:").grid(row=1, column=2, sticky="e"); ttk.Label(count_frame, textvariable=widgets['trap_count']).grid(row=1, column=3, sticky="w", padx=2)
        frame.widgets = widgets
        self.update_card_list(deck=deck_char, frame_widgets=widgets) # Populates with effective pool
        return frame

    def _setup_file_ops(self):
        # ... (Same as before, includes Manage DB button) ...
        self.load_deck_button_a = ttk.Button(self.file_frame, text="Load A", command=lambda: self.load_deck(deck='a'), width=8); self.load_deck_button_a.pack(side="left", padx=(5,2), pady=5)
        self.load_deck_dropdown_a = ttk.Combobox(self.file_frame, values=[], state="readonly", width=20); self.load_deck_dropdown_a.pack(side="left", padx=(0,5), pady=5)
        self.save_button_a = ttk.Button(self.file_frame, text="Save A", command=lambda: self.save_deck(deck='a'), width=8); self.save_button_a.pack(side="left", padx=5, pady=5)
        self.save_as_button_a = ttk.Button(self.file_frame, text="Save A As...", command=lambda: self.save_deck_as(deck='a'), width=10); self.save_as_button_a.pack(side="left", padx=(0,15), pady=5)
        self.load_deck_button_b = ttk.Button(self.file_frame, text="Load B", command=lambda: self.load_deck(deck='b'), width=8); self.load_deck_button_b.pack(side="left", padx=(5,2), pady=5)
        self.load_deck_dropdown_b = ttk.Combobox(self.file_frame, values=[], state="readonly", width=20); self.load_deck_dropdown_b.pack(side="left", padx=(0,5), pady=5)
        self.save_button_b = ttk.Button(self.file_frame, text="Save B", command=lambda: self.save_deck(deck='b'), width=8); self.save_button_b.pack(side="left", padx=5, pady=5)
        self.save_as_button_b = ttk.Button(self.file_frame, text="Save B As...", command=lambda: self.save_deck_as(deck='b'), width=10); self.save_as_button_b.pack(side="left", padx=5, pady=5)
        self.manage_db_button = ttk.Button(self.file_frame, text="Manage Card DB", command=self._open_db_editor); self.manage_db_button.pack(side="right", padx=5, pady=5)
        self.manage_combos_button = ttk.Button(self.file_frame, text="Manage Combos", command=self._open_combo_editor); self.manage_combos_button.pack(side="right", padx=5, pady=5)
        self.manage_categories_button = ttk.Button(self.file_frame, text="Manage Categories", command=self._open_category_manager); self.manage_categories_button.pack(side="right", padx=5, pady=5)

    def _setup_simulation_controls(self):
        # ... (Same as before) ...
        self.submit_button = ttk.Button(self.simulation_frame, text="Submit Deck(s)", command=self.submit_decks); self.submit_button.pack(side="left", padx=5, pady=5)
        num_sim_label = ttk.Label(self.simulation_frame, text="Simulations:"); num_sim_label.pack(side="left", padx=(10, 2), pady=5)
        num_sim_entry = ttk.Entry(self.simulation_frame, textvariable=self.num_simulations, width=10); num_sim_entry.pack(side="left", padx=(0, 5), pady=5)
        self.start_simulation_button = ttk.Button(self.simulation_frame, text="Start Simulation", command=self.start_simulation_thread, state="disabled"); self.start_simulation_button.pack(side="left", padx=5, pady=5)
        self.comparison_mode_check = ttk.Checkbutton(self.simulation_frame, text="Comparison Mode", variable=self.comparison_mode, command=self.toggle_comparison_mode); self.comparison_mode_check.pack(side="left", padx=15, pady=5)

    # --- GUI Update Methods ---
    def _get_deck_widgets(self, deck):
        # ... (Same as before) ...
        frame = self.deck_a_frame if deck == 'a' else self.deck_b_frame; return getattr(frame, 'widgets', None)

    def _get_deck_list(self, deck):
        # ... (Same as before) ...
        if deck == 'a': return self.deck_list_a
        elif deck == 'b': return self.deck_list_b
        else: self.update_status(f"Invalid deck id '{deck}'", True); return None

    def update_card_list(self, deck, frame_widgets=None):
        # ... (Uses effective self.card_pool) ...
        widgets = frame_widgets or self._get_deck_widgets(deck)
        if not widgets: return
        search_term = widgets['search_var'].get().lower(); listbox = widgets['card_listbox']; listbox.delete(0, tk.END)
        for card in self.card_pool: # Uses effective pool
            if search_term in card.lower(): listbox.insert(tk.END, card)

    def select_card(self, event, deck): pass

    def update_deck_listbox(self, deck):
        # ... (Same as before) ...
        widgets = self._get_deck_widgets(deck); deck_list = self._get_deck_list(deck)
        if not widgets or deck_list is None: return
        listbox = widgets['deck_listbox']; listbox.delete(0, tk.END)
        for card, quantity in sorted(deck_list.items()): listbox.insert(tk.END, f"{card} x{quantity}")

    def update_deck_counts(self, deck):
        # ... (Uses effective self.card_types) ...
        widgets = self._get_deck_widgets(deck); deck_list = self._get_deck_list(deck)
        if not widgets or deck_list is None: return
        m, s, t, total = 0, 0, 0, 0
        for card, quantity in deck_list.items():
            card_type = self.card_types.get(card, "UNKNOWN"); total += quantity # Use effective types
            if card_type == "MONSTER": m += quantity
            elif card_type == "SPELL": s += quantity
            elif card_type == "TRAP": t += quantity
        widgets['total_count'].set(total); widgets['monster_count'].set(m); widgets['spell_count'].set(s); widgets['trap_count'].set(t)
        self.validate_decks_for_submission()

    def update_load_deck_dropdown(self):
        # ... (Same as before) ...
        try:
            saved_decks = self.get_saved_decks()
            self.load_deck_dropdown_a["values"] = saved_decks; self.load_deck_dropdown_b["values"] = saved_decks
            current_a = self.load_deck_dropdown_a.get(); current_b = self.load_deck_dropdown_b.get()
            if current_a and current_a not in saved_decks: self.load_deck_dropdown_a.set("")
            if current_b and current_b not in saved_decks: self.load_deck_dropdown_b.set("")
        except Exception as e: self.update_status(f"Err updating lists: {e}", True)

    def update_deck_differences(self):
        # ... (Same as before) ...
        if not self.comparison_mode.get(): self.deck_differences_label.config(text=""); self.deck_differences_frame.grid_remove(); return
        self.deck_differences_frame.grid(); diff_lines = []
        all_cards = set(self.deck_list_a.keys()) | set(self.deck_list_b.keys())
        for card in sorted(list(all_cards)):
            c_a, c_b = self.deck_list_a.get(card, 0), self.deck_list_b.get(card, 0); diff = c_b - c_a
            if diff > 0: diff_lines.append(f"+{diff} {card} (B has more)")
            elif diff < 0: diff_lines.append(f"{diff} {card} (A has more)")
        diff_text = "\n".join(diff_lines) if diff_lines else "No differences."; self.deck_differences_label.config(text=diff_text)

    def toggle_comparison_mode(self):
        # ... (Same as before) ...
        is_comparing = self.comparison_mode.get(); widgets_b = self._get_deck_widgets('b')
        if is_comparing:
            self.deck_b_frame.grid(); self.deck_differences_frame.grid(); self.submit_button.config(text="Submit Decks")
            self.load_deck_button_b.config(state="normal"); self.load_deck_dropdown_b.config(state="readonly")
            self.save_button_b.config(state="normal"); self.save_as_button_b.config(state="normal")
            if widgets_b:
                for widget in widgets_b.values():
                    if hasattr(widget, 'config'): widget.config(state="normal")
                widgets_b['quantity_dropdown'].config(state="readonly")
            self.update_deck_differences()
        else:
            self.deck_b_frame.grid_remove(); self.deck_differences_frame.grid_remove(); self.submit_button.config(text="Submit Deck A")
            self.load_deck_button_b.config(state="disabled"); self.load_deck_dropdown_b.config(state="disabled")
            self.save_button_b.config(state="disabled"); self.save_as_button_b.config(state="disabled")
            if widgets_b:
                for name, widget in widgets_b.items():
                    if name not in ['search_var', 'quantity_var', 'total_count', 'monster_count', 'spell_count', 'trap_count']:
                        if hasattr(widget, 'config'): widget.config(state="disabled")
            self.current_submitted_deck_b = ""; self.current_deck_label_b.config(text="Submitted B: ")
        self.validate_decks_for_submission()

    def update_status(self, message, error=False, temporary=False):
        # ... (Same as before) ...
        if self._after_id_status_clear: self.root.after_cancel(self._after_id_status_clear); self._after_id_status_clear = None
        prefix = "ERROR: " if error else "Status: "; self.simulation_status_var.set(f"{prefix}{message}")
        if error: print(f"ERROR: {message}")
        else: print(f"STATUS: {message}")
        if temporary: self._after_id_status_clear = self.root.after(STATUS_CLEAR_DELAY, lambda: self.update_status("Idle"))

    # --- Deck Manipulation Methods ---
    def add_card(self, deck):
        # ... (Uses effective self.card_pool implicitly via listbox) ...
        widgets = self._get_deck_widgets(deck); deck_list = self._get_deck_list(deck)
        idx = widgets['card_listbox'].curselection()
        if not idx: messagebox.showwarning("No Card", "Select from pool."); return
        card = widgets['card_listbox'].get(idx); quantity = int(widgets['quantity_var'].get())
        current = deck_list.get(card, 0); total = self.get_total_cards(deck)
        if current + quantity > MAX_CARD_COPIES: messagebox.showwarning("Limit", f"Max {MAX_CARD_COPIES}."); return
        if total + quantity > MAX_DECK_SIZE: messagebox.showwarning("Limit", f"Max {MAX_DECK_SIZE}."); return
        deck_list[card] = current + quantity; self.update_deck_listbox(deck); self.update_deck_counts(deck)
        if self.comparison_mode.get(): self.update_deck_differences()

    def remove_card(self, deck):
        # ... (Same as before) ...
        widgets = self._get_deck_widgets(deck); deck_list = self._get_deck_list(deck)
        idx = widgets['deck_listbox'].curselection()
        if not idx: messagebox.showwarning("No Card", f"Select from Deck {deck.upper()}."); return
        item = widgets['deck_listbox'].get(idx); match = re.match(r"^(.*)\s+x\d+$", item)
        if not match: messagebox.showerror("Parse Error", "Cannot parse card."); return
        card = match.group(1).strip(); quantity = int(widgets['quantity_var'].get())
        current = deck_list.get(card, 0)
        if current == 0: messagebox.showwarning("Not Found", f"'{card}' not in deck."); return
        if quantity > current: messagebox.showwarning("Invalid", f"Only {current} exist."); return
        deck_list[card] = current - quantity
        if deck_list[card] <= 0: del deck_list[card]
        self.update_deck_listbox(deck); self.update_deck_counts(deck)
        if self.comparison_mode.get(): self.update_deck_differences()

    def get_total_cards(self, deck):
        # ... (Same as before) ...
        deck_list = self._get_deck_list(deck); return sum(deck_list.values()) if deck_list else 0

    # --- File Operations ---
    def get_saved_decks(self):
        # ... (Same as before) ...
        try:
            if not os.path.exists(DECKS_DIR): os.makedirs(DECKS_DIR)
            files = [f for f in os.listdir(DECKS_DIR) if f.endswith(".json")]
            return sorted(files)
        except Exception as e: self.update_status(f"Error accessing decks dir: {e}", True); return []

    def save_deck_as(self, deck):
        # ... (Same as before) ...
        deck_list=self._get_deck_list(deck); current=self.current_deck_name_a if deck=='a' else self.current_deck_name_b
        no_deck=NO_DECK_A if deck=='a' else NO_DECK_B
        if not deck_list: messagebox.showwarning("Empty", f"Deck {deck.upper()} empty."); return
        initial=current if current!=no_deck else f"deck_{deck}.json"
        path=filedialog.asksaveasfilename(initialdir=DECKS_DIR, initialfile=initial, defaultextension=".json", filetypes=[("JSON","*.json")], title=f"Save Deck {deck.upper()} As")
        if path:
            name=os.path.basename(path)
            if deck=='a': self.current_deck_name_a=name
            else: self.current_deck_name_b=name
            if self.save_deck(file_path=path, deck=deck): self.update_load_deck_dropdown()

    def save_deck(self, file_path=None, deck=None):
        # ... (uses status bar now) ...
        deck_list=self._get_deck_list(deck); current=self.current_deck_name_a if deck=='a' else self.current_deck_name_b
        no_deck=NO_DECK_A if deck=='a' else NO_DECK_B
        if not deck_list: messagebox.showwarning("Empty", f"Deck {deck.upper()} empty."); return False
        if file_path is None:
            if current==no_deck: self.save_deck_as(deck=deck); return False
            else: file_path=os.path.join(DECKS_DIR, current)
        try:
            with open(file_path, "w") as f: json.dump(deck_list, f, indent=4)
            self.update_status(f"Deck {deck.upper()} saved as {os.path.basename(file_path)}", temporary=True) # Use status bar
            return True
        except Exception as e: self.update_status(f"Failed save: {e}", True); return False

    def load_deck(self, deck, deck_filename=None):
        # ... (uses status bar, validates against effective pool) ...
        if deck_filename is None:
             dropdown = self.load_deck_dropdown_a if deck == 'a' else self.load_deck_dropdown_b
             deck_filename = dropdown.get()
             if not deck_filename: messagebox.showwarning("No Deck", "Select deck from dropdown."); return False
        path = os.path.join(DECKS_DIR, deck_filename)
        try:
            with open(path, "r") as f: loaded = json.load(f)
            if not isinstance(loaded, dict): raise TypeError("Invalid format.")
            total = 0; invalid_cards = []
            for card, count in loaded.items():
                if not isinstance(card, str) or not isinstance(count, int) or count<1 or count>MAX_CARD_COPIES: raise ValueError(f"Invalid: {card} x{count}")
                if card not in self.card_pool: # Check against effective pool
                     print(f"Warning: Card '{card}' in loaded deck not found in current effective card pool.")
                     invalid_cards.append(card)
                total += count
            if total > MAX_DECK_SIZE: raise ValueError(f"Too many cards: {total}")

            if invalid_cards:
                 messagebox.showwarning("Load Warning", f"Deck '{deck_filename}' loaded, but contains unknown cards removed from database:\n- " + "\n- ".join(invalid_cards) + "\nThese cards were NOT added.")
                 for card in invalid_cards: del loaded[card] # Remove invalid cards

            if deck=='a': self.deck_list_a = loaded; self.current_deck_name_a = deck_filename
            else: self.deck_list_b = loaded; self.current_deck_name_b = deck_filename
            self.update_deck_listbox(deck); self.update_deck_counts(deck)
            if self.comparison_mode.get(): self.update_deck_differences()
            self.update_status(f"'{deck_filename}' loaded to Deck {deck.upper()}.", temporary=True)
            dropdown = self.load_deck_dropdown_a if deck == 'a' else self.load_deck_dropdown_b
            dropdown.set(deck_filename)
            return True
        except FileNotFoundError: self.update_status(f"Not found: {deck_filename}", True); self.update_load_deck_dropdown(); return False
        except (json.JSONDecodeError, ValueError, TypeError) as e: self.update_status(f"Invalid file '{deck_filename}': {e}", True); return False
        except Exception as e: self.update_status(f"Error loading '{deck_filename}': {e}", True); return False

    # --- Category Management Methods ---
    def _load_initial_categories(self):
        # ... (same as previous version) ...
        try:
            if os.path.exists(CATEGORY_FILE):
                with open(CATEGORY_FILE, 'r') as f: data = json.load(f)
                if isinstance(data, dict):
                    converted_data = {}; needs_resave = False
                    for card, value in data.items():
                        # Use effective pool for validation here too
                        if card not in self.card_pool: print(f"Warn: Ignoring category for unknown card '{card}'"); continue
                        if isinstance(value, str): converted_data[card] = [value]; needs_resave = True
                        elif isinstance(value, list): converted_data[card] = sorted(list(set(value)))
                        else: print(f"Warning: Skipping invalid category data for '{card}'")
                    if needs_resave:
                        print("Info: Converting category file to new list format.")
                        try:
                            with open(CATEGORY_FILE, 'w') as wf: json.dump(converted_data, wf, indent=4, sort_keys=True)
                        except Exception as save_err: print(f"Error saving converted categories: {save_err}")
                    print(f"Loaded {len(converted_data)} category assignments.")
                    return converted_data
                else: print(f"Warn: {CATEGORY_FILE} invalid."); return {}
            else: return {}
        except Exception as e: self.update_status(f"Error loading categories: {e}", True); return {}

    def load_card_categories(self):
         # ... (same as previous version) ...
         self.card_categories = self._load_initial_categories()
         self.update_status("Card categories reloaded.")

    def _open_category_manager(self):
        # ... (Passes effective card pool) ...
        if hasattr(self, '_category_window') and self._category_window.winfo_exists(): self._category_window.lift(); return
        self._category_window = CategoryManagerWindow(self, self.card_pool) # Pass self (app instance) and effective pool

    # --- App State Persistence ---
    def _load_app_state(self):
        # ... (same as previous version) ...
        try:
            if os.path.exists(APP_STATE_FILE):
                with open(APP_STATE_FILE, 'r') as f: state = json.load(f)
                return state.get("last_deck_a"), state.get("last_deck_b")
        except (json.JSONDecodeError, Exception) as e: print(f"Warn: Could not load app state: {e}")
        return None, None

    def _save_app_state(self, deck_a_name, deck_b_name):
        # ... (same as previous version) ...
        state = {"last_deck_a": deck_a_name, "last_deck_b": deck_b_name}
        try:
            with open(APP_STATE_FILE, 'w') as f: json.dump(state, f, indent=4)
        except Exception as e: print(f"Warn: Could not save app state: {e}")

    def _load_last_submitted_decks(self):
         # ... (same as previous version) ...
         last_a, last_b = self._load_app_state()
         loaded_any = False
         if last_a and last_a != NO_DECK_A:
              print(f"Attempting to preload Deck A: {last_a}")
              if self.load_deck(deck='a', deck_filename=last_a): loaded_any = True
         if self.comparison_mode.get() and last_b and last_b != NO_DECK_B:
              print(f"Attempting to preload Deck B: {last_b}")
              if self.load_deck(deck='b', deck_filename=last_b): loaded_any = True
         if loaded_any: self.update_status("Loaded last submitted deck(s).", temporary=True)
         else: self.update_status("No previous decks found or loaded.")

    # --- Simulation & Analysis Trigger Methods ---
    def validate_decks_for_submission(self):
        # ... (same as previous version) ...
        valid_a = self.get_total_cards('a') >= MIN_DECK_SIZE
        valid_b = self.get_total_cards('b') >= MIN_DECK_SIZE
        can_submit = valid_a and (valid_b if self.comparison_mode.get() else True)
        self.submit_button.config(state="normal" if can_submit else "disabled")
        if not can_submit: self.start_simulation_button.config(state="disabled")
        return can_submit

    def submit_decks(self):
        # ... (uses status bar, saves state) ...
        if not self.validate_decks_for_submission():
            msg = f"Deck(s) must have >= {MIN_DECK_SIZE} cards."
            messagebox.showwarning("Invalid Deck(s)", msg); return
        self.current_submitted_deck_a = self.current_deck_name_a
        self.current_deck_label_a.config(text=f"Submitted A: {self.current_submitted_deck_a}")
        is_comp = self.comparison_mode.get(); self.submitted_is_comparison = is_comp
        self.submitted_deck_list_a = self.deck_list_a.copy()
        self.submitted_stats_a = {'total': self.get_total_cards('a'), 'M': self._get_deck_widgets('a')['monster_count'].get(), 'S': self._get_deck_widgets('a')['spell_count'].get(), 'T': self._get_deck_widgets('a')['trap_count'].get()}
        if is_comp:
            self.current_submitted_deck_b = self.current_deck_name_b
            self.current_deck_label_b.config(text=f"Submitted B: {self.current_submitted_deck_b}")
            self.submitted_deck_list_b = self.deck_list_b.copy()
            self.submitted_stats_b = {'total': self.get_total_cards('b'), 'M': self._get_deck_widgets('b')['monster_count'].get(), 'S': self._get_deck_widgets('b')['spell_count'].get(), 'T': self._get_deck_widgets('b')['trap_count'].get()}
        else:
            self.current_submitted_deck_b = ""; self.current_deck_label_b.config(text="Submitted B: ")
            self.submitted_deck_list_b = {}; self.submitted_stats_b = {}
        self._save_app_state(self.current_submitted_deck_a, self.current_submitted_deck_b)
        self.start_simulation_button.config(state="normal")
        self.update_status("Deck(s) submitted. Ready for simulation.", temporary=True)

    def start_simulation_thread(self):
        # ... (passes combined combos) ...
        self.update_status("Starting simulation..."); self.start_simulation_button.config(state="disabled")
        self.submit_button.config(state="disabled")
        try: num_sim = self.num_simulations.get(); assert num_sim > 0
        except (ValueError, AssertionError): self.update_status("Invalid #simulations.", True); self.validate_decks_for_submission(); return
        deck_a_to_sim = self.submitted_deck_list_a; is_comp_to_sim = self.submitted_is_comparison
        deck_b_to_sim = self.submitted_deck_list_b if is_comp_to_sim else None
        name_a_to_sim = self.current_submitted_deck_a; name_b_to_sim = self.current_submitted_deck_b
        stats_a_to_sim = self.submitted_stats_a; stats_b_to_sim = self.submitted_stats_b if is_comp_to_sim else None
        cats_copy = self.card_categories.copy()
        # Combine hardcoded and custom combos
        all_combos_to_pass = analysis_engine._define_combos()
        all_combos_to_pass.update(self.custom_combos) # Custom overwrites hardcoded if names match
        combo_map_to_pass = analysis_engine._define_combo_card_map() # Still using hardcoded map

        sim_thread = threading.Thread(
            target=self._run_simulation_task,
            args=(num_sim, is_comp_to_sim, deck_a_to_sim, deck_b_to_sim,
                  name_a_to_sim, name_b_to_sim, stats_a_to_sim, stats_b_to_sim,
                  cats_copy, all_combos_to_pass, combo_map_to_pass),
            daemon=True)
        sim_thread.start()

    def _run_simulation_task(self, num_sim, is_comp, deck_a, deck_b, name_a, name_b, stats_a, stats_b, card_categories, card_combos, combo_card_map):
        # ... (Calls analysis_engine.run_simulation and analyze_and_generate_pdf as before) ...
        try:
            # card_combos and combo_card_map are now passed in
            self.simulation_queue.put(("status", f"Simulating Deck A ({name_a})..."))
            results_a = analysis_engine.run_simulation(num_sim, deck_a, "A", card_combos, card_categories, self.simulation_queue)
            if not results_a: self.simulation_queue.put(("error", "Deck A sim failed")); return
            results_b = None
            if is_comp:
                self.simulation_queue.put(("status", f"Simulating Deck B ({name_b})..."))
                results_b = analysis_engine.run_simulation(num_sim, deck_b, "B", card_combos, card_categories, self.simulation_queue)
                if not results_b: self.simulation_queue.put(("error", "Deck B sim failed")); return
            self.simulation_queue.put(("status", "Analyzing & generating PDF..."))
            pdf_filename = analysis_engine.analyze_and_generate_pdf(
                results_a, results_b, deck_a, deck_b, name_a, name_b, is_comp,
                card_combos, combo_card_map, card_categories, self.simulation_queue,
                stats_a, stats_b
            )
            if pdf_filename: self.simulation_queue.put(("pdf_ready", pdf_filename))
        except Exception as e: self.simulation_queue.put(("error", f"Task error: {e}"))

    def _check_simulation_queue(self):
        # ... (same as previous version) ...
        try:
            while True:
                msg_type, msg_data = self.simulation_queue.get_nowait()
                if msg_type == "status": self.update_status(msg_data)
                elif msg_type == "error":
                    self.update_status(msg_data, error=True)
                    self.validate_decks_for_submission(); self._unbind_pdf_prompt_keys()
                elif msg_type == "pdf_ready":
                    pdf_path = msg_data; self.last_pdf_path = pdf_path
                    status_msg = f"PDF Ready: {os.path.basename(pdf_path)}. Press Space=Open Folder, X=Dismiss."
                    self.update_status(status_msg)
                    self._bind_pdf_prompt_keys()
                    self.validate_decks_for_submission()
                elif msg_type == "complete": # Fallback complete message
                    self.update_status(msg_data)
                    self.validate_decks_for_submission()
        except queue.Empty:
            self.root.after(100, self._check_simulation_queue)

    # --- PDF Prompt Handlers ---
    def _bind_pdf_prompt_keys(self):
        # ... (same as previous version) ...
        self._unbind_pdf_prompt_keys()
        self.root.bind("<space>", self._handle_open_pdf_prompt)
        self.root.bind("<KeyPress-x>", self._handle_dismiss_pdf_prompt)
        self.root.bind("<KeyPress-X>", self._handle_dismiss_pdf_prompt)
        self.root.focus_set()

    def _unbind_pdf_prompt_keys(self):
        # ... (same as previous version) ...
        self.root.unbind("<space>")
        self.root.unbind("<KeyPress-x>")
        self.root.unbind("<KeyPress-X>")

    def _handle_open_pdf_prompt(self, event=None):
        # ... (same as previous version) ...
        if self.last_pdf_path and os.path.exists(self.last_pdf_path):
            folder_path = os.path.dirname(self.last_pdf_path)
            try:
                if sys.platform == "win32": os.startfile(folder_path)
                elif sys.platform == "darwin": subprocess.call(["open", folder_path])
                else: subprocess.call(["xdg-open", folder_path])
                self.update_status(f"Opened: {folder_path}", temporary=True)
            except Exception as e: self.update_status(f"Error opening folder: {e}", error=True)
        else: self.update_status("PDF path not found.", error=True)
        self._unbind_pdf_prompt_keys(); self.last_pdf_path = None

    def _handle_dismiss_pdf_prompt(self, event=None):
        # ... (same as previous version) ...
        self._unbind_pdf_prompt_keys(); self.last_pdf_path = None
        self.update_status("Idle")

    # --- Custom Combo Methods ---
    def _load_initial_custom_combos(self):
        # ... (same as previous version) ...
        try:
            if os.path.exists(CUSTOM_COMBO_FILE):
                with open(CUSTOM_COMBO_FILE, 'r') as f: data = json.load(f)
                if isinstance(data, dict): print(f"Loaded {len(data)} custom combos."); return data
                else: print(f"Warn: {CUSTOM_COMBO_FILE} invalid format."); return {}
            else: return {}
        except Exception as e: self.update_status(f"Error loading custom combos: {e}", True); return {}

    def load_custom_combos(self):
        # ... (same as previous version) ...
        self.custom_combos = self._load_initial_custom_combos()
        self.update_status("Custom combos reloaded.")

    def _open_combo_editor(self):
        # ... (same as previous version) ...
        if hasattr(self, '_combo_editor_window') and self._combo_editor_window.winfo_exists(): self._combo_editor_window.lift(); return
        self._combo_editor_window = ComboEditorWindow(self.root, self.card_pool, self.custom_combos, self.hardcoded_combo_definitions)

    # --- Card DB Editor Methods ---
    def _open_db_editor(self):
         """Opens the Toplevel window for managing the card database."""
         if hasattr(self, '_db_editor_window') and self._db_editor_window.winfo_exists():
              self._db_editor_window.lift(); return
         # <<< FIX: Pass self (app instance) instead of self.root >>>
         # Pass base pool/types and user data separately
         self._db_editor_window = CardDatabaseEditorWindow(self)


if __name__ == "__main__":
    root = tk.Tk()
    app = DeckSimulatorApp(root)
    root.mainloop()
