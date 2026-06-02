import os
import sys
import random
import json
import csv
import re 

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8') 

# ---------------------------------------------------------
# Definition Filtering and Scoring System
# ---------------------------------------------------------
def score_definition(word, defn, tags, pos):
    word_lower = word.lower()
    score = 100
    
    # 1. Check for exact word itself (severe penalty)
    pattern_word = re.compile(r'\b' + re.escape(word_lower) + r'\b', re.IGNORECASE)
    if pattern_word.search(defn):
        score -= 200
        
    # Check for root word variants to avoid spoiling (e.g. "desserts" -> "dessert", "stressed" -> "stress")
    roots_to_check = []
    if word_lower.endswith('s') and len(word_lower) > 3:
        roots_to_check.append(word_lower[:-1])
    if word_lower.endswith('ed') and len(word_lower) > 4:
        roots_to_check.append(word_lower[:-2])
        roots_to_check.append(word_lower[:-1])
    if word_lower.endswith('ing') and len(word_lower) > 5:
        roots_to_check.append(word_lower[:-3])
        
    for r in roots_to_check:
        pattern_root = re.compile(r'\b' + re.escape(r) + r'\b', re.IGNORECASE)
        if pattern_root.search(defn):
            score -= 200
            break
            
    # 2. Penalize tags
    severe_tags = {'obsolete', 'archaic', 'dialectal', 'rare', 'nonstandard', 'vulgar', 'clipping'}
    moderate_tags = {'slang', 'informal', 'abbreviation', 'dated', 'colloquial', 'regional', 'error'}
    
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower in severe_tags:
            score -= 80
        elif tag_lower in moderate_tags:
            score -= 40
            
    # 3. Length penalties
    words_count = len(defn.split())
    if words_count <= 2:
        score -= 30
    elif words_count > 30:
        score -= 10
        
    # 4. Part of speech preference
    preferred_pos = {'noun', 'verb', 'adjective'}
    if pos.lower() not in preferred_pos:
        score -= 20
        
    return score


def sanitize_definition(defn, word):
    word_lower = word.lower()
    cleaned = defn
    words_to_hide = [word_lower]
    
    # Extract common roots to prevent spoiling
    if word_lower.endswith('s') and len(word_lower) > 3:
        words_to_hide.append(word_lower[:-1])
    if word_lower.endswith('ed') and len(word_lower) > 4:
        words_to_hide.append(word_lower[:-2])
        words_to_hide.append(word_lower[:-1])
    if word_lower.endswith('ing') and len(word_lower) > 5:
        words_to_hide.append(word_lower[:-3])
        
    # Sort roots by length descending to replace longer matches first
    for w in sorted(words_to_hide, key=len, reverse=True):
        pattern = re.compile(r'\b' + re.escape(w) + r'\w*\b', re.IGNORECASE)
        cleaned = pattern.sub("[word]", cleaned)
    return cleaned

# ---------------------------------------------------------
# Data Loading
# ---------------------------------------------------------
def load_game_data(csv_file, json_file):
    print("Loading game data... Please wait.")
    levels = []
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            dict_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find '{json_file}'.")
        sys.exit()

    def get_best_definition(word):
        word_lower = word.lower()
        if word_lower not in dict_data:
            return None
            
        scored_senses = []
        entries = dict_data[word_lower].get("entries", [])
        for entry in entries:
            pos = entry.get("partOfSpeech", "Unknown")
            senses = entry.get("senses", [])
            for sense in senses:
                defn = sense.get("definition", "")
                if defn:
                    tags = sense.get("tags", [])
                    score = score_definition(word_lower, defn, tags, pos)
                    scored_senses.append((defn, score))
                    
        if not scored_senses:
            return None
            
        # Sort by score descending to get the highest quality sense
        scored_senses.sort(key=lambda x: x[1], reverse=True)
        best_defn = scored_senses[0][0]
        
        # Sanitize definition to mask word variants
        sanitized = sanitize_definition(best_defn, word_lower)
        return sanitized

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None) 
            for row in reader:
                if len(row) >= 2:
                    w1 = row[0].strip().lower()
                    w2 = row[1].strip().lower()
                    diff_class = row[4].strip().title() if len(row) >= 5 else "Easy"
                    
                    d1 = get_best_definition(w1)
                    d2 = get_best_definition(w2)
                    
                    if d1 and d2:
                        levels.append({
                            "w1": w1.upper(),
                            "w2": w2.upper(),
                            "d1": d1,
                            "d2": d2,
                            "difficulty": diff_class
                        })
    except FileNotFoundError:
        print(f"Error: Could not find '{csv_file}'.")
        sys.exit()
        
    print(f"Success! Loaded {len(levels)} playable anadrome pairs.\n")
    return levels

