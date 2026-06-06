import csv
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from groq import Groq
except ImportError:
    print("Please install groq: pip install groq")
    sys.exit(1)

# Load .env file manually if exists
env_path = Path(r"d:\Anadromes\.env")
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("GROQ_API_KEY="):
                os.environ["GROQ_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")

# Ensure the GROQ_API_KEY environment variable is set
if not os.environ.get("GROQ_API_KEY"):
    print("ERROR: GROQ_API_KEY environment variable is not set.")
    sys.exit(1)

client = Groq()
MODEL = "llama-3.1-8b-instant"
BATCH_SIZE = 15
WAIT_BETWEEN_BATCHES = 1.0

# Files
FINAL_CSV = Path(r"d:\Anadromes\anadromes_ranked_llm.csv")
DEFINITIONS_CSV = Path(r"d:\Anadromes\best_definitions_ai.csv")
REASSIGN_JSON = Path(r"d:\Anadromes\themes_reassign.json")

REMOVED_THEMES = [
    "Oops! My Bad",
    "Sports Center",
    "What's in a Name?",
    "Smooth Criminals",
    "Spooky Season",
    "Double Vowels",
    "Action Movie"
]

KEPT_THEMES = [
    "Animal Kingdom",
    "Sound Effects",
    "Body Language",
    "Home Sweet Home",
    "Food Coma",
    "Gross Out!",
    "Internet Culture",
    "Fashion Disasters",
    "Emotional Rollercoaster",
    "Weird Science",
    "Grammar Police",
    "Nautical Nonsense",
    "A Bit Insulting",
    "Heavy Machinery"
]

ThemeLiteral = Literal[
    "Animal Kingdom", "Sound Effects", "Body Language", "Home Sweet Home",
    "Food Coma", "Gross Out!", "Internet Culture", "Fashion Disasters",
    "Emotional Rollercoaster", "Weird Science", "Grammar Police", "Nautical Nonsense",
    "A Bit Insulting", "Heavy Machinery"
]

class ThemeRanking(BaseModel):
    word1: str
    word2: str
    choice_1: ThemeLiteral
    choice_2: ThemeLiteral
    choice_3: ThemeLiteral

class BatchThemeRanking(BaseModel):
    rankings: list[ThemeRanking]

PROMPT_TEMPLATE = """\
You are an expert word categorizer for the puzzle game Anadromes.
An anadrome is a pair of words that are exact letter-reversals of each other (e.g. "emit" and "time").

Your task is to assign the best matching themes to a list of word pairs based on their words and definitions.

The available themes are exactly these 14 strings:
- "Animal Kingdom" (Animals, beasts, bugs)
- "Sound Effects" (Noises, shouts, onomatopoeia)
- "Body Language" (Anatomy, physical sensations)
- "Home Sweet Home" (Furniture, domestic life, housing)
- "Food Coma" (Eating, drinking, overindulging, cooking)
- "Gross Out!" (Icky, sticky, bodily-fluid related words, gross stuff)
- "Internet Culture" (Memes, tech, slang, modern chatter)
- "Fashion Disasters" (Clothing, fabrics, dressing up)
- "Emotional Rollercoaster" (Feelings, moods, states of mind)
- "Weird Science" (Laboratory terms, math, physics units)
- "Grammar Police" (Syntax, prepositions, conjunctions, simple verbs)
- "Nautical Nonsense" (Ships, sailing, oceans, swimming)
- "A Bit Insulting" (Name-calling, sass, derogatory terms)
- "Heavy Machinery" (Transportation, vehicles, tracks, engineering)

For each pair, provide the 1st best, 2nd best, and 3rd best theme.
DO NOT use any other strings. They MUST match the exact names of the 14 themes above.

IMPORTANT: You must return a JSON object with a single key "rankings", which is a list of your categorizations.
DO NOT output the schema itself. ONLY output the actual data matching the schema.

Example Output format:
{{
  "rankings": [
    {{
      "word1": "dog",
      "word2": "god",
      "choice_1": "Animal Kingdom",
      "choice_2": "Emotional Rollercoaster",
      "choice_3": "Home Sweet Home"
    }}
  ]
}}

Puzzles to categorize:
{puzzles_json}
"""

def load_csv() -> list[dict]:
    pairs = []
    with open(FINAL_CSV, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) >= 5:
                pairs.append({
                    "w1": row[0],
                    "w2": row[1],
                    "len": row[2],
                    "score": row[3],
                    "diff": row[4],
                    "theme": row[5] if len(row) >= 6 else "",
                    "original_row": row
                })
    return pairs

def load_definitions() -> dict[str, str]:
    defs = {}
    with open(DEFINITIONS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = row["word"].strip().lower()
            defs[word] = row["definition"].strip()
    return defs

def categorize_batch(batch_data: list[dict], max_retries: int = 3) -> BatchThemeRanking | None:
    puzzles_json = json.dumps(batch_data, indent=2)
    prompt = PROMPT_TEMPLATE.format(puzzles_json=puzzles_json)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            
            if isinstance(data, list):
                data = {"rankings": data}
            elif isinstance(data, dict) and "rankings" not in data:
                if all(isinstance(v, dict) for v in data.values()):
                     fixed_list = []
                     for k, v in data.items():
                         if "word1" in v and "word2" in v:
                             fixed_list.append(v)
                     if fixed_list:
                         data = {"rankings": fixed_list}
            
            return BatchThemeRanking.model_validate(data)
        except Exception as e:
            print(f"  Error on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))
            else:
                return None

def main():
    print("Loading data...")
    pairs = load_csv()
    definitions = load_definitions()
    
    # Identify pairs to reassign
    to_reassign = [p for p in pairs if p["theme"] in REMOVED_THEMES]
    print(f"Found {len(to_reassign)} pairs to reassign.")
    
    results = {}
    if REASSIGN_JSON.exists():
        try:
            with open(REASSIGN_JSON, "r", encoding="utf-8") as f:
                results = json.load(f)
        except json.JSONDecodeError:
            results = {}
            
    remaining_pairs = [p for p in to_reassign if f"{p['w1']}_{p['w2']}" not in results]
    
    if remaining_pairs:
        puzzle_items = []
        for pair in remaining_pairs:
            w1, w2 = pair["w1"], pair["w2"]
            puzzle_items.append({
                "word1": w1,
                "def1": definitions.get(w1.lower(), ""),
                "word2": w2,
                "def2": definitions.get(w2.lower(), "")
            })
            
        total_batches = (len(puzzle_items) - 1) // BATCH_SIZE + 1
        for i in range(0, len(puzzle_items), BATCH_SIZE):
            batch = puzzle_items[i : i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            print(f"Processing Batch {batch_num}/{total_batches}...")
            
            res = categorize_batch(batch)
            if res:
                for r in res.rankings:
                    key = f"{r.word1}_{r.word2}"
                    results[key] = {
                        "c1": r.choice_1,
                        "c2": r.choice_2,
                        "c3": r.choice_3
                    }
                with open(REASSIGN_JSON, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2)
            else:
                print("Failed batch! Aborting so we don't lose progress.")
                sys.exit(1)
            
            print(f"Waiting {WAIT_BETWEEN_BATCHES} seconds...")
            time.sleep(WAIT_BETWEEN_BATCHES)

    print("All reassignment preferences collected. Running assignment...")
    
    assigned_themes = {}
    theme_counts = {t: 0 for t in KEPT_THEMES}
    
    # 1. Start with the existing assignments that are kept
    for p in pairs:
        key = f"{p['w1']}_{p['w2']}"
        if p["theme"] in KEPT_THEMES:
            assigned_themes[key] = p["theme"]
            theme_counts[p["theme"]] += 1
            
    # 2. Assign the newly evaluated ones greedily
    for p in to_reassign:
        key = f"{p['w1']}_{p['w2']}"
        pref = results[key]
        c1 = pref["c1"]
        assigned_themes[key] = c1
        theme_counts[c1] += 1
        
    # 3. Fix Max Constraint (Max 30) for ALL themes
    for t in KEPT_THEMES:
        while theme_counts[t] > 30:
            moved = False
            # Try to move one of the NEWLY reassigned pairs out of this theme first
            for p in to_reassign:
                key = f"{p['w1']}_{p['w2']}"
                if assigned_themes[key] == t:
                    pref = results[key]
                    c2 = pref["c2"]
                    c3 = pref["c3"]
                    if theme_counts[c2] < 30:
                        assigned_themes[key] = c2
                        theme_counts[t] -= 1
                        theme_counts[c2] += 1
                        moved = True
                        break
                    elif theme_counts[c3] < 30:
                        assigned_themes[key] = c3
                        theme_counts[t] -= 1
                        theme_counts[c3] += 1
                        moved = True
                        break
            if not moved:
                # Force move to the emptiest theme
                emptiest = min(KEPT_THEMES, key=lambda x: theme_counts[x])
                for p in to_reassign:
                    key = f"{p['w1']}_{p['w2']}"
                    if assigned_themes[key] == t:
                        assigned_themes[key] = emptiest
                        theme_counts[t] -= 1
                        theme_counts[emptiest] += 1
                        moved = True
                        break
                        
            # If still not moved (meaning all pairs in this theme were original pairs, which could happen if it started at 30)
            if not moved:
                print(f"Warning: Theme {t} has >30 pairs, but no reassignable pairs to move. Forcing move of an original pair.")
                emptiest = min(KEPT_THEMES, key=lambda x: theme_counts[x])
                for key, assigned in assigned_themes.items():
                    if assigned == t:
                        assigned_themes[key] = emptiest
                        theme_counts[t] -= 1
                        theme_counts[emptiest] += 1
                        break
                        
    # 4. We don't necessarily need to enforce Min 5 since 16 themes and 364 pairs averages 22
    # but let's do a quick pass anyway.
    for t in KEPT_THEMES:
        while theme_counts[t] < 5:
            most_populated = max(KEPT_THEMES, key=lambda x: theme_counts[x])
            for key, assigned in assigned_themes.items():
                if assigned == most_populated:
                    theme_counts[most_populated] -= 1
                    assigned_themes[key] = t
                    theme_counts[t] += 1
                    break

    print("\nFinal distribution:")
    for t in KEPT_THEMES:
        print(f"  {t}: {theme_counts[t]}")
        
    # Write back to CSV
    with open(FINAL_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["Word 1", "Word 2", "Length", "Difficulty Score", "Difficulty Class", "Theme"])
        for p in pairs:
            key = f"{p['w1']}_{p['w2']}"
            theme = assigned_themes[key]
            
            row = p["original_row"]
            out_row = row[:5]
            while len(out_row) < 5:
                out_row.append("")
            out_row.append(theme)
            writer.writerow(out_row)
            
    print(f"\nSuccess! Wrote updated pairs to {FINAL_CSV}")

if __name__ == "__main__":
    main()
