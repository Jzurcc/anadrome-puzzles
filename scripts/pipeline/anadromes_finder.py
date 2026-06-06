import csv

def find_asymmetric_anadromes(common_word_list, expanded_word_list):
    """
    Finds anadrome pairs where at least ONE word is in the common list,
    and its reverse exists in the expanded list.
    """
    common_words = set(word.strip().lower() for word in common_word_list)
    expanded_words = set(word.strip().lower() for word in expanded_word_list)
    
    anadrome_pairs = set()
    
    for word in common_words:
        if len(word) < 3:
            continue
            
        reversed_word = word[::-1]
        
        # Look for the reversed word in the expanded dictionary
        if reversed_word in expanded_words and word != reversed_word:
            # Sort alphabetically to avoid adding duplicates
            pair = tuple(sorted([word, reversed_word]))
            anadrome_pairs.add(pair)
            
    # Sort by length (descending)
    sorted_anadromes = sorted(list(anadrome_pairs), key=lambda x: (-len(x[0]), x[0]))
    
    return sorted_anadromes

if __name__ == "__main__":
    
    print("Loading datasets...")
    
    with open('scowl-70.txt', 'r', encoding='utf-8') as file60:
        scowl_60_data = file60.readlines()

    with open('scowl-80.txt', 'r', encoding='utf-8') as file80:
        scowl_80_data = file80.readlines()

    print("Processing asymmetric anadromes... this might take a moment.")
    results = find_asymmetric_anadromes(scowl_60_data, scowl_80_data)
    
    output_file = 'anadromes_list_scowl_70_to_80.csv'
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        writer.writerow(['Word 1', 'Word 2', 'Length'])
        
        for word1, word2 in results:
            writer.writerow([word1, word2, len(word1)])
            
    print(f"Success! Saved {len(results)} valid educational pairs to {output_file}")