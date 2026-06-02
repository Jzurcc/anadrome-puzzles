import os
import sys
import random
import json
import csv
import re
import time

from rich.console import Console, Group
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.align import Align
from rich import box

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8') 

console = Console()
USE_FIRST_DEFINITION = True

# Difficulty tier color themes
DIFF_COLORS = {
    "Very Easy": "cyan",
    "Easy":      "green",
    "Medium":    "yellow",
    "Hard":      "dark_orange",
    "Very Hard": "red",
    "Insane":    "magenta",
}

# Definition filtering and scoring system
def score_definition(word, defn, tags, pos):
    word_lower = word.lower()
    score = 100
    
    pattern_word = re.compile(r'\b' + re.escape(word_lower) + r'\b', re.IGNORECASE)
    if pattern_word.search(defn):
        score -= 200
        
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
            
    severe_tags = {'obsolete', 'archaic', 'dialectal', 'rare', 'nonstandard', 'vulgar', 'clipping'}
    moderate_tags = {'slang', 'informal', 'abbreviation', 'dated', 'colloquial', 'regional', 'error'}
    
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower in severe_tags:
            score -= 80
        elif tag_lower in moderate_tags:
            score -= 40
            
    words_count = len(defn.split())
    if words_count <= 2:
        score -= 30
    elif words_count > 30:
        score -= 10
        
    preferred_pos = {'noun', 'verb', 'adjective'}
    if pos.lower() not in preferred_pos:
        score -= 20
        
    return score


def sanitize_definition(defn, word):
    word_lower = word.lower()
    pattern = re.compile(r'\b' + re.escape(word_lower) + r'\b', re.IGNORECASE)
    return pattern.sub("[word]", defn)


# High score persistence
def get_save_path():
    # Save next to the executable when packaged, or in the script dir during dev
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "anadromes_save.json")

def load_high_score():
    path = get_save_path()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("high_score", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        return 0

def save_high_score(score):
    path = get_save_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({"high_score": score}, f)
    except Exception:
        pass


# Data loading
def load_game_data(csv_file, json_file):
    console.print(Panel("[bold cyan]Loading game data... Please wait.[/bold cyan]", border_style="cyan", expand=False))
    levels = []
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            dict_data = json.load(f)
    except FileNotFoundError:
        console.print(f"[red]Error: Could not find '{json_file}'.[/red]")
        sys.exit()

    def get_best_definition(word):
        word_lower = word.lower()
        if word_lower not in dict_data: return None
        entries = dict_data[word_lower].get("entries", [])
        if not entries: return None
            
        if USE_FIRST_DEFINITION:
            first_defn = None
            for entry in entries:
                senses = entry.get("senses", [])
                for sense in senses:
                    defn = sense.get("definition", "")
                    if defn:
                        first_defn = defn
                        break
                if first_defn: break
            if not first_defn: return None
            return sanitize_definition(first_defn, word_lower)
            
        scored_senses = []
        for entry in entries:
            pos = entry.get("partOfSpeech", "Unknown")
            for sense in entry.get("senses", []):
                defn = sense.get("definition", "")
                if defn:
                    score = score_definition(word_lower, defn, sense.get("tags", []), pos)
                    scored_senses.append((defn, score))
        if not scored_senses: return None
        scored_senses.sort(key=lambda x: x[1], reverse=True)
        return sanitize_definition(scored_senses[0][0], word_lower)

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None) 
            for row in reader:
                if len(row) >= 2:
                    w1, w2 = row[0].strip().lower(), row[1].strip().lower()
                    diff_class = row[4].strip().title() if len(row) >= 5 else "Easy"
                    d1, d2 = get_best_definition(w1), get_best_definition(w2)
                    if d1 and d2:
                        levels.append({"w1": w1.upper(), "w2": w2.upper(), "d1": d1, "d2": d2, "difficulty": diff_class})
    except FileNotFoundError:
        console.print(f"[red]Error: Could not find '{csv_file}'.[/red]")
        sys.exit()
        
    console.print(Panel(f"[bold green]Success! Loaded {len(levels)} playable anadrome pairs.[/bold green]", expand=False))
    time.sleep(1)
    return levels

