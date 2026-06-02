"""
llm_judge_definitions.py
========================
Acts as an "LLM-as-a-Judge" to select the single BEST definition for each
word in raw_dictionary_data_scowl70.json for use in an anadrome puzzle game.

Selection criteria (in descending priority):
  1. Must not reveal the word itself (hard filter then score penalty)
  2. Must not be a trivial meta-definition ("plural of X", "past tense of Y",
     "alternative spelling of X", "misspelling of X", "abbreviation of X")
  3. Prefer common register (avoid: archaic, obsolete, rare, dialectal, vulgar)
  4. Prefer noun > verb > adjective > other PoS
  5. Prefer definitions with good, readable prose (15-40 words ideal)
  6. Prefer definitions that have examples (signal of importance)
  7. Prefer first sense within a PoS entry (Wiktionary orders by frequency)

Output: best_definitions.csv  (word, definition)
"""

import json
import re
import csv
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
INPUT_JSON  = Path(r"d:\Anadromes\raw_dictionary_data_scowl70.json")
OUTPUT_CSV  = Path(r"d:\Anadromes\best_definitions.csv")

# ---------------------------------------------------------------------------
# Tag classification tables
# ---------------------------------------------------------------------------
TRIVIAL_TAGS = {
    "form of", "plural", "plural of",
    "alternative", "alt of",
    "misspelling", "error",
    "abbreviation", "initialism", "clipping",
    "past tense", "past participle", "present participle",
    "comparative", "superlative",
    "gerund",
}

SEVERE_PENALISE = {
    "nonstandard", "vulgar", "offensive",
}

# Senses with these tags are hard-disqualified — never selected, even as fallback
STALE_TAGS = {
    "obsolete", "archaic", "dialectal", "rare",
}

# Definition text that opens with these labels is also hard-disqualified
# (catches cases where the tag is in the text but not in the tags array)
STALE_DEF_PREFIX = re.compile(
    r"^("
    # Opening parenthetical containing a stale word anywhere inside it
    r"\([^)]*\b(obsolete|archaic|dialectal|rare|poetic|dated|historical)\b[^)]*\)|"
    # Bare stale word at the very start (no parens)
    r"(obsolete|archaic|dialectal|dated)\b|"
    # Phrases like "Dated form of", "Archaic in the form", "Archaic spelling of"
    r"(dated|archaic|obsolete)\s+(form|spelling|in the)\b"
    r")",
    re.IGNORECASE
)

MODERATE_PENALISE = {
    "slang", "informal", "dated", "colloquial",
    "regional", "humorous", "euphemistic",
    "attributive", "predicative",
}

# Patterns that mark a definition as a trivial redirect
TRIVIAL_PATTERNS = re.compile(
    r"^(plural( of)?|alternative (spelling|form)|misspelling|"
    r"past (tense|participle)|present participle|"
    r"comparative|superlative|gerund|abbreviation|"
    r"simple past( and past participle)?|inflection|eye dialect|clipping|"
    r"past and past participle|plural and past tense|"
    r"third.person singular|second.person|first.person|"
    r"singular of|diminutive of|augmentative of|dated spelling|"
    r"archaic spelling|obsolete spelling|nonstandard spelling)\b",
    re.IGNORECASE
)

# Trailing noise: 'plural of X' / 'past tense of X' that follows a real sentence.
# Only strip when preceded by sentence-ending punctuation to avoid clobbering
# standalone grammatical definitions like "simple past and past participle of sing".
TRAILING_NOISE = re.compile(
    r"[.!?]\s+(plural of|singular of|past tense of|past participle of|"
    r"present participle of|alternative (spelling|form) of|misspelling of|"
    r"abbreviation of|initialism of|clipping of)\b.+$",
    re.IGNORECASE
)

# PoS preference order (lower index = more preferred)
POS_RANK = {
    "noun": 0,
    "verb": 1,
    "adjective": 2,
    "adverb": 3,
    "pronoun": 4,
    "preposition": 5,
    "conjunction": 6,
    "interjection": 7,
    "article": 8,
    "numeral": 9,
    "determiner": 10,
    "particle": 11,
    "prefix": 12,
    "suffix": 13,
    "phrase": 14,
    "proverb": 15,
    "unknown": 99,
}

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def get_roots(word):
    """Return word variants that would spoil the puzzle if they appear."""
    w = word.lower()
    roots = {w}
    if w.endswith("s") and len(w) > 3:
        roots.add(w[:-1])
    if w.endswith("es") and len(w) > 4:
        roots.add(w[:-2])
    if w.endswith("ed") and len(w) > 4:
        roots.add(w[:-2])
        roots.add(w[:-1])
    if w.endswith("ing") and len(w) > 5:
        roots.add(w[:-3])
    return roots




def reveals_word(defn, roots):
    """Return True if the definition gives away the word."""
    for r in roots:
        if re.search(r"\b" + re.escape(r) + r"\b", defn, re.IGNORECASE):
            return True
    return False


def is_stale(defn, tags):
    """Return True if this sense is obsolete/archaic/dialectal/rare — hard skip."""
    tag_set = {t.lower() for t in tags}
    if STALE_TAGS & tag_set:
        return True
    if STALE_DEF_PREFIX.match(defn.strip()):
        return True
    return False


def is_trivial(defn, tags):
    """Return True if this sense is a morphological redirect, not a real definition."""
    tag_set = {t.lower() for t in tags}
    if TRIVIAL_TAGS & tag_set:
        return True
    if TRIVIAL_PATTERNS.match(defn.strip()):
        return True
    return False


def score_sense(defn, tags, pos, has_examples, sense_index,
                entry_index, word, roots):
    """
    Higher score = better definition for the puzzle game.
    Returns -1e9 for disqualified senses (trivial or word-revealing).
    """
    # Hard disqualify
    if reveals_word(defn, roots):
        return -1e9
    if is_trivial(defn, tags):
        return -1e9
    if is_stale(defn, tags):
        return -1e9

    score = 500.0

    # PoS preference (lower rank = better)
    pos_lower = pos.lower()
    pos_penalty = POS_RANK.get(pos_lower, 99) * 10
    score -= pos_penalty

    # Tag penalties
    tag_set = {t.lower() for t in tags}
    for tag in tag_set:
        if tag in SEVERE_PENALISE:
            score -= 120
        elif tag in MODERATE_PENALISE:
            score -= 50

    # Definition length quality
    word_count = len(defn.split())
    if word_count < 4:
        score -= 80          # Too terse to be useful as a hint
    elif word_count < 8:
        score -= 30
    elif word_count <= 40:
        score += 20          # Sweet spot
    elif word_count <= 60:
        score += 5
    else:
        score -= 15          # Over-long

    # Reward having examples (signals common/important sense)
    if has_examples:
        score += 30

    # Prefer earlier senses (Wiktionary puts most common first)
    score -= sense_index * 8
    score -= entry_index * 5

    # Penalise definitions that are just a synonym dump (all caps / comma-list)
    if re.match(r"^[A-Z][A-Z ,;]+$", defn):
        score -= 60

    # Penalise very short definitions that look like labels ("See X.")
    if re.match(r"^See\b", defn, re.IGNORECASE) and word_count <= 4:
        score -= 80

    # Parenthetical-heavy definitions are harder to read as hints
    paren_count = defn.count("(")
    if paren_count >= 2:
        score -= paren_count * 10

    return score


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------
def collect_candidates(word, entry_data):
    """
    Return a list of (score, definition) for every non-trivial sense
    in this word's entry data.
    """
    roots = get_roots(word)
    candidates = []

    for entry_idx, entry in enumerate(entry_data.get("entries", [])):
        pos = entry.get("partOfSpeech", "unknown")
        senses = entry.get("senses", [])

        for sense_idx, sense in enumerate(senses):
            defn = sense.get("definition", "").strip()
            if not defn:
                continue
            tags = sense.get("tags", [])
            examples = sense.get("examples", []) or sense.get("quotes", [])
            has_examples = bool(examples)

            sc = score_sense(defn, tags, pos, has_examples,
                             sense_idx, entry_idx, word, roots)
            if sc > -1e8:   # Not hard-disqualified
                candidates.append((sc, defn))

            # Also evaluate subsenses
            for sub_idx, sub in enumerate(sense.get("subsenses", [])):
                sub_defn = sub.get("definition", "").strip()
                if not sub_defn:
                    continue
                sub_tags = sub.get("tags", [])
                sub_examples = sub.get("examples", []) or sub.get("quotes", [])
                sub_has_ex = bool(sub_examples)
                sub_sc = score_sense(
                    sub_defn, sub_tags, pos, sub_has_ex,
                    sense_idx + 0.5 + sub_idx * 0.1,
                    entry_idx, word, roots
                )
                if sub_sc > -1e8:
                    candidates.append((sub_sc, sub_defn))

    return candidates


def clean_definition(defn):
    """Strip trailing 'plural of X' noise that sometimes appears after a real definition."""
    cleaned = TRAILING_NOISE.sub("", defn).strip()
    return cleaned if cleaned else defn


def pick_best(word, entry_data):
    candidates = collect_candidates(word, entry_data)
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return clean_definition(candidates[0][1])

    # Fallback: any non-trivial, non-stale definition in this entry
    for entry in entry_data.get("entries", []):
        for sense in entry.get("senses", []):
            defn = sense.get("definition", "").strip()
            tags = sense.get("tags", [])
            if defn and not is_trivial(defn, tags) and not is_stale(defn, tags):
                return clean_definition(defn)

    # Last resort: accept grammatical/inflectional definitions, but still block stale ones.
    # "plural of dessert" is fine; "(obsolete) A garden." is not.
    for entry in entry_data.get("entries", []):
        for sense in entry.get("senses", []):
            defn = sense.get("definition", "").strip()
            tags = sense.get("tags", [])
            if defn and not is_stale(defn, tags):
                return clean_definition(defn)

    return None  # Word genuinely has nothing at all


def main():
    print(f"Loading {INPUT_JSON} ...", flush=True)
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    words = sorted(data.keys())
    print(f"Found {len(words)} words. Selecting best definitions ...", flush=True)

    results = []
    skipped = []
    for i, word in enumerate(words):
        best = pick_best(word, data[word])
        if best:
            results.append((word, best))
        else:
            skipped.append(word)

        if (i + 1) % 100 == 0:
            print(f"  ... processed {i+1}/{len(words)}", flush=True)

    print(f"\nWriting {len(results)} entries to {OUTPUT_CSV} ...", flush=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["word", "definition"])
        writer.writerows(results)

    print(f"Done.  {len(results)} definitions selected.")
    if skipped:
        print(f"WARNING: {len(skipped)} words had no usable definition: {skipped}")


if __name__ == "__main__":
    main()
