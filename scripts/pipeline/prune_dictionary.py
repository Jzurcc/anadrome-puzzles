"""
prune_dictionary.py
===================
Creates a pruned copy of raw_dictionary_data_scowl70.json that retains
only the single best sense (as chosen by best_definitions.csv) for each word.

- Words present in the CSV  -> kept with exactly one entry containing one sense
- Words absent from the CSV -> removed from the output entirely
"""

import json
import csv
from pathlib import Path

INPUT_JSON  = Path(r"d:\Anadromes\raw_dictionary_data_scowl70.json")
INPUT_CSV   = Path(r"d:\Anadromes\best_definitions.csv")
OUTPUT_JSON = Path(r"d:\Anadromes\dictionary_pruned.json")

# ---------------------------------------------------------------------------
# 1. Load chosen definitions from CSV
# ---------------------------------------------------------------------------
print("Loading chosen definitions from CSV ...", flush=True)
chosen = {}          # word -> chosen definition string
with open(INPUT_CSV, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        chosen[row["word"].strip().lower()] = row["definition"].strip()

print(f"  {len(chosen)} words with chosen definitions.", flush=True)

# ---------------------------------------------------------------------------
# 2. Load the full JSON
# ---------------------------------------------------------------------------
print("Loading JSON (this may take a moment) ...", flush=True)
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)
print(f"  {len(data)} words in JSON.", flush=True)

# ---------------------------------------------------------------------------
# 3. Build the pruned output
# ---------------------------------------------------------------------------
print("Pruning ...", flush=True)

pruned = {}
matched   = 0
unmatched = 0   # word in CSV but chosen def not found verbatim in JSON -> keep first

for word, word_data in data.items():
    w = word.lower()
    if w not in chosen:
        continue   # not in CSV, drop entirely

    target_def = chosen[w]

    # Search all entries/senses for the one matching the chosen definition
    found_entry = None
    found_sense = None

    for entry in word_data.get("entries", []):
        for sense in entry.get("senses", []):
            defn = sense.get("definition", "").strip()
            if defn == target_def:
                found_entry = entry
                found_sense = sense
                break
            # Also check subsenses
            for sub in sense.get("subsenses", []):
                if sub.get("definition", "").strip() == target_def:
                    found_entry = entry
                    found_sense = sub
                    break
            if found_entry:
                break
        if found_entry:
            break

    if found_entry and found_sense:
        matched += 1
        # Build a clean entry with only the chosen sense
        kept_entry = {
            "language":      found_entry.get("language", {}),
            "partOfSpeech":  found_entry.get("partOfSpeech", ""),
            "pronunciations": found_entry.get("pronunciations", []),
            "forms":         found_entry.get("forms", []),
            "senses": [found_sense],
            "synonyms":      found_entry.get("synonyms", []),
            "antonyms":      found_entry.get("antonyms", []),
        }
    else:
        # Chosen definition wasn't found verbatim (e.g. clean_definition stripped trailing noise).
        # Fall back to keeping the first non-empty sense of the first entry.
        unmatched += 1
        kept_entry = None
        for entry in word_data.get("entries", []):
            for sense in entry.get("senses", []):
                if sense.get("definition", "").strip():
                    kept_entry = {
                        "language":      entry.get("language", {}),
                        "partOfSpeech":  entry.get("partOfSpeech", ""),
                        "pronunciations": entry.get("pronunciations", []),
                        "forms":         entry.get("forms", []),
                        "senses": [sense],
                        "synonyms":      entry.get("synonyms", []),
                        "antonyms":      entry.get("antonyms", []),
                    }
                    break
            if kept_entry:
                break

    if kept_entry:
        pruned[word] = {
            "word":    word_data.get("word", word),
            "entries": [kept_entry],
            "source":  word_data.get("source", {}),
        }

print(f"  Exact match found:     {matched}")
print(f"  Fallback (first sense): {unmatched}")
print(f"  Total words kept:       {len(pruned)}")

# ---------------------------------------------------------------------------
# 4. Write output
# ---------------------------------------------------------------------------
print(f"\nWriting to {OUTPUT_JSON} ...", flush=True)
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(pruned, f, indent=4, ensure_ascii=False)

size_mb = OUTPUT_JSON.stat().st_size / 1_048_576
print(f"Done.  {OUTPUT_JSON.name}  ({size_mb:.1f} MB)")
