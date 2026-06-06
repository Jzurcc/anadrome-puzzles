import os
import sys
import random
import json
import csv
import re
import time
import shutil

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

# Level-select group configuration
GROUP_SIZE = 20

GROUP_NAMES = [
    "Dawn",    "Tide",    "Grove",   "Breeze",  "Mosaic",
    "Wander",  "Mist",    "Gloam",   "Tangle",  "Veil",
    "Hollow",  "Thorn",   "Cipher",  "Dusk",    "Marrow",
    "Abyss",   "Rune",    "Hex",     "Enigma",
]

GROUP_COLORS = [
    "bright_cyan",   # Dawn
    "cyan",          # Tide
    "bright_green",  # Grove
    "green",         # Breeze
    "chartreuse3",   # Mosaic
    "yellow",        # Wander
    "gold1",         # Mist
    "dark_orange",   # Gloam
    "orange_red1",   # Tangle
    "red",           # Veil
    "bright_red",    # Hollow
    "dark_red",      # Thorn
    "magenta",       # Cipher
    "medium_purple1",# Dusk
    "purple",        # Marrow
    "blue_violet",   # Abyss
    "dark_blue",     # Rune
    "grey50",        # Hex
    "white",         # Enigma
]

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

def load_high_scores():
    path = get_save_path()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            old_hs = data.get("high_score", 0)
            compact_hs = data.get("compact_high_score", 0)
            extensive_hs = data.get("extensive_high_score", old_hs)
            level_progress = data.get("level_progress", {})
            unlocked_words = data.get("unlocked_words", [])
            return {"compact": compact_hs, "extensive": extensive_hs, "level_progress": level_progress, "unlocked_words": unlocked_words}
    except (FileNotFoundError, json.JSONDecodeError):
        return {"compact": 0, "extensive": 0, "level_progress": {}, "unlocked_words": []}

def load_high_score(mode="extensive"):
    scores = load_high_scores()
    return scores.get(mode, 0)

def save_high_score(score, mode):
    path = get_save_path()
    scores = load_high_scores()
    scores[mode] = max(scores.get(mode, 0), score)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                "compact_high_score": scores["compact"],
                "extensive_high_score": scores["extensive"],
                "level_progress": scores["level_progress"],
                "unlocked_words": scores["unlocked_words"]
            }, f)
    except Exception:
        pass

def save_level_progress(level_progress):
    path = get_save_path()
    scores = load_high_scores()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                "compact_high_score": scores["compact"],
                "extensive_high_score": scores["extensive"],
                "level_progress": level_progress,
                "unlocked_words": scores["unlocked_words"]
            }, f)
    except Exception:
        pass

def save_unlocked_words(w1, w2):
    path = get_save_path()
    scores = load_high_scores()
    unlocked = set(scores.get("unlocked_words", []))
    w1_low = w1.lower()
    w2_low = w2.lower()
    
    if w1_low in unlocked and w2_low in unlocked:
        return
        
    unlocked.add(w1_low)
    unlocked.add(w2_low)
    scores["unlocked_words"] = list(unlocked)
    
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                "compact_high_score": scores["compact"],
                "extensive_high_score": scores["extensive"],
                "level_progress": scores["level_progress"],
                "unlocked_words": scores["unlocked_words"]
            }, f)
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
            
        scored_senses = []
        for entry in entries:
            pos = entry.get("partOfSpeech", "Unknown")
            for sense in entry.get("senses", []):
                defn = sense.get("definition", "")
                if defn:
                    score = score_definition(word_lower, defn, sense.get("tags", []), pos)
                    scored_senses.append((sense, pos, score))
                    
        if not scored_senses: return None
        
        if not USE_FIRST_DEFINITION:
            scored_senses.sort(key=lambda x: x[2], reverse=True)
            
        best_sense, best_pos, _ = scored_senses[0]
        
        defn = sanitize_definition(best_sense.get("definition", ""), word_lower)
        synonyms = best_sense.get("synonyms", [])
        examples = best_sense.get("examples", [])
        quotes = best_sense.get("quotes", [])
        
        example = examples[0] if examples else None
        
        quote = None
        if quotes:
            q = random.choice(quotes)
            quote = {
                "text": q.get("text", ""),
                "reference": q.get("reference", "")
            }
            
        return {
            "pos": best_pos.capitalize() if best_pos else "Unknown",
            "definition": defn,
            "synonyms": synonyms[:3],
            "example": example,
            "quote": quote
        }

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None) 
            for row in reader:
                if len(row) >= 2:
                    w1, w2 = row[0].strip().lower(), row[1].strip().lower()
                    diff_class = row[4].strip().title() if len(row) >= 5 else "Easy"
                    theme = row[5].strip() if len(row) >= 6 else "General"
                    meta1, meta2 = get_best_definition(w1), get_best_definition(w2)
                    if meta1 and meta2:
                        levels.append({
                            "w1": w1.upper(), "w2": w2.upper(), 
                            "d1": meta1["definition"], "d2": meta2["definition"],
                            "pos1": meta1["pos"], "pos2": meta2["pos"],
                            "synonyms1": meta1["synonyms"], "synonyms2": meta2["synonyms"],
                            "example1": meta1["example"], "example2": meta2["example"],
                            "quote1": meta1["quote"], "quote2": meta2["quote"],
                            "difficulty": diff_class,
                            "theme": theme
                        })
    except FileNotFoundError:
        console.print(f"[red]Error: Could not find '{csv_file}'.[/red]")
        sys.exit()
        
    console.print(Panel(f"[bold green]Success! Loaded {len(levels)} playable anadrome pairs.[/bold green]", expand=False))
    time.sleep(1)
    return levels

