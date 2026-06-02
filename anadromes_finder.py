import csv

def find_asymmetric_anadromes(common_word_list, expanded_word_list):
    """
    Finds anadrome pairs where at least ONE word is in the common list,
    and its reverse exists in the expanded list.
    """
    # 1. Create two separate sets for O(1) lookups
    common_words = set(word.strip().lower() for word in common_word_list)
    expanded_words = set(word.strip().lower() for word in expanded_word_list)
    
    anadrome_pairs = set()
    
    # 2. Iterate ONLY through the common words
    # This guarantees that at least one word in every pair is highly recognizable
    for word in common_words:
        if len(word) < 3:
            continue
            
        reversed_word = word[::-1]
        
        # 3. The Asymmetric Logic Check:
        # We look for the reversed word in the EXPANDED dictionary.
        if reversed_word in expanded_words and word != reversed_word:
            # We still sort alphabetically before adding to the set.
            # This ensures that if BOTH words happen to be in the common list, 
            # we don't accidentally add the pair twice.
            pair = tuple(sorted([word, reversed_word]))
            anadrome_pairs.add(pair)
            
    # 4. Sort the final list by length (descending)
    sorted_anadromes = sorted(list(anadrome_pairs), key=lambda x: (-len(x[0]), x[0]))
    
    return sorted_anadromes

# ==========================================
# Example Usage 
# ==========================================
if __name__ == "__main__":
    
    print("Loading datasets...")
    
    # Load the Collegiate list (The anchor words)
    with open('scowl-70.txt', 'r', encoding='utf-8') as file60:
        scowl_60_data = file60.readlines()

    # Load the Huge list (The targets to check against)
    with open('scowl-80.txt', 'r', encoding='utf-8') as file80:
        scowl_80_data = file80.readlines()

    print("Processing asymmetric anadromes... this might take a moment.")
    results = find_asymmetric_anadromes(scowl_60_data, scowl_80_data)
    
    # Write to a CSV file
    output_file = 'anadromes_list_scowl_70_to_80.csv'
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write the header row
        writer.writerow(['Word 1', 'Word 2', 'Length'])
        
        # Write the data rows
        for word1, word2 in results:
            writer.writerow([word1, word2, len(word1)])
            
    print(f"Success! Saved {len(results)} valid educational pairs to {output_file}")