# Anadromes

I had this random idea at 5 AM the other night and decided to build it out into a full terminal game. 

An "anadrome" is a word that forms a completely different word when spelled backwards (like DOG and GOD). The game gives you two dictionary definitions (sourced from the Free Dictionary API), and you have to figure out the pair of words that match them. It's fully playable right in your terminal and doesn't require any messy dependencies.

## Features

- **Campaign Mode:** I grouped the puzzles into 19 chapters. I spent a lot of time carefully mapping out the difficulty curve, so it scales up nicely as you progress.
- **Arcade Mode:** A classic endless survival mode where you try to build up a huge streak and earn skips to get the highest score possible.
- **The Compendium:** Since there are a ton of obscure words in here, I added a persistent dictionary. Any time you solve a puzzle, the words get unlocked and saved to your compendium so you can go back and read their full definitions, synonyms, and quotes.
- **Hints & Progression:** You get 6 lives per puzzle. If you run out, the game automatically reveals a letter for you so you don't get permanently stuck. You can also manually ask for up to two letter hints if you just need a nudge.
- **Responsive UI:** The whole interface dynamically resizes its grids based on how wide your terminal window is, and the educational debriefs happen right on the game board instead of throwing you into a different screen.

## How it was made

I wanted to keep this entirely in the terminal, so I built it in **Python**. 
- The UI is powered by the `rich` library, which handles all the grid layouts, colored text, and formatting. 
- I used standard libraries like `shutil` to make the grids and compendium dynamically respond to your terminal's dimensions.
- The word data itself (definitions, parts of speech, synonyms, quotes, and examples) was curated and compiled using the **Free Dictionary API**.
- To make it easy for anyone to play, I packaged the entire thing into a single standalone executable using `PyInstaller`.

## How to play

**The easy way:**
Just download the `Anadromes.exe` file from the Releases page and run it directly in your terminal or command prompt. No installations required!

**Running from source:**
If you prefer to run the raw Python code, clone the repo and install the requirement:
```bash
git clone https://github.com/your-username/anadromes.git
cd anadromes
pip install rich
python main.py
```
