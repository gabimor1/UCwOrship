import re
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import shutil
import sys
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageTk
import arabic_reshaper
from bidi.algorithm import get_display

# This line IMPORTS your perfected image creation function from your script.
# Make sure 'image_automation_script.py' is in the same folder.
from image_automation_script import create_arabic_song_image

# --- 1. Music Theory Engine ---
# This class handles all chord transpositions for scale and capo adjustments.
class MusicTheory:
    NOTES_SHARP = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']
    NOTES_FLAT = ['A', 'Bb', 'B', 'C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab']

    @staticmethod
    def transpose_chord(chord_str, steps):
        if not chord_str or steps == 0:
            return chord_str
            
        match = re.match(r'([A-G][b#]?)', chord_str)
        if not match: return chord_str

        root = match.group(1)
        quality = chord_str[len(root):]

        try:
            if '#' in root or (len(root) == 1 and root not in ['B', 'E']):
                scale = MusicTheory.NOTES_SHARP
                current_index = scale.index(root)
            else:
                scale = MusicTheory.NOTES_FLAT
                current_index = scale.index(root)
        except ValueError:
            return chord_str

        new_index = (current_index + steps) % 12
        new_root = MusicTheory.NOTES_SHARP[new_index] # Always return sharp for consistency
        return new_root + quality

