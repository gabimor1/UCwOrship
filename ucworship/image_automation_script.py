import re

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont



def create_arabic_song_image(song_data, params):
    """
    Generates a right-to-left song sheet image from pre-parsed song data and GUI parameters.
    This is your perfected logic, adapted to be called as a function.
    """
    debug = 0

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
    image_width = 1850
    padding = 70
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
    except (OSError, IOError) as e:
        print(f"Error loading font: {e}. Please check your font paths. Aborting.")
        return None

    # --- 4. Prepare High-Resolution Image Canvas ---
    temp_height = 4000 * scale_factor

    img = Image.new('RGB', (image_width_scaled, temp_height), color=background_color)
    draw = ImageDraw.Draw(img)
    y_position = padding_scaled/3
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


    #image_width_scaled_post = int((max_line_size + 2*padding_scaled)*scale_factor)
    #img = Image.new('RGB', (image_width_scaled_post, temp_height), color=background_color)
    #draw = ImageDraw.Draw(img)

    # --- 5. Draw Each Section with Right-to-Left Logic ---
    for section in song_data:
        sec_type = section['type']

        if sec_type == 'title':
            bidi_text = get_display(arabic_reshaper.reshape(section['content']))
            text_width = draw.textlength(bidi_text, font=title_font)
            if text_width > x_size: x_size = text_width
            offset_to_center = (max_line_size - text_width)/2
            draw.text((image_width_scaled - padding_scaled*2 - offset_to_center, y_position), bidi_text, font=title_font, fill=text_color, anchor="mt")
            y_position += title_font.getbbox(bidi_text)[3] + line_spacing_scaled
        
        elif sec_type == 'capo':
            capo_text = f"Capo: {params['capo']}"
            text_width = draw.textlength(capo_text, font=capo_font)
            if text_width > x_size: x_size = text_width
            draw.text((image_width_scaled - padding_scaled - max_line_size, y_position), capo_text, font=capo_font, fill=text_color, anchor="mt")
            y_position += capo_font.getbbox(capo_text)[3] #+ section_spacing_scaled

        elif sec_type == 'lyrics_section':
            is_chorus = 'chorus' in section['title'].lower()
            current_lyric_font = bold_lyric_font if is_chorus else lyric_font
            
            for line in section['lines']:
                clean_lyric_line = re.sub(r'\[.*?\]', '', line)
                # print(clean_lyric_line)
                reshaped_clean_line = get_display(arabic_reshaper.reshape(clean_lyric_line))
                # print("reshaped_clean_line", reshaped_clean_line)
                segments = [s for s in re.split(r'(\[.*?\])', line) if s]

                # print(segments)
                lyric_y_pos = y_position + chord_font.getbbox("Cm")[3]

                total_lyric_width = draw.textlength(reshaped_clean_line, font=current_lyric_font)
                offset_to_center = (max_line_size - total_lyric_width) / 2

                draw.text((image_width_scaled - padding_scaled - offset_to_center, lyric_y_pos), reshaped_clean_line, font=current_lyric_font, fill=text_color, anchor="ra")
                # print("Text start x:",image_width_scaled - padding_scaled - offset_to_center)
                # print("Text end x:",image_width_scaled - padding_scaled - offset_to_center-total_lyric_width)
                # print(image_width_scaled,"-", padding_scaled,"-", offset_to_center)
                if show_chords:
                    last_accord_end = 10000000
                    current_for_double_trouble = 10000000

                    x_calculator = image_width_scaled - padding_scaled - offset_to_center
                    reshaped_lyric_cursor = len(reshaped_clean_line)
                    # print("reshaped_clean_line", reshaped_clean_line, reshaped_lyric_cursor)
                    # print("reshaped_clean_line reversed", reshaped_clean_line[::-1], reshaped_lyric_cursor)
                    for segment in segments:

                        if not re.fullmatch(r"\[.*?\]", segment):
                            segment_len = len(segment)
                            # reshaped_clean_line_len = len(reshaped_clean_line)
                            # print("-"*30, reshaped_clean_line[0])

                            # Find lam alef sequence
                            index = 0
                            occurrence_count = 0
                            while index < len(segment):
                                # Check for the sequence at the current position
                                if index + 1 < len(segment) and (
                                    (segment[index] == "ل" and segment[index + 1] == "ا")
                                    or (segment[index] == "ل" and segment[index + 1] == "أ")
                                ):
                                    # If found, increment the counter and skip the next two characters
                                    occurrence_count += 1
                                    # print("-"*10, "found la is segment", "-"*10)
                                    index += 2
                                else:
                                    # Otherwise, just move to the next one
                                    index += 1

                            if debug: print(occurrence_count, "occurrence_count")

                            # Find allah sequence
                            index = 0
                            occurrence_countـallah = 0
                            while index < len(segment):
                                # Check for the sequence at the current position
                                if index + 3 < len(segment) and segment[index] == "ا" and segment[index+1] == "ل" and segment[index+2] == "ل" and segment[index+3] == "ه":
                                    # If found, increment the counter and skip the next two characters
                                    occurrence_countـallah += 3 
                                    if debug: print("-"*10, "found allah is segment", "-"*10)

                                    index += 4
                                else:
                                    # Otherwise, just move to the next one
                                    index += 1

                            if debug: print(occurrence_count, "occurrence_count")

                            shaped_substring = reshaped_clean_line[reshaped_lyric_cursor - segment_len + occurrence_count + occurrence_countـallah: reshaped_lyric_cursor]
                            
                            
                            adjustment = 0
                            if get_display(arabic_reshaper.reshape("لا")) in shaped_substring:
                                if debug: print("-"*10, "found la", "-"*10)
                                adjustment = occurrence_count*(draw.textlength(get_display(arabic_reshaper.reshape("لا")), font=current_lyric_font) - (draw.textlength(get_display(arabic_reshaper.reshape("ل")), font=current_lyric_font)+draw.textlength(get_display(arabic_reshaper.reshape("ا")), font=current_lyric_font)))
                            elif get_display(arabic_reshaper.reshape("سلا")[1:]) in shaped_substring:
                                if debug: print("-"*10, "found la", "-"*10)
                                adjustment = occurrence_count*(draw.textlength(get_display(arabic_reshaper.reshape("سلا")[1:]), font=current_lyric_font) - (draw.textlength(get_display(arabic_reshaper.reshape("ل")), font=current_lyric_font)+draw.textlength(get_display(arabic_reshaper.reshape("ا")), font=current_lyric_font)))
                            # print("adjustment", adjustment)

                            if debug: print("segment", segment, len(segment))
                            if debug: print("shaped_substring", shaped_substring, len(shaped_substring))

                            # la_shit = get_display(arabic_reshaper.arabic_reshaper.reshape("ال"))
                            # print(draw.textlength(get_display(arabic_reshaper.reshape("لا")), font=current_lyric_font))
                            # print(draw.textlength(get_display(arabic_reshaper.reshape("ل")), font=current_lyric_font))
                            # print(draw.textlength(get_display(arabic_reshaper.reshape("ا")), font=current_lyric_font))

                            reshaped_lyric_cursor -= segment_len - occurrence_count - occurrence_countـallah

                            lyric_width = draw.textlength(shaped_substring, font=current_lyric_font)
                            # print(lyric_width)
                            x_calculator = x_calculator - lyric_width
                        else:
                            chord_text = segment[1:-1]

                            if debug: print(chord_text)
                            # font_adjusted = chord_font
                            # if "(" in chord_text:
                            #     font_adjusted = chord_font - int(chord_font)*0.2
                             
                            #if len(chord_text) > 1: x_calculator += draw.textlength(chord_text[1:], font=chord_font)
                            # print("Chord start x:",x_calculator)
                            chord_size_mid = draw.textlength(chord_text, font=chord_font)/2
                            # x_calculator += chord_size_mid
                            if (x_calculator >= last_accord_end) or (x_calculator >= current_for_double_trouble):
                                draw.text((min(last_accord_end,current_for_double_trouble), y_position), chord_text, font=chord_font, fill=chord_color, anchor="ra")
                                if debug: print("I AM PUSHING AN ACCORD  ---  ", chord_text)
                                current_for_double_trouble = last_accord_end - chord_size_mid*2
                            else:
                                draw.text((x_calculator, y_position), chord_text, font=chord_font, fill=chord_color, anchor="ra")
                            # x_calculator -= chord_size_mid
                            #if len(chord_text) > 1: x_calculator -= draw.textlength(chord_text[1:], font=chord_font)
                            last_accord_end = x_calculator - chord_size_mid*2

                y_position += current_lyric_font.getbbox("Sample")[3] + chord_font.getbbox("Cm")[3] + line_spacing_scaled
            y_position += section_spacing_scaled

    # --- 6. Crop, Resize, and Return Final Image ---
    croping_redundant_area = int((max_line_size + 2*padding_scaled))
    final_image_scaled = img.crop((image_width_scaled-croping_redundant_area, 0, image_width_scaled, y_position))

    final_width = int(final_image_scaled.width / scale_factor)
    final_height = int(final_image_scaled.height / scale_factor)

    try:
        resample_filter = Image.Resampling.LANCZOS
    except AttributeError:
        resample_filter = Image.LANCZOS

    final_image = final_image_scaled.resize((final_width, final_height), resample_filter)

    return final_image  # Return the image object for the GUI


# Note: The if __name__ == '__main__': block is removed as this script
# will now be imported and run by 'gui.py'.
