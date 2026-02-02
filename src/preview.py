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
        
        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.scroll.setWidget(self.container)
        self.layout.addWidget(self.scroll)
        
        # Controls
        ctrl_layout = QHBoxLayout()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.close_btn)
        self.layout.addLayout(ctrl_layout)
        
        # Generate and Render
        try:
            self.generate_preview(items, bg_image, bg_pattern, page_size)
        except Exception as e:
            lbl = QLabel(f"Error generating preview: {e}")
            self.container_layout.addWidget(lbl)

    def generate_preview(self, items, bg_image, bg_pattern, page_size):
        # Generate PDF to memory
        pdf_buffer = io.BytesIO()
        
        # We need to process items to ensure 'content' is valid (it might be in QPixmap format)
        # generate_output_pdf expects 'content' to be something ImageReader accepts (like PIL Image or bytes)
        # or it handles paths.
        # But wait, sidebar items have 'content' as QPixmap.
        # gui.py finish_process converts QPixmap to bytes.
        # We should replicate that conversion here.
        
        processed_items = []
        for item in items:
            new_item = item.copy()
            if item.get("type") == "image" and "content" in item:
                pix = item["content"]
                if isinstance(pix, QPixmap):
                    qimg = pix.toImage()
                    ba = qimg.bits()
                    ba.setsize(qimg.sizeInBytes())
                    
                    from PyQt6.QtCore import QBuffer, QIODevice
                    buff = QBuffer()
                    buff.open(QIODevice.OpenModeFlag.ReadWrite)
                    qimg.save(buff, "PNG")
                    new_item["content"] = io.BytesIO(buff.data().data())
            processed_items.append(new_item)
            
        generate_output_pdf(processed_items, pdf_buffer, bg_image, bg_pattern, page_size)
        
        pdf_buffer.seek(0)
        
        # Render with pymupdf
        doc = fitz.open(stream=pdf_buffer, filetype="pdf")
        
        for page in doc:
            pix = page.get_pixmap(dpi=100) # Reasonable DPI for screen
            fmt = QImage.Format.Format_RGB888
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
            qpix = QPixmap.fromImage(qimg)
            
            lbl = QLabel()
            lbl.setPixmap(qpix)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("border: 1px solid gray; margin-bottom: 10px;")
            self.container_layout.addWidget(lbl)
            
        doc.close()