# --- 2. Main GUI Application ---
class SongSheetApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Song Sheet Generator")
        self.geometry("1200x800")

        # --- Initialize State & Parameters ---
        self.all_media_files = [] # A single list for all songs and images
        self.current_mode = 'song' # Can be 'song' or 'image'
        self.current_song_data = None
        self.current_media_name = ""
        self.current_file_path = ""
        self.pil_image = None # To hold the original, full-resolution PIL image
        self.pil_image_zoomed = None # To hold the currently zoomed image for the projector
        self.projector_window = None # To hold the external projector window
        self.projector_label = None
        
        # --- Zoom State ---
        self.is_zoomed = False
        self.zoom_start_x = 0
        self.zoom_start_y = 0
        self.zoom_rect_id = None
        
        self.font_reg = "fonts/NotoNaskhArabic-Regular.ttf"
        self.font_bold = "fonts/NotoNaskhArabic-Bold.ttf"
        self.font_chord = "fonts/ARIAL.TTF"
        
        self.params = {
            'lyric_font_size': tk.IntVar(value=56),
            'chord_font_size': tk.IntVar(value=24),
            'capo': tk.IntVar(value=0),
            'scale_steps': tk.IntVar(value=0),
            'show_chords': tk.BooleanVar(value=True),
            'scale_factor': 10,
            'title_font_size': 32,
            'capo_font_size': 14,
            'font_reg': self.font_reg,
            'font_bold': self.font_bold,
            'font_chord': self.font_chord,
            'transpose_steps': 0
        }
        
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
        controls_frame.grid_rowconfigure(0, weight=1) # Allow paned window to expand
        controls_frame.grid_columnconfigure(0, weight=1)

        # --- Main Paned Window for resizable lists ---
        main_paned_window = ttk.PanedWindow(controls_frame, orient=tk.VERTICAL)
        main_paned_window.grid(row=0, column=0, sticky="nsew")

        # --- Top Pane: Unified Media Browser ---
        browser_pane = ttk.Frame(main_paned_window, padding=5)
        main_paned_window.add(browser_pane, weight=1)
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
        ttk.Label(parent_frame, text="Media Library", font=("Helvetica", 12, "bold")).grid(row=0, column=0, pady=5)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search)
        search_entry = ttk.Entry(parent_frame, textvariable=self.search_var)
        search_entry.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        self.media_listbox = tk.Listbox(parent_frame, exportselection=False)
        self.media_listbox.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.media_listbox.bind("<<ListboxSelect>>", self.on_media_select)
        
        # --- Action buttons for the browser ---
        button_frame = ttk.Frame(parent_frame)
        button_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=5)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        button_frame.grid_columnconfigure(2, weight=1)
        ttk.Button(button_frame, text="Add to Session ↓", command=self._add_to_session).grid(row=0, column=0, sticky="ew", padx=2)
        ttk.Button(button_frame, text="Import Media...", command=self._import_files).grid(row=0, column=1, sticky="ew", padx=2)
        ttk.Button(button_frame, text="Create Song...", command=self._create_new_song).grid(row=0, column=2, sticky="ew", padx=2)

    def _populate_session_list(self, parent_frame):
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(1, weight=1)
        ttk.Label(parent_frame, text="Session List", font=("Helvetica", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=5)
        self.session_listbox = tk.Listbox(parent_frame, exportselection=False)
        self.session_listbox.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        self.session_listbox.bind("<<ListboxSelect>>", self.on_session_item_select)
        session_buttons_frame = ttk.Frame(parent_frame)
        session_buttons_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        session_buttons_frame.grid_columnconfigure(0, weight=1); session_buttons_frame.grid_columnconfigure(1, weight=1); session_buttons_frame.grid_columnconfigure(2, weight=1)
        ttk.Button(session_buttons_frame, text="▲", command=lambda: self._move_in_session(-1)).grid(row=0, column=0, sticky="ew")
        ttk.Button(session_buttons_frame, text="▼", command=lambda: self._move_in_session(1)).grid(row=0, column=1, sticky="ew")
        ttk.Button(session_buttons_frame, text="Remove", command=self._remove_from_session).grid(row=0, column=2, sticky="ew")

    def _populate_parameter_controls(self):
        ttk.Separator(self.parameter_controls_frame, orient='horizontal').pack(fill='x', pady=15)
        ttk.Label(self.parameter_controls_frame, text="Controls", font=("Helvetica", 14, "bold")).pack(pady=5)
        self._create_slider(self.parameter_controls_frame, "Lyrics Font Size", self.params['lyric_font_size'], 10, 80)
        self._create_slider(self.parameter_controls_frame, "Chords Font Size", self.params['chord_font_size'], 8, 50)
        ttk.Checkbutton(self.parameter_controls_frame, text="Show Chords", variable=self.params['show_chords'], command=self.update_image).pack(pady=10)
        ttk.Separator(self.parameter_controls_frame, orient='horizontal').pack(fill='x', pady=15)
        self._create_stepper(self.parameter_controls_frame, "Capo", self.params['capo'], self.on_capo_change)
        self._create_stepper(self.parameter_controls_frame, "Scale", self.params['scale_steps'], self.on_scale_change)
        ttk.Separator(self.parameter_controls_frame, orient='horizontal').pack(fill='x', pady=15)
        action_frame = ttk.Frame(self.parameter_controls_frame)
        action_frame.pack(fill='x', pady=5)
        self.set_default_button = ttk.Button(action_frame, text="Set as Default", command=self.set_as_default)
        self.set_default_button.pack(side="left", expand=True, fill='x', padx=2, ipady=5)
        ttk.Button(action_frame, text="Export as PNG", command=self.export_image).pack(side="left", expand=True, fill='x', padx=2, ipady=5)
        ttk.Button(action_frame, text="Open Projector", command=self.open_projector_window).pack(side="left", expand=True, fill='x', padx=2, ipady=5)

    def _toggle_controls(self, state):
        widget_state = [state] if state == 'disabled' else ['!disabled']
        for child in self.parameter_controls_frame.winfo_children():
            if hasattr(child, 'state'):
                if child != self.set_default_button:
                    child.state(widget_state)
            if isinstance(child, (ttk.Frame)):
                 for sub_child in child.winfo_children():
                    if hasattr(sub_child, 'state'): sub_child.state(widget_state)
        self.set_default_button.state(['!disabled'] if self.current_mode == 'song' else ['disabled'])

    def _create_slider(self, parent, label_text, variable, from_, to):
        frame = ttk.Frame(parent); frame.pack(fill='x', pady=5)
        ttk.Label(frame, text=label_text).pack(side="left", padx=5)
        ttk.Scale(frame, from_=from_, to=to, variable=variable, orient="horizontal", command=lambda e: self.update_image()).pack(side="right", fill="x", expand=True)

    def _create_stepper(self, parent, label_text, variable, command):
        frame = ttk.Frame(parent); frame.pack(fill='x', pady=5)
        ttk.Label(frame, text=label_text).pack(side="left", padx=5)
        ttk.Button(frame, text="-", width=3, command=lambda: command(-1)).pack(side="left", padx=2)
        label = ttk.Label(frame, textvariable=variable, width=4, anchor="center"); label.pack(side="left")
        ttk.Button(frame, text="+", width=3, command=lambda: command(1)).pack(side="left", padx=2)

    def _create_image_panel(self):
        self.image_canvas = tk.Canvas(self, bg="gray")
        self.image_canvas.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        # Bind events for zoom functionality
        self.image_canvas.bind("<ButtonPress-1>", self._start_zoom)
        self.image_canvas.bind("<B1-Motion>", self._drag_zoom)
        self.image_canvas.bind("<ButtonRelease-1>", self._end_zoom)
        self.image_canvas.bind("<Double-Button-1>", self._reset_zoom)

    def load_media_files(self):
        self.all_media_files = []
        try:
            txt_dir = "txt_files"
            self.all_media_files.extend(sorted([f for f in os.listdir(txt_dir) if f.endswith('.txt')]))
        except FileNotFoundError: print("'txt_files' directory not found.")
        try:
            img_dir = "image_files"
            self.all_media_files.extend(sorted([f for f in os.listdir(img_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]))
        except FileNotFoundError: print("'image_files' directory not found.")
        
        self.all_media_files.sort()
        self._update_listbox(self.media_listbox, self.all_media_files)

    def _update_listbox(self, listbox, file_list):
        listbox.delete(0, tk.END)
        for item in file_list: listbox.insert(tk.END, item)

    def _on_search(self, *args):
        search_term = self.search_var.get().lower()
        if not search_term: self._update_listbox(self.media_listbox, self.all_media_files)
        else:
            filtered = [f for f in self.all_media_files if search_term in f.lower()]
            self._update_listbox(self.media_listbox, filtered)

    def _add_to_session(self):
        selection_indices = self.media_listbox.curselection()
        if not selection_indices: return
        selected_item = self.media_listbox.get(selection_indices[0])
        if selected_item not in self.session_listbox.get(0, tk.END):
            self.session_listbox.insert(tk.END, selected_item)

    def _remove_from_session(self):
        selection_indices = self.session_listbox.curselection()
        if not selection_indices: return
        self.session_listbox.delete(selection_indices[0])

    def _move_in_session(self, direction):
        selection_indices = self.session_listbox.curselection()
        if not selection_indices: return
        idx = selection_indices[0]; new_idx = idx + direction
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
        if current_listbox != self.media_listbox: self.media_listbox.selection_clear(0, tk.END)
        if current_listbox != self.session_listbox: self.session_listbox.selection_clear(0, tk.END)

    def _process_selection(self, listbox):
        selection_indices = listbox.curselection()
        if not selection_indices: return
        
        selected_file = listbox.get(selection_indices[0])
        self.current_media_name = os.path.splitext(selected_file)[0]
        
        if selected_file.lower().endswith('.txt'):
            self.current_mode = 'song'
            self._toggle_controls('!disabled')
            self.current_file_path = os.path.join("txt_files", selected_file)
            self._parse_song_file(self.current_file_path)
            self.params['scale_steps'].set(0)
            self.update_image()
        else:
            self.current_mode = 'image'
            self._toggle_controls('disabled')
            self.current_file_path = os.path.join("image_files", selected_file)
            try:
                self.pil_image = Image.open(self.current_file_path)
                self.update_image(is_static_image=True)
            except Exception as e:
                print(f"Error opening image {self.current_file_path}: {e}")
                self.pil_image = None; self.image_canvas.delete("all")
    
    def on_capo_change(self, direction):
        self.params['capo'].set(self.params['capo'].get() + direction)
        self.update_image()
        
    def on_scale_change(self, direction):
        self.params['scale_steps'].set(self.params['scale_steps'].get() + direction)
        self.update_image()

    def update_image(self, is_static_image=False):
        if is_static_image:
            if not self.pil_image: return
            self.is_zoomed = False
        else: # Is a song
            if not self.current_song_data: return
            self.is_zoomed = False
            gui_params = {key: var.get() if isinstance(var, (tk.IntVar, tk.BooleanVar)) else var for key, var in self.params.items()}
            gui_params['transpose_steps'] = gui_params['scale_steps'] - gui_params['capo']
            song_data_for_render = self._get_transposed_song_data(gui_params)
            self.pil_image = create_arabic_song_image(song_data_for_render, gui_params)
            if not self.pil_image: return

        self._display_on_canvas(self.pil_image, self.image_canvas)
        self._update_projector_view()

    def _display_on_canvas(self, pil_img, canvas_widget):
        self.after(50, lambda: self._display_on_canvas_after_delay(pil_img, canvas_widget))

    def _display_on_canvas_after_delay(self, pil_img, canvas_widget):
        if not (canvas_widget and canvas_widget.winfo_exists()): return
        canvas_width = canvas_widget.winfo_width()
        canvas_height = canvas_widget.winfo_height()
        if canvas_width < 2 or canvas_height < 2: return

        img_copy = pil_img.copy()
        try: resample_filter = Image.Resampling.LANCZOS
        except AttributeError: resample_filter = Image.LANCZOS

        if canvas_widget == self.projector_label:
            img_w, img_h = img_copy.size
            ratio = min(canvas_width / img_w, canvas_height / img_h)
            new_w, new_h = int(img_w * ratio), int(img_h * ratio)
            img_copy = img_copy.resize((new_w, new_h), resample_filter)
        else:
            img_copy.thumbnail((canvas_width, canvas_height), resample_filter)
        
        tk_img = ImageTk.PhotoImage(img_copy)
        canvas_widget.delete("all")
        canvas_widget.create_image(canvas_width / 2, canvas_height / 2, image=tk_img, anchor="center")
        canvas_widget.image = tk_img

    def _update_projector_view(self):
        if not (self.projector_window and self.projector_window.winfo_exists()): return
        image_to_show = self.pil_image_zoomed if self.is_zoomed else self.pil_image
        if image_to_show: self._display_on_canvas(image_to_show, self.projector_label)

    def _get_transposed_song_data(self, gui_params):
        song_data_for_render = []
        for section in self.current_song_data:
            if section['type'] != 'lyrics_section':
                song_data_for_render.append(section)
            else:
                new_section = {'type': 'lyrics_section', 'title': section['title'], 'lines': []}
                for line_info in section['lines']:
                    transposed_line = line_info['line']
                    transposed_chords = [MusicTheory.transpose_chord(c, gui_params['transpose_steps']) for c in line_info['chords']]
                    for original, transposed in zip(line_info['chords'], transposed_chords):
                        transposed_line = transposed_line.replace(f"[{original}]", f"[{transposed}]", 1)
                    new_section['lines'].append(transposed_line)
                song_data_for_render.append(new_section)
        return song_data_for_render

    def _parse_song_file(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f: lines = f.readlines()
        self.current_song_data = []
        current_section = None
        for line in lines:
            line = line.strip()
            if not line: continue
            if line.startswith("Title:"): self.current_song_data.append({'type': 'title', 'content': line.replace("Title:", "").strip()})
            elif line.startswith("Capo:"):
                try: self.params['capo'].set(int(line.replace('Capo:', '').strip()))
                except ValueError: self.params['capo'].set(0)
                self.current_song_data.append({'type': 'capo'})
            elif re.fullmatch(r'\[.*?\]', line):
                current_section = {'type': 'lyrics_section', 'title': line[1:-1], 'lines': []}
                self.current_song_data.append(current_section)
            elif current_section:
                chords = re.findall(r'\[(.*?)\]', line)
                current_section['lines'].append({'line': line, 'chords': chords})
    
    def _import_files(self):
        title = "Import Media Files"
        filetypes = [
            ("All Media Files", "*.txt *.png *.jpg *.jpeg *.bmp *.gif"),
            ("Song Files", "*.txt"),
            ("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif")
        ]
        
        filepaths = filedialog.askopenfilenames(title=title, filetypes=filetypes)
        
        if not filepaths: return

        song_dest = "txt_files"
        image_dest = "image_files"
        if not os.path.exists(song_dest): os.makedirs(song_dest)
        if not os.path.exists(image_dest): os.makedirs(image_dest)

        copied_count = 0
        for src_path in filepaths:
            try:
                if src_path.lower().endswith('.txt'):
                    shutil.copy(src_path, song_dest)
                else:
                    shutil.copy(src_path, image_dest)
                copied_count += 1
            except Exception as e:
                messagebox.showerror("Import Error", f"Could not import {os.path.basename(src_path)}.\nError: {e}")

        self.load_media_files()
        messagebox.showinfo("Import Complete", f"Successfully imported {copied_count} file(s).")

    def _create_new_song(self):
        song_title = simpledialog.askstring("New Song", "Enter the title for the new song:")
        if not song_title:
            return

        filename = f"{song_title}.txt"
        
        dest_folder = "txt_files"
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)
            
        filepath = os.path.join(dest_folder, filename)

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
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(template)

            self.load_media_files()
            
            if sys.platform == "win32":
                os.startfile(filepath)
            elif sys.platform == "darwin": # macOS
                subprocess.call(["open", filepath])
            else: # linux
                subprocess.call(["xdg-open", filepath])

        except Exception as e:
            messagebox.showerror("Error", f"Could not create the song file.\nError: {e}")


    def export_image(self):
        if not self.pil_image: return
        suggested_filename = f"{self.current_media_name}.png"
        filepath = filedialog.asksaveasfilename(initialfile=suggested_filename, defaultextension=".png", filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")])
        if filepath:
            try: self.pil_image.save(filepath); print(f"Image saved to: {filepath}")
            except Exception as e: print(f"Error saving image: {e}")

    def set_as_default(self):
        if not self.current_file_path or self.current_mode != 'song': return
        transpose_steps = self.params['scale_steps'].get()
        new_capo = self.params['capo'].get()
        new_lines = []
        with open(self.current_file_path, 'r', encoding='utf-8') as f: original_lines = f.readlines()
        for line in original_lines:
            stripped_line = line.strip()
            if stripped_line.startswith("Capo:"): new_lines.append(f"Capo: {new_capo}\n")
            elif re.search(r'\[.*?\]', stripped_line) and not re.fullmatch(r'\[.*?\]', stripped_line):
                original_chords = re.findall(r'\[(.*?)\]', stripped_line)
                new_line = stripped_line
                for chord in original_chords:
                    transposed = MusicTheory.transpose_chord(chord, transpose_steps)
                    new_line = new_line.replace(f"[{chord}]", f"[{transposed}]", 1)
                new_lines.append(new_line + '\n')
            else: new_lines.append(line)
        try:
            with open(self.current_file_path, 'w', encoding='utf-8') as f: f.writelines(new_lines)
            print(f"Successfully updated defaults for {os.path.basename(self.current_file_path)}")
            self.params['scale_steps'].set(0)
            self._parse_song_file(self.current_file_path)
            self.update_image()
        except Exception as e: print(f"Error updating file: {e}")

    def open_projector_window(self):
        if self.projector_window and self.projector_window.winfo_exists():
            self.projector_window.lift()
            return
        self.projector_window = tk.Toplevel(self)
        self.projector_window.title(f"Projector View - {self.current_media_name}")
        self.projector_window.attributes('-fullscreen', True)
        self.projector_window.bind('<Escape>', self._exit_fullscreen)
        self.projector_label = tk.Canvas(self.projector_window, bg='white', highlightthickness=0)
        self.projector_label.pack(expand=True, fill="both")
        self.projector_window.after(100, self._update_projector_view)
        self.projector_window.protocol("WM_DELETE_WINDOW", self.on_projector_close)

    def _exit_fullscreen(self, event=None):
        if self.projector_window: self.projector_window.attributes('-fullscreen', False)

    def on_projector_close(self):
        if self.projector_window:
            self.projector_window.destroy()
            self.projector_window = None
            self.projector_label = None

    def _reset_zoom(self, event):
        """ Resets zoom on double-click """
        self.is_zoomed = False
        self._update_projector_view()

    def _start_zoom(self, event):
        self.zoom_start_x = self.image_canvas.canvasx(event.x)
        self.zoom_start_y = self.image_canvas.canvasy(event.y)
        if self.zoom_rect_id: self.image_canvas.delete(self.zoom_rect_id)
        self.zoom_rect_id = self.image_canvas.create_rectangle(
            self.zoom_start_x, self.zoom_start_y, self.zoom_start_x, self.zoom_start_y,
            outline='red', width=2, dash=(4, 4)
        )

    def _drag_zoom(self, event):
        if not self.zoom_rect_id: return
        cur_x = self.image_canvas.canvasx(event.x)
        cur_y = self.image_canvas.canvasy(event.y)
        self.image_canvas.coords(self.zoom_rect_id, self.zoom_start_x, self.zoom_start_y, cur_x, cur_y)

    def _end_zoom(self, event):
        if not self.zoom_rect_id: return
        x1, y1, x2, y2 = self.image_canvas.coords(self.zoom_rect_id)
        self.image_canvas.delete(self.zoom_rect_id)
        self.zoom_rect_id = None
        x1, x2 = sorted((x1, x2)); y1, y2 = sorted((y1, y2))
        if abs(x1 - x2) < 10 or abs(y1 - y2) < 10: return

        if not self.pil_image: return

        displayed_image = self.image_canvas.image
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
        
        self.pil_image_zoomed = self.pil_image.crop((crop_x1, crop_y1, crop_x2, crop_y2))
        self.is_zoomed = True
        
        self._update_projector_view()

if __name__ == "__main__":
    app = SongSheetApp()
    app.mainloop()
