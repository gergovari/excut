import fitz  # PyMuPDF
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib import pagesizes
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import black
import io
import os
import re

def load_input_files(paths):
    """
    Generator that yields (image_bytes, filename, page_number)
    for each page in the input PDF(s) or each image file.
    """
    for path in paths:
        if not os.path.exists(path):
            continue
            
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            doc = fitz.open(path)
            for i, page in enumerate(doc):
                pix = page.get_pixmap()
                img_data = pix.tobytes("ppm")
                yield img_data, path, i + 1
            doc.close()
        elif ext in [".png", ".jpg", ".jpeg", ".bmp"]:
            with open(path, "rb") as f:
                yield f.read(), path, 1

def generate_output_pdf(items, output_path, bg_image=None, bg_pattern=None, page_size_str="A4"):
    """
    items: List of dicts {'type': 'image'|'title', 'content': ..., 'title': ...}
    output_path: Path to save PDF
    bg_image: Optional background image path
    bg_pattern: Optional background pattern name
    page_size_str: "A4", "A3", or "WIDTHxHEIGHT" (e.g. "1860x2480")
    """
    # Determine page size
    if "x" in page_size_str and re.match(r'^\d+(\.\d+)?x\d+(\.\d+)?$', page_size_str):
        parts = page_size_str.lower().split('x')
        current_pagesize = (float(parts[0]), float(parts[1]))
    else:
        # Try to find standard size (case insensitive)
        fname = page_size_str.upper()
        if hasattr(pagesizes, fname):
            current_pagesize = getattr(pagesizes, fname)
        else:
            print(f"Warning: Unknown page size '{page_size_str}', defaulting to A4")
            current_pagesize = pagesizes.A4

    c = canvas.Canvas(output_path, pagesize=current_pagesize)
    width, height = current_pagesize
    
    # Calculate scale factor relative to A4 width
    # If page is bigger, everything should be bigger
    base_width = pagesizes.A4[0] # 595.27
    scale_factor = width / base_width
    
    # Default to squared if neither provided
    if not bg_image and not bg_pattern:
        bg_pattern = "squared"

    # Separate counters
    ex_count = 0
    title_count = 0

    for i, item in enumerate(items):
        # Draw background
        if bg_image and os.path.exists(bg_image):
            c.drawImage(bg_image, 0, 0, width=width, height=height)
        elif bg_pattern == "squared":
            c.setStrokeColor(black)
            c.setLineWidth(0.5 * scale_factor)
            grid_size = 14 * scale_factor
            c.setStrokeAlpha(0.2)
            for gx in range(0, int(width), int(grid_size)):
                c.line(gx, 0, gx, height)
            for gy in range(0, int(height), int(grid_size)):
                c.line(0, gy, width, gy)
            c.setStrokeAlpha(1.0)

        # Content
        display_title = item.get("title", "")
        
        if item["type"] == "title":
            title_count += 1
            
            # Bookmark
            # Title text only in bookmark
            c.bookmarkPage(f"T{title_count}")
            c.addOutlineEntry(display_title, f"T{title_count}", level=0, closed=True)
            
            # Title Text
            # Smart font sizing: bigger if short
            # Base sizes: 36, 52, 42
            base_font_size = 36
            if len(display_title) < 20:
                base_font_size = 52
            elif len(display_title) < 40:
                base_font_size = 42
            
            title_font_size = base_font_size * scale_factor
                
            c.setFont("Helvetica-Bold", title_font_size)
            
            # Wrapping (Manual to enforce char breaking for long words)
            from reportlab.lib.utils import simpleSplit
            
            margin_x = 100 * scale_factor
            max_text_width = width - margin_x
            
            # First pass: try standard split
            initial_lines = simpleSplit(display_title, "Helvetica-Bold", title_font_size, max_text_width)
            
            lines = []
            for line in initial_lines:
                # Check if this line exceeds width? simpleSplit usually handles it unless it's one long word
                # If simpleSplit returned the long word as one line, it might overflow.
                # Let's force split if too long.
                if c.stringWidth(line, "Helvetica-Bold", title_font_size) > max_text_width:
                    # Force break by chars
                    current_line = ""
                    for char in line:
                        test_line = current_line + char
                        if c.stringWidth(test_line, "Helvetica-Bold", title_font_size) < max_text_width:
                            current_line = test_line
                        else:
                            lines.append(current_line)
                            current_line = char
                    if current_line:
                        lines.append(current_line)
                else:
                    lines.append(line)
            
            text_h = len(lines) * (title_font_size + (4 * scale_factor))
            start_y = (height / 2) + (text_h / 2) + (50 * scale_factor) 
            
            for line in lines:
                c.drawCentredString(width/2, start_y, line)
                start_y -= (title_font_size + (10 * scale_factor))
                
            # Title Number at bottom
            # "not tied to the title" -> absolute position at bottom
            c.setFont("Helvetica-Bold", 60 * scale_factor) # Huge
            c.drawCentredString(width/2, 100 * scale_factor, str(title_count))
        
        elif item["type"] == "image":
            ex_count += 1
            
            # Bookmark if title exists
            key = f"E{ex_count}"
            c.bookmarkPage(key)
            if display_title:
                 # If no titles yet, this is a top-level exercise (level 0)
                 # If titles exist, indent it (level 1)
                 lvl = 1 if title_count > 0 else 0
                 c.addOutlineEntry(f"{ex_count}: {display_title}", key, level=lvl, closed=True)

            # Draw Ordinal Number "<num> /"
            bottom_margin = 50 * scale_factor
            current_y = height - bottom_margin 
            
            font_size_num = 20 * scale_factor
            c.setFont("Helvetica-Bold", font_size_num)
            
            left_margin = 40 * scale_factor
            
            title_text = f"{ex_count} /"
            if item.get("show_title") and display_title:
                title_text += f" {display_title}"
                
            c.drawString(left_margin, current_y, title_text)
            
            # Draw Tick Circle
            cx = width - (50 * scale_factor)
            cy = current_y + (7 * scale_factor) 
            radius = 12 * scale_factor
            c.setLineWidth(2 * scale_factor)
            c.circle(cx, cy, radius, stroke=1, fill=0)
            
            # Reduce space between number/circle and picture
            # Previously current_y -= 40. Reduce to 20? 
            current_y -= (25 * scale_factor) # Tighter
            
            exercise_img = item["content"]
            img_reader = ImageReader(exercise_img)
            img_w, img_h = img_reader.getSize()
            
            margin = 40 * scale_factor
            max_w = width - (2 * margin)
            max_h = current_y - margin
            
            # Start with scaling up relative to page size difference
            # This ensures images look "normal size" on huge pages
            scale = scale_factor

            # Then constrain if it exceeds available space
            if (img_w * scale) > max_w:
                scale = max_w / img_w
            if (img_h * scale) > max_h:
                scale = max_h / img_h

            draw_w = img_w * scale
            draw_h = img_h * scale
            
            x = (width - draw_w) / 2
            y = current_y - draw_h 
            
            c.drawImage(img_reader, x, y, width=draw_w, height=draw_h)

        c.showPage()
        
    c.save()
