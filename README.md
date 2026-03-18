# UCwOrship

Worship songs presenter and projector by UCO Galilee.

## Installing as a Desktop App (Recommended)

The easiest way to use UCwOrship — no Python or terminal required.

### Download

Go to the [Releases page](../../releases) and download the latest version for your platform:

- **macOS**: `UCwOrship-macOS.zip` → unzip → move `UCwOrship.app` to your Applications folder
- **Windows**: `UCwOrship-Windows.zip` → unzip → run `UCwOrship\UCwOrship.exe`

### macOS: First Launch

macOS will block the app on first open because it is not signed by the App Store. To open it:

1. Right-click (or Control-click) `UCwOrship.app`
2. Choose **Open**
3. Click **Open** in the dialog

You only need to do this once.

### Windows: First Launch

Windows Defender SmartScreen may warn you that the app is from an unknown publisher. To open it:

1. Double-click `UCwOrship.exe`
2. If a blue "Windows protected your PC" dialog appears, click **More info**
3. Click **Run anyway**

You only need to do this once. The app does not modify your system or connect to the internet.

**Windows Defender / Antivirus:** Some antivirus programs flag PyInstaller-packaged apps as suspicious (false positive). If this happens:
- Check the file in [VirusTotal](https://www.virustotal.com) to confirm it's safe
- Add an exception for the `UCwOrship` folder in your antivirus settings

### Where are my files?

Songs and images you add are stored in a writable folder outside the app, so they survive updates:

- **macOS**: `~/Library/Application Support/UCwOrship/assets/`
- **Windows**: `%APPDATA%\UCwOrship\assets\`

The bundled default songs are copied there automatically on first launch.

---

## Using the App

### Main Window

The left panel has three areas:

| Area | What it does |
|------|-------------|
| **Search bar** | Filter songs/images by name (Ctrl+A to select all text) |
| **Media list** | All available songs (`.txt`) and images; click to preview |
| **Session list** | Your current set list for a service |

### Loading a Song or Image

- **Click** any item in the media list to preview it on the right canvas.
- **Scroll** or use zoom buttons to zoom in/out on the preview.
- **Double-click** the canvas to reset zoom.

### Building a Session

- **Drag** a song from the media list and drop it onto the session list, or click **+ Add**.
- Use **↑ / ↓** to reorder items in the session.
- Click an item in the session list to load it.

### Projector

1. Connect a second screen (TV/projector).
2. Click **Open Projector** — a full-screen window opens on the second display.
3. The projector follows whichever song/image you select.
4. **⏸ Pause** freezes the projector on the current slide so you can browse privately; click **▶ Resume** to sync it again.
5. After pausing, a **↩ Return** button appears — click it to jump back to the song that was showing before you paused.

### Transposition

- **Capo** — shifts displayed chords up (positive) or down (negative) semitones.
- **Scale ▲ / Scale ▼** — transposes the actual key of the song.

### Themes

- **Light / Dark** toggle in the controls panel switches between a bright theme (for rehearsal) and a dark theme (for low-light worship rooms). The projector window also switches.

### Adding Songs

- **Import** — brings in `.txt` song files or image files (`.png`, `.jpg`, etc.) from anywhere on your computer.
- **New Song** — creates a blank song template and opens it in your default text editor.

Song files use this format:

```
Title: Song Name
Capo: 0

[Verse 1]
Lyrics line with inline [C]chords [G]like [Am]this

[Chorus]
Chorus text [Em]here
```

Chords are placed inline with `[ChordName]` immediately before the syllable they fall on. The app renders them above the lyrics automatically.

### Export All Songs

**Export All** renders every `.txt` song to a `.png` image (with current transposition settings) and saves them to a folder you choose.

---

## Running from Source (Developers)

### Prerequisites

Python ≥ 3.11 with tkinter.

**macOS (Homebrew):**
```shell
brew install tcl-tk
brew reinstall python3 --with-tcl-tk
echo 'export PATH="/opt/homebrew/opt/tcl-tk/bin:$PATH"' >> ~/.zprofile
export LDFLAGS="-L/opt/homebrew/opt/tcl-tk/lib"
export CPPFLAGS="-I/opt/homebrew/opt/tcl-tk/include"
```

Verify: `python3 -m tkinter`

### Setup

```shell
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

### Run

```shell
python -m ucworship
```

### Build the desktop app locally

```shell
pip install pyinstaller
pyinstaller UCwOrship.spec
```

Output is in `dist/`. On macOS the `.app` bundle is at `dist/UCwOrship.app`.

_PyCharm users: append `--config-settings editable_mode=compat` to the `pip install` command if imports don't resolve._