# OS-specific raw keyboard input handling
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
            elif ch in ('\x7f', '\x08'): return 'back' 
            elif ch in ('\r', '\n'): return 'enter' 
            elif ch == '\t': return 'tab'
            elif ch == '\x03': sys.exit() 
            return ch.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


# UI rendering functions (using Rich)
def show_title_screen(high_score=0):
    title_art = """[bold magenta]

░█████╗░███╗░░██╗░█████╗░██████╗░██████╗░░█████╗░███╗░░░███╗███████╗░██████╗
██╔══██╗████╗░██║██╔══██╗██╔══██╗██╔══██╗██╔══██╗████╗░████║██╔════╝██╔════╝
███████║██╔██╗██║███████║██║░░██║██████╔╝██║░░██║██╔████╔██║█████╗░░╚█████╗░
██╔══██║██║╚████║██╔══██║██║░░██║██╔══██╗██║░░██║██║╚██╔╝██║██╔══╝░░░╚═══██╗
██║░░██║██║░╚███║██║░░██║██████╔╝██║░░██║╚█████╔╝██║░╚═╝░██║███████╗██████╔╝
╚═╝░░╚═╝╚═╝░░╚══╝╚═╝░░╚═╝╚═════╝░╚═╝░░╚═╝░╚════╝░╚═╝░░░░░╚═╝╚══════╝╚═════╝░
[/bold magenta]"""
    
    options = ["Play", "Tutorial", "Exit"]
    selected_index = 0
    
    while True:
        clear_screen()
        console.print(title_art, justify="center")
        console.print("\n")
        
        if high_score > 0:
            console.print(f"[bold yellow]✦ Best Score: {high_score:,}[/bold yellow]", justify="center")
            console.print("\n")
        
        for i, option in enumerate(options):
            if i == selected_index:
                console.print(f"[bold cyan]> [ {option} ] <[/bold cyan]", justify="center")
            else:
                console.print(f"[dim]  [ {option} ]  [/dim]", justify="center")
                
        cmd = get_keypress()
        if cmd == 'up':
            selected_index = (selected_index - 1) % len(options)
        elif cmd == 'down':
            selected_index = (selected_index + 1) % len(options)
        elif cmd == 'enter':
            return options[selected_index].lower()

def show_tutorial_screen():
    segments = [
        (
            "[bold cyan]How to Play:[/bold cyan]\n"
            "Anadromes are words that form different words when reversed.\n"
            "For example, the word [bold yellow]\"DOG\"[/bold yellow] is formed by reversing the word [bold yellow]\"GOD\"[/bold yellow]."
        ),
        (
            "[bold cyan]Gameplay:[/bold cyan]\n"
            "You will be given two dictionary definitions.\n"
            "Type the word that matches the first definition in Row 1.\n"
            "Its anadrome will automatically be typed in Row 2."
        ),
        (
            "[bold yellow]Progression & Scoring:[/bold yellow]\n"
            "You start with 6 Skips (►) and 3 Lives (♥).\n"
            "Earn +1 Skip every 5 wins, and +1 Life every 10 wins.\n"
            "Chain correct answers to build a Streak for bonus multipliers!\n"
            "Press [.] to reveal a hint letter (costs 50% of round points).\n"
            "Difficulties range from [green]Very Easy[/green] to [bold red]Insane[/bold red].\n"
            "Harder difficulties award more points. Good luck!"
        )
    ]
    
    for i, text in enumerate(segments):
        clear_screen()
        if i == len(segments) - 1:
            panel_text = text + "\n\n[dim]Press any key to return to the title screen...[/dim]"
        else:
            panel_text = text + f"\n\n[dim]Press any key to continue... ({i+1}/{len(segments)})[/dim]"
            
        console.print(Panel(panel_text, title="[bold magenta]TUTORIAL[/bold magenta]", border_style="cyan"))
        get_keypress()

