import re
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

def create_arabic_song_image(song_data, params):
    """
    Generates a right-to-left song sheet image from pre-parsed song data and GUI parameters.
    This is your perfected logic, adapted to be called as a function.
    """
    # --- 1. Unpack GUI Parameters ---
    scale_factor = 4
    lyric_font_size = params['lyric_font_size']
    chord_font_size = params['chord_font_size']
    title_font_size = params['title_font_size']
    capo_font_size = params['capo_font_size']
    show_chords = params['show_chords']
    arabic_font_path = params['font_reg']
    arabic_bold_font_path = params['font_bold']
    chord_font_path = params['font_chord']

    # --- 2. Define Styles & Quality (from your script) ---
    image_width = 850
    padding = 130
    line_spacing = 18
    section_spacing = 70
    
    image_width_scaled = image_width * scale_factor
    padding_scaled = padding * scale_factor
    line_spacing_scaled = line_spacing * scale_factor
    section_spacing_scaled = section_spacing * scale_factor
    
    background_color = (255, 255, 255)
    text_color = (0, 0, 0)
    chord_color = (180, 180, 180)
    
    # --- 3. Load Fonts (Scaled) ---
    try:
        title_font = ImageFont.truetype(arabic_bold_font_path, title_font_size * scale_factor)
        lyric_font = ImageFont.truetype(arabic_font_path, lyric_font_size * scale_factor)
        bold_lyric_font = ImageFont.truetype(arabic_bold_font_path, lyric_font_size * scale_factor)
        chord_font = ImageFont.truetype(chord_font_path, chord_font_size * scale_factor)
        capo_font = ImageFont.truetype(arabic_font_path, capo_font_size * scale_factor)
    except IOError as e:
        print(f"Error loading font: {e}. Please check your font paths. Aborting.")
        return None

    # --- 4. Prepare High-Resolution Image Canvas ---
    temp_height = 4000 * scale_factor
    img = Image.new('RGB', (image_width_scaled, temp_height), color=background_color)
    draw = ImageDraw.Draw(img)
    y_position = padding_scaled
    x_size = 0
    
    # --- Pre-calculation loop to find the widest line (from your script) ---
    max_line_size = 0
    for section in song_data:
        if section['type'] == 'lyrics_section':
            is_chorus = 'chorus' in section['title'].lower()
            current_lyric_font = bold_lyric_font if is_chorus else lyric_font
            for line in section['lines']:
                clean_lyric_line = re.sub(r'\[.*?\]', '', line)
                reshaped_clean_line = get_display(arabic_reshaper.reshape(clean_lyric_line))
                total_lyric_width = draw.textlength(reshaped_clean_line, font=current_lyric_font)
                if total_lyric_width > max_line_size:
                    max_line_size = total_lyric_width

    # --- 5. Draw Each Section with Right-to-Left Logic ---
    for section in song_data:
        sec_type = section['type']

        if sec_type == 'title':
            bidi_text = get_display(arabic_reshaper.reshape(section['content']))
            text_width = draw.textlength(bidi_text, font=title_font)
            if text_width > x_size: x_size = text_width
            draw.text((image_width_scaled / 2, y_position), bidi_text, font=title_font, fill=text_color, anchor="mt")
            y_position += title_font.getbbox(bidi_text)[3] + line_spacing_scaled
        
        elif sec_type == 'capo':
            capo_text = f"Capo: {params['capo']}"
            text_width = draw.textlength(capo_text, font=capo_font)
            if text_width > x_size: x_size = text_width
            draw.text((padding*2, y_position), capo_text, font=capo_font, fill=text_color, anchor="mt")
            y_position += capo_font.getbbox(capo_text)[3] + section_spacing_scaled

        elif sec_type == 'lyrics_section':
            is_chorus = 'chorus' in section['title'].lower()
            current_lyric_font = bold_lyric_font if is_chorus else lyric_font
            
            for line in section['lines']:
                clean_lyric_line = re.sub(r'\[.*?\]', '', line)
                reshaped_clean_line = get_display(arabic_reshaper.reshape(clean_lyric_line))
                
                segments = [s for s in re.split(r'(\[.*?\])', line) if s]
                
                lyric_y_pos = y_position + chord_font.getbbox("Cm")[3]

                total_lyric_width = draw.textlength(reshaped_clean_line, font=current_lyric_font)
                offset_to_center = (max_line_size - total_lyric_width) / 2
                
                draw.text((image_width_scaled - padding_scaled - offset_to_center, lyric_y_pos), reshaped_clean_line, font=current_lyric_font, fill=text_color, anchor="ra")

                if show_chords:
                    x_calculator = image_width_scaled - padding_scaled - offset_to_center
                    reshaped_lyric_cursor = len(reshaped_clean_line)
                    
                    for segment in segments:
                        move_chords = 0
                        if not re.fullmatch(r'\[.*?\]', segment):
                            segment_len = len(segment)
                            shaped_substring = reshaped_clean_line[reshaped_lyric_cursor - segment_len : reshaped_lyric_cursor]
                            #print(shaped_substring)
                            #move_chords = draw.textlength(shaped_substring[:-1], font=current_lyric_font)
                            reshaped_lyric_cursor -= segment_len
                            lyric_width = draw.textlength(shaped_substring, font=current_lyric_font)
                            x_calculator -= lyric_width
                        else:
                            chord_text = segment[1:-1]
                            #if len(chord_text) > 1: x_calculator += draw.textlength(chord_text[1:], font=chord_font)
                            #x_calculator += move_chords
                            draw.text((x_calculator, y_position), chord_text, font=chord_font, fill=chord_color, anchor="ra")
                            #x_calculator -= move_chords
                            #if len(chord_text) > 1: x_calculator -= draw.textlength(chord_text[1:], font=chord_font)

                y_position += current_lyric_font.getbbox("Sample")[3] + chord_font.getbbox("Cm")[3] + line_spacing_scaled
            y_position += section_spacing_scaled

    # --- 6. Crop, Resize, and Return Final Image ---
    final_image_scaled = img.crop((0, 0, image_width_scaled, y_position))
    final_width = int(final_image_scaled.width / scale_factor)
    final_height = int(final_image_scaled.height / scale_factor)

    try:
        resample_filter = Image.Resampling.LANCZOS
    except AttributeError:
        resample_filter = Image.LANCZOS

    final_image = final_image_scaled.resize((final_width, final_height), resample_filter)
    
    return final_image # Return the image object for the GUI

# Note: The if __name__ == '__main__': block is removed as this script
# will now be imported and run by 'gui.py'.
