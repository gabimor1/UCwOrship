# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UCwOrship is a tkinter-based GUI application for displaying and projecting Arabic worship songs. It renders high-quality song sheets with Arabic RTL text, chord notation, and supports transposition, session management, and an external projector window.

## Setup & Running

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Run the app
python -m ucworship
```

**macOS note:** Requires tcl-tk via Homebrew for tkinter support (see README.md for brew commands).

## Development Commands

```bash
# Install with dev/test extras
pip install -e ".[dev,test]"

# Run linting (ruff + pylint via pre-commit)
pre-commit run --all-files

# Run ruff directly
ruff check ucworship/
ruff format ucworship/

# Run tests (no tests exist yet, but pytest is configured)
pytest
```

## Architecture

The app has two main modules:

### `ucworship/ImageCreationGUI.py` — GUI Layer
- **`MusicTheory`**: Static utility class for chord transposition across 12 semitones (handles sharp/flat)
- **`SongSheetApp(tk.Tk)`**: Main application window (1200×800)
  - Left panel: media browser (searchable), session/playlist list, parameter controls
  - Right panel: image canvas with zoom
  - Manages state: `current_mode` ("song" or "image"), `current_song_data`, `all_media_files`
  - Key methods: `_parse_song_file()`, `_get_transposed_song_data()`, `update_image()`, `open_projector_window()`

### `ucworship/image_automation_script.py` — Image Rendering
- **`create_arabic_song_image(song_data, params)`**: Generates PIL Image objects
  - Renders at 4× scale (7400px wide) then downsamples with LANCZOS for quality
  - Uses `arabic_reshaper` + `python-bidi` for proper RTL text shaping
  - Places English chords above Arabic lyrics with pixel-accurate positioning
  - Bold rendering for chorus sections

### Song File Format

Song files live in `ucworship/assets/txt_files/` as `.txt` files:

```
Title: Song Name
Capo: 0

[Verse 1]
Lyrics line[C] with[G] inline chords[Am]

[Chorus]
Chorus text[Em] here
```

Images imported by the user go in `ucworship/assets/image_files/`.

## Known Issues (from bugsAndFeatures.txt)

- Scale transposition breaks when reaching the "C" note
- Hash (`#`) symbols not handled correctly with chords during transposition
- Chord placement at line start needs adjustment
- Capo + scale combined transposition is unsupported for parenthesized half-notes

## Code Style

- Line length: 100 characters (ruff)
- Target: Python 3.11+
- Linting: ruff + pylint (via pre-commit); mypy/pyright hooks are present but disabled