def load_groups(csv_file, json_file):
    console.print(Panel("[bold cyan]Loading level groups... Please wait.[/bold cyan]", border_style="cyan", expand=False))
    
    levels = load_game_data(csv_file, json_file)
    
    themes_map = {}
    for lvl in levels:
        t = lvl.get("theme", "General")
        if t not in themes_map:
            themes_map[t] = []
        themes_map[t].append(lvl)
        
    themes_ordered = sorted(themes_map.keys())
    theme_groups = [themes_map[t] for t in themes_ordered]
    
    orig_groups = []
    for i in range(0, len(levels), GROUP_SIZE):
        orig_groups.append(levels[i:i+GROUP_SIZE])
    orig_names = GROUP_NAMES[:len(orig_groups)]
    
    return theme_groups, themes_ordered, orig_groups, orig_names

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
def show_title_screen(compact_hs=0, extensive_hs=0):
    title_art = """[bold magenta]
░█████╗░███╗░░██╗░█████╗░██████╗░██████╗░░█████╗░███╗░░░███╗███████╗░██████╗
██╔══██╗████╗░██║██╔══██╗██╔══██╗██╔══██╗██╔══██╗████╗░████║██╔════╝██╔════╝
███████║██╔██╗██║███████║██║░░██║██████╔╝██║░░██║██╔████╔██║█████╗░░╚█████╗░
██╔══██║██║╚████║██╔══██║██║░░██║██╔══██╗██║░░██║██║╚██╔╝██║██╔══╝░░░╚═══██╗
██║░░██║██║░╚███║██║░░██║██████╔╝██║░░██║╚█████╔╝██║░╚═╝░██║███████╗██████╔╝
╚═╝░░╚═╝╚═╝░░╚══╝╚═╝░░╚═╝╚═════╝░╚═╝░░╚═╝░╚════╝░╚═╝░░░░░╚═╝╚══════╝╚═════╝░
[/bold magenta]"""

    options = ["Play", "Arcade", "Tutorial", "Compendium", "Exit"]
    selected_index = 0
    
    while True:
        clear_screen()
        
        header_text = Text.from_markup(title_art)
        if compact_hs > 0 or extensive_hs > 0:
            score_line = "\n"
            if compact_hs > 0:
                score_line += f"✦ Compact Best: {compact_hs:,} ✦"
            if extensive_hs > 0:
                if compact_hs > 0:
                    score_line += "  |  "
                score_line += f"✦ Extensive Best: {extensive_hs:,} ✦"
            score_line += "\n"
            header_text.append(score_line, style="bold yellow")
        header_panel = Panel(Align.center(header_text), box=box.MINIMAL)
        
        menu_text = Text()
        menu_text.append("\n")
        for i, option in enumerate(options):
            if i == selected_index:
                menu_text.append(f"> [ {option.upper()} ] <\n", style="bold cyan")
            else:
                menu_text.append(f"  [ {option.upper()} ]  \n", style="dim")
        
        menu_panel = Panel(Align.center(menu_text), title="Main Menu", border_style="magenta", padding=(1, 2))
        
        footer_text = Text("Use [UP/DOWN ARROWS] to select option and [ENTER] to confirm", style="dim")
        footer_panel = Panel(Align.center(footer_text), box=box.MINIMAL)
        
        ui_panel = Panel(
            Group(
                header_panel,
                menu_panel,
                footer_panel
            ),
            box=box.MINIMAL
        )
        
        console.print(Align.center(ui_panel))
        
        cmd = get_keypress()
        if cmd == 'up':
            selected_index = (selected_index - 1) % len(options)
        elif cmd == 'down':
            selected_index = (selected_index + 1) % len(options)
        elif cmd == 'enter':
            return options[selected_index].lower()

def show_mode_select_screen(compact_hs=0, extensive_hs=0):
    options = ["Compact", "Extensive"]
    selected_index = 0
    
    while True:
        clear_screen()
        
        header_text = Text("=== SELECT GAME MODE ===\n", style="bold magenta")
        current_mode = options[selected_index].lower()
        mode_hs = compact_hs if current_mode == "compact" else extensive_hs
        if mode_hs > 0:
            header_text.append(f"♦ {options[selected_index]} Best: {mode_hs:,}", style="bold yellow")
        else:
            header_text.append(f"♦ {options[selected_index]} Best: 0", style="dim")
        header_panel = Panel(Align.center(header_text), box=box.ROUNDED, style="magenta")
        
        mode_text = Text()
        mode_text.append("\n")
        for i, option in enumerate(options):
            if i == selected_index:
                mode_text.append(f"> [ {option.upper()} ] <\n", style="bold cyan")
            else:
                mode_text.append(f"  [ {option.upper()} ]  \n", style="dim")
        
        mode_panel = Panel(Align.center(mode_text), title="Game Mode", border_style="cyan", padding=(1, 2))
        
        footer_text = Text()
        if selected_index == 0:
            footer_text.append("COMPACT MODE: Only play a set number of random puzzles per difficulty tier,\nthen advance to the next level. (Recommended game mode.)", style="yellow")
        else:
            footer_text.append("EXTENSIVE MODE: Exhaust all available puzzles in each difficulty tier\nbefore advancing, and ocassinally get harder puzzles (full challenge).", style="yellow")
            
        footer_panel = Panel(Align.center(footer_text), box=box.MINIMAL)
        
        ui_panel = Panel(
            Group(
                header_panel,
                mode_panel,
                footer_panel
            ),
            box=box.MINIMAL
        )
        
        console.print(Align.center(ui_panel))
        
        cmd = get_keypress()
        if cmd == 'up':
            selected_index = (selected_index - 1) % len(options)
        elif cmd == 'down':
            selected_index = (selected_index + 1) % len(options)
        elif cmd in ('enter', 'right'):
            return options[selected_index].lower()
        elif cmd in ('left', '\x1b'):
            return "back"

