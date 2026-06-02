import json
import csv
import os
import sys
import time
from pathlib import Path
from pydantic import BaseModel, Field

# Fix Windows terminal Unicode printing issues
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from groq import Groq
except ImportError:
    print("Please install the required packages: pip install groq pydantic")
    sys.exit(1)

# Configuration
INPUT_JSON = Path(r"d:\Anadromes\raw_dictionary_data_scowl70.json")
OUTPUT_CSV = Path(r"d:\Anadromes\best_definitions_ai.csv")
OUTPUT_JSON = Path(r"d:\Anadromes\dictionary_pruned_ai.json")
BATCH_SIZE = 15

# Ensure the GROQ_API_KEY environment variable is set
if not os.environ.get("GROQ_API_KEY"):
    print("ERROR: GROQ_API_KEY environment variable is not set.")
    print("Please set it in your terminal before running this script.")
    sys.exit(1)

client = Groq()

# Define Structured Outputs
class WordSelection(BaseModel):
    word: str = Field(description="The word being evaluated")
    selected_index: int = Field(description="The 0-based index of the chosen definition from the provided list")
    reasoning: str = Field(description="Brief reason for selecting this definition")

class BatchSelection(BaseModel):
    selections: list[WordSelection]

def get_all_definitions(entry_data):
    """Extract a flat list of all definitions for a given word entry."""
    defs = []
    for entry in entry_data.get("entries", []):
        for sense in entry.get("senses", []):
            d = sense.get("definition", "").strip()
            if d:
                defs.append(d)
            for sub in sense.get("subsenses", []):
                sd = sub.get("definition", "").strip()
                if sd:
                    defs.append(sd)
    return defs

def evaluate_batch(batch_data, max_retries=3):
    """
    Sends a batch of words and their definitions to Groq.
    batch_data format: [{'word': 'apple', 'definitions': ['a fruit', 'a tech company']}, ...]
    """
    schema_json = BatchSelection.model_json_schema()
    
    prompt = f"""
    You are an expert puzzle designer for a game called 'Anadromes' (an anagram guessing game).
    Your task is to select the single best dictionary definition to act as a hint for each word.
    
    CRITICAL RULES for selecting a definition:
    1. Must NOT reveal the word itself or use close variations (e.g., if the word is 'dessert', the definition cannot say 'a dessert wine').
    2. Must NOT be a trivial grammatical redirect (e.g., do NOT select 'plural of X', 'past participle of Y', 'alternative spelling of Z').
    3. Should be a common, readable, and natural description of the word. Avoid highly obscure, obsolete, or purely technical jargon if a simpler definition exists.
    4. FALLBACK: If ALL available definitions for a word violate these rules (e.g., they are all trivial redirects), you MUST still pick the best available option from the list. You must always return a valid 0-based index. Do NOT return -1 or skip the word.
    
    Below is a JSON list of words, each with an array of available definitions. 
    Evaluate each word and select the 0-based index of the best definition.
    
    IMPORTANT: You must return ONLY valid JSON matching this exact schema:
    {json.dumps(schema_json, indent=2)}
    
    Data:
    {json.dumps(batch_data, indent=2)}
    """
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            return BatchSelection.model_validate_json(response.choices[0].message.content)
        except Exception as e:
            print(f"Error on attempt {attempt+1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1)) # Exponential backoff
            else:
                print("Failed to evaluate batch after max retries.")
                return None

def main(test_mode=False):
    print(f"Loading {INPUT_JSON}...")
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    words = sorted(data.keys())
    
    # Load existing state to resume
    results = []
    pruned_dict = {}
    processed_words = set()
    
    if OUTPUT_JSON.exists():
        print(f"Found existing {OUTPUT_JSON}, loading to resume...")
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            try:
                pruned_dict = json.load(f)
                processed_words.update(pruned_dict.keys())
            except json.JSONDecodeError:
                print("Warning: existing JSON was malformed or empty. Starting fresh JSON.")
            
    if OUTPUT_CSV.exists():
        print(f"Found existing {OUTPUT_CSV}, loading to resume...")
        with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) >= 3:
                    results.append(tuple(row))
                    processed_words.add(row[0])
                    
    words = [w for w in words if w not in processed_words]
    
    if test_mode:
        print("Running in TEST MODE (only processing first 20 words).")
        words = words[:20]
        
    print(f"Total words left to process: {len(words)}")
    if len(words) == 0:
        print("All words have already been processed! Exiting.")
        return
    
    # Prepare word data
    all_word_data = []
    for word in words:
        defs = get_all_definitions(data[word])
        if defs:
            all_word_data.append({"word": word, "definitions": defs})
        else:
            print(f"WARNING: Word '{word}' has no definitions in the JSON.")
            
    # Process in batches
    for i in range(0, len(all_word_data), BATCH_SIZE):
        batch = all_word_data[i:i+BATCH_SIZE]
        print(f"\nProcessing batch {i//BATCH_SIZE + 1}/{(len(all_word_data)-1)//BATCH_SIZE + 1} (Words {i} to {i+len(batch)})...")
        
        batch_result = evaluate_batch(batch)
        
        if batch_result:
            # Map the selections back to the definitions
            for selection in batch_result.selections:
                word = selection.word
                idx = selection.selected_index
                
                # Find the original word data in this batch
                word_info = next((w for w in batch if w["word"] == word), None)
                if word_info:
                    defs = word_info["definitions"]
                    
                    if not (0 <= idx < len(defs)):
                        print(f"WARNING: LLM returned invalid index {idx} for word {word} (has {len(defs)} defs). Forcing index 0.")
                        idx = 0
                        selection.reasoning = f"Forced fallback (LLM returned {idx})"
                        
                    best_def = defs[idx]
                    results.append((word, best_def, selection.reasoning))
                    
                    print(f"  -> {word}: '{best_def}'")
                    print(f"     Reason: {selection.reasoning}")
                    
                    # Search original data to retain full sense metadata (tags, examples, etc.)
                    original_entry = None
                    original_sense = None
                    
                    for entry in data[word].get("entries", []):
                        for sense in entry.get("senses", []):
                            if sense.get("definition", "").strip() == best_def:
                                original_entry = entry
                                original_sense = sense
                                break
                            for sub in sense.get("subsenses", []):
                                if sub.get("definition", "").strip() == best_def:
                                    original_entry = entry
                                    original_sense = sub
                                    break
                        if original_entry:
                            break
                            
                    if original_entry and original_sense:
                        pruned_dict[word] = {
                            "entries": [{
                                "partOfSpeech": original_entry.get("partOfSpeech", "unknown"),
                                "senses": [original_sense]
                            }]
                        }
                    else:
                        # Fallback if original sense couldn't be matched (should not happen)
                        pruned_dict[word] = {
                            "entries": [{
                                "senses": [{
                                    "definition": best_def
                                }]
                            }]
                        }
                else:
                    print(f"WARNING: LLM returned evaluation for unknown word in batch: {word}")
        else:
            print("Skipping batch due to evaluation failure.")
            
        # Save progress after every batch
        print(f"Saving progress (total {len(results)} words processed so far)...")
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(["word", "definition", "reasoning"])
            for r in results:
                writer.writerow(r)
                
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(pruned_dict, f, indent=4)
            
        time.sleep(30) # Respect Groq's Tokens-Per-Minute limit
        
    print("\nDone! All words processed.")

if __name__ == "__main__":
    # Change to True to test quickly on 20 words
    main()
