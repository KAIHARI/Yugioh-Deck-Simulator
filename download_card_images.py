import os
import json
import sys
import time
import re
import requests # Needs: pip install requests

# --- Configuration ---
# Assume card_database.py is in the same directory or Python path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DB_FILE = "user_card_database.json"
CARD_IMAGES_DIR = "card_images"
# YGOPRODeck API endpoint
API_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
# Delay between API requests to be polite (seconds)
REQUEST_DELAY = 0.2

# --- Import Base Card Pool ---
try:
    # Assumes card_database.py is runnable or importable from script location
    from card_database import CARD_POOL
    BASE_CARD_POOL = set(CARD_POOL)
    print(f"Successfully imported {len(BASE_CARD_POOL)} base cards from card_database.py")
except ImportError:
    print("ERROR: Could not import CARD_POOL from card_database.py.")
    print("Ensure card_database.py exists and is in the same directory or Python path.")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: An unexpected error occurred importing from card_database.py: {e}")
    sys.exit(1)

# --- Helper Functions ---

def sanitize_filename(name):
    """Removes or replaces characters invalid for filenames."""
    # Remove characters that are definitely problematic
    name = re.sub(r'[\\/*?:"<>|]', '', name)
    # Replace other potentially problematic characters like colons if needed
    # name = name.replace(':', '_') # Example: replace colon
    return name

def load_user_db():
    """Loads user additions and removals from the JSON file."""
    added_cards = {}
    removed_cards = set()
    try:
        if os.path.exists(USER_DB_FILE):
            with open(USER_DB_FILE, 'r') as f:
                data = json.load(f)
            if isinstance(data, dict):
                # Load added cards (just need names)
                added_data = data.get("added_cards", {})
                if isinstance(added_data, dict):
                    added_cards = set(str(k) for k in added_data.keys())
                else:
                    print(f"Warning: 'added_cards' in {USER_DB_FILE} is not a dictionary. Ignoring.")

                # Load removed cards
                removed_data = data.get("removed_cards", [])
                if isinstance(removed_data, list):
                    removed_cards = set(str(c) for c in removed_data)
                else:
                     print(f"Warning: 'removed_cards' in {USER_DB_FILE} is not a list. Ignoring.")
            else:
                print(f"Warning: {USER_DB_FILE} content is not a dictionary.")
        else:
            print(f"Info: {USER_DB_FILE} not found. No user changes loaded.")
    except (json.JSONDecodeError, Exception) as e:
        print(f"ERROR: Failed to load or parse {USER_DB_FILE}: {e}")
        # Continue without user data if file is corrupt
    print(f"Loaded {len(added_cards)} added cards and {len(removed_cards)} removed cards from user DB.")
    return added_cards, removed_cards

def calculate_effective_card_pool(base_pool, added_cards, removed_cards):
    """Calculates the final list of card names needing images."""
    effective_pool = base_pool.copy()
    effective_pool.update(added_cards) # Add user-added card names
    effective_pool -= removed_cards    # Remove user-removed card names
    return sorted(list(effective_pool))

def get_image_url(card_name):
    """Queries the API to get the small image URL for a card."""
    params = {'name': card_name}
    try:
        response = requests.get(API_URL, params=params, timeout=10) # Added timeout
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        data = response.json()

        # Check if 'data' key exists and is a non-empty list
        if 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
            card_info = data['data'][0] # Assume first result is the correct one for exact name match
            if 'card_images' in card_info and isinstance(card_info['card_images'], list) and len(card_info['card_images']) > 0:
                # Look for 'image_url_small'
                if 'image_url_small' in card_info['card_images'][0]:
                    return card_info['card_images'][0]['image_url_small']
                else:
                    print(f"Warning: 'image_url_small' not found for '{card_name}'.")
                    return None
            else:
                 print(f"Warning: No 'card_images' data found for '{card_name}'.")
                 return None
        else:
            print(f"Warning: Card '{card_name}' not found in API response.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Network error fetching URL for '{card_name}': {e}")
        return None
    except json.JSONDecodeError:
        print(f"ERROR: Could not decode API response for '{card_name}'.")
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error getting URL for '{card_name}': {e}")
        return None

def download_image(image_url, save_path):
    """Downloads an image from a URL and saves it."""
    try:
        img_response = requests.get(image_url, stream=True, timeout=15) # Added timeout
        img_response.raise_for_status()

        with open(save_path, 'wb') as f:
            for chunk in img_response.iter_content(chunk_size=8192):
                f.write(chunk)
        # print(f"      Success: Saved to {os.path.basename(save_path)}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Network error downloading image for {os.path.basename(save_path)}: {e}")
        return False
    except IOError as e:
         print(f"ERROR: Could not write image file {save_path}: {e}")
         return False
    except Exception as e:
        print(f"ERROR: Unexpected error downloading image for {os.path.basename(save_path)}: {e}")
        return False

# --- Main Download Logic ---
def main():
    print("-" * 30)
    print("Starting Yu-Gi-Oh! Card Image Downloader")
    print("-" * 30)

    # Ensure target directory exists
    if not os.path.exists(CARD_IMAGES_DIR):
        try:
            os.makedirs(CARD_IMAGES_DIR)
            print(f"Created image directory: {CARD_IMAGES_DIR}")
        except OSError as e:
            print(f"ERROR: Could not create image directory '{CARD_IMAGES_DIR}': {e}")
            sys.exit(1)

    # Get card list
    added_names, removed_names = load_user_db()
    effective_cards = calculate_effective_card_pool(BASE_CARD_POOL, added_names, removed_names)

    if not effective_cards:
        print("No effective cards found to download images for.")
        sys.exit(0)

    print(f"Found {len(effective_cards)} cards in the effective pool.")
    print(f"Checking/Downloading images to '{CARD_IMAGES_DIR}'...")

    downloaded_count = 0
    skipped_count = 0
    error_count = 0

    total_cards = len(effective_cards)
    for i, card_name in enumerate(effective_cards):
        print(f"\n[{i+1}/{total_cards}] Processing: {card_name}")

        # Create a safe filename (API usually provides jpg)
        safe_filename = sanitize_filename(card_name) + ".jpg"
        save_path = os.path.join(CARD_IMAGES_DIR, safe_filename)

        # Check if image already exists
        if os.path.exists(save_path):
            print("      Skipping: Image already exists.")
            skipped_count += 1
            continue

        # Get image URL from API
        print("      Querying API...")
        image_url = get_image_url(card_name)
        time.sleep(REQUEST_DELAY) # Wait before next request

        if image_url:
            print(f"      Found URL: {image_url.split('/')[-1]}") # Show just filename part of URL
            print("      Downloading...")
            if download_image(image_url, save_path):
                downloaded_count += 1
            else:
                error_count += 1
                # Optional: Try to remove partially downloaded file on error
                if os.path.exists(save_path):
                    try: os.remove(save_path)
                    except OSError: pass
        else:
            print(f"      ERROR: Could not find image URL for '{card_name}'.")
            error_count += 1

    print("-" * 30)
    print("Download Summary:")
    print(f"  Total Cards Processed: {total_cards}")
    print(f"  Images Downloaded:     {downloaded_count}")
    print(f"  Images Skipped:        {skipped_count}")
    print(f"  Errors / Not Found:    {error_count}")
    print("-" * 30)

if __name__ == "__main__":
    main()