# ---------------------------------------------------------
# OS-Specific Raw Keyboard Input Handling
# ---------------------------------------------------------
try:
    import msvcrt
    is_windows = True
except ImportError:
    import tty
    import termios
    is_windows = False

def get_keypress():
    """Reads a single keystroke instantly."""
    if is_windows:
        key = msvcrt.getch()
        if key in (b'\x00', b'\xe0'):
            special = msvcrt.getch()
            if special == b'K': return 'left'
            if special == b'M': return 'right'
            if special == b'H': return 'up'
            if special == b'P': return 'down'
            return 'unknown'
        elif key == b'\x08': return 'back'  
        elif key == b'\r': return 'enter'   
        elif key == b'\t': return 'tab'
        elif key == b'\x03': sys.exit()     
        else:
            try: return key.decode('utf-8').lower()
            except: return 'unknown'
    else:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'D': return 'left'
                    if ch3 == 'C': return 'right'
                    if ch3 == 'A': return 'up'
                    if ch3 == 'B': return 'down'
            elif ch == '\x7f' or ch == '\x08': return 'back' 
            elif ch == '\r' or ch == '\n': return 'enter' 
            elif ch == '\t': return 'tab'
            elif ch == '\x03': sys.exit() 
            return ch.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

# ---------------------------------------------------------
# Main Game Loop
# ---------------------------------------------------------
def play_game(levels):
    if not levels:
        print("No valid levels found to play. Exiting.")
        sys.exit()
        
    # Organize levels by difficulty
    by_diff = {
        "Very Easy": [lvl for lvl in levels if lvl.get("difficulty") == "Very Easy"],
        "Easy": [lvl for lvl in levels if lvl.get("difficulty") == "Easy"],
        "Medium": [lvl for lvl in levels if lvl.get("difficulty") == "Medium"],
        "Hard": [lvl for lvl in levels if lvl.get("difficulty") == "Hard"],
        "Very Hard": [lvl for lvl in levels if lvl.get("difficulty") == "Very Hard"],
        "Insane": [lvl for lvl in levels if lvl.get("difficulty") == "Insane"]
    }
    diff_order = ["Very Easy", "Easy", "Medium", "Hard", "Very Hard", "Insane"]
        
    while True: # Outer Loop: Full Game Reset
        score = 0
        skips = 3
        successful_guesses = 0
        lives = 6
        
        # Reset pools and cycling state for new game
        unplayed = {}
        for d in diff_order:
            shuffled_list = list(by_diff[d])
            random.shuffle(shuffled_list)
            unplayed[d] = shuffled_list
            
        current_difficulty_idx = 0
        current_difficulty_count = 0
        
        while True: # Middle Loop: Level Progression
            # Determine which difficulty to play (skip empty ones)
            attempts_diff = 0
            while attempts_diff < 6:
                diff_name = diff_order[current_difficulty_idx]
                if unplayed[diff_name]:
                    break
                else:
                    current_difficulty_idx = (current_difficulty_idx + 1) % 6
                    current_difficulty_count = 0
                    attempts_diff += 1
            
            if attempts_diff == 6:
                # Replenish all pools and shuffle them
                for d in diff_order:
                    shuffled_list = list(by_diff[d])
                    random.shuffle(shuffled_list)
                    unplayed[d] = shuffled_list
                # Try to pick from current index
                diff_name = diff_order[current_difficulty_idx]
                if not unplayed[diff_name]:
                    print("Error: No playable levels found in any difficulty. Exiting.")
                    sys.exit()
            
            # Select the next level (pop the first element to preserve CSV order)
            current_level = unplayed[diff_name].pop(0)
            word1 = current_level["w1"]
            word2 = current_level["w2"]
            length = len(word1)
            
            # Display information
            display_count = current_difficulty_count + 1
            
            grid = {1: [None] * length, 2: [None] * length}
            active_row = 1
            active_col = 0
            
            message = ""
            game_over = False
            
            while True: # Inner Loop: Active Typing Gameplay
                clear_screen()
                print("=== ANADROME: THE GAME ===")
                diff_label = diff_name.upper()
                print(f"🏆 Score: {score}  |  ⏭️  Skips: {skips}/3  |  ❤️  Lives: {lives}/6")
                print(f"🌟 Difficulty: {diff_label}  |  📊 Tier Progress: {display_count}/5")
                print("-" * 60)
                print(f"Hint 1: {current_level['d1']}")
                print(f"Hint 2: {current_level['d2']}")
                print("-" * 60)
                
                # Render the grid
                for r in [1, 2]:
                    row_str = []
                    for c in range(length):
                        char = grid[r][c]
                        display_char = char if char else "_"
                        
                        if r == active_row and c == active_col:
                            row_str.append(f"[{display_char}]")
                        else:
                            row_str.append(f" {display_char} ")
                    
                    prefix = "Row 1 -> " if r == 1 else "Row 2 -> "
                    print(prefix + "".join(row_str))
                    
                print("-" * 60)
                
                if message:
                    print(f" > {message} < \n")
                else:
                    print("\n")
                    
                print("CONTROLS: Type letters | Arrows move/switch rows | Tab to Skip | Enter Submit | Esc to exit")
                
                cmd = get_keypress()
                message = "" 
                mirror_row = 2 if active_row == 1 else 1
                
                if cmd == '\x1b': 
                    clear_screen()
                    print(f"Thanks for playing! Final Score: {score}")
                    sys.exit() 
                    
                elif cmd in ('up', 'down'):
                    active_row = mirror_row
                    active_col = min(active_col, length - 1)
                    
                elif cmd == 'left':
                    if active_col > 0: active_col -= 1
                    
                elif cmd == 'right':
                    if active_col < length - 1: active_col += 1
                    
                elif cmd == 'back':
                    if grid[active_row][active_col] is not None:
                        grid[active_row][active_col] = None
                        grid[mirror_row][length - 1 - active_col] = None
                    else:
                        if active_col > 0:
                            active_col -= 1
                            grid[active_row][active_col] = None
                            grid[mirror_row][length - 1 - active_col] = None
                            
                elif cmd == 'tab':
                    if skips > 0:
                        skips -= 1
                        clear_screen()
                        print("=" * 60)
                        print("⏭️  LEVEL SKIPPED  ⏭️")
                        print(f"The words were: {word1} & {word2}")
                        print(f"Skips remaining: {skips}/3")
                        print("=" * 60)
                        print("\nPress ANY KEY to continue to the next level...")
                        get_keypress()
                        break 
                    else:
                        message = "⚠️ No skips remaining!"
                            
                elif cmd == 'enter':
                    current_w1 = "".join([c for c in grid[1] if c])
                    current_w2 = "".join([c for c in grid[2] if c])
                    
                    if len(current_w1) < length:
                        message = "⚠️ Please fill all letters before submitting!"
                    elif current_w1 == word1 and current_w2 == word2:
                        difficulty_points = {
                            "Very Easy": 100,
                            "Easy": 200,
                            "Medium": 300,
                            "Hard": 400,
                            "Very Hard": 500,
                            "Insane": 600
                        }
                        points_earned = difficulty_points.get(diff_name, 100)
                        score += points_earned
                        successful_guesses += 1
                        
                        skip_msg = ""
                        if successful_guesses % 3 == 0:
                            if skips < 3:
                                skips += 1
                                skip_msg = "\n🌟 AWESOME! You earned +1 Skip for 3 successful guesses! 🌟"
                            else:
                                skip_msg = "\n(3 successful guesses! Skip slots are currently full.)"

                        clear_screen()
                        print("=" * 60)
                        print(f"🎉 CORRECT! 🎉")
                        print(f"The words were: {word1} & {word2}")
                        print(f"+{points_earned} Points! (Total Score: {score})")
                        if skip_msg:
                            print(skip_msg)
                        print("=" * 60)
                        print("\nPress ANY KEY to play the next level...")
                        get_keypress() 
                        break 
                    else:
                        lives -= 1
                        if lives <= 0:
                            clear_screen()
                            print("=" * 60)
                            print("💀 GAME OVER 💀")
                            print("Out of lives!")
                            print(f"The correct words were: {word1} & {word2}")
                            print(f"Final Score: {score}")
                            print("=" * 60)
                            print("\nPlay Again? (Y/N)")
                            
                            while True:
                                retry_cmd = get_keypress()
                                if retry_cmd == 'y':
                                    game_over = True
                                    break
                                elif retry_cmd == 'n' or retry_cmd == '\x1b':
                                    clear_screen()
                                    print(f"Thanks for playing! Final Score: {score}")
                                    sys.exit()
                            break
                        else:
                            message = f"❌ Incorrect! {lives} lives remaining."
                            
                elif len(cmd) == 1 and cmd.isalpha():
                    char = cmd.upper()
                    grid[active_row][active_col] = char
                    grid[mirror_row][length - 1 - active_col] = char
                    
                    if active_col < length - 1:
                        active_col += 1

            if game_over:
                break 
                
            current_difficulty_count += 1
            if current_difficulty_count >= 5:
                current_difficulty_idx = (current_difficulty_idx + 1) % 6
                current_difficulty_count = 0 

# ==========================================
# Execution Block
# ==========================================
if __name__ == "__main__":
    CSV_FILE = 'anadromes_ranked.csv'
    JSON_FILE = 'raw_dictionary_data_scowl70.json'
    
    loaded_levels = load_game_data(CSV_FILE, JSON_FILE)
    play_game(loaded_levels)