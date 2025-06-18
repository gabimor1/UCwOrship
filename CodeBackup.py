import re
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

def create_arabic_song_image(
    text_file_path,
    output_image_path,
    arabic_font_path,
    arabic_bold_font_path,
    chord_font_path=None
):
    """
    Generates a right-to-left song sheet image from a text file with Arabic lyrics.

    This function reads a structured text file containing a song's title, capo setting,
    verses, and choruses. It then creates a PNG image, rendering the Arabic lyrics
    correctly from right-to-left, placing English chords above the text, and styling
    the chorus in bold.

    Args:
        text_file_path (str): Path to the song's .txt file.
        output_image_path (str): Path where the final .png image will be saved.
        arabic_font_path (str): Path to the .ttf file for the regular Arabic font.
        arabic_bold_font_path (str): Path to the .ttf file for the bold Arabic font.
        chord_font_path (str, optional): Path to a font for chords (e.g., Arial.ttf).
                                         Defaults to a basic font if not provided.
    """
    # --- 1. Define Styles & Quality ---
    # Increase scale_factor for higher resolution output (e.g., 2 or 3).
    scale_factor = 2

    # Base values
    image_width = 850 # This now acts as a maximum canvas width
    padding = 30
    line_spacing = 18
    section_spacing = 70  # The vertical space between verses/choruses
    chord_font_size = 24
    lyric_font_size = 56
    title_font_size = 32
    capo_font_size = 14
    section_title_font_size = 20

    # Scaled values for high-quality rendering
    image_width_scaled = image_width * scale_factor
    padding_scaled = padding * scale_factor
    line_spacing_scaled = line_spacing * scale_factor
    section_spacing_scaled = section_spacing * scale_factor
    
    background_color = (255, 255, 255)  # White
    text_color = (0, 0, 0)              # Black
    chord_color = (200, 0, 0)           # Dark Red
    section_title_color = (50, 50, 50)  # Dark Gray

    # --- 2. Load Fonts (Scaled) ---
    try:
        # Load fonts with scaled sizes
        title_font = ImageFont.truetype(arabic_bold_font_path, title_font_size * scale_factor)
        lyric_font = ImageFont.truetype(arabic_font_path, lyric_font_size * scale_factor)
        bold_lyric_font = ImageFont.truetype(arabic_bold_font_path, lyric_font_size * scale_factor)
        section_title_font = ImageFont.truetype(arabic_bold_font_path, section_title_font_size * scale_factor)
        capo_font = ImageFont.truetype(arabic_font_path, capo_font_size * scale_factor)
        chord_font = ImageFont.truetype(chord_font_path, chord_font_size * scale_factor) if chord_font_path else ImageFont.load_default()
    except IOError as e:
        print(f"Error loading font: {e}. Please check your font paths. Aborting.")
        return

    # --- 3. Read and Parse the Text File into Structured Sections ---
    with open(text_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    song_data = []
    current_section = None
    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("Title:"):
            song_data.append({'type': 'title', 'content': line.replace("Title:", "").strip()})
        elif line.startswith("Capo:"):
            # The 'Capo:' text is added here for consistent display
            song_data.append({'type': 'capo', 'content': f"Capo: {line.replace('Capo:', '').strip()}"})
        elif re.fullmatch(r'\[.*?\]', line):  # A line containing ONLY a section marker like [Verse 1]
            section_title = line[1:-1]
            current_section = {'type': 'lyrics_section', 'title': section_title, 'lines': []}
            song_data.append(current_section)
        elif current_section:
            # This line is part of the current section (verse or chorus)
            current_section['lines'].append(line)

    # --- 4. Prepare High-Resolution Image Canvas ---
    # Create a tall temporary image; we will crop it to the final height later.
    temp_height = 4000 * scale_factor
    img = Image.new('RGB', (image_width_scaled, temp_height), color=background_color)
    draw = ImageDraw.Draw(img)
    y_position = padding_scaled # Start drawing from the top
    x_size = 0 # This will track the maximum content width

    max_line_size = 0
    for section in song_data:
        sec_type = section['type']
        if sec_type in ['title', 'capo']:
            continue
        elif sec_type == 'lyrics_section':
          for line in section['lines']:
            # Get the clean lyric string (without chords) for proper shaping
            clean_lyric_line = re.sub(r'\[.*?\]', '', line)
            reshaped_clean_line = get_display(arabic_reshaper.reshape(clean_lyric_line))

            # Split the original line to know the order of lyrics and chords
            segments = [s for s in re.split(r'(\[.*?\])', line) if s]
            
            current_lyric_font = bold_lyric_font

            # First Pass: Draw the entire unbroken lyric line. This guarantees correct letter shaping.
            total_lyric_width = draw.textlength(reshaped_clean_line, font=current_lyric_font)
            if total_lyric_width > max_line_size: max_line_size = total_lyric_width


    # --- 5. Draw Each Section with Right-to-Left Logic ---
    for section in song_data:
        sec_type = section['type']

        # Draw Title and Capo (Right-Aligned)
        if sec_type in ['title', 'capo']:
            font = title_font if sec_type == 'title' else capo_font
            content = section.get('content', '')
            reshaped_text = arabic_reshaper.reshape(content)
            bidi_text = get_display(reshaped_text)
            text_width = draw.textlength(bidi_text, font=font)
            # Track maximum width
            if text_width > x_size:
                x_size = text_width
            x_pos = image_width_scaled - text_width - padding_scaled
            draw.text((x_pos, y_position), bidi_text, font=font, fill=text_color)
            y_position += font.getbbox(bidi_text)[3] + (section_spacing_scaled if sec_type == 'capo' else line_spacing_scaled)

        # Draw Lyric Sections (Verses, Choruses)
        elif sec_type == 'lyrics_section':
            section_title_text = section['title']
            is_chorus = 'chorus' in section_title_text.lower()
            
            # draw.text((padding_scaled, y_position), section_title_text, font=section_title_font, fill=section_title_color)
            #y_position += section_title_font.getbbox(section_title_text)[3] + int(line_spacing_scaled / 2)

            # Draw each line of lyrics and chords
            for line in section['lines']:
                # Get the clean lyric string (without chords) for proper shaping
                clean_lyric_line = re.sub(r'\[.*?\]', '', line)
                reshaped_clean_line = get_display(arabic_reshaper.reshape(clean_lyric_line))

                # Split the original line to know the order of lyrics and chords
                segments = [s for s in re.split(r'(\[.*?\])', line) if s]
                
                current_lyric_font = bold_lyric_font if is_chorus else lyric_font
                lyric_y_pos = y_position + chord_font.getbbox("Cm")[3]

                # First Pass: Draw the entire unbroken lyric line. This guarantees correct letter shaping.
                total_lyric_width = draw.textlength(reshaped_clean_line, font=current_lyric_font)
                offset_to_center = (max_line_size - total_lyric_width)/2
                draw.text((image_width_scaled - padding_scaled - offset_to_center, lyric_y_pos), reshaped_clean_line, font=current_lyric_font, fill=text_color, anchor="ra")

                # Second Pass: Calculate where the chords go and draw them.
                x_calculator = image_width_scaled - padding_scaled - offset_to_center # Start calculating from the right margin.
                reshaped_lyric_cursor = len(reshaped_clean_line) # This tracks our position in the pre-shaped string
                
                # Track maximum width
                if total_lyric_width > x_size:
                    x_size = total_lyric_width
                for segment in segments:
                    if not re.fullmatch(r'\[.*?\]', segment): # It's a lyric segment
                        # We must measure the width of the SLICE from the FULLY SHAPED string.
                        segment_len = len(segment)
                        shaped_substring = reshaped_clean_line[reshaped_lyric_cursor - segment_len : reshaped_lyric_cursor][::-1]
                        reshaped_lyric_cursor -= segment_len
                        lyric_width = draw.textlength(shaped_substring, font=current_lyric_font)
                        x_calculator -= lyric_width
                    
                    else: # It's a chord segment
                        # The chord goes at the current calculator position, which is where the previous lyric ended.
                        chord_text = segment[1:-1]
                        if len(chord_text) > 1: x_calculator += draw.textlength(chord_text[1], font=chord_font)
                        # Using anchor "ra" aligns the RIGHT of the chord to the cursor position, which is more accurate.
                        draw.text((x_calculator, y_position), chord_text, font=chord_font, fill=chord_color, anchor="ra")
                        if len(chord_text) > 1: x_calculator -= draw.textlength(chord_text[1], font=chord_font)

                y_position += lyric_font.getbbox("Sample")[3] + chord_font.getbbox("Cm")[3] + line_spacing_scaled
            
            y_position += section_spacing_scaled

    # --- 6. Crop, Resize, and Save Final Image ---
    # Determine the dynamic width based on the widest content found
    final_content_width_scaled = int(x_size) + padding_scaled * 2
    # Ensure the final width does not exceed the initial canvas width
    final_content_width_scaled = min(final_content_width_scaled, image_width_scaled)
    
    # Calculate the left edge for cropping to center the content
    left_crop_edge = image_width_scaled - final_content_width_scaled
    
    # Crop the oversized image to the exact content dimensions
    final_image_scaled = img.crop((left_crop_edge, 0, image_width_scaled, y_position))
    
    # Calculate the final dimensions based on the scaling factor
    final_width = int(final_content_width_scaled / scale_factor)
    final_height = int(y_position / scale_factor)
    
    # Resize the image down to the target size using a high-quality filter
    try:
        resample_filter = Image.Resampling.LANCZOS
    except AttributeError:
        # For older versions of Pillow
        resample_filter = Image.LANCZOS

    final_image = final_image_scaled.resize((final_width, final_height), resample_filter)

    final_image.save(output_image_path)
    print(f"High-quality song image successfully created at: {output_image_path}")



# --- How to Run This Script ---
if __name__ == '__main__':
    # IMPORTANT: You MUST replace these with the actual paths to your downloaded font files.
    # On Windows, a path might look like 'C:/Windows/Fonts/arial.ttf'.
    # On macOS, a path might look like '/System/Library/Fonts/Supplemental/Arial.ttf'.
    
    ARABIC_FONT_REGULAR = "fonts/NotoNaskhArabic-Regular.ttf"
    ARABIC_FONT_BOLD = "fonts/NotoNaskhArabic-Bold.ttf"
    CHORD_FONT = "fonts/ARIAL.TTF" # A standard font like Arial works well for chords

    create_arabic_song_image(
        text_file_path='txt_files/Title.txt',
        output_image_path='png_files/Title.png',
        arabic_font_path=ARABIC_FONT_REGULAR,
        arabic_bold_font_path=ARABIC_FONT_BOLD,
        chord_font_path=CHORD_FONT
    )
