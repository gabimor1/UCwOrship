import os
import re
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

# This line IMPORTS your perfected image creation function from your script.
# Make sure 'image_automation_script.py' is in the same folder.
from ucworship.image_automation_script import create_arabic_song_image

def _get_bundle_dir():
    """Read-only assets (fonts, bundled defaults) — inside the frozen bundle or source tree."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(__file__)


def _get_data_dir():
    """User-writable data directory (songs, imported images)."""
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return os.path.expanduser("~/Library/Application Support/UCwOrship")
        if sys.platform == "win32":
            return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "UCwOrship")
        return os.path.expanduser("~/.local/share/UCwOrship")
    return os.path.dirname(__file__)


def _init_user_data(bundle_dir: str, data_dir: str):
    """On first run as a frozen app, copy bundled default songs to the user data dir."""
    songs_dir = os.path.join(data_dir, "assets", "txt_files")
    images_dir = os.path.join(data_dir, "assets", "image_files")
    os.makedirs(songs_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)

    if bundle_dir == data_dir:
        return  # development mode — nothing to copy

    for src_subdir, dst_subdir in [("txt_files", songs_dir), ("image_files", images_dir)]:
        src = os.path.join(bundle_dir, "assets", src_subdir)
        if os.path.isdir(src):
            for fname in os.listdir(src):
                dest = os.path.join(dst_subdir, fname)
                if not os.path.exists(dest):
                    shutil.copy(os.path.join(src, fname), dest)


_bundle_dir = _get_bundle_dir()
_data_dir = _get_data_dir()
_init_user_data(_bundle_dir, _data_dir)

fonts_dir = os.path.join(_bundle_dir, "assets", "fonts")
song_dest = os.path.join(_data_dir, "assets", "txt_files")
image_dest = os.path.join(_data_dir, "assets", "image_files")


# --- 1. Music Theory Engine ---
# This class handles all chord transpositions for scale and capo adjustments.
class MusicTheory:
    CHROMATIC_SHARP = ["A", "A#", "B", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#"]
    CHROMATIC_FLAT  = ["A", "Bb", "B", "C", "Db",  "D", "Eb",  "E", "F", "Gb",  "G", "Ab"]

    @staticmethod
    def _note_index(note):
        """Return (semitone_index, prefer_flat) for a note string like 'A', 'Bb', 'C#'."""
        if "#" in note:
            return MusicTheory.CHROMATIC_SHARP.index(note), False
        if "b" in note:
            return MusicTheory.CHROMATIC_FLAT.index(note), True
        # Natural note — same index in both scales
        return MusicTheory.CHROMATIC_SHARP.index(note), False

    @staticmethod
    def _index_to_note(idx, prefer_flat):
        """Return note name for a chromatic index, using flat or sharp based on preference."""
        sharp = MusicTheory.CHROMATIC_SHARP[idx % 12]
        flat  = MusicTheory.CHROMATIC_FLAT[idx % 12]
        # Return flat only when preferred AND the note is actually an accidental (not natural)
        return flat if (prefer_flat and flat != sharp) else sharp

    @staticmethod
    def _transpose_root(root, steps, prefer_flat):
        """Transpose a single root note string by steps semitones."""
        try:
            idx, _ = MusicTheory._note_index(root)
        except ValueError:
            return root
        return MusicTheory._index_to_note(idx + steps, prefer_flat)

    @staticmethod
    def transpose_chord(chord_str, steps):
        """Transpose a full chord string by `steps` semitones.

        Handles: Am, C#maj7, Bbsus4, G/B, F#m7b5, Dm7, Esus2, etc.
        Preserves the flat/sharp preference of the original chord root.
        Slash-chord bass notes (e.g. G/B) are also transposed.
        """
        if not chord_str or steps == 0:
            return chord_str

        match = re.match(r"^([A-G][b#]?)(.*)", chord_str)
        if not match:
            return chord_str

        root = match.group(1)
        rest = match.group(2)

        try:
            idx, prefer_flat = MusicTheory._note_index(root)
        except ValueError:
            return chord_str

        new_root = MusicTheory._index_to_note(idx + steps, prefer_flat)

        # Handle slash chords: e.g. "G/B", "Am/E", "C#maj7/F"
        slash_match = re.match(r"^(.*)/([A-G][b#]?)$", rest)
        if slash_match:
            quality = slash_match.group(1)
            bass    = slash_match.group(2)
            new_bass = MusicTheory._transpose_root(bass, steps, prefer_flat)
            return f"{new_root}{quality}/{new_bass}"

        return new_root + rest

    @staticmethod
    def transpose_line(line, steps):
        """Transpose all [chord] tokens in a lyric line in a single pass.

        Uses regex substitution to avoid the double-replacement bug that occurs
        when two chords in the same line share an enharmonic name after transposition.
        """
        if steps == 0:
            return line
        return re.sub(
            r"\[([A-G][b#]?[^\]]*)\]",
            lambda m: f"[{MusicTheory.transpose_chord(m.group(1), steps)}]",
            line,
        )


# --- 2. Main GUI Application ---
class SongSheetApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Song Sheet Generator")
        self.geometry("1200x800")

        # --- Initialize State & Parameters ---
        self.all_media_files = []  # A single list for all songs and images
        self.current_mode = "song"  # Can be 'song' or 'image'
        self.current_song_data = None
        self.current_media_name = ""
        self.current_file_path = ""
        self.original_capo = 0  # --- CHANGE 1: Added to store the capo from the file ---
        self.pil_image = None  # To hold the original, full-resolution PIL image
        self.pil_image_zoomed = None  # To hold the currently zoomed image for the projector
        self.projector_window = None  # To hold the external projector window
        self.projector_label = None
        self.projector_paused = False
        self.dark_mode = False
        self._pre_pause_snapshot = None  # saved state when pause is pressed

        # --- Theme Colors ---
        self.LIGHT = {
            "bg": (255, 255, 255), "text": (0, 0, 0), "chord": (180, 180, 180),
            "ui_bg": "#F0F0F0", "ui_fg": "#000000", "list_bg": "#FFFFFF",
            "list_sel": "#0078D7", "canvas_bg": "gray",
        }
        self.DARK = {
            "bg": (28, 28, 28), "text": (240, 240, 240), "chord": (140, 140, 140),
            "ui_bg": "#1C1C1C", "ui_fg": "#F0F0F0", "list_bg": "#2A2A2A",
            "list_sel": "#4A90D9", "canvas_bg": "#111111",
        }

        # --- Zoom State ---
        self.is_zoomed = False
        self.zoom_start_x = 0
        self.zoom_start_y = 0
        self.zoom_rect_id = None

        self.font_reg = os.path.join(fonts_dir, "NotoNaskhArabic-Regular.ttf")
        self.font_bold = os.path.join(fonts_dir, "NotoNaskhArabic-Bold.ttf")
        self.font_chord = os.path.join(fonts_dir, "ARIAL.TTF")
        self.font_english = os.path.join(fonts_dir, "ARIAL.TTF")
        self.font_english_bold = os.path.join(fonts_dir, "arial", "ARIALBD.TTF")

        self.params = {
            "lyric_font_size": tk.IntVar(value=46),
            "chord_font_size": tk.IntVar(value=24),
            "capo": tk.IntVar(value=0),
            "scale_steps": tk.IntVar(value=0),
            "show_chords": tk.BooleanVar(value=True),
            "scale_factor": 5,
            "title_font_size": 32,
            "capo_font_size": 14,
            "font_reg": self.font_reg,
            "font_bold": self.font_bold,
            "font_chord": self.font_chord,
            "font_english": self.font_english,
            "font_english_bold": self.font_english_bold,
            "transpose_steps": 0,
            "bg_color": self.LIGHT["bg"],
            "text_color": self.LIGHT["text"],
            "chord_color": self.LIGHT["chord"],
        }

        # --- Set base theme once so toggling colors never changes button shapes ---
        ttk.Style().theme_use("clam")

        # --- Create UI Layout ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)
        self._create_controls_panel()
        self._create_image_panel()
        self.load_media_files()

    def _create_controls_panel(self):
        controls_frame = ttk.Frame(self, padding="10")
        controls_frame.grid(row=0, column=0, sticky="nsew")
        controls_frame.grid_rowconfigure(0, weight=1)  # Allow paned window to expand
        controls_frame.grid_columnconfigure(0, weight=1)

        # --- Main Paned Window for resizable lists ---
        main_paned_window = ttk.PanedWindow(controls_frame, orient=tk.VERTICAL)
        main_paned_window.grid(row=0, column=0, sticky="nsew")

        # --- Top Pane: Unified Media Browser ---
        browser_pane = ttk.Frame(main_paned_window, padding=5)
        main_paned_window.add(browser_pane, weight=5)
        self._populate_media_browser(browser_pane)

        # --- Bottom Pane: Session List ---
        session_pane = ttk.Frame(main_paned_window, padding=5)
        main_paned_window.add(session_pane, weight=1)
        self._populate_session_list(session_pane)

        # --- Parameter Controls at the very bottom ---
        self.parameter_controls_frame = ttk.Frame(controls_frame)
        self.parameter_controls_frame.grid(row=1, column=0, sticky="ew")
        self._populate_parameter_controls()

    def _populate_media_browser(self, parent_frame):
        parent_frame.grid_rowconfigure(2, weight=1)
        parent_frame.grid_columnconfigure(0, weight=1)

        ttk.Label(parent_frame, text="Media Library", font=("Helvetica", 13, "bold")).grid(
            row=0, column=0, pady=(4, 2)
        )

        # Search bar with placeholder hint
        search_frame = ttk.Frame(parent_frame)
        search_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(2, 5))
        search_frame.grid_columnconfigure(0, weight=1)
        ttk.Label(search_frame, text="🔍").grid(row=0, column=0, sticky="w")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, font=("Helvetica", 12))
        search_entry.grid(row=1, column=0, sticky="ew", ipady=5)
        search_entry.bind("<Control-a>", lambda e: (e.widget.select_range(0, tk.END), e.widget.icursor(tk.END)) or "break")

        self.media_listbox = tk.Listbox(parent_frame, exportselection=False, font=("Helvetica", 13))
        self.media_listbox.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.media_listbox.bind("<<ListboxSelect>>", self.on_media_select)
        self.media_listbox.bind("<ButtonPress-1>", self._on_drag_start)
        self.media_listbox.bind("<B1-Motion>", self._on_drag_motion)
        self.media_listbox.bind("<ButtonRelease-1>", self._on_drag_release)
        self._drag_item = None
        self._drag_started = False

        # --- Action buttons for the browser ---
        button_frame = ttk.Frame(parent_frame)
        button_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=(2, 5))
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(button_frame, text="＋ Add to Session", command=self._add_to_session).grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=2, pady=(0, 2), ipady=2
        )
        ttk.Button(button_frame, text="📂 Import...", command=self._import_files).grid(
            row=1, column=0, sticky="ew", padx=2, ipady=2
        )
        ttk.Button(button_frame, text="✏️ New Song...", command=self._create_new_song).grid(
            row=1, column=1, sticky="ew", padx=2, ipady=2
        )

    def _populate_session_list(self, parent_frame):
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(1, weight=1)
        ttk.Label(parent_frame, text="Session", font=("Helvetica", 11, "bold")).grid(
            row=0, column=0, pady=(2, 1)
        )
        self.session_listbox = tk.Listbox(parent_frame, exportselection=False, font=("Helvetica", 12))
        self.session_listbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=2)
        self.session_listbox.bind("<<ListboxSelect>>", self.on_session_item_select)
        session_buttons_frame = ttk.Frame(parent_frame)
        session_buttons_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=(1, 2))
        session_buttons_frame.grid_columnconfigure(0, weight=1)
        session_buttons_frame.grid_columnconfigure(1, weight=1)
        session_buttons_frame.grid_columnconfigure(2, weight=2)
        ttk.Button(session_buttons_frame, text="▲", command=lambda: self._move_in_session(-1)).grid(
            row=0, column=0, sticky="ew", padx=2, ipady=1
        )
        ttk.Button(session_buttons_frame, text="▼", command=lambda: self._move_in_session(1)).grid(
            row=0, column=1, sticky="ew", padx=2, ipady=1
        )
        ttk.Button(session_buttons_frame, text="🗑 Remove", command=self._remove_from_session).grid(
            row=0, column=2, sticky="ew", padx=2, ipady=1
        )

    def _populate_parameter_controls(self):
        f = self.parameter_controls_frame

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=(6, 4))

        # --- Capo + Scale side by side ---
        transpose_frame = ttk.Frame(f)
        transpose_frame.pack(fill="x", padx=5, pady=1)
        transpose_frame.grid_columnconfigure(0, weight=1)
        transpose_frame.grid_columnconfigure(1, weight=1)
        self._create_stepper_grid(transpose_frame, "Capo", self.params["capo"], self.on_capo_change, col=0)
        self._create_stepper_grid(transpose_frame, "Scale", self.params["scale_steps"], self.on_scale_change, col=1)

        # --- Show Chords checkbox ---
        ttk.Checkbutton(
            f, text="Show Chords", variable=self.params["show_chords"], command=self.update_image
        ).pack(pady=3)

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=(3, 4))

        # --- Song actions ---
        song_frame = ttk.Frame(f)
        song_frame.pack(fill="x", padx=5, pady=1)
        song_frame.grid_columnconfigure(0, weight=1)
        song_frame.grid_columnconfigure(1, weight=1)
        self.set_default_button = ttk.Button(song_frame, text="Set as Default", command=self.set_as_default)
        self.set_default_button.grid(row=0, column=0, sticky="ew", padx=2, ipady=3)
        ttk.Button(song_frame, text="Export PNG", command=self.export_image).grid(
            row=0, column=1, sticky="ew", padx=2, ipady=3
        )

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=(4, 4))

        # --- Projector controls ---
        proj_frame = ttk.Frame(f)
        proj_frame.pack(fill="x", padx=5, pady=1)
        proj_frame.grid_columnconfigure(0, weight=1)
        proj_frame.grid_columnconfigure(1, weight=1)
        self.projector_button = ttk.Button(proj_frame, text="▶ Open Projector", command=self.open_projector_window)
        self.projector_button.grid(row=0, column=0, sticky="ew", padx=2, ipady=4)
        self.pause_button = ttk.Button(proj_frame, text="⏸ Pause", command=self._toggle_projector_pause)
        self.pause_button.grid(row=0, column=1, sticky="ew", padx=2, ipady=4)
        self.return_button = ttk.Button(f, text="↩ Return to Previous", command=self._return_to_pre_pause)
        # shown only while paused — pack_forget keeps it hidden initially

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=(4, 4))

        # --- Bottom utilities ---
        util_frame = ttk.Frame(f)
        util_frame.pack(fill="x", padx=5, pady=1)
        util_frame.grid_columnconfigure(0, weight=1)
        util_frame.grid_columnconfigure(1, weight=1)
        self.theme_button = ttk.Button(util_frame, text="🌙 Dark Mode", command=self._toggle_theme)
        self.theme_button.grid(row=0, column=0, sticky="ew", padx=2, ipady=3)
        ttk.Button(util_frame, text="Export All...", command=self._export_all_songs).grid(
            row=0, column=1, sticky="ew", padx=2, ipady=3
        )

    def _toggle_controls(self, state):
        widget_state = [state] if state == "disabled" else ["!disabled"]
        always_enabled = {self.set_default_button, self.projector_button, self.pause_button, self.theme_button, self.return_button}

        def apply(widget):
            for child in widget.winfo_children():
                if hasattr(child, "state") and child not in always_enabled:
                    child.state(widget_state)
                apply(child)

        apply(self.parameter_controls_frame)
        self.set_default_button.state(
            ["!disabled"] if self.current_mode == "song" else ["disabled"]
        )
        self.projector_button.state(["!disabled"])

    def _create_slider(self, parent, label_text, variable, from_, to):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=5)
        ttk.Label(frame, text=label_text).pack(side="left", padx=5)
        ttk.Scale(
            frame,
            from_=from_,
            to=to,
            variable=variable,
            orient="horizontal",
            command=lambda e: self.update_image(),
        ).pack(side="right", fill="x", expand=True)

    def _create_stepper_grid(self, parent, label_text, variable, command, col):
        """Stepper widget placed in a grid cell (for side-by-side layout)."""
        cell = ttk.Frame(parent)
        cell.grid(row=0, column=col, sticky="ew", padx=4)
        ttk.Label(cell, text=label_text, font=("Helvetica", 10, "bold")).pack()
        row = ttk.Frame(cell)
        row.pack()
        ttk.Button(row, text="−", width=3, command=lambda: command(-1)).pack(side="left", padx=1)
        ttk.Label(row, textvariable=variable, width=4, anchor="center").pack(side="left")
        ttk.Button(row, text="+", width=3, command=lambda: command(1)).pack(side="left", padx=1)

    def _create_stepper(self, parent, label_text, variable, command):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=5)
        ttk.Label(frame, text=label_text).pack(side="left", padx=5)
        ttk.Button(frame, text="-", width=3, command=lambda: command(-1)).pack(side="left", padx=2)
        label = ttk.Label(frame, textvariable=variable, width=4, anchor="center")
        label.pack(side="left")
        ttk.Button(frame, text="+", width=3, command=lambda: command(1)).pack(side="left", padx=2)

    def _create_image_panel(self):
        self.image_canvas = tk.Canvas(self, bg="gray")
        self.image_canvas.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.image_canvas.bind("<ButtonPress-1>", self._start_zoom)
        self.image_canvas.bind("<B1-Motion>", self._drag_zoom)
        self.image_canvas.bind("<ButtonRelease-1>", self._end_zoom)
        self.image_canvas.bind("<Double-Button-1>", self._reset_zoom)

    def load_media_files(self):
        self.all_media_files = []
        try:
            self.all_media_files.extend(
                sorted([f for f in os.listdir(song_dest) if f.endswith(".txt")])
            )
        except FileNotFoundError:
            print("'txt_files' directory not found.")
        try:
            self.all_media_files.extend(
                sorted(
                    [
                        f
                        for f in os.listdir(image_dest)
                        if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif"))
                    ]
                )
            )
        except FileNotFoundError:
            print("'image_files' directory not found.")
        self.all_media_files.sort()
        self._update_listbox(self.media_listbox, self.all_media_files)

    def _update_listbox(self, listbox, file_list):
        listbox.delete(0, tk.END)
        for item in file_list:
            listbox.insert(tk.END, item)

    def _on_search(self, *args):
        search_term = self.search_var.get().lower()
        if not search_term:
            self._update_listbox(self.media_listbox, self.all_media_files)
        else:
            filtered = [f for f in self.all_media_files if search_term in f.lower()]
            self._update_listbox(self.media_listbox, filtered)

    def _add_to_session(self):
        selection_indices = self.media_listbox.curselection()
        if not selection_indices:
            return
        selected_item = self.media_listbox.get(selection_indices[0])
        if selected_item not in self.session_listbox.get(0, tk.END):
            self.session_listbox.insert(tk.END, selected_item)

    def _remove_from_session(self):
        selection_indices = self.session_listbox.curselection()
        if not selection_indices:
            return
        self.session_listbox.delete(selection_indices[0])

    def _move_in_session(self, direction):
        selection_indices = self.session_listbox.curselection()
        if not selection_indices:
            return
        idx = selection_indices[0]
        new_idx = idx + direction
        if 0 <= new_idx < self.session_listbox.size():
            item = self.session_listbox.get(idx)
            self.session_listbox.delete(idx)
            self.session_listbox.insert(new_idx, item)
            self.session_listbox.selection_set(new_idx)

    def on_media_select(self, event):
        self._clear_other_selections(self.media_listbox)
        self._process_selection(self.media_listbox)

    def on_session_item_select(self, event):
        self._clear_other_selections(self.session_listbox)
        self._process_selection(self.session_listbox)

    def _clear_other_selections(self, current_listbox):
        if current_listbox != self.media_listbox:
            self.media_listbox.selection_clear(0, tk.END)
        if current_listbox != self.session_listbox:
            self.session_listbox.selection_clear(0, tk.END)

    def _process_selection(self, listbox):
        selection_indices = listbox.curselection()
        if not selection_indices:
            return

        selected_file = listbox.get(selection_indices[0])
        self.current_media_name = os.path.splitext(selected_file)[0]

        if selected_file.lower().endswith(".txt"):
            self.current_mode = "song"
            self._toggle_controls("!disabled")
            self.current_file_path = os.path.join(song_dest, selected_file)
            self._parse_song_file(self.current_file_path)
            self.params["scale_steps"].set(0)
            self.update_image()
        else:
            self.current_mode = "image"
            self._toggle_controls("disabled")
            self.current_file_path = os.path.join(image_dest, selected_file)
            try:
                self.pil_image = Image.open(self.current_file_path)
                self.update_image(is_static_image=True)
            except Exception as e:
                print(f"Error opening image {self.current_file_path}: {e}")
                self.pil_image = None
                self.image_canvas.delete("all")

    def on_capo_change(self, direction):
        self.params["capo"].set(self.params["capo"].get() + direction)
        self.update_image()

    def on_scale_change(self, direction):
        self.params["scale_steps"].set(self.params["scale_steps"].get() + direction)
        self.update_image()

    def update_image(self, is_static_image=False):
        if is_static_image:
            if not self.pil_image:
                return
            self.is_zoomed = False
        else:  # Is a song
            if not self.current_song_data:
                return
            self.is_zoomed = False
            gui_params = {
                key: var.get() if isinstance(var, (tk.IntVar, tk.BooleanVar)) else var
                for key, var in self.params.items()
            }

            # --- CHANGE 3: New logic for calculating transposition ---
            scale_transposition = gui_params["scale_steps"]
            capo_compensation = self.original_capo - gui_params["capo"]
            gui_params["transpose_steps"] = scale_transposition + capo_compensation

            song_data_for_render = self._get_transposed_song_data(gui_params)
            self.pil_image = create_arabic_song_image(song_data_for_render, gui_params)
            if not self.pil_image:
                return

        self._display_on_canvas(self.pil_image, self.image_canvas)
        self._update_projector_view()

    def _display_on_canvas(self, pil_img, canvas_widget):
        self.after(50, lambda: self._display_on_canvas_after_delay(pil_img, canvas_widget))

    def _display_on_canvas_after_delay(self, pil_img, canvas_widget):
        if not (canvas_widget and canvas_widget.winfo_exists()):
            return
        canvas_width = canvas_widget.winfo_width()
        canvas_height = canvas_widget.winfo_height()
        if canvas_width < 2 or canvas_height < 2:
            return

        img_copy = pil_img.copy()
        try:
            resample_filter = Image.Resampling.LANCZOS
        except AttributeError:
            resample_filter = Image.LANCZOS

        if canvas_widget == self.projector_label:
            img_w, img_h = img_copy.size
            ratio = min(canvas_width / img_w, canvas_height / img_h)
            new_w, new_h = int(img_w * ratio), int(img_h * ratio)
            img_copy = img_copy.resize((new_w, new_h), resample_filter)
        else:
            img_copy.thumbnail((canvas_width, canvas_height), resample_filter)

        tk_img = ImageTk.PhotoImage(img_copy)
        canvas_widget.delete("all")
        canvas_widget.create_image(
            canvas_width / 2, canvas_height / 2, image=tk_img, anchor="center"
        )
        canvas_widget.image = tk_img

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        theme = self.DARK if self.dark_mode else self.LIGHT
        self.params["bg_color"] = theme["bg"]
        self.params["text_color"] = theme["text"]
        self.params["chord_color"] = theme["chord"]
        self.theme_button.config(text="☀️ Light Mode" if self.dark_mode else "🌙 Dark Mode")
        self._apply_ui_theme(theme)
        if self.pil_image:
            self.update_image(is_static_image=(self.current_mode == "image"))

    def _apply_ui_theme(self, theme):
        style = ttk.Style()
        bg = theme["ui_bg"]
        fg = theme["ui_fg"]
        list_bg = theme["list_bg"]
        sel = theme["list_sel"]
        style.configure(".", background=bg, foreground=fg, fieldbackground=list_bg,
                         troughcolor=bg, bordercolor=bg)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=bg, foreground=fg)
        style.map("TButton", background=[("active", list_bg)])
        style.configure("TCheckbutton", background=bg, foreground=fg)
        style.configure("TScale", background=bg, troughcolor=list_bg)
        style.configure("TSeparator", background=fg)
        style.configure("TPanedwindow", background=bg)
        self.configure(bg=bg)
        self.image_canvas.config(bg=theme["canvas_bg"])
        for lb in (self.media_listbox, self.session_listbox):
            lb.config(bg=list_bg, fg=fg, selectbackground=sel,
                      selectforeground=fg if self.dark_mode else "#FFFFFF")
        if self.projector_window and self.projector_window.winfo_exists():
            proj_bg = "#000000" if self.dark_mode else "#FFFFFF"
            self.projector_window.configure(bg=proj_bg)
            self.projector_label.config(bg=proj_bg)

    def _toggle_projector_pause(self):
        self.projector_paused = not self.projector_paused
        if self.projector_paused:
            self.pause_button.config(text="▶ Resume")
            # Save current state so the user can return to it
            self._pre_pause_snapshot = {
                "file_path": self.current_file_path,
                "media_name": self.current_media_name,
                "mode": self.current_mode,
                "capo": self.params["capo"].get(),
                "scale_steps": self.params["scale_steps"].get(),
                "pil_image": self.pil_image,
            }
            # Show the return button right after the pause button's separator
            self.return_button.pack(fill="x", padx=5, pady=(2, 0), ipady=4,
                                    after=self.pause_button.master)
        else:
            self.pause_button.config(text="⏸ Pause")
            self._pre_pause_snapshot = None
            self.return_button.pack_forget()
            self._update_projector_view()  # push current preview to projector on resume

    def _return_to_pre_pause(self):
        """Restore the state that was active when Pause was pressed, then resume."""
        snap = self._pre_pause_snapshot
        if not snap:
            return
        # Restore params
        self.params["capo"].set(snap["capo"])
        self.params["scale_steps"].set(snap["scale_steps"])
        # Re-select the item in whichever listbox it lives in
        filename = os.path.basename(snap["file_path"]) if snap["file_path"] else None
        if filename:
            for lb in (self.media_listbox, self.session_listbox):
                items = list(lb.get(0, tk.END))
                if filename in items:
                    idx = items.index(filename)
                    lb.selection_clear(0, tk.END)
                    lb.selection_set(idx)
                    lb.see(idx)
                    self._process_selection(lb)
                    break
        # Resume projector (clears snapshot + hides return button)
        self.projector_paused = True   # trick _toggle to resume
        self._toggle_projector_pause()

    def _update_projector_view(self):
        if not (self.projector_window and self.projector_window.winfo_exists()):
            return
        if self.projector_paused:
            return
        image_to_show = self.pil_image_zoomed if self.is_zoomed else self.pil_image
        if image_to_show:
            self._display_on_canvas(image_to_show, self.projector_label)

    def _get_transposed_song_data(self, gui_params):
        steps = gui_params["transpose_steps"]
        song_data_for_render = []
        for section in self.current_song_data:
            if section["type"] != "lyrics_section":
                song_data_for_render.append(section)
            else:
                new_section = {"type": "lyrics_section", "title": section["title"], "lines": []}
                for line_info in section["lines"]:
                    new_section["lines"].append(
                        MusicTheory.transpose_line(line_info["line"], steps)
                    )
                song_data_for_render.append(new_section)
        return song_data_for_render

    def _parse_song_file(self, file_path):
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
        self.current_song_data = []
        current_section: dict | None = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("Title:"):
                self.current_song_data.append(
                    {"type": "title", "content": line.replace("Title:", "").strip()}
                )
            elif line.startswith("Capo:"):
                # --- CHANGE 2: Store the original capo from the file ---
                try:
                    capo_val = int(line.replace("Capo:", "").strip())
                    self.params["capo"].set(capo_val)
                    self.original_capo = capo_val
                except ValueError:
                    self.params["capo"].set(0)
                    self.original_capo = 0
                self.current_song_data.append({"type": "capo"})
            elif re.fullmatch(r"\[.*?\]", line):
                current_section = {"type": "lyrics_section", "title": line[1:-1], "lines": []}
                self.current_song_data.append(current_section)
            elif current_section is not None:
                chords = re.findall(r"\[(.*?)\]", line)
                current_section["lines"].append({"line": line, "chords": chords})

    def _import_files(self):
        title = "Import Media Files"
        filetypes = [
            ("All Media Files", "*.txt *.png *.jpg *.jpeg *.bmp *.gif"),
            ("Song Files", "*.txt"),
            ("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif"),
        ]

        filepaths = filedialog.askopenfilenames(title=title, filetypes=filetypes)

        if not filepaths:
            return

        if not os.path.exists(song_dest):
            os.makedirs(song_dest)
        if not os.path.exists(image_dest):
            os.makedirs(image_dest)

        copied_count = 0
        for src_path in filepaths:
            try:
                if src_path.lower().endswith(".txt"):
                    shutil.copy(src_path, song_dest)
                else:
                    shutil.copy(src_path, image_dest)
                copied_count += 1
            except Exception as e:
                messagebox.showerror(
                    "Import Error", f"Could not import {os.path.basename(src_path)}.\nError: {e}"
                )

        self.load_media_files()
        messagebox.showinfo("Import Complete", f"Successfully imported {copied_count} file(s).")

    def _create_new_song(self):
        song_title = simpledialog.askstring("New Song", "Enter the title for the new song:")
        if not song_title:
            return

        filename = f"{song_title}.txt"

        if not os.path.exists(song_dest):
            os.makedirs(song_dest)

        filepath = os.path.join(song_dest, filename)

        if os.path.exists(filepath):
            messagebox.showerror("Error", f"A song named '{filename}' already exists.")
            return

        template = (
            f"Title: {song_title}\n"
            "Capo: 0\n\n"
            "[Verse 1]\n"
            "Lyrics go here[C]\n"
            "More lyrics[G] here\n\n"
            "[Chorus]\n"
            "Chorus lyrics[Am] here\n"
        )

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(template)

            self.load_media_files()

            # Auto-select the new song in the list
            items = list(self.media_listbox.get(0, tk.END))
            if filename in items:
                idx = items.index(filename)
                self.media_listbox.selection_set(idx)
                self.media_listbox.see(idx)
                self._process_selection(self.media_listbox)

            if sys.platform == "win32":
                os.startfile(filepath)
            elif sys.platform == "darwin":  # macOS
                subprocess.call(["open", filepath])
            else:  # linux
                subprocess.call(["xdg-open", filepath])

        except Exception as e:
            messagebox.showerror("Error", f"Could not create the song file.\nError: {e}")

    def export_image(self):
        if not self.pil_image:
            return
        suggested_filename = f"{self.current_media_name}.png"
        filepath = filedialog.asksaveasfilename(
            initialfile=suggested_filename,
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")],
        )
        if filepath:
            try:
                self.pil_image.save(filepath)
                print(f"Image saved to: {filepath}")
            except Exception as e:
                print(f"Error saving image: {e}")

    def set_as_default(self):
        if not self.current_file_path:
            return
        transpose_steps = self.params["scale_steps"].get()
        new_capo = self.params["capo"].get()

        new_lines = []
        with open(self.current_file_path, encoding="utf-8") as f:
            original_lines = f.readlines()

        for line in original_lines:
            stripped_line = line.strip()
            if stripped_line.startswith("Capo:"):
                new_lines.append(f"Capo: {new_capo}\n")
            elif re.search(r"\[.*?\]", stripped_line) and not re.fullmatch(
                r"\[.*?\]", stripped_line
            ):
                new_lines.append(MusicTheory.transpose_line(stripped_line, transpose_steps) + "\n")
            else:
                new_lines.append(line)

        try:
            with open(self.current_file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            print(f"Successfully updated defaults for {os.path.basename(self.current_file_path)}")

            self.params["scale_steps"].set(0)
            self._parse_song_file(self.current_file_path)
            self.update_image()

        except Exception as e:
            print(f"Error updating file: {e}")

    def _on_drag_start(self, event):
        self._drag_item = None
        self._drag_started = False
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        # Read selection after the listbox finishes processing the click
        self.after_idle(self._record_drag_item)

    def _record_drag_item(self):
        sel = self.media_listbox.curselection()
        if sel:
            self._drag_item = self.media_listbox.get(sel[0])

    def _on_drag_motion(self, event):
        if not self._drag_started and self._drag_item:
            dx = abs(event.x - self._drag_start_x)
            dy = abs(event.y - self._drag_start_y)
            if dx > 8 or dy > 8:
                self._drag_started = True
                self.media_listbox.config(cursor="fleur")

    def _on_drag_release(self, event):
        self.media_listbox.config(cursor="")
        if not self._drag_started or not self._drag_item:
            self._drag_started = False
            self._drag_item = None
            return
        x_root = event.widget.winfo_rootx() + event.x
        y_root = event.widget.winfo_rooty() + event.y
        slb = self.session_listbox
        if (
            slb.winfo_rootx() <= x_root <= slb.winfo_rootx() + slb.winfo_width()
            and slb.winfo_rooty() <= y_root <= slb.winfo_rooty() + slb.winfo_height()
        ):
            if self._drag_item not in self.session_listbox.get(0, tk.END):
                self.session_listbox.insert(tk.END, self._drag_item)
        self._drag_started = False
        self._drag_item = None

    def _export_all_songs(self):
        output_dir = filedialog.askdirectory(title="Select Output Directory for Song Images")
        if not output_dir:
            return

        txt_files = [f for f in self.all_media_files if f.endswith(".txt")]
        if not txt_files:
            messagebox.showinfo("Export All", "No song files found.")
            return

        # Capture base params (fonts, colors, show_chords, etc.) — capo will be set per song
        base_params = {
            key: var.get() if isinstance(var, (tk.IntVar, tk.BooleanVar)) else var
            for key, var in self.params.items()
        }
        base_params["scale_steps"] = 0
        base_params["transpose_steps"] = 0

        success, errors = 0, []
        for filename in txt_files:
            try:
                file_path = os.path.join(song_dest, filename)
                self._parse_song_file(file_path)
                # Build per-song params with this file's actual capo
                song_params = dict(base_params)
                song_params["capo"] = self.params["capo"].get()
                # Convert raw song data (dicts) to render-ready strings via _get_transposed_song_data
                song_data_for_render = self._get_transposed_song_data(song_params)
                img = create_arabic_song_image(song_data_for_render, song_params)
                if img:
                    out_path = os.path.join(output_dir, os.path.splitext(filename)[0] + ".png")
                    img.save(out_path)
                    success += 1
            except Exception as e:
                errors.append(f"{filename}: {e}")

        msg = f"Exported {success} of {len(txt_files)} songs to:\n{output_dir}"
        if errors:
            msg += f"\n\nFailed ({len(errors)}):\n" + "\n".join(errors)
        messagebox.showinfo("Export All Songs", msg)

        # Restore the previously selected song state
        if self.current_file_path:
            self._parse_song_file(self.current_file_path)
            self.params["scale_steps"].set(0)
            self.update_image()

    def open_projector_window(self):
        if self.projector_window and self.projector_window.winfo_exists():
            self.projector_window.lift()
            return
        self.projector_window = tk.Toplevel(self)
        self.projector_window.title(f"Projector View - {self.current_media_name}")
        self.projector_window.attributes("-fullscreen", False)
        self.projector_window.bind("<Escape>", self._exit_fullscreen)
        self.projector_label = tk.Canvas(self.projector_window, bg="white", highlightthickness=0)
        self.projector_label.pack(expand=True, fill="both")
        self.projector_window.after(100, self._update_projector_view)
        self.projector_window.protocol("WM_DELETE_WINDOW", self.on_projector_close)

    def _exit_fullscreen(self, event=None):
        if self.projector_window:
            self.projector_window.attributes("-fullscreen", False)

    def on_projector_close(self):
        if self.projector_window:
            self.projector_window.destroy()
            self.projector_window = None
            self.projector_label = None

    def _reset_zoom(self, event):
        self.is_zoomed = False
        self._update_projector_view()

    def _start_zoom(self, event):
        self.zoom_start_x = self.image_canvas.canvasx(event.x)
        self.zoom_start_y = self.image_canvas.canvasy(event.y)
        if self.zoom_rect_id:
            self.image_canvas.delete(self.zoom_rect_id)
        self.zoom_rect_id = self.image_canvas.create_rectangle(
            self.zoom_start_x,
            self.zoom_start_y,
            self.zoom_start_x,
            self.zoom_start_y,
            outline="red",
            width=2,
            dash=(4, 4),
        )

    def _drag_zoom(self, event):
        if not self.zoom_rect_id:
            return
        cur_x = self.image_canvas.canvasx(event.x)
        cur_y = self.image_canvas.canvasy(event.y)
        self.image_canvas.coords(
            self.zoom_rect_id, self.zoom_start_x, self.zoom_start_y, cur_x, cur_y
        )

    def _end_zoom(self, event):
        if not self.zoom_rect_id:
            return
        x1, y1, x2, y2 = self.image_canvas.coords(self.zoom_rect_id)
        self.image_canvas.delete(self.zoom_rect_id)
        self.zoom_rect_id = None
        x1, x2 = sorted((x1, x2))
        y1, y2 = sorted((y1, y2))
        if abs(x1 - x2) < 10 or abs(y1 - y2) < 10:
            return

        if not self.pil_image:
            return

        displayed_image = self.image_canvas.image  # pylint: disable=no-member
        disp_w, disp_h = displayed_image.width(), displayed_image.height()
        canvas_w, canvas_h = self.image_canvas.winfo_width(), self.image_canvas.winfo_height()
        offset_x = (canvas_w - disp_w) / 2
        offset_y = (canvas_h - disp_h) / 2

        img_x1 = x1 - offset_x
        img_y1 = y1 - offset_y

        ratio = self.pil_image.width / disp_w

        crop_x1 = int(img_x1 * ratio)
        crop_y1 = int(img_y1 * ratio)
        crop_x2 = crop_x1 + int(abs(x1 - x2) * ratio)
        crop_y2 = crop_y1 + int(abs(y1 - y2) * ratio)

        # Handle out-of-bounds zooming (panning past edges) with white background
        desired_w = crop_x2 - crop_x1
        desired_h = crop_y2 - crop_y1
        
        # Create a white background image of the desired size
        zoomed_img = Image.new("RGB", (desired_w, desired_h), (255, 255, 255))
        
        # Calculate intersection with the actual image
        src_w, src_h = self.pil_image.size
        inter_x1 = max(0, crop_x1)
        inter_y1 = max(0, crop_y1)
        inter_x2 = min(src_w, crop_x2)
        inter_y2 = min(src_h, crop_y2)
        
        if inter_x2 > inter_x1 and inter_y2 > inter_y1:
            patch = self.pil_image.crop((inter_x1, inter_y1, inter_x2, inter_y2))
            paste_x = inter_x1 - crop_x1
            paste_y = inter_y1 - crop_y1
            zoomed_img.paste(patch, (paste_x, paste_y))

        self.pil_image_zoomed = zoomed_img
        self.is_zoomed = True

        self._update_projector_view()