def show_level_select_screen(theme_groups, theme_names, orig_groups, orig_names, level_progress):
    selected = 0
    mode = "theme"
    
    while True:
        groups = theme_groups if mode == "theme" else orig_groups
        group_names = theme_names if mode == "theme" else orig_names
        num_groups = len(groups)
        
        # Adjust selected if it exceeds bounds after switching
        if selected >= num_groups:
            selected = num_groups - 1
            
        term_width = shutil.get_terminal_size((80, 24)).columns
        box_width = 21 # 18 for box + 3 for spacing
        cols = max(1, (term_width - 8) // box_width)
        cols = min(cols, num_groups) # don't make more cols than groups
        
        clear_screen()
        
        switch_label = "Difficulty Chapters" if mode == "theme" else "Themed Categories"
        header_text = Text.from_markup(f"[bold magenta]\u2726 SELECT YOUR CATEGORY \u2726[/bold magenta]   [dim](Press \\[TAB] for {switch_label})[/dim]")
        header_panel = Panel(Align.center(header_text), box=box.ROUNDED, style="magenta", padding=(1, 2))
        
        grid_text = Text()
        grid_text.append("\n")
        
        # Build rows of 3
        for r in range(0, num_groups, cols):
            # Row arrays
            names1, names2, fractions, box_styles = [], [], [], []
            for c in range(cols):
                idx = r + c
                if idx < num_groups:
                    name = group_names[idx]
                    grp_color = GROUP_COLORS[idx % len(GROUP_COLORS)]
                    total = len(groups[idx])
                    prog = level_progress.get(str(idx), 0)
                    
                    if prog >= total:
                        frac_str = f" ✓ {total}/{total} "
                    else:
                        frac_str = f"   {prog}/{total}   "
                        
                    is_sel = (idx == selected)
                    if is_sel:
                        box_styles.append("bold white")
                    else:
                        box_styles.append(grp_color)
                        
                    # Split name into two lines if needed
                    words = name.split()
                    line1, line2 = "", ""
                    for word in words:
                        if not line1:
                            line1 = word
                        elif len(line1) + 1 + len(word) <= 16:
                            line1 += " " + word
                        elif not line2:
                            line2 = word
                        elif len(line2) + 1 + len(word) <= 16:
                            line2 += " " + word
                        else:
                            line2 += " " + word

                    names1.append(line1.center(16))
                    names2.append(line2.center(16))
                    fractions.append(frac_str.center(16))
                else:
                    names1.append(" " * 16)
                    names2.append(" " * 16)
                    fractions.append(" " * 16)
                    box_styles.append("dim")
            
            # Construct ASCII boxes
            top_line = ""
            mid_name1 = ""
            mid_name2 = ""
            mid_frac = ""
            bot_line = ""
            
            for c in range(cols):
                idx = r + c
                if idx < num_groups:
                    style = box_styles[c]
                    sel_flag = (idx == selected)
                    
                    # Top
                    top_line += f"[{style}]┌────────────────┐[/{style}]   "
                    
                    # Name row 1
                    name_fmt1 = f"[bold white]{names1[c]}[/bold white]" if sel_flag else f"[{style}]{names1[c]}[/{style}]"
                    mid_name1 += f"[{style}]│[/{style}]{name_fmt1}[{style}]│[/{style}]   "
                    
                    # Name row 2
                    name_fmt2 = f"[bold white]{names2[c]}[/bold white]" if sel_flag else f"[{style}]{names2[c]}[/{style}]"
                    mid_name2 += f"[{style}]│[/{style}]{name_fmt2}[{style}]│[/{style}]   "
                    
                    # Fraction row
                    frac_fmt = f"[bold white]{fractions[c]}[/bold white]" if sel_flag else f"[{style}]{fractions[c]}[/{style}]"
                    mid_frac += f"[{style}]│[/{style}]{frac_fmt}[{style}]│[/{style}]   "
                    
                    # Bottom
                    bot_line += f"[{style}]└────────────────┘[/{style}]   "
                else:
                    pad = "                   " # 18 chars for box + 3 spaces = 21 chars
                    top_line += pad
                    mid_name1 += pad
                    mid_name2 += pad
                    mid_frac += pad
                    bot_line += pad
            
            grid_text.append(top_line + "\n")
            grid_text.append(mid_name1 + "\n")
            grid_text.append(mid_name2 + "\n")
            grid_text.append(mid_frac + "\n")
            grid_text.append(bot_line + "\n\n")
            
        grid_panel = Panel(Align.center(Text.from_markup(str(grid_text))), border_style="cyan", padding=(0, 2))
        
        footer_text = Text("[ARROWS] Navigate   [ENTER] Play Category   [TAB] Switch Mode   [ESC] Back to Menu", style="dim")
        footer_panel = Panel(Align.center(footer_text), box=box.MINIMAL)
        
        ui_panel = Panel(Group(header_panel, grid_panel, footer_panel), box=box.MINIMAL)
        console.print(Align.center(ui_panel))
        
        cmd = get_keypress()
        if cmd == 'tab':
            mode = "original" if mode == "theme" else "theme"
            selected = 0
            continue
        elif cmd == 'up':
            if selected >= cols:
                selected -= cols
        elif cmd == 'down':
            if selected + cols < num_groups:
                selected += cols
            else:
                # jump to last item if going down from last row
                selected = num_groups - 1
        elif cmd == 'left':
            if selected % cols > 0:
                selected -= 1
        elif cmd == 'right':
            if selected % cols < cols - 1 and selected + 1 < num_groups:
                selected += 1
        elif cmd == 'enter':
            return selected, mode
        elif cmd == '\x1b':
            return None, None

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
            "[bold cyan]Main Game - Chapters:[/bold cyan]\n"
            "Progress through a curated set of Word Galleries.\n"
            "You have [bold red]6 Lives (♥)[/bold red] per puzzle.\n"
            "Press [bold yellow][.][/bold yellow] to reveal hints if you get stuck. It's free."
        ),
        (
            "[bold yellow]Arcade Mode:[/bold yellow]\n"
            "A high-score survival mode where you only have [bold red]3 Lives (♥)[/bold red].\n"
            "• Build [bold magenta]Streaks[/bold magenta] for huge bonus multipliers.\n"
            "• Earn [bold cyan]Skips (►)[/bold cyan] every 5 correct answers.\n"
            "• Hints cost 50% of your round points.\n"
            "Compete to set the highest score in Compact or Extensive mode!"
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

def show_dictionary_entry(word_data, is_reversed):
    while True:
        clear_screen()
        
        word_to_show = word_data['w2'] if is_reversed else word_data['w1']
        def_to_show = word_data['d2'] if is_reversed else word_data['d1']
        
        pos_key = 'pos2' if is_reversed else 'pos1'
        syn_key = 'synonyms2' if is_reversed else 'synonyms1'
        ex_key = 'example2' if is_reversed else 'example1'
        quote_key = 'quote2' if is_reversed else 'quote1'
        
        hints_text = Text()
        hints_text.append(f"{word_to_show.upper()}\n\n", style="bold cyan")
        
        if word_data.get(pos_key):
            hints_text.append(f"Part of Speech: {word_data[pos_key]}\n", style="italic")
        
        hints_text.append(f"Definition: ", style="bold yellow")
        hints_text.append(f"{def_to_show}\n")
        
        if word_data.get(syn_key):
            hints_text.append(f"Synonyms: {', '.join(word_data[syn_key])}\n", style="dim")
            
        if word_data.get(ex_key):
            hints_text.append("\n  Example\n", style="bold white")
            append_example_highlighted(hints_text, word_data[ex_key], word_to_show, "italic yellow")
            
        if word_data.get(quote_key):
            q = word_data[quote_key]
            hints_text.append("\n  Quote\n", style="bold white")
            append_example_highlighted(hints_text, q['text'], word_to_show, base_style="italic yellow")
            hints_text.append(f"    — {q['reference']}\n", style="dim yellow")
            
        hints_panel = Panel(hints_text, title="Dictionary Entry", border_style="cyan", padding=(1, 2))
        
        footer_text = Text("Press [TAB] to flip to reversed word | [ESC] or [ENTER] to return", style="dim")
        footer_panel = Panel(Align.center(footer_text), box=box.MINIMAL)
        
        ui_panel = Panel(Group(hints_panel, footer_panel), box=box.MINIMAL)
        console.print(Align.center(ui_panel))
        
        cmd = get_keypress()
        if cmd == 'tab':
            is_reversed = not is_reversed
        elif cmd in ('\x1b', 'enter', 'back'):
            break

def show_compendium_screen(all_groups, unlocked_words_set):
    compendium_list = []
    for group in all_groups:
        for lvl in group:
            compendium_list.append({
                "word": lvl["w1"].lower(),
                "is_reversed": False,
                "data": lvl
            })
            compendium_list.append({
                "word": lvl["w2"].lower(),
                "is_reversed": True,
                "data": lvl
            })
    
    selected_idx = 0
    num_items = len(compendium_list)
    cols = 2
    
    while True:
        term_height = shutil.get_terminal_size((80, 24)).lines
        list_height = max(5, min(10, term_height - 12)) # max 10 rows
        
        current_row = selected_idx // cols
        page_start_row = max(0, current_row - (list_height // 2))
        
        total_rows = (num_items + cols - 1) // cols
        page_end_row = min(total_rows, page_start_row + list_height)
        
        if page_end_row - page_start_row < list_height:
            page_start_row = max(0, page_end_row - list_height)
            
        clear_screen()
        
        header_text = Text("=== COMPENDIUM ===\n", style="bold magenta")
        header_text.append(f"Unlocked: {len(unlocked_words_set)} / {num_items}", style="cyan")
        header_panel = Panel(Align.center(header_text), box=box.ROUNDED, style="magenta")
        
        list_table = Table.grid(expand=True, padding=(0, 2))
        list_table.add_column(ratio=1, justify="center")
        list_table.add_column(ratio=1, justify="center")
        
        for r in range(page_start_row, page_end_row):
            row_cells = []
            for c in range(cols):
                i = r * cols + c
                if i < num_items:
                    item = compendium_list[i]
                    is_unlocked = item["word"] in unlocked_words_set
                    display_word = item["word"].upper() if is_unlocked else " ".join(["?"] * len(item["word"]))
                    
                    if i == selected_idx:
                        cell_text = Text(f"> [ {display_word} ] <", style="bold cyan")
                    else:
                        cell_text = Text(f"  [ {display_word} ]  ", style="dim" if not is_unlocked else "white")
                    row_cells.append(cell_text)
                else:
                    row_cells.append(Text(""))
            list_table.add_row(*row_cells)
                
        list_panel = Panel(list_table, title="All Words", border_style="cyan", padding=(1, 2))
        
        footer_text = Text("Use [ARROWS] to navigate | [ENTER] to view | [ESC] to return", style="dim")
        footer_panel = Panel(Align.center(footer_text), box=box.MINIMAL)
        
        ui_panel = Panel(Group(header_panel, list_panel, footer_panel), box=box.MINIMAL)
        console.print(Align.center(ui_panel))
        
        cmd = get_keypress()
        if cmd == 'up':
            if selected_idx >= cols:
                selected_idx -= cols
        elif cmd == 'down':
            if selected_idx + cols < num_items:
                selected_idx += cols
        elif cmd == 'left':
            if selected_idx % cols > 0:
                selected_idx -= 1
        elif cmd == 'right':
            if selected_idx % cols < cols - 1 and selected_idx + 1 < num_items:
                selected_idx += 1
        elif cmd == 'enter':
            item = compendium_list[selected_idx]
            if item["word"] in unlocked_words_set:
                show_dictionary_entry(item["data"], item["is_reversed"])
        elif cmd in ('\x1b', 'back'):
            break

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
              streak=0, hint_level=0, show_debrief=False, manual_letters=0, hint_positions=None):
    
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
    if current_level.get('theme'):
        header_text.append(f"  |  Theme: {current_level['theme']}", style="bold magenta")
    if streak_label:
        header_text.append("  |  ", style="yellow")
        header_text.append(Text.from_markup(streak_label))
    header_panel = Panel(Align.center(header_text), box=box.ROUNDED, style=tier_color)
    
    # Hints Panel
    hints_text = Text()
    w1, w2 = current_level['w1'], current_level['w2']
    
    pos1 = current_level.get('pos1', 'Unknown')
    if show_debrief:
        hints_text.append(f"{w1.upper()} ", style="bold green")
        hints_text.append(f"({pos1})\n", style="dim")
        hints_text.append(f"{current_level['d1']}\n", style="italic")
        if current_level.get('synonyms1'):
            hints_text.append(f"Synonyms: {', '.join(current_level['synonyms1'])}\n", style="dim")
        if current_level.get('example1'):
            hints_text.append("  Example\n", style="bold white")
            append_example_highlighted(hints_text, current_level['example1'], w1, "italic green")
        if current_level.get('quote1'):
            q = current_level['quote1']
            hints_text.append("  Quote\n", style="bold white")
            append_example_highlighted(hints_text, q['text'], w1, base_style="italic green")
            hints_text.append(f"    — {q['reference']}\n", style="dim green")
    else:
        hints_text.append(f"Row 1 Hint ({pos1}): ", style="bold green")
        hints_text.append(f"{current_level['d1']}\n")
        if current_level.get('synonyms1'):
            hints_text.append(f"  Synonyms: {', '.join(current_level['synonyms1'])}\n", style="dim")
        if current_level.get('example1'):
            censored1 = re.sub(re.escape(w1), "[word]", current_level['example1'], flags=re.IGNORECASE)
            hints_text.append(f"  Example: \"{censored1}\"\n", style="italic cyan")
            
    hints_text.append("\n")
    
    pos2 = current_level.get('pos2', 'Unknown')
    if show_debrief:
        hints_text.append(f"{w2.upper()} ", style="bold yellow")
        hints_text.append(f"({pos2})\n", style="dim")
        hints_text.append(f"{current_level['d2']}\n", style="italic")
        if current_level.get('synonyms2'):
            hints_text.append(f"Synonyms: {', '.join(current_level['synonyms2'])}\n", style="dim")
        if current_level.get('example2'):
            hints_text.append("  Example\n", style="bold white")
            append_example_highlighted(hints_text, current_level['example2'], w2, "italic yellow")
        if current_level.get('quote2'):
            q = current_level['quote2']
            hints_text.append("  Quote\n", style="bold white")
            append_example_highlighted(hints_text, q['text'], w2, base_style="italic yellow")
            hints_text.append(f"    — {q['reference']}\n", style="dim yellow")
    else:
        hints_text.append(f"Row 2 Hint ({pos2}): ", style="bold yellow")
        hints_text.append(f"{current_level['d2']}\n")
        if current_level.get('synonyms2'):
            hints_text.append(f"  Synonyms: {', '.join(current_level['synonyms2'])}\n", style="dim")
        if current_level.get('example2'):
            censored2 = re.sub(re.escape(w2), "[word]", current_level['example2'], flags=re.IGNORECASE)
            hints_text.append(f"  Example: \"{censored2}\"\n", style="italic cyan")
        
    hints_panel = Panel(hints_text, title="Dictionary Definitions", border_style=tier_color)
    
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
            
            if hint_positions and (r, c) in hint_positions:
                text_style = "bold cyan"
            else:
                text_style = "bold"
            
            if r == active_row and c == active_col:
                if status == "neutral":
                    row_str.append(f"[ {display_char} ]", style=f"reverse {text_style}")
                else:
                    if text_style == "bold cyan":
                        row_str.append(f"[ {display_char} ]", style=f"reverse bold cyan")
                    else:
                        row_str.append(f"[ {display_char} ]", style=f"reverse {border_style}")
            else:
                row_str.append(f"  {display_char}  ", style=text_style)
        
        board_text.append(row_str)
        if r == 1:
            board_text.append("\n\n")
            
    if manual_letters < 2:
        if hint_level == 0:
            hint_state = "  [dim][.] Hint[/dim]"
        else:
            hint_state = "  [dim][.] Extra Hint[/dim]"
    else:
        hint_state = "  [dim][Max Hints Used][/dim]"
        
    hint_title = f"The Board{hint_state}"
    board_panel = Panel(Align.center(board_text), title=hint_title, border_style=border_style, padding=(1, 2))
    
    # Footer
    footer_text = Text()
    if message:
        footer_text.append(Text.from_markup(f"{message}\n", style=border_style))
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

from rich.columns import Columns
from rich.table import Table

def create_campaign_ui(group, group_name, tier_color, current_idx, grid, length, active_row, active_col, message, status, hint_level, lives, show_debrief=False, manual_letters=0, hint_positions=None, is_original_mode=False, unlocked_words=None):
    
    current_level = group[current_idx]
    diff = current_level.get("difficulty", "Unknown")
    
    header_text = Text()
    header_text.append(f"✦ Category: {group_name} ✦   |   ", style="bold white")
    header_text.append(f"Lives: {'♥ ' * lives}   |   ", style="bold red")
    header_text.append(f"Difficulty: {diff}", style="bold yellow")
    if is_original_mode and current_level.get("theme"):
        header_text.append(f"   |   Theme: {current_level.get('theme')}", style="bold magenta")
    header_panel = Panel(Align.center(header_text), box=box.ROUNDED, style=tier_color)
    
    # Left side: Puzzle Board & Hints
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
            if hint_positions and (r, c) in hint_positions:
                text_style = "bold cyan"
            else:
                text_style = "bold"
                
            if r == active_row and c == active_col:
                if status == "neutral":
                    row_str.append(f"[ {display_char} ]", style=f"reverse {text_style}")
                else:
                    if text_style == "bold cyan":
                        row_str.append(f"[ {display_char} ]", style=f"reverse bold cyan")
                    else:
                        row_str.append(f"[ {display_char} ]", style=f"reverse {border_style}")
            else:
                row_str.append(f"  {display_char}  ", style=text_style)
        
        board_text.append(row_str)
        if r == 1:
            board_text.append("\n\n")
            
    max_hints = max(2, length - 2)
    hints_remaining = max_hints - manual_letters
    if hints_remaining > 0:
        hint_state = f"  [dim][.] Hint ({hints_remaining} remaining)[/dim]"
    else:
        hint_state = "  [dim][Max Hints Used][/dim]"
        
    hint_title = f"The Board{hint_state}"
    board_panel = Panel(Align.center(board_text), title=hint_title, border_style=border_style, padding=(1, 2))
    
    hints_text = Text()
    w1, w2 = current_level['w1'], current_level['w2']
    
    pos1 = current_level.get('pos1', 'Unknown')
    if show_debrief:
        hints_text.append(f"{w1.upper()} ", style="bold green")
        hints_text.append(f"({pos1})\n", style="dim")
        hints_text.append(f"{current_level['d1']}\n", style="italic")
        if current_level.get('synonyms1'):
            hints_text.append(f"Synonyms: {', '.join(current_level['synonyms1'])}\n", style="dim")
        if current_level.get('example1'):
            hints_text.append("  Example\n", style="bold white")
            append_example_highlighted(hints_text, current_level['example1'], w1, "italic green")
        if current_level.get('quote1'):
            q = current_level['quote1']
            hints_text.append("  Quote\n", style="bold white")
            append_example_highlighted(hints_text, q['text'], w1, base_style="italic green")
            hints_text.append(f"    — {q['reference']}\n", style="dim green")
    else:
        hints_text.append(f"Row 1: ", style="bold green")
        hints_text.append(f"{current_level['d1']}\n")
        if current_level.get('example1'):
            censored1 = re.sub(re.escape(w1), "[word]", current_level['example1'], flags=re.IGNORECASE)
            hints_text.append(f"  Example: \"{censored1}\"\n", style="italic cyan")
        
    hints_text.append("\n")
    
    pos2 = current_level.get('pos2', 'Unknown')
    if show_debrief:
        hints_text.append(f"{w2.upper()} ", style="bold yellow")
        hints_text.append(f"({pos2})\n", style="dim")
        hints_text.append(f"{current_level['d2']}\n", style="italic")
        if current_level.get('synonyms2'):
            hints_text.append(f"Synonyms: {', '.join(current_level['synonyms2'])}\n", style="dim")
        if current_level.get('example2'):
            hints_text.append("  Example\n", style="bold white")
            append_example_highlighted(hints_text, current_level['example2'], w2, "italic yellow")
        if current_level.get('quote2'):
            q = current_level['quote2']
            hints_text.append("  Quote\n", style="bold white")
            append_example_highlighted(hints_text, q['text'], w2, base_style="italic yellow")
            hints_text.append(f"    — {q['reference']}\n", style="dim yellow")
    else:
        hints_text.append(f"Row 2: ", style="bold yellow")
        hints_text.append(f"{current_level['d2']}\n")
        if current_level.get('example2'):
            censored2 = re.sub(re.escape(w2), "[word]", current_level['example2'], flags=re.IGNORECASE)
            hints_text.append(f"  Example: \"{censored2}\"\n", style="italic cyan")
        
    hints_panel = Panel(hints_text, title="Definitions", border_style=tier_color)
    
    # Right side: Word Gallery
    gallery_text = Text()
    for i in range(len(group)):
        if i < current_idx or (i == current_idx and status == "success"):
            # Solved
            w1 = group[i]['w1']
            w2 = group[i]['w2']
            gallery_text.append(f"{i+1:2d}. {w1.upper()} ↔ {w2.upper()}\n", style="bold white")
        elif i == current_idx:
            # Current
            gallery_text.append(f"{i+1:2d}. ", style="bold cyan")
            gallery_text.append(f"{'-' * len(group[i]['w1'])} ↔ {'-' * len(group[i]['w2'])}\n", style="blink bold cyan")
        else:
            # Unsolved
            gallery_text.append(f"{i+1:2d}. {'-' * len(group[i]['w1'])} ↔ {'-' * len(group[i]['w2'])}\n", style="dim")
            
    gallery_panel = Panel(gallery_text, title="Word Gallery", border_style=tier_color)
    
    # Layout using a hidden table for stable 50/50 sizing
    layout_table = Table.grid(expand=True, padding=(0, 2))
    layout_table.add_column(ratio=6)
    layout_table.add_column(ratio=4)
    layout_table.add_row(Group(board_panel, hints_panel), gallery_panel)
    
    footer_text = Text()
    if message:
        footer_text.append(Text.from_markup(f"{message}\n", style=border_style))
    footer_text.append("CONTROLS: [A-Z] Type | [ARROWS] Move | [.] Hint | [ENTER] Submit | [ESC] Save & Exit", style="dim")
    footer_panel = Panel(Align.center(footer_text), box=box.MINIMAL)
    
    return Align.center(
        Panel(
            Group(header_panel, layout_table, footer_panel),
            box=box.MINIMAL
        )
    )

def append_example_highlighted(text, example, word, base_style="italic cyan"):
    """Append an example sentence to a Rich Text, bolding every occurrence of the target word."""
    bold_style = f"bold {base_style}"
    text.append('    "', style=base_style)
    parts = re.split(f"({re.escape(word)})", example, flags=re.IGNORECASE)
    for part in parts:
        if part.lower() == word.lower():
            text.append(part, style=bold_style)
        else:
            text.append(part, style=base_style)
    text.append('"\n', style=base_style)


def show_tier_mastered(tier_name):
    clear_screen()
    tier_color = DIFF_COLORS.get(tier_name, "cyan")
    
    text = Text(justify="center")
    text.append("\n\n")
    text.append("✦ TIER MASTERED ✦\n", style=f"bold {tier_color}")
    text.append(f"\n{tier_name.upper()}\n", style=f"bold white on {tier_color}")
    text.append("\n\nYou've mastered this difficulty!\n", style="dim")
    
    console.print(Panel(Align.center(text), border_style=tier_color, box=box.DOUBLE, padding=(1, 4)))
    time.sleep(0.2)
    console.print(Align.center(f"[dim]Press any key to continue...[/dim]"))
    get_keypress()

def show_streak_lost(lost_streak):
    clear_screen()
    
    text = Text(justify="center")
    text.append("\n\n")
    text.append("✗ STREAK LOST ✗\n", style="bold red")
    text.append(f"\nYou lost your streak of {lost_streak}!\n", style="bold white")
    text.append("\n\nHint: Press period (.) for useful hints!\n", style="dim")
    
    console.print(Panel(Align.center(text), border_style="red", box=box.DOUBLE, padding=(1, 4)))
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
                length, active_row, active_col, level, wins, streak, hint_level=0, hint_positions=None):
    # Quick visual flicker to sell the wrong-answer sting
    for _ in range(3):
        clear_screen()
        console.print(create_ui(score, skips, lives, diff_name, progress, current_level,
                                grid, length, active_row, active_col,
                                "[bold red]✗ Incorrect![/bold red]", "error", level, wins, streak, hint_level, hint_positions=hint_positions, is_original_mode=is_original_mode, unlocked_words=unlocked_words))
        time.sleep(0.07)
        clear_screen()
        console.print(create_ui(score, skips, lives, diff_name, progress, current_level,
                                grid, length, active_row, active_col,
                                "", "neutral", level, wins, streak, hint_level, hint_positions=hint_positions, is_original_mode=is_original_mode, unlocked_words=unlocked_words))
        time.sleep(0.05)


# Main game loop
def play_game(levels, high_score=0, mode="extensive"):
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
            
        if mode == "compact":
            limits = {
                "Very Easy": 10,
                "Easy": 20,
                "Medium": 30,
                "Hard": 40,
                "Very Hard": 50,
                "Insane": 39
            }
            for d in diff_order:
                unplayed[d] = unplayed[d][:limits.get(d, 10)]
            
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

            # Show tier mastered screen when the base difficulty advances
            if current_difficulty_idx > prev_difficulty_idx:
                show_tier_mastered(diff_order[prev_difficulty_idx])
            prev_difficulty_idx = current_difficulty_idx

            # Dynamic difficulty scaling selection
            level_num = total_levels_played + 1
            chosen_diff_idx = None
            
            if mode == "compact":
                chosen_diff_idx = current_difficulty_idx
            elif level_num % 5 == 0:
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
            if mode == "compact":
                limits = {
                    "Very Easy": 10,
                    "Easy": 20,
                    "Medium": 30,
                    "Hard": 40,
                    "Very Hard": 50,
                    "Insane": 39
                }
                tier_total = min(tier_total, limits.get(chosen_diff_name, tier_total))
            tier_done = tier_total - len(unplayed[chosen_diff_name])
            progress = f"{tier_done}/{tier_total}"
            
            diff_name = chosen_diff_name
            
            grid = {1: [None] * length, 2: [None] * length}
            active_row = 1
            active_col = 0
            
            message = ""
            status = "neutral"
            game_over = False
            hint_level = 0
            hint_positions = set()  # tracks which (row, col) pairs were revealed by hint
            lost_streak_value = 0
            fails_on_level = 0
            manual_letters_revealed = 0
            
            while True: 
                clear_screen()
                console.print(create_ui(score, skips, lives, diff_name, progress, current_level,
                                        grid, length, active_row, active_col, message, status,
                                        total_levels_played + 1, successful_guesses, streak, hint_level, manual_letters=manual_letters_revealed, hint_positions=hint_positions, is_original_mode=is_original_mode, unlocked_words=unlocked_words))
                
                status = "neutral" 
                
                cmd = get_keypress()
                message = "" 
                mirror_row = 2 if active_row == 1 else 1
                
                if cmd == '\x1b': 
                    if score > high_score:
                        save_high_score(score, mode)
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

                elif cmd == '.':
                    if hint_level == 0:
                        has_examples = bool(current_level.get('example1') or current_level.get('example2'))
                        if has_examples:
                            hint_level = 1
                            message = "[dim]Example hints unlocked: Round points halved.[/dim]"
                            status = "neutral"
                            continue

                    max_hints = max(2, length - 2)
                    # Reveal letter logic
                    if manual_letters_revealed < max_hints:
                        empty_cols = [c for c in range(length) if grid[1][c] != word1[c]]
                        if empty_cols:
                            hc = random.choice(empty_cols)
                            grid[1][hc] = word1[hc]
                            grid[2][length - 1 - hc] = word2[length - 1 - hc]
                            hint_positions.add((1, hc))
                            hint_positions.add((2, length - 1 - hc))
                            hint_level += 1
                            manual_letters_revealed += 1
                            message = "[dim]Letter revealed: Round points halved.[/dim]"
                        else:
                            message = "[dim]No empty cells to reveal.[/dim]"
                    else:
                        message = "[dim]Maximum letter hints used![/dim]"
                    status = "neutral"
                        
                elif cmd == 'tab':
                    if skips > 0:
                        skips -= 1
                        lost_streak_value = streak
                        streak = 0
                        total_levels_played += 1
                        if lost_streak_value > 0:
                            show_streak_lost(lost_streak_value)
                        
                        grid[1] = list(word1)
                        grid[2] = list(word2)
                        d_info = "Skipped! [Press ANY KEY to continue]"
                        clear_screen()
                        console.print(create_ui(score, skips, lives, diff_name, progress, current_level,
                                                grid, length, active_row, active_col, d_info,
                                                "error", total_levels_played, successful_guesses,
                                                streak, hint_level, show_debrief=True, hint_positions=hint_positions, is_original_mode=is_original_mode, unlocked_words=unlocked_words))
                        get_keypress()
                        break 
                    else:
                        message = "[bold red]⚠ No skips remaining![/bold red]"
                        status = "error"
                            
                elif cmd == 'enter':
                    current_w1 = "".join([c for c in grid[1] if c])
                    current_w2 = "".join([c for c in grid[2] if c])
                    
                    if len(current_w1) < length:
                        message = "[bold red]⚠ Please fill all letters before submitting![/bold red]"
                        status = "error"
                    else:
                        if current_w1 == word1 and current_w2 == word2:
                            save_unlocked_words(word1, word2)
                            pts_base = {"Very Easy": 100, "Easy": 200, "Medium": 300,
                                        "Hard": 400, "Very Hard": 500, "Insane": 600}
                            base_pts = pts_base.get(diff_name, 100)
                            if hint_level > 0:
                                base_pts = base_pts // (2 ** hint_level)
                            
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
                            
                            # Reward feedback flash
                            clear_screen()
                            console.print(create_ui(score, skips, lives, diff_name, progress, current_level,
                                                    grid, length, active_row, active_col, "Correct!",
                                                    "success", total_levels_played, successful_guesses,
                                                    streak, hint_level, hint_positions=hint_positions, is_original_mode=is_original_mode, unlocked_words=unlocked_words))
                            time.sleep(0.6)
                            
                            if lost_streak_value > 0:
                                show_streak_lost(lost_streak_value)
                            
                            d_info = f"Earned {points_earned} pts! "
                            if earned_skip: d_info += " +1 Skip "
                            if earned_life: d_info += " +1 Life "
                            if streak > 1: d_info += f" ({multiplier}x Streak) "
                            d_info += "[Press ANY KEY to continue]"
                            
                            clear_screen()
                            console.print(create_ui(score, skips, lives, diff_name, progress, current_level,
                                                    grid, length, active_row, active_col, d_info,
                                                    "success", total_levels_played, successful_guesses,
                                                    streak, hint_level, show_debrief=True, hint_positions=hint_positions, is_original_mode=is_original_mode, unlocked_words=unlocked_words))
                            get_keypress()
                            break
                        else:
                            if streak > 0:
                                lost_streak_value = streak
                            streak = 0
                            lives -= 1
                            fails_on_level += 1
                            
                            # 1. Compute hint BEFORE shake_error so the flash includes the hint!
                            auto_hinted = False
                            if lives > 0 and fails_on_level % 2 == 0:
                                empty_cols = [c for c in range(length) if grid[1][c] != word1[c]]
                                if empty_cols:
                                    import random
                                    hc = random.choice(empty_cols)
                                    grid[1][hc] = word1[hc]
                                    grid[2][length - 1 - hc] = word2[length - 1 - hc]
                                    hint_positions.add((1, hc))
                                    hint_positions.add((2, length - 1 - hc))
                                    auto_hinted = True
                                    
                            # 2. Flash error
                            shake_error(score, skips, lives, diff_name, progress, current_level,
                                        grid, length, active_row, active_col,
                                        total_levels_played + 1, successful_guesses, streak, hint_level, hint_positions=hint_positions)
                            
                            if lives <= 0:
                                total_levels_played += 1
                                if lost_streak_value > 0:
                                    show_streak_lost(lost_streak_value)
                                    
                                grid[1] = list(word1)
                                grid[2] = list(word2)
                                d_info = "Out of lives! [Press ANY KEY to continue]"
                                clear_screen()
                                console.print(create_ui(score, skips, lives, diff_name, progress, current_level,
                                                        grid, length, active_row, active_col, d_info,
                                                        "error", total_levels_played, successful_guesses,
                                                        streak, hint_level, show_debrief=True, hint_positions=hint_positions, is_original_mode=is_original_mode, unlocked_words=unlocked_words))
                                get_keypress()
                                
                                # Save high score before showing summary
                                new_high = max(score, high_score)
                                if score > high_score:
                                    save_high_score(score, mode)
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
                                        sys.exit()
                                break
                            else:
                                if auto_hinted:
                                    message = "[bold red]✗ Incorrect! You lost a heart. (Auto-hint: Letter revealed!)[/bold red]"
                                else:
                                    message = "[bold red]✗ Incorrect! You lost a heart.[/bold red]"
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

def play_group(groups, group_idx, group_names, level_progress, is_original_mode=False, unlocked_words=None):
    if unlocked_words is None:
        unlocked_words = set()
    group = groups[group_idx]
    group_name = group_names[group_idx]
    tier_color = GROUP_COLORS[group_idx % len(GROUP_COLORS)]
    total_levels = len(group)
    
    # Start from where they left off, or 0 if they completed it
    start_idx = level_progress.get(group_name, 0)
    if start_idx >= total_levels:
        start_idx = 0
        level_progress[group_name] = 0
        save_level_progress(level_progress)
        
    for i in range(start_idx, total_levels):
        current_level = group[i]
        word1, word2 = current_level["w1"], current_level["w2"]
        length = len(word1)
        
        if word1.lower() in unlocked_words:
            new_prog = i + 1
            if level_progress.get(group_name, 0) < new_prog:
                level_progress[group_name] = new_prog
                save_level_progress(level_progress)
            continue
            
        lives = 6
        
        grid = {1: [None] * length, 2: [None] * length}
        active_row = 1
        active_col = 0
        
        message = ""
        status = "neutral"
        hint_level = 0
        hint_positions = set()
        level_done = False
        fails_on_level = 0
        manual_letters_revealed = 0
        
        while not level_done:
            clear_screen()
            console.print(create_campaign_ui(group, group_name, tier_color, i, grid, length, active_row, active_col, message, status, hint_level, lives, manual_letters=manual_letters_revealed, hint_positions=hint_positions, is_original_mode=is_original_mode, unlocked_words=unlocked_words))
            
            status = "neutral"
            cmd = get_keypress()
            message = ""
            mirror_row = 2 if active_row == 1 else 1
            
            if cmd == '\x1b': 
                return
                
            elif cmd in ('up', 'down'):
                active_row = mirror_row
                active_col = min(active_col, length - 1)
                
            elif cmd == 'left':
                if active_col > 0: active_col -= 1
                
            elif cmd == 'right':
                if active_col < length - 1: active_col += 1
                
            elif cmd == 'back':
                if grid[active_row][active_col] is not None and (active_row, active_col) not in hint_positions:
                    grid[active_row][active_col] = None
                    grid[mirror_row][length - 1 - active_col] = None
                else:
                    if active_col > 0:
                        active_col -= 1
                        if (active_row, active_col) not in hint_positions:
                            grid[active_row][active_col] = None
                            grid[mirror_row][length - 1 - active_col] = None

            elif cmd == '.':
                max_hints = max(2, length - 2)
                if manual_letters_revealed < max_hints:
                    empty_cols = [c for c in range(length) if grid[1][c] != word1[c]]
                    if empty_cols:
                        hc = random.choice(empty_cols)
                        grid[1][hc] = word1[hc]
                        grid[2][length - 1 - hc] = word2[length - 1 - hc]
                        hint_positions.add((1, hc))
                        hint_positions.add((2, length - 1 - hc))
                        hint_level += 1
                        manual_letters_revealed += 1
                        message = "[dim]Letter revealed.[/dim]"
                    else:
                        message = "[dim]No empty cells to reveal.[/dim]"
                else:
                    message = "[dim]Maximum letter hints used![/dim]"
                status = "neutral"
                        
            elif cmd == 'enter':
                current_w1 = "".join([c for c in grid[1] if c])
                current_w2 = "".join([c for c in grid[2] if c])
                
                if len(current_w1) < length:
                    message = "[bold red]⚠ Please fill all letters before submitting![/bold red]"
                    status = "error"
                else:
                    if current_w1 == word1 and current_w2 == word2:
                        save_unlocked_words(word1, word2)
                        clear_screen()
                        console.print(create_campaign_ui(group, group_name, tier_color, i, grid, length, active_row, active_col, "Correct! [Press ANY KEY to continue]", "success", hint_level, lives, show_debrief=True, hint_positions=hint_positions, is_original_mode=is_original_mode, unlocked_words=unlocked_words))
                        get_keypress()
                        
                        # Advance progress
                        level_progress[group_name] = i + 1
                        save_level_progress(level_progress)
                        level_done = True
                    else:
                        lives -= 1
                        fails_on_level += 1
                        if lives <= 0:
                            grid[1] = list(word1)
                            grid[2] = list(word2)
                            clear_screen()
                            console.print(create_campaign_ui(group, group_name, tier_color, i, grid, length, active_row, active_col, "Out of lives! [Press ANY KEY to return]", "error", hint_level, lives, show_debrief=True, hint_positions=hint_positions, is_original_mode=is_original_mode, unlocked_words=unlocked_words))
                            get_keypress()
                            return
                        else:
                            if fails_on_level % 2 == 0:
                                empty_cols = [c for c in range(length) if grid[1][c] != word1[c]]
                                if empty_cols:
                                    hc = random.choice(empty_cols)
                                    grid[1][hc] = word1[hc]
                                    grid[2][length - 1 - hc] = word2[length - 1 - hc]
                                    hint_positions.add((1, hc))
                                    hint_positions.add((2, length - 1 - hc))
                                    message = f"[bold red]✗ Incorrect. {lives} {'life' if lives == 1 else 'lives'} remaining! (Auto-hint: Letter revealed!)[/bold red]"
                                else:
                                    message = f"[bold red]✗ Incorrect. {lives} {'life' if lives == 1 else 'lives'} remaining![/bold red]"
                            else:
                                message = f"[bold red]✗ Incorrect. {lives} {'life' if lives == 1 else 'lives'} remaining![/bold red]"
                            status = "error"
                            
            elif len(cmd) == 1 and cmd.isalpha():
                char = cmd.upper()
                if (active_row, active_col) not in hint_positions:
                    grid[active_row][active_col] = char
                    grid[mirror_row][length - 1 - active_col] = char
                if active_col < length - 1:
                    active_col += 1

    # End of group reached
    clear_screen()
    text = Text("\n\n✦ CHAPTER COMPLETE ✦\n\n", style="bold bright_cyan")
    text.append(f"You finished {group_name}!\n", style="bold white")
    console.print(Panel(Align.center(text), border_style="cyan"))
    time.sleep(2)


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    CSV_FILE = resource_path('anadromes_ranked_llm.csv')
    JSON_FILE = resource_path('dictionary_pruned.json')  
    
    # Load grouped levels for Level Select mode
    theme_groups, theme_names, orig_groups, orig_names = load_groups(CSV_FILE, JSON_FILE)
    
    # Auto-unlock retroactively based on level_progress
    scores = load_high_scores()
    lp = scores.get("level_progress", {})
    unlocked = set(scores.get("unlocked_words", []))
    changed = False
    
    # Migrate old level_progress format (string indices) to original mode names
    for g_idx, orig_name in enumerate(orig_names):
        old_key = str(g_idx)
        if old_key in lp:
            if orig_name not in lp:
                lp[orig_name] = lp[old_key]
            del lp[old_key]
            changed = True
            
    # Auto-unlock based on progress in BOTH modes
    for mode_groups, mode_names in [(theme_groups, theme_names), (orig_groups, orig_names)]:
        for g_idx, group in enumerate(mode_groups):
            solved_up_to = lp.get(mode_names[g_idx], 0)
            for i in range(solved_up_to):
                if i < len(group):
                    w1_low = group[i]['w1'].lower()
                    w2_low = group[i]['w2'].lower()
                    if w1_low not in unlocked:
                        unlocked.add(w1_low)
                        changed = True
                    if w2_low not in unlocked:
                        unlocked.add(w2_low)
                        changed = True
    
    if changed:
        scores["unlocked_words"] = list(unlocked)
        path = get_save_path()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({
                    "compact_high_score": scores["compact"],
                    "extensive_high_score": scores["extensive"],
                    "level_progress": scores["level_progress"],
                    "unlocked_words": scores["unlocked_words"]
                }, f)
        except Exception:
            pass
    
    while True:
        scores = load_high_scores()
        compact_hs = scores.get("compact", 0)
        extensive_hs = scores.get("extensive", 0)
        level_progress = scores.get("level_progress", {})
        
        choice = show_title_screen(compact_hs, extensive_hs)
        if choice == "play":
            while True:
                grp_idx, mode = show_level_select_screen(theme_groups, theme_names, orig_groups, orig_names, level_progress)
                if grp_idx is None:
                    break
                active_groups = theme_groups if mode == "theme" else orig_groups
                active_names = theme_names if mode == "theme" else orig_names
                play_group(active_groups, grp_idx, active_names, level_progress, is_original_mode=(mode == "original"), unlocked_words=unlocked)
                # reload progress after returning
                scores = load_high_scores()
                level_progress = scores.get("level_progress", {})
        elif choice == "arcade":
            # For backward compatibility, load classic flat structure
            loaded_levels = load_game_data(CSV_FILE, JSON_FILE)
            mode = show_mode_select_screen(compact_hs, extensive_hs)
            if mode == "back":
                continue
            active_hs = compact_hs if mode == "compact" else extensive_hs
            play_game(loaded_levels, active_hs, mode)
        elif choice == "tutorial":
            show_tutorial_screen()
        elif choice == "compendium":
            unlocked_words = set(scores.get("unlocked_words", []))
            show_compendium_screen(orig_groups, unlocked_words)
        elif choice == "exit":
            clear_screen()
            sys.exit()