import csv
import json
import requests
import time

def load_unique_words_from_csv(csv_filename):
    """Reads the CSV, extracts a flat, unique list of all words, and sorts them alphabetically."""
    unique_words = set()
    try:
        with open(csv_filename, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader) # Skip the header row
            
            for row in reader:
                if len(row) >= 2:
                    unique_words.add(row[0])
                    unique_words.add(row[1])
                    
        # Sort alphabetically so you can track progress easily in the terminal
        return sorted(list(unique_words))
    
    except FileNotFoundError:
        print(f"Error: Could not find {csv_filename}. Make sure it is in the same folder.")
        return []

def fetch_all_dictionary_data(word_list):
    """
    Loops through the word list, hits the FreeDictionaryAPI, and stores responses.
    Tracks words that return a 404 error.
    """
    base_url = "https://freedictionaryapi.com/api/v1/entries/en/"
    master_dictionary = {}
    missing_words_tracker = [] 
    
    total_words = len(word_list)
    print(f"Starting API fetch for {total_words} words. This will take about 3 to 4 minutes...\n")
    
    for index, word in enumerate(word_list, 1):
        print(f"[{index}/{total_words}] Fetching: {word.ljust(15)}...", end=" ")
        
        try:
            response = requests.get(base_url + word)
            
            if response.status_code == 200:
                master_dictionary[word] = response.json()
                print("Success")
                
            elif response.status_code == 404:
                master_dictionary[word] = {"error": "Word not found in API"}
                missing_words_tracker.append(word) 
                print("Not Found (404)")
                
            elif response.status_code == 429:
                print("RATE LIMITED! Pausing for 60 seconds...")
                time.sleep(60)
                master_dictionary[word] = {"error": "Rate limited"}
                
            else:
                print(f"Failed (Status Code: {response.status_code})")
                master_dictionary[word] = {"error": f"HTTP {response.status_code}"}
                
        except requests.exceptions.RequestException as e:
            print(f"Network Error: {e}")
            master_dictionary[word] = {"error": "Network connection failed"}
            
        # Safe 0.2s delay for freedictionaryapi.com
        time.sleep(0.2)
        
    return master_dictionary, missing_words_tracker

if __name__ == "__main__":
    # Define filenames
    input_csv = 'anadromes_list_scowl_70.csv' 
    output_json = 'raw_dictionary_data_scowl70_2.json'
    missing_csv = 'missing_words_scowl70_2.csv' 
    
    # Load and sort the words
    words_to_fetch = load_unique_words_from_csv(input_csv)
    
    if words_to_fetch:
        # Fire off the fetcher
        final_data, words_not_found = fetch_all_dictionary_data(words_to_fetch)
        
        # Save the master JSON data
        with open(output_json, 'w', encoding='utf-8') as json_file:
            json.dump(final_data, json_file, indent=4)
            
        # Save the missing words to a CSV file (if there are any)
        if words_not_found:
            with open(missing_csv, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Missing Word']) 
                
                for missing in words_not_found:
                    writer.writerow([missing])
                    
            print(f"\nSaved {len(words_not_found)} missing words to {missing_csv}.")
        else:
            print("\nAmazing! Every single word was found in the API.")
            
        print(f"All raw dictionary data safely saved to {output_json}.")