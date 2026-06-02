import csv
import math
import os

def load_wiki_ranks(filename):
    ranks = {}
    if not os.path.exists(filename):
        print(f"Error: {filename} not found.")
        return ranks
        
    with open(filename, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f, 1):
            w = line.strip().lower()
            if w and w not in ranks:
                ranks[w] = idx
    return ranks

def calculate_difficulty(w1, w2, wiki_ranks):
    w1_lower = w1.strip().lower()
    w2_lower = w2.strip().lower()
    
    # 1-indexed rank, default to 100,000 if not found
    r1 = wiki_ranks.get(w1_lower, 100000)
    r2 = wiki_ranks.get(w2_lower, 100000)
    
    # Obscurity scores (0.0 to 1.0)
    o1 = math.log10(max(1, r1)) / 5.0
    o2 = math.log10(max(1, r2)) / 5.0
    
    # Combine obscurity (75% min, 25% max)
    o_min = min(o1, o2)
    o_max = max(o1, o2)
    o_pair = 0.75 * o_min + 0.25 * o_max
    
    return o_pair

def get_difficulty_class(score):
    if score < 0.55:
        return "Very Easy"
    elif score < 0.68:
        return "Easy"
    elif score < 0.80:
        return "Medium"
    elif score < 0.90:
        return "Hard"
    elif score < 1.0:
        return "Very Hard"
    else:
        return "Insane"

def main():
    wiki_file = 'wiki-100k.txt'
    csv_file = 'anadromes_list_scowl_70.csv'
    output_file = 'anadromes_ranked.csv'
    not_found_file = 'not_found_words.csv'
    
    print("Loading word ranks from wiki-100k.txt...")
    wiki_ranks = load_wiki_ranks(wiki_file)
    print(f"Loaded {len(wiki_ranks)} unique word ranks.")
    
    ranked_pairs = []
    not_found_words = []
    
    print(f"Reading anadromes from {csv_file}...")
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, None)  # Skip header
        
        for row in reader:
            if len(row) >= 3:
                w1 = row[0].strip()
                w2 = row[1].strip()
                try:
                    length = int(row[2].strip())
                except ValueError:
                    length = len(w1)
                
                score = calculate_difficulty(w1, w2, wiki_ranks)
                diff_class = get_difficulty_class(score)
                
                ranked_pairs.append({
                    "Word 1": w1,
                    "Word 2": w2,
                    "Length": length,
                    "Difficulty Score": round(score, 4),
                    "Difficulty Class": diff_class
                })
                
                # Check for not found words
                w1_lower = w1.lower()
                w2_lower = w2.lower()
                if w1_lower not in wiki_ranks:
                    not_found_words.append({
                        "Word": w1,
                        "Partner": w2,
                        "Length": length
                    })
                if w2_lower not in wiki_ranks:
                    not_found_words.append({
                        "Word": w2,
                        "Partner": w1,
                        "Length": length
                    })
                
    # Sort pairs by Difficulty Score (ascending)
    ranked_pairs.sort(key=lambda x: x["Difficulty Score"])
    
    # Count distributions
    counts = {"Very Easy": 0, "Easy": 0, "Medium": 0, "Hard": 0, "Very Hard": 0, "Insane": 0}
    for pair in ranked_pairs:
        counts[pair["Difficulty Class"]] += 1
        
    print("\nDifficulty Class Distribution:")
    for k, v in counts.items():
        print(f" - {k}: {v} pairs ({round(v / len(ranked_pairs) * 100, 2)}%)")
        
    print(f"\nWriting ranked pairs to {output_file}...")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["Word 1", "Word 2", "Length", "Difficulty Score", "Difficulty Class"])
        writer.writeheader()
        writer.writerows(ranked_pairs)
        
    # Write not found words CSV
    print(f"Writing {len(not_found_words)} not found words to {not_found_file}...")
    with open(not_found_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["Word", "Partner", "Length"])
        writer.writeheader()
        writer.writerows(not_found_words)
        
    print("Finished successfully!")

if __name__ == '__main__':
    main()