def get_streak_multiplier(streak):
    if streak >= 50: return 10.0
    if streak >= 30: return 5.0
    if streak >= 20: return 4.0
    if streak >= 10: return 3.0
    if streak >= 5:  return 2.0
    if streak >= 3:  return 1.5
    return 1.0

def get_streak_label(streak):
    mult = get_streak_multiplier(streak)
    if streak >= 50: return f"[bold white on red]🔥 ULTIMATE STREAK x{streak} ({mult}x) 🔥[/bold white on red]"
    if streak >= 30: return f"[bold magenta]✦ MEGA STREAK x{streak} ({mult}x) ✦[/bold magenta]"
    if streak >= 20: return f"[bold blue]✦ ULTRA STREAK x{streak} ({mult}x) ✦[/bold blue]"
    if streak >= 10: return f"[bold red]✦ STREAK x{streak} ({mult}x) ✦[/bold red]"
    if streak >= 5:  return f"[bold dark_orange]✦ STREAK x{streak} ({mult}x)[/bold dark_orange]"
    if streak >= 3:  return f"[bold yellow]✦ STREAK x{streak} ({mult}x)[/bold yellow]"
    if streak >= 1:  return f"[cyan]Streak: {streak} ({mult}x)[/cyan]"
    return ""

def create_ui(score, skips, lives, diff_name, progress, current_level, grid, length,
              active_row, active_col, message, status="neutral", level=1, wins=0,
              streak=0, hint_used=False):
    
    tier_color = DIFF_COLORS.get(diff_name, "cyan")
    
    # Header
    header_text = Text()
    header_text.append("=== ANADROME PUZZLES ===\n", style="bold magenta")
    header_text.append(f"♦ Score: ", style="bold")
    header_text.append(f"{score:,}", style="cyan")
    
    heart_str = "♥" * lives + "♡" * (3 - lives)
    skip_str = "►" * skips + "▹" * (6 - skips)
    
    header_text.append("  |  Lives: ")
    header_text.append(heart_str)
    header_text.append("  |  Skips: ")
    header_text.append(skip_str)
    
    streak_label = get_streak_label(streak)
    header_text.append(f"\n✦ Tier: {diff_name} ({progress})  |  Level: {level}  |  Wins: {wins}", style="yellow")
    if streak_label:
        header_text.append("  |  ", style="yellow")
        header_text.append(Text.from_markup(streak_label))
    header_panel = Panel(Align.center(header_text), box=box.ROUNDED, style=tier_color)
    
    # Hints Panel
    hints_text = Text()
    hints_text.append("Row 1 Hint: ", style="bold green")
    hints_text.append(f"{current_level['d1']}\n\n")
    hints_text.append("Row 2 Hint: ", style="bold yellow")
    hints_text.append(f"{current_level['d2']}")
    hints_panel = Panel(hints_text, title="Dictionary Definitions", border_style="blue")
    
    # Game Board
    board_text = Text()
    
    border_style = tier_color
    if status == "error":
        border_style = "bold red"
    elif status == "success":
        border_style = "bold green"
        
    for r in [1, 2]:
        row_str = Text()
        row_str.append(f"Row {r}  ", style="dim")
        for c in range(length):
            char = grid[r][c]
            display_char = char if char else "_"
            
            # Mark hinted cells differently
            is_hinted = hint_used and char is not None and grid[r][c] == char
            
            if r == active_row and c == active_col:
                if status == "neutral":
                    row_str.append(f"[ {display_char} ]", style="reverse bold cyan")
                else:
                    row_str.append(f"[ {display_char} ]", style=f"reverse {border_style}")
            else:
                row_str.append(f"  {display_char}  ", style="bold")
        
        board_text.append(row_str)
        if r == 1:
            board_text.append("\n\n")
            
    hint_title = "The Board" + ("  [dim][. used][/dim]" if hint_used else "  [dim][.] Hint[/dim]")
    board_panel = Panel(Align.center(board_text), title=hint_title, border_style=border_style, padding=(1, 2))
    
    # Footer
    footer_text = Text()
    if message:
        footer_text.append(f"{message}\n", style=border_style)
    footer_text.append("CONTROLS: [A-Z] Type | [ARROWS] Move | [.] Hint | [TAB] Skip | [ENTER] Submit | [ESC] Exit", style="dim")
    footer_panel = Panel(Align.center(footer_text), box=box.MINIMAL)
    
    return Align.center(
        Panel(
            Group(
                header_panel,
                board_panel,
                hints_panel,
                footer_panel
            ),
            box=box.MINIMAL
        )
    )

def show_educational_debrief(level, status="win", points=0, earned_skip=False,
                              earned_life=False, streak=0, multiplier=1.0):
    clear_screen()
    
    w1, w2 = level["w1"], level["w2"]
    d1, d2 = level["d1"], level["d2"]
    
    title_text = ""
    color = "white"
    if status == "win":
        base_pts = int(points / multiplier)
        if multiplier > 1.0:
            title_text = f"✦ CORRECT! {base_pts} × {multiplier:.1f} = +{points} Points ✦"
        else:
            title_text = f"✦ CORRECT! +{points} Points ✦"
        if earned_life:
            title_text += " [ +1 ♥ ]"
        elif earned_skip:
            title_text += " [ +1 ► ]"
        if streak >= 3:
            title_text += f"  [ {streak} STREAK! ]"
        color = "green"
    elif status == "lose":
        title_text = "[X] OUT OF LIVES! The words were... [X]"
        color = "red"
    elif status == "skip":
        title_text = "► LEVEL SKIPPED! The words were... ►"
        color = "yellow"
        
    text = Text()
    text.append(f"\n{w1}\n", style=f"bold {color}")
    text.append(f"{d1}\n\n", style="italic")
    text.append(f"{w2}\n", style=f"bold {color}")
    text.append(f"{d2}\n", style="italic")
    
    panel = Panel(Align.center(text), title=title_text, border_style=color, box=box.DOUBLE)
    console.print(panel)
    
    console.print(Align.center("\n[dim]Press ANY KEY to continue...[/dim]"))
    get_keypress()

def show_tier_unlock(tier_name):
    clear_screen()
    tier_color = DIFF_COLORS.get(tier_name, "cyan")
    
    text = Text(justify="center")
    text.append("\n\n")
    text.append("✦ TIER UNLOCKED ✦\n", style=f"bold {tier_color}")
    text.append(f"\n{tier_name.upper()}\n", style=f"bold white on {tier_color}")
    text.append("\n\nYou've reached a new difficulty!\n", style="dim")
    
    console.print(Panel(Align.center(text), border_style=tier_color, box=box.DOUBLE, padding=(1, 4)))
    time.sleep(0.2)
    console.print(Align.center(f"[dim]Press any key to continue...[/dim]"))
    get_keypress()

def show_game_over_summary(score, high_score, successful_guesses, total_played,
                            best_streak, best_diff, diff_order):
    clear_screen()
    
    accuracy = int((successful_guesses / total_played) * 100) if total_played > 0 else 0
    
    # Letter grade based on score and accuracy
    if accuracy >= 90 and best_streak >= 10:
        grade = "S"
        grade_color = "bold magenta"
    elif accuracy >= 75 and successful_guesses >= 20:
        grade = "A"
        grade_color = "bold green"
    elif accuracy >= 60:
        grade = "B"
        grade_color = "bold yellow"
    elif accuracy >= 40:
        grade = "C"
        grade_color = "bold dark_orange"
    else:
        grade = "D"
        grade_color = "bold red"
    
    is_new_best = score > high_score
    
    text = Text(justify="center")
    text.append("\n")
    text.append(f"Grade: ", style="bold")
    text.append(f"{grade}\n\n", style=grade_color)
    
    if is_new_best:
        text.append("★ NEW HIGH SCORE! ★\n", style="bold yellow")
    
    text.append(f"Score:        {score:>8,}\n", style="cyan")
    text.append(f"Best ever:    {max(score, high_score):>8,}\n", style="yellow")
    text.append(f"Words solved: {successful_guesses:>8}\n")
    text.append(f"Accuracy:     {accuracy:>7}%\n")
    text.append(f"Best streak:  {best_streak:>8}\n")
    text.append(f"Highest tier: {best_diff:>8}\n")
    
    title = "[bold red]GAME OVER[/bold red]"
    border = "magenta" if is_new_best else "red"
    console.print(Panel(Align.center(text), title=title, border_style=border, box=box.DOUBLE))
    console.print(Align.center("\n[dim]Play Again? (Y/N)[/dim]"))

def shake_error(score, skips, lives, diff_name, progress, current_level, grid,
                length, active_row, active_col, level, wins, streak):
    # Quick visual flicker to sell the wrong-answer sting
    for _ in range(3):
        clear_screen()
        console.print(create_ui(score, skips, lives, diff_name, progress, current_level,
                                grid, length, active_row, active_col,
                                "[X] Incorrect!", "error", level, wins, streak))
        time.sleep(0.07)
        clear_screen()
        console.print(create_ui(score, skips, lives, diff_name, progress, current_level,
                                grid, length, active_row, active_col,
                                "", "neutral", level, wins, streak))
        time.sleep(0.05)


# Main game loop
def play_game(levels, high_score=0):
    if not levels:
        console.print("[red]No valid levels found to play. Exiting.[/red]")
        sys.exit()
        
    by_diff = {
        "Very Easy": [lvl for lvl in levels if lvl.get("difficulty") == "Very Easy"],
        "Easy":      [lvl for lvl in levels if lvl.get("difficulty") == "Easy"],
        "Medium":    [lvl for lvl in levels if lvl.get("difficulty") == "Medium"],
        "Hard":      [lvl for lvl in levels if lvl.get("difficulty") == "Hard"],
        "Very Hard":  [lvl for lvl in levels if lvl.get("difficulty") == "Very Hard"],
        "Insane":    [lvl for lvl in levels if lvl.get("difficulty") == "Insane"],
    }
    diff_order = ["Very Easy", "Easy", "Medium", "Hard", "Very Hard", "Insane"]
        
    while True: 
        score = 0
        skips = 6
        successful_guesses = 0
        total_levels_played = 0
        lives = 3
        streak = 0
        best_streak = 0
        best_diff_idx = 0
        
        unplayed = {}
        for d in diff_order:
            shuffled_list = list(by_diff[d])
            random.shuffle(shuffled_list)
            unplayed[d] = shuffled_list
            
        current_difficulty_idx = 0
        prev_difficulty_idx = 0

        while True:
            # Ensure base difficulty tier contains unplayed words, recycling pools if all depleted
            attempts_diff = 0
            while attempts_diff < 6:
                diff_name = diff_order[current_difficulty_idx]
                if unplayed[diff_name]: 
                    break
                else:
                    current_difficulty_idx = (current_difficulty_idx + 1) % 6
                    attempts_diff += 1
            
            if attempts_diff == 6:
                for d in diff_order:
                    shuffled_list = list(by_diff[d])
                    random.shuffle(shuffled_list)
                    unplayed[d] = shuffled_list
                diff_name = diff_order[current_difficulty_idx]
                if not unplayed[diff_name]:
                    console.print("[red]Error: No playable levels found. Exiting.[/red]")
                    sys.exit()

            # Show tier unlock screen when the base difficulty advances
            if current_difficulty_idx > prev_difficulty_idx:
                show_tier_unlock(diff_order[current_difficulty_idx])
            prev_difficulty_idx = current_difficulty_idx

            # Dynamic difficulty scaling selection
            level_num = total_levels_played + 1
            chosen_diff_idx = None
            
            if level_num % 5 == 0:
                # Guaranteed next harder difficulty that has unfinished words
                for idx in range(current_difficulty_idx + 1, len(diff_order)):
                    if unplayed[diff_order[idx]]:
                        chosen_diff_idx = idx
                        break
                if chosen_diff_idx is None:
                    chosen_diff_idx = current_difficulty_idx
            else:
                # Small upscale chance to next hardest or second next hardest, scaling per win
                upscale_chance = min(0.30, 0.03 + 0.005 * successful_guesses)
                if random.random() < upscale_chance:
                    next_idx = current_difficulty_idx + 1
                    second_idx = current_difficulty_idx + 2
                    
                    next_ok = next_idx < len(diff_order) and bool(unplayed[diff_order[next_idx]])
                    second_ok = second_idx < len(diff_order) and bool(unplayed[diff_order[second_idx]])
                    
                    if next_ok and second_ok:
                        chosen_diff_idx = second_idx if random.random() < 0.30 else next_idx
                    elif next_ok:
                        chosen_diff_idx = next_idx
                    elif second_ok:
                        chosen_diff_idx = second_idx
                    else:
                        chosen_diff_idx = current_difficulty_idx
                else:
                    chosen_diff_idx = current_difficulty_idx
            
            chosen_diff_name = diff_order[chosen_diff_idx]
            current_level = unplayed[chosen_diff_name].pop(0)
            
            if chosen_diff_idx > best_diff_idx:
                best_diff_idx = chosen_diff_idx

            word1, word2 = current_level["w1"], current_level["w2"]
            length = len(word1)
            
            tier_total = len(by_diff[chosen_diff_name])
            tier_done = tier_total - len(unplayed[chosen_diff_name])
            progress = f"{tier_done}/{tier_total}"
            
            diff_name = chosen_diff_name
            
            grid = {1: [None] * length, 2: [None] * length}
            active_row = 1
            active_col = 0
            
            message = ""
            status = "neutral"
            game_over = False
            hint_used = False
            hint_positions = set()  # tracks which (row, col) pairs were revealed by hint
            
            while True: 
                clear_screen()
                console.print(create_ui(score, skips, lives, diff_name, progress, current_level,
                                        grid, length, active_row, active_col, message, status,
                                        total_levels_played + 1, successful_guesses, streak, hint_used))
                
                status = "neutral" 
                
                cmd = get_keypress()
                message = "" 
                mirror_row = 2 if active_row == 1 else 1
                
                if cmd == '\x1b': 
                    clear_screen()
                    console.print(f"[bold magenta]Thanks for playing! Final Score: {score:,}[/bold magenta]")
                    time.sleep(1.5)
                    return
                    
                elif cmd in ('up', 'down'):
                    active_row = mirror_row
                    active_col = min(active_col, length - 1)
                    
                elif cmd == 'left':
                    if active_col > 0: active_col -= 1
                    
                elif cmd == 'right':
                    if active_col < length - 1: active_col += 1
                    
                elif cmd == 'back':
                    if grid[active_row][active_col] is not None:
                        # Don't erase hinted cells
                        if (active_row, active_col) not in hint_positions:
                            grid[active_row][active_col] = None
                            grid[mirror_row][length - 1 - active_col] = None
                    else:
                        if active_col > 0:
                            active_col -= 1
                            if (active_row, active_col) not in hint_positions:
                                grid[active_row][active_col] = None
                                grid[mirror_row][length - 1 - active_col] = None

                elif cmd == '.' and not hint_used:
                    # Reveal one random unfilled letter from row 1
                    empty_cols = [c for c in range(length) if grid[1][c] is None]
                    if empty_cols:
                        hc = random.choice(empty_cols)
                        grid[1][hc] = word1[hc]
                        grid[2][length - 1 - hc] = word2[length - 1 - hc]
                        hint_positions.add((1, hc))
                        hint_positions.add((2, length - 1 - hc))
                        hint_used = True
                        message = "[dim]Hint used — round points halved.[/dim]"
                    else:
                        message = "[dim]No empty cells to reveal.[/dim]"
                    status = "neutral"
                        
                elif cmd == 'tab':
                    if skips > 0:
                        skips -= 1
                        streak = 0
                        total_levels_played += 1
                        show_educational_debrief(current_level, "skip")
                        break 
                    else:
                        message = "[!] No skips remaining!"
                        status = "error"
                            
                elif cmd == 'enter':
                    current_w1 = "".join([c for c in grid[1] if c])
                    current_w2 = "".join([c for c in grid[2] if c])
                    
                    if len(current_w1) < length:
                        message = "[!] Please fill all letters before submitting!"
                        status = "error"
                    else:
                        if current_w1 == word1 and current_w2 == word2:
                            pts_base = {"Very Easy": 100, "Easy": 200, "Medium": 300,
                                        "Hard": 400, "Very Hard": 500, "Insane": 600}
                            base_pts = pts_base.get(diff_name, 100)
                            if hint_used:
                                base_pts = base_pts // 2
                            
                            streak += 1
                            if streak > best_streak:
                                best_streak = streak
                            
                            multiplier = get_streak_multiplier(streak)
                            points_earned = int(base_pts * multiplier)
                            score += points_earned
                            successful_guesses += 1
                            
                            total_levels_played += 1
                            
                            earned_skip = False
                            earned_life = False
                            
                            if successful_guesses % 5 == 0 and skips < 6:
                                skips += 1
                                earned_skip = True
                                
                            if successful_guesses % 10 == 0 and lives < 3:
                                lives += 1
                                earned_life = True
                            
                            # Reward feedback flash
                            clear_screen()
                            console.print(create_ui(score, skips, lives, diff_name, progress, current_level,
                                                    grid, length, active_row, active_col, "Correct!",
                                                    "success", total_levels_played, successful_guesses,
                                                    streak, hint_used))
                            time.sleep(0.6)
                            
                            show_educational_debrief(current_level, "win", points_earned,
                                                     earned_skip, earned_life, streak, multiplier)
                            break 
                        else:
                            streak = 0
                            lives -= 1
                            
                            shake_error(score, skips, lives, diff_name, progress, current_level,
                                        grid, length, active_row, active_col,
                                        total_levels_played + 1, successful_guesses, streak)
                            
                            if lives <= 0:
                                total_levels_played += 1
                                show_educational_debrief(current_level, "lose")
                                
                                # Save high score before showing summary
                                new_high = max(score, high_score)
                                if score > high_score:
                                    save_high_score(score)
                                    high_score = score
                                
                                show_game_over_summary(score, high_score, successful_guesses,
                                                       total_levels_played, best_streak,
                                                       diff_order[best_diff_idx], diff_order)
                                
                                while True:
                                    retry = get_keypress()
                                    if retry == 'y':
                                        game_over = True
                                        break
                                    elif retry in ('n', '\x1b'):
                                        clear_screen()
                                        console.print(f"[bold magenta]Thanks for playing! Final Score: {score:,}[/bold magenta]")
                                        time.sleep(1.5)
                                        return
                                break
                            else:
                                message = f"[X] Incorrect! You lost a heart."
                                status = "error"
                                
                elif len(cmd) == 1 and cmd.isalpha():
                    char = cmd.upper()
                    # Don't overwrite hinted cells
                    if (active_row, active_col) not in hint_positions:
                        grid[active_row][active_col] = char
                        grid[mirror_row][length - 1 - active_col] = char
                    
                    if active_col < length - 1:
                        active_col += 1

            if game_over:
                break 


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    CSV_FILE = resource_path('anadromes_ranked_clean.csv')
    JSON_FILE = resource_path('dictionary_pruned.json')  
    
    loaded_levels = load_game_data(CSV_FILE, JSON_FILE)
    high_score = load_high_score()
    
    while True:
        choice = show_title_screen(high_score)
        if choice == "play":
            play_game(loaded_levels, high_score)
            # Reload in case it changed during play
            high_score = load_high_score()
        elif choice == "tutorial":
            show_tutorial_screen()
        elif choice == "exit":
            clear_screen()
            sys.exit()