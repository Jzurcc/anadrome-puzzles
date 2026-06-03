import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field

# Fix Windows terminal Unicode printing issues
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from groq import Groq
except ImportError:
    print("Please install the required packages: pip install groq pydantic")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ANADROMES_CSV   = Path(r"d:\Anadromes\anadromes_ranked_clean.csv")
DEFINITIONS_CSV = Path(r"d:\Anadromes\best_definitions_ai.csv")
OUTPUT_CSV      = Path(r"d:\Anadromes\anadromes_difficulty_llm.csv")   # intermediate
FINAL_CSV       = Path(r"d:\Anadromes\anadromes_ranked_llm.csv")        # clean final

BATCH_SIZE      = 10
MODEL           = "llama-3.1-8b-instant"

DIFFICULTY_TIERS = ["Very Easy", "Easy", "Medium", "Hard", "Very Hard", "Insane"]

# Ensure the GROQ_API_KEY environment variable is set
if not os.environ.get("GROQ_API_KEY"):
    print("ERROR: GROQ_API_KEY environment variable is not set.")
    print("Please set it in your terminal before running this script.")
    sys.exit(1)

client = Groq()

# ---------------------------------------------------------------------------
# Pydantic models for structured output
# ---------------------------------------------------------------------------
class PuzzleDifficulty(BaseModel):
    word1: str = Field(description="The first word of the anadrome pair")
    word2: str = Field(description="The second word of the anadrome pair (reverse of word1)")
    difficulty: Literal["Very Easy", "Easy", "Medium", "Hard", "Very Hard", "Insane"] = Field(
        description="The difficulty tier for this puzzle"
    )
    reasoning: str = Field(description="Brief reasoning for the chosen difficulty tier")

class BatchDifficulty(BaseModel):
    ratings: list[PuzzleDifficulty]

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------
def load_word_pairs(path: Path) -> list[dict]:
    """Load anadrome pairs from anadromes_ranked_clean.csv."""
    pairs = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pairs.append({
                "word1":  row["Word 1"].strip(),
                "word2":  row["Word 2"].strip(),
                "length": int(row["Length"].strip()),
            })
    return pairs


def load_definitions(path: Path) -> dict[str, str]:
    """Return a mapping of word -> definition from best_definitions_ai.csv."""
    defs = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = row["word"].strip().lower()
            defs[word] = row["definition"].strip()
    return defs


def load_existing_results(path: Path) -> dict[tuple[str, str], dict]:
    """Load already-rated pairs so we can resume a partial run."""
    results = {}
    if not path.exists():
        return results
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["word1"].strip(), row["word2"].strip())
            results[key] = {
                "word1":      row["word1"].strip(),
                "word2":      row["word2"].strip(),
                "length":     row["length"].strip(),
                "difficulty": row["difficulty"].strip(),
                "reasoning":  row["reasoning"].strip(),
            }
    return results

# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------
PROMPT_TEMPLATE = """\
You are an expert puzzle designer for a game called **Anadromes**.

## How the game works
The player sees TWO definitions side by side. The two answers are words that are
exact letter-reversals of each other (e.g. "emit" ↔ "time", "lager" ↔ "regal").

**Crucially**: the player does NOT need to know both words to solve the puzzle.
The intended strategy is:
1. Read both definitions.
2. Identify whichever word you recognise from its clue (the "anchor").
3. Reverse the anchor word's letters — that gives you the other word.
4. If you were right, you also just *learned* the new word.

This means a puzzle where one word is very common and the other is obscure can
still be straightforward — the player anchors on the common word and discovers
the obscure one. The obscure word by itself does NOT make the puzzle hard.

## Your task
You are given:
- `word1` / `word2` — the two words (for your reference)
- `def1` / `def2` — the exact definitions shown to the player as clues

Rate difficulty **based on how easily a typical adult English speaker can find
their anchor** — i.e., how recognisable the EASIER of the two word/definition
pairs is.

### The two factors that determine difficulty

**1. How guessable is the easier clue?**
Ask: *"Given just this definition, how quickly does the word come to mind for
most English speakers?"*
- A vivid, primary-meaning definition of a common word → very guessable
- A technical, archaic, or non-primary-meaning definition of any word → harder

**2. Is there at least one clear anchor at all?**
- If at least one word/definition pair is immediately obvious → the puzzle is
  easy regardless of how obscure the other word is (the obscure one is
  discovered, not guessed).
- If BOTH clues are cryptic, specialised, or describe very obscure words →
  the player has no anchor to start from → the puzzle is genuinely hard.

**Do NOT factor in word length.**

## Difficulty tiers — defined by the EASIER side

| Tier | What it means |
|------|--------------|
| **Very Easy** | At least one definition immediately gives away a very common everyday word. Almost anyone can anchor instantly. (e.g. saw/was, dog/god, emit/time, evil/live, desserts/stressed) |
| **Easy** | The easier clue points to a familiar word, though it may need a moment's thought. Most speakers find an anchor quickly. (e.g. part/trap, know/wonk, door/rood) |
| **Medium** | Neither clue is immediately obvious, but a reasonably well-read speaker can work out at least one. One word may be common but its given definition describes a less typical meaning. (e.g. dah/had, der/red, drawer/reward) |
| **Hard** | Both clues are moderately difficult — neither word jumps out easily. A player needs decent vocabulary or domain knowledge to find an anchor. (e.g. lager/regal, lever/revel, knar/rank) |
| **Very Hard** | Both clues are genuinely hard — the words are rare, archaic, regional, or technical, and neither definition is a natural giveaway. Most players will struggle to find any foothold. |
| **Insane** | Both words are so obscure, dialectal, or non-standard that the vast majority of native English speakers cannot anchor on either one. Even knowledgeable players will find this extremely difficult. |

## Calibration examples
Use these to calibrate your ratings:
- saw / was → **Very Easy** (both instantly known)
- dog / god → **Very Easy** (both instantly known)  
- emit / time → **Very Easy** ("to send out" immediately clues "emit"; "time" is obvious)
- evil / live → **Very Easy** (both instantly known)
- desserts / stressed → **Very Easy** (despite length, both are household words)
- part / trap → **Easy** (both common, slight thought needed)
- know / wonk → **Easy** ("know" is the obvious anchor; "wonk" is learnable)
- may / yam → **Easy** ("may" is trivial anchor; "yam" is familiar enough)
- dah / had → **Medium** ("had" is obvious but "dah" as Morse code is unusual)
- drawer / reward → **Medium** (both known but neither clue is an immediate giveaway)
- lager / regal → **Hard** (both recognisable but neither clue is trivially obvious)
- feer / reef → **Very Hard** ("feer" is obscure agricultural term; "reef" is easy but still hard overall)

## IMPORTANT: Return ONLY valid JSON matching this exact schema:
{schema}

## Puzzles to rate:
{puzzles_json}
"""



def evaluate_batch(batch_data: list[dict], max_retries: int = 3) -> BatchDifficulty | None:
    """
    Send a batch of puzzles to Groq and return structured difficulty ratings.

    batch_data format:
    [
      {
        "word1": "emit",  "def1": "to send out or give off",
        "word2": "time",  "def2": "the indefinite continued progress of existence",
        "length": 4
      },
      ...
    ]
    """
    schema_json = json.dumps(BatchDifficulty.model_json_schema(), indent=2)
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
            return BatchDifficulty.model_validate_json(response.choices[0].message.content)
        except Exception as e:
            print(f"  Error on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                print("  Failed to evaluate batch after max retries.")
                return None

# ---------------------------------------------------------------------------
# CSV save helpers
# ---------------------------------------------------------------------------
def save_results(results: dict[tuple, dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["word1", "word2", "length", "difficulty", "reasoning"])
        for row in results.values():
            writer.writerow([
                row["word1"],
                row["word2"],
                row["length"],
                row["difficulty"],
                row["reasoning"],
            ])


def build_final_csv(pairs: list[dict], results: dict[tuple, dict]) -> None:
    """
    Produce anadromes_ranked_llm.csv:
    - Same word order as the original anadromes_ranked_clean.csv
    - Columns: Word 1, Word 2, Length, Difficulty Score (empty placeholder), Difficulty Class
    - Empty Difficulty Score keeps column indices compatible with main.py (row[4])
    """
    with open(FINAL_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["Word 1", "Word 2", "Length", "Difficulty Score", "Difficulty Class"])
        for pair in pairs:
            key = (pair["word1"], pair["word2"])
            if key in results:
                writer.writerow([
                    pair["word1"],
                    pair["word2"],
                    pair["length"],
                    "",                          # empty Difficulty Score placeholder
                    results[key]["difficulty"],
                ])
            else:
                print(f"WARNING: no result found for pair {pair['word1']}/{pair['word2']}, skipping.")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print(f"Loading word pairs from {ANADROMES_CSV}...")
    all_pairs = load_word_pairs(ANADROMES_CSV)

    print(f"Loading definitions from {DEFINITIONS_CSV}...")
    definitions = load_definitions(DEFINITIONS_CSV)

    print(f"Loading existing results from {OUTPUT_CSV} (if any)...")
    results = load_existing_results(OUTPUT_CSV)
    processed_keys = set(results.keys())

    # Filter out already-processed pairs
    remaining_pairs = [
        p for p in all_pairs
        if (p["word1"], p["word2"]) not in processed_keys
    ]

    print(f"Total pairs        : {len(all_pairs)}")
    print(f"Already processed  : {len(processed_keys)}")
    print(f"Remaining to rate  : {len(remaining_pairs)}")

    if not remaining_pairs:
        print("All pairs have already been rated!")
    else:
        # Build puzzle data with definitions
        puzzle_items = []
        for pair in remaining_pairs:
            w1, w2 = pair["word1"], pair["word2"]
            d1 = definitions.get(w1.lower(), "(no definition available)")
            d2 = definitions.get(w2.lower(), "(no definition available)")
            puzzle_items.append({
                "word1":  w1,
                "def1":   d1,
                "word2":  w2,
                "def2":   d2,
                "length": pair["length"],
            })

        total_batches = (len(puzzle_items) - 1) // BATCH_SIZE + 1

        for i in range(0, len(puzzle_items), BATCH_SIZE):
            batch = puzzle_items[i : i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            print(f"\n--- Batch {batch_num}/{total_batches} "
                  f"(pairs {i + 1}–{i + len(batch)}) ---")

            batch_result = evaluate_batch(batch)

            if batch_result:
                for rating in batch_result.ratings:
                    key = (rating.word1, rating.word2)

                    # Validate the returned difficulty tier
                    if rating.difficulty not in DIFFICULTY_TIERS:
                        print(f"  WARNING: invalid tier '{rating.difficulty}' "
                              f"for {rating.word1}/{rating.word2}. Defaulting to 'Medium'.")
                        rating.difficulty = "Medium"

                    # Find the original pair to get the length
                    original = next(
                        (p for p in batch if p["word1"] == rating.word1
                         and p["word2"] == rating.word2),
                        None,
                    )
                    length = original["length"] if original else "?"

                    results[key] = {
                        "word1":      rating.word1,
                        "word2":      rating.word2,
                        "length":     length,
                        "difficulty": rating.difficulty,
                        "reasoning":  rating.reasoning,
                    }
                    print(f"  {rating.word1:>12} / {rating.word2:<12} "
                          f"[{rating.difficulty}]  — {rating.reasoning[:80]}")
            else:
                print("  Skipping batch due to repeated failures.")

            # Save after every batch so a crash doesn't lose progress
            save_results(results, OUTPUT_CSV)
            print(f"  Progress saved ({len(results)}/{len(all_pairs)} rated).")

            if i + BATCH_SIZE < len(puzzle_items):
                print(f"  Waiting 30 s before next batch...")
                time.sleep(30)

    # -----------------------------------------------------------------------
    # Build the final clean CSV once all pairs are rated
    # -----------------------------------------------------------------------
    print(f"\nAll pairs rated. Building final CSV: {FINAL_CSV}")
    build_final_csv(all_pairs, results)
    print(f"Done! Wrote {FINAL_CSV}")

    # Print a quick distribution summary
    from collections import Counter
    dist = Counter(r["difficulty"] for r in results.values())
    print("\nDifficulty distribution:")
    for tier in DIFFICULTY_TIERS:
        print(f"  {tier:<12}: {dist.get(tier, 0)}")


if __name__ == "__main__":
    main()
