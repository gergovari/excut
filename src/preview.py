from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QScrollArea, QLabel, QPushButton, QHBoxLayout, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage
import fitz
import io
from .pdf_utils import generate_output_pdf

class PreviewDialog(QDialog):
    def __init__(self, items, bg_image=None, bg_pattern=None, page_size="A4", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Final PDF Preview")
        self.resize(1000, 900)
        self.layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setFixedSize(30, 30)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar.addWidget(self.zoom_out_btn)

        self.zoom_lvl_lbl = QLabel("100%")
        self.zoom_lvl_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_lvl_lbl.setMinimumWidth(50)
        toolbar.addWidget(self.zoom_lvl_lbl)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedSize(30, 30)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar.addWidget(self.zoom_in_btn)
        
        toolbar.addSpacing(20)
        
        self.fit_width_btn = QPushButton("Fit Width")
        self.fit_width_btn.clicked.connect(self.fit_to_width)
        toolbar.addWidget(self.fit_width_btn)

        toolbar.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        toolbar.addWidget(self.close_btn)
        
        self.layout.addLayout(toolbar)

        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.scroll.setWidget(self.container)
        self.layout.addWidget(self.scroll)
        
        # State
        self.pdf_data = None
        self.current_zoom = 1.0
        self.doc = None

        # Generate and Render
        try:
            self.generate_preview_data(items, bg_image, bg_pattern, page_size)
            # Initial render: Fit to width
            # We need the dialog to be shown or layout to be ready to calculate width
            # But we can default to 100% or guess. 
            # Let's try to fit width after a short delay or just default to 1.0?
            # Better: Fit to width logic immediately if possible, or use a default safe zoom (e.g. 0.5 for A4 on small screen)
            # Let's start with Fit Width logic (approximate) or just render.
            self.fit_to_width() 
        except Exception as e:
            lbl = QLabel(f"Error generating preview: {e}")
            self.container_layout.addWidget(lbl)

    def generate_preview_data(self, items, bg_image, bg_pattern, page_size):
        # Generate PDF to memory
        self.pdf_data = io.BytesIO()
        
        processed_items = []
        for item in items:
            new_item = item.copy()
            if item.get("type") == "image" and "content" in item:
                pix = item["content"]
                if isinstance(pix, QPixmap):
                    qimg = pix.toImage()
                    # Keep everything in memory
                    from PyQt6.QtCore import QBuffer, QIODevice
                    buff = QBuffer()
                    buff.open(QIODevice.OpenModeFlag.ReadWrite)
                    qimg.save(buff, "PNG")
                    new_item["content"] = io.BytesIO(buff.data().data())
            processed_items.append(new_item)
            
        generate_output_pdf(processed_items, self.pdf_data, bg_image, bg_pattern, page_size)
        self.pdf_data.seek(0)
        self.doc = fitz.open(stream=self.pdf_data, filetype="pdf")

    def render_pages(self):
        if not self.doc:
            return

        # Clear existing
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        zoom_matrix = fitz.Matrix(self.current_zoom, self.current_zoom)

        for page in self.doc:
            pix = page.get_pixmap(matrix=zoom_matrix)
            fmt = QImage.Format.Format_RGB888
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
            qpix = QPixmap.fromImage(qimg)
            
            lbl = QLabel()
            lbl.setPixmap(qpix)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("border: 1px solid gray; margin-bottom: 10px;")
            self.container_layout.addWidget(lbl)
            
        self.zoom_lvl_lbl.setText(f"{int(self.current_zoom * 100)}%")

    def zoom_in(self):
        self.current_zoom += 0.25
        self.render_pages()

    def zoom_out(self):
        if self.current_zoom > 0.25:
            self.current_zoom -= 0.25
            self.render_pages()

    def fit_to_width(self):
        if not self.doc:
            return
            
        # Get viewport width (available width for content)
        viewport_w = self.scroll.viewport().width() - 40 # Subtract scrollbar/margins padding guess
        if viewport_w <= 0:
            viewport_w = 800 # Fallback
            
        page = self.doc[0]
        # Base width at scale 1.0 (72 dpi usually in fitz unless matrix)
        # fitz default dpi is 72. get_pixmap with default matrix is scale 1.0 = 72 dpi?
        # No, fitz uses points. 1 pt = 1/72 inch.
        # page.rect.width is in points. 
        # If we want to fit to screen pixels... 
        # Screen is usually 96 DPI or higher. 
        # Let's aim for: (page_width_points * zoom) = viewport_width_pixels
        
        base_w = page.rect.width
        if base_w > 0:
            self.current_zoom = viewport_w / base_w
            
        # Clamp min zoom
        if self.current_zoom < 0.1: self.current_zoom = 0.1
        
        self.render_pages()

