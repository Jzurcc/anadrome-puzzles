import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import json
import csv
import re
import requests
import time
from pathlib import Path

# Paths
PRUNED_JSON_PATH = Path(r"d:\Anadromes\dictionary_pruned.json")
BEST_DEF_CSV_PATH = Path(r"d:\Anadromes\best_definitions_ai.csv")

# Regex to detect grammar definitions
GRAMMAR_PATTERN = re.compile(
    r"^(plural of|past tense of|third-person singular of|present participle of|past participle of|third-person singular simple present indicative form of)\s+([a-zA-Z0-9_-]+)[\.\s]*$",
    re.IGNORECASE
)

def fetch_root_definition(root_word):
    """Fetch the definition and example of the root word from Free Dictionary API."""
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{root_word}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                meanings = data[0].get("meanings", [])
                if meanings:
                    defs = meanings[0].get("definitions", [])
                    if defs:
                        return defs[0].get("definition", ""), defs[0].get("example", "")
    except Exception as e:
        print(f"Error fetching {root_word}: {e}")
    return None, None

def main():
    print("Loading data...")
    
    # 1. Load PRUNED_JSON
    with open(PRUNED_JSON_PATH, "r", encoding="utf-8") as f:
        pruned_data = json.load(f)
        
    # 2. Load BEST_DEF_CSV
    csv_rows = []
    with open(BEST_DEF_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            csv_rows.append(row)
            
    # Track changes
    updated_count = 0
    not_found_count = 0
    
    print("Scanning for grammatical definitions...")
    for row in csv_rows:
        word = row["word"]
        defn = row["definition"]
        
        match = GRAMMAR_PATTERN.match(defn)
        if match:
            prefix = match.group(1).lower()
            root = match.group(2).lower()
            
            print(f"[{word}] found: '{prefix}' of '{root}'")
            
            root_def, root_ex = fetch_root_definition(root)
            if root_def:
                new_def = f"[{prefix} {root}] {root_def}"
                print(f"  -> New Def: {new_def}")
                
                # Update CSV Row
                row["definition"] = new_def
                
                # Update JSON
                if word in pruned_data:
                    entries = pruned_data[word].get("entries", [])
                    for entry in entries:
                        for sense in entry.get("senses", []):
                            if sense.get("definition") == defn:
                                sense["definition"] = new_def
                                if root_ex:
                                    if "examples" not in sense:
                                        sense["examples"] = []
                                    sense["examples"].insert(0, root_ex)
                updated_count += 1
            else:
                print(f"  -> Could not fetch API definition for root '{root}'")
                not_found_count += 1
                
            time.sleep(0.5) # Be nice to the API
            
    # Write back CSV
    if updated_count > 0:
        print("\nWriting updated CSV...")
        with open(BEST_DEF_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["word", "definition", "reasoning"])
            writer.writeheader()
            writer.writerows(csv_rows)
            
        print("Writing updated JSON...")
        with open(PRUNED_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(pruned_data, f, indent=4, ensure_ascii=False)
            
        print(f"Successfully updated {updated_count} definitions! ({not_found_count} failed)")
    else:
        print("No grammatical definitions found or updated.")

if __name__ == "__main__":
    main()
