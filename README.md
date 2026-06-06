<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/9533d40b-8a37-4f6f-abae-ca3856583952" />

# Anadromes

I had this random idea at 5 AM the other night and decided to build it out into a full terminal game. 

An "anadrome" is a word that forms a completely different word when spelled backwards (like DOG and GOD). The game gives you two dictionary definitions, and you have to figure out the pair of words that match them. 

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/378b35cd-fbd9-40e3-8c96-bb4ed0e4d749" />

## What's inside

I grouped the main puzzles into 20 themed chapters (like Animal Kingdom, Sound Effects, Internet, etc.), and I spent a lot of time carefully mapping out the difficulty curve so it scales up nicely as you progress. If you just want to chase high scores, there's a classic endless arcade mode where you can build up streaks and earn skips.

Since there are a ton of obscure words in here, I added a persistent compendium. Any time you solve a puzzle, the words get unlocked and saved there so you can go back and read their full dictionary entries. You get 6 lives per puzzle, and if you run out, the game automatically reveals a letter for you so you don't get permanently stuck.

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/3f1e326f-78a5-43b1-9385-28ccfba0871a" />




## How it was made

I wanted to keep this entirely in the terminal, so I built it in Python. The UI is powered by the `rich` library which handles all the grid layouts, colored text, and formatting, while standard libraries like `shutil` handle making the grids dynamically respond to your terminal's dimensions. The word data itself—definitions, parts of speech, synonyms, quotes, and examples—was curated and compiled using the Free Dictionary API. To make it easy for anyone to play without messing with dependencies, I packaged the entire thing into a single executable using `PyInstaller`.

## How to play

Just download the `Anadromes.exe` file from the Releases page and run it directly in your terminal. No installations required!

If you prefer to run the raw Python code, clone the repo, run `pip install rich`, and then execute `python main.py`.

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/8e6c7664-024d-41d8-beb4-3486786ca90c" />

