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
WAIT_BETWEEN_BATCHES = 1.0  # Adjust this to experiment with rate limiting (in seconds)

# Files
FINAL_CSV = Path(r"d:\Anadromes\anadromes_ranked_llm.csv")
DEFINITIONS_CSV = Path(r"d:\Anadromes\best_definitions_ai.csv")
INTERMEDIATE_JSON = Path(r"d:\Anadromes\themes_intermediate.json")

THEMES = [
    "Animal Kingdom",
    "Double Vowels",
    "Sound Effects",
    "Body Language",
    "Home Sweet Home",
    "Food Coma",
    "Gross Out!",
    "Internet Culture",
    "Action Movie",
    "Fashion Disasters",
    "Emotional Rollercoaster",
    "Weird Science",
    "Smooth Criminals",
    "Spooky Season",
    "Grammar Police",
    "Nautical Nonsense",
    "A Bit Insulting",
    "Heavy Machinery",
    "Oops! My Bad",
    "Sports Center",
    "What's in a Name?"
]

ThemeLiteral = Literal[
    "Animal Kingdom", "Double Vowels", "Sound Effects", "Body Language", "Home Sweet Home",
    "Food Coma", "Gross Out!", "Internet Culture", "Action Movie", "Fashion Disasters",
    "Emotional Rollercoaster", "Weird Science", "Smooth Criminals", "Spooky Season",
    "Grammar Police", "Nautical Nonsense", "A Bit Insulting", "Heavy Machinery",
    "Oops! My Bad", "Sports Center", "What's in a Name?"
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

The available themes are exactly these 21 strings:
- "Animal Kingdom" (Animals, beasts, bugs)
- "Double Vowels" (Words with consecutive identical vowels, like ee, oo)
- "Sound Effects" (Noises, shouts, onomatopoeia)
- "Body Language" (Anatomy, physical sensations)
- "Home Sweet Home" (Furniture, domestic life, housing)
- "Food Coma" (Eating, drinking, overindulging, cooking)
- "Gross Out!" (Icky, sticky, bodily-fluid related words, gross stuff)
- "Internet Culture" (Memes, tech, slang, modern chatter)
- "Action Movie" (Guns, fighting, chases, aggressive verbs)
- "Fashion Disasters" (Clothing, fabrics, dressing up)
- "Emotional Rollercoaster" (Feelings, moods, states of mind)
- "Weird Science" (Laboratory terms, math, physics units)
- "Smooth Criminals" (Stealing, deceit, bad-guy behavior)
- "Spooky Season" (Monsters, magic, darkness, Halloween vibes)
- "Grammar Police" (Syntax, prepositions, conjunctions, simple verbs)
- "Nautical Nonsense" (Ships, sailing, oceans, swimming)
- "A Bit Insulting" (Name-calling, sass, derogatory terms)
- "Heavy Machinery" (Transportation, vehicles, tracks, engineering)
- "Oops! My Bad" (Clumsiness, accidents, rejections, mistakes)
- "Sports Center" (Athletics, games, competitive activities)
- "What's in a Name?" (Words that reverse to reveal human names)

For each pair, provide the 1st best, 2nd best, and 3rd best theme.
DO NOT use any other strings. They MUST match the exact names of the 21 themes above.

IMPORTANT: You must return a JSON object with a single key "rankings", which is a list of your categorizations.
DO NOT output the schema itself. ONLY output the actual data matching the schema.

Example Output format:
{{
  "rankings": [
    {{
      "word1": "dog",
      "word2": "god",
      "choice_1": "Animal Kingdom",
      "choice_2": "Spooky Season",
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
                # We will preserve all original columns to write back exactly
                pairs.append({
                    "w1": row[0],
                    "w2": row[1],
                    "len": row[2],
                    "score": row[3],
                    "diff": row[4],
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
    schema_json = json.dumps(BatchThemeRanking.model_json_schema(), indent=2)
    puzzles_json = json.dumps(batch_data, indent=2)
    prompt = PROMPT_TEMPLATE.format(schema=schema_json, puzzles_json=puzzles_json)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            content = response.choices[0].message.content
            # Parse manually to handle cases where the LLM returns a list directly
            data = json.loads(content)
            
            # If the LLM returned the schema or messed up, try to extract 'rankings'
            if isinstance(data, list):
                data = {"rankings": data}
            elif isinstance(data, dict) and "rankings" not in data:
                # If it returned a dict of dicts instead of list
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
    
    # Load intermediate if exists
    results = {}
    if INTERMEDIATE_JSON.exists():
        try:
            with open(INTERMEDIATE_JSON, "r", encoding="utf-8") as f:
                results = json.load(f)
        except json.JSONDecodeError:
            print("Intermediate JSON is empty or invalid. Starting fresh.")
            results = {}
            
    remaining_pairs = [p for p in pairs if f"{p['w1']}_{p['w2']}" not in results]
    
    if remaining_pairs:
        puzzle_items = []
        for pair in remaining_pairs:
            w1, w2 = pair["w1"], pair["w2"]
            d1 = definitions.get(w1.lower(), "")
            d2 = definitions.get(w2.lower(), "")
            puzzle_items.append({
                "word1": w1,
                "def1": d1,
                "word2": w2,
                "def2": d2
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
                with open(INTERMEDIATE_JSON, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2)
            else:
                print("Failed batch! Aborting so we don't lose progress.")
                sys.exit(1)
            
            print(f"Waiting {WAIT_BETWEEN_BATCHES} seconds before the next batch...")
            time.sleep(WAIT_BETWEEN_BATCHES) # rate limit prevention

    print("All pairs have theme preferences. Running assignment algorithm...")
    
    # Assignment Logic (Min 5, Max 30 per theme)
    assigned_themes = {}
    theme_counts = {t: 0 for t in THEMES}
    
    # Simple Greedy Assignment starting with Choice 1
    pair_keys = [f"{p['w1']}_{p['w2']}" for p in pairs]
    
    for key in pair_keys:
        pref = results[key]
        c1 = pref["c1"]
        assigned_themes[key] = c1
        theme_counts[c1] += 1
        
    print("\nInitial distribution:")
    for t in THEMES:
        print(f"  {t}: {theme_counts[t]}")
        
    # Fix Max Constraint (Max 30)
    for t in THEMES:
        while theme_counts[t] > 30:
            # Find a pair in this theme that can move to its 2nd or 3rd choice 
            # where that choice has < 30
            moved = False
            for key, assigned in assigned_themes.items():
                if assigned == t:
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
                emptiest = min(THEMES, key=lambda x: theme_counts[x])
                for key, assigned in assigned_themes.items():
                    if assigned == t:
                        assigned_themes[key] = emptiest
                        theme_counts[t] -= 1
                        theme_counts[emptiest] += 1
                        break
                        
    # Fix Min Constraint (Min 5)
    for t in THEMES:
        while theme_counts[t] < 5:
            # Find a pair in another theme (which has > 5) whose 2nd or 3rd choice is t
            moved = False
            for key, assigned in assigned_themes.items():
                if theme_counts[assigned] > 5:
                    pref = results[key]
                    if pref["c2"] == t or pref["c3"] == t:
                        theme_counts[assigned] -= 1
                        assigned_themes[key] = t
                        theme_counts[t] += 1
                        moved = True
                        break
            if not moved:
                # Force move from the most populated theme
                most_populated = max(THEMES, key=lambda x: theme_counts[x])
                for key, assigned in assigned_themes.items():
                    if assigned == most_populated:
                        theme_counts[most_populated] -= 1
                        assigned_themes[key] = t
                        theme_counts[t] += 1
                        break

    print("\nFinal distribution (after constraints):")
    for t in THEMES:
        print(f"  {t}: {theme_counts[t]}")
        
    # Write back to CSV
    with open(FINAL_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["Word 1", "Word 2", "Length", "Difficulty Score", "Difficulty Class", "Theme"])
        for p in pairs:
            key = f"{p['w1']}_{p['w2']}"
            theme = assigned_themes[key]
            
            # Extract old columns (max 5)
            row = p["original_row"]
            out_row = row[:5]
            # Ensure it has exactly 5 columns before appending theme
            while len(out_row) < 5:
                out_row.append("")
            out_row.append(theme)
            writer.writerow(out_row)
            
    print(f"\nSuccess! Wrote updated pairs to {FINAL_CSV}")

if __name__ == "__main__":
    main()
