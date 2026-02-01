from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter, QMessageBox, QProgressDialog, 
    QDialog, QVBoxLayout, QPushButton, QApplication, QLabel
)
from PyQt6.QtCore import Qt, QTimer, QRect, QRectF, QRectF
from PyQt6.QtGui import QAction, QPixmap, QPainter, QShortcut, QKeySequence, QColor, QPalette
from .canvas import ImageCanvas
from .sidebar import Sidebar
from .pdf_utils import load_input_files, generate_output_pdf
import sys
import io

class RecropDialog(QDialog):
    def __init__(self, page_pixmap, initial_rects, parent=None):
        """
        initial_rects: list of QRect (scene coords)
        """
        super().__init__(parent)
        self.setWindowTitle("Edit Crop")
        self.resize(1000, 800)
        self.layout = QVBoxLayout(self)
        
        # Info
        info_label = QLabel("Controls: Drag on empty space to ADD selection. Double-click selection to REMOVE. Drag red box to MOVE/RESIZE.")
        info_label.setStyleSheet("font-weight: bold; color: gray;")
        self.layout.addWidget(info_label)
        
        self.canvas = ImageCanvas()
        self.canvas.selection_finished.connect(self.add_from_selection)
        self.canvas.auto_reset_selection = True
        
        # Load image
        qimg = page_pixmap.toImage()
        from PyQt6.QtCore import QBuffer, QIODevice
        buff = QBuffer()
        buff.open(QIODevice.OpenModeFlag.ReadWrite)
        qimg.save(buff, "PNG")
        self.canvas.set_image(buff.data())
        
        # Add Resizable Rects
        self.rect_items = []
        from .canvas import ResizableRectItem
        for r in initial_rects:
            # Create interactive item on scene
            item = ResizableRectItem(QRectF(r))
            item.geometry_changed.connect(self.update_numbers)
            item.removed.connect(lambda i=item: self.remove_rect(i))
            self.canvas.scene.addItem(item)
            self.rect_items.append(item)
        
        self.update_numbers()
        
        self.layout.addWidget(self.canvas)
        
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Cut")
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        self.layout.addLayout(btn_layout)
    
    def update_numbers(self):
        # Do NOT auto-sort. Keep creation order as requested.
        for i, item in enumerate(self.rect_items):
            item.order_index = i + 1
            item.update() # Trigger repaint

    def add_from_selection(self, rect):
        from .canvas import ResizableRectItem
        # Convert QRect to QRectF
        item = ResizableRectItem(QRectF(rect))
        item.geometry_changed.connect(self.update_numbers)
        item.removed.connect(lambda i=item: self.remove_rect(i))
        self.canvas.scene.addItem(item)
        self.rect_items.append(item)
        self.update_numbers()

    def remove_rect(self, item):
        self.canvas.scene.removeItem(item)
        if item in self.rect_items:
            self.rect_items.remove(item)
        self.update_numbers()

    def get_result(self):
        # Return list of rects
        # Sort again to be sure (update_numbers keeps them sorted in list? No, update_numbers sorts the list)
        self.update_numbers() 
        
        rects = []
        for item in self.rect_items:
            # Absolute scene coords
            top_left = item.mapToScene(item.rect().topLeft())
            bottom_right = item.mapToScene(item.rect().bottomRight())
            r = QRectF(top_left, bottom_right).toRect()
            
            # Normalize and intersect with image
            img_rect = self.canvas.pixmap_item.boundingRect().toRect()
            r = r.intersected(img_rect)
            if not r.isEmpty():
                rects.append(r)
        
        # Re-generate pixmaps
        parts_pixmaps = []
        full_pix = self.canvas.pixmap_item.pixmap()
        for r in rects:
            parts_pixmaps.append(full_pix.copy(r))
        
        # Combine
        return parts_pixmaps, rects

class MainWindow(QMainWindow):
    # ... (init remains mostly same until cut_selection) ...
    def __init__(self, input_paths, output_file, bg_image=None, bg_pattern=None, theme="dark"):
        super().__init__()
        self.setWindowTitle("ExCut")
        self.resize(1200, 800)
        
        self.input_paths = input_paths
        self.output_file = output_file
        self.bg_image = bg_image
        self.bg_pattern = bg_pattern
        self.theme = theme
        
        # Central Widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.splitter)
        
        # Canvas
        self.canvas = ImageCanvas()
        self.splitter.addWidget(self.canvas)
        
        # Sidebar
        self.sidebar = Sidebar()
        self.splitter.addWidget(self.sidebar)
        self.sidebar.finish_clicked.connect(self.finish_process)
        self.sidebar.request_recrop.connect(self.handle_recrop)
        
        # Adjust splitter sizes (Canvas takes most space)
        self.splitter.setSizes([900, 300])
        
        # Data
        self.pages = [] # List of (image_bytes, filename, page_num)
        self.current_idx = 0
        self.pending_parts = [] # List of (QPixmap, metadata_dict) where metadata_dict={'page_idx': i, 'rect': r}
        
        # Theme Toggle
        self.theme_btn = QPushButton("Toggle Theme", self.sidebar)
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.sidebar.layout.insertWidget(0, self.theme_btn)
        
        # Loading
        QTimer.singleShot(0, self.load_data)

        # Global Shortcuts for Navigation (works regardless of focus)
        self.shortcut_prev_arrow = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self.shortcut_prev_arrow.activated.connect(self.prev_page)
        self.shortcut_next_arrow = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self.shortcut_next_arrow.activated.connect(self.next_page)
        self.shortcut_prev_h = QShortcut(QKeySequence(Qt.Key.Key_H), self)
        self.shortcut_prev_h.activated.connect(self.prev_page)
        self.shortcut_next_l = QShortcut(QKeySequence(Qt.Key.Key_L), self)
        self.shortcut_next_l.activated.connect(self.next_page)
        
        self.apply_theme(self.theme)

    def apply_theme(self, theme):
        app = QApplication.instance()
        if theme == "dark":
            app.setStyle("Fusion")
            dark_palette = QPalette()
            dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
            dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
            dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
            dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
            dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
            dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
            dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
            dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
            app.setPalette(dark_palette)
        else:
            app.setPalette(QPalette()) 
        self.sidebar.set_theme(theme)
            
    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply_theme(self.theme)

    def load_data(self):
        progress = QProgressDialog("Loading files...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        try:
            generator = load_input_files(self.input_paths)
            for img_data, fname, pnum in generator:
                self.pages.append((img_data, fname, pnum))
                QApplication.processEvents()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load files: {e}")
            sys.exit(1)
        progress.close()
        if not self.pages:
            QMessageBox.warning(self, "Warning", "No valid images/PDFs found.")
            sys.exit(0)
        self.show_current_page()

    def show_current_page(self):
        if 0 <= self.current_idx < len(self.pages):
            img_data, fname, pnum = self.pages[self.current_idx]
            self.canvas.set_image(img_data)
            self.setWindowTitle(f"ExCut - {fname} (Page {pnum}) [{self.current_idx + 1}/{len(self.pages)}]")
            self.canvas.clear_selection()
            self.canvas.setFocus()

    def prev_page(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self.show_current_page()

    def next_page(self):
        if self.current_idx < len(self.pages) - 1:
            self.current_idx += 1
            self.show_current_page()

    def cut_selection(self, is_partial):
        selection = self.canvas.get_selection()
        rect = self.canvas.current_selection_rect
        
        if not selection and not is_partial and not self.pending_parts:
            return

        metadata = None
        if selection:
            # Store metadata: page_idx and specific rect
            metadata = {'page_idx': self.current_idx, 'rect': rect}
            self.pending_parts.append((selection, metadata))
            self.canvas.clear_selection()
        
        if self.pending_parts:
            parts_visuals = [p[0] for p in self.pending_parts]
            preview = self.combine_parts(parts_visuals)
            self.sidebar.update_pending_exercise(preview)
        
        if not is_partial:
            if self.pending_parts:
                parts_visuals = [p[0] for p in self.pending_parts]
                final_exercise = self.combine_parts(parts_visuals)
                
                # Consolidate metadata
                # Format: {'parts': [{'page_idx': i, 'rect': r}, ...]}
                all_metadata = []
                for p in self.pending_parts:
                    if p[1]: all_metadata.append(p[1])
                
                final_meta = {'parts': all_metadata}
                
                self.sidebar.remove_pending()
                self.sidebar.add_exercise(final_exercise, metadata=final_meta)
                self.pending_parts = [] 

    def combine_parts(self, parts):
        if len(parts) == 1:
            return parts[0]
        total_h = sum(p.height() for p in parts)
        max_w = max(p.width() for p in parts)
        combined = QPixmap(max_w, total_h)
        combined.fill(Qt.GlobalColor.white) 
        painter = QPainter(combined)
        y = 0
        for p in parts:
            painter.drawPixmap(0, y, p)
            y += p.height()
        painter.end()
        return combined

    def handle_recrop(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        # Check metadata
        if 'parts' in data and data['parts']:
            parts_meta = data['parts']
            
            # Use page of first part for now (assumption: same page editing)
            first_part = parts_meta[0]
            page_idx = first_part['page_idx']
            
            # Check if all parts are on same page
            same_page = all(p['page_idx'] == page_idx for p in parts_meta)
            if not same_page:
                 QMessageBox.warning(self, "Edit Limit", "This exercise spans multiple pages. Editing is currently only supported for single-page exercises.")
                 return

            # Retrieve page image
            img_data, _, _ = self.pages[page_idx]
            from PyQt6.QtGui import QImage
            page_img = QImage.fromData(img_data)
            page_pix = QPixmap.fromImage(page_img)
            
            rects = [p['rect'] for p in parts_meta]
            
            dlg = RecropDialog(page_pix, rects, self)
            if dlg.exec():
                new_pixmaps, new_rects = dlg.get_result()
                if new_pixmaps:
                    # Combine new pixmaps
                    combined_pix = self.combine_parts(new_pixmaps)
                    
                    # Update item data
                    data['content'] = combined_pix
                    # Update metadata with new rects (preserving page_idx)
                    new_meta_parts = []
                    for r in new_rects:
                        new_meta_parts.append({'page_idx': page_idx, 'rect': r})
                    data['parts'] = new_meta_parts
                    
                    item.setData(Qt.ItemDataRole.UserRole, data)
                    
                    # Update widget icon
                    widget = self.sidebar.list_widget.itemWidget(item)
                    if widget:
                        scaled = combined_pix.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio)
                        widget.icon_label.setPixmap(scaled)
        else:
            QMessageBox.information(self, "Info", "This exercise cannot be re-cropped (missing metadata).")

    def finish_process(self):
        items = self.sidebar.get_items()
        if not items:
            QMessageBox.information(self, "Info", "No items to export.")
            return
        pdf_items = []
        for item in items:
            new_item = item.copy()
            if item["type"] == "image":
                pix = item["content"]
                qimg = pix.toImage()
                ba = qimg.bits()
                ba.setsize(qimg.sizeInBytes())
                from PyQt6.QtCore import QBuffer, QIODevice
                buff = QBuffer()
                buff.open(QIODevice.OpenModeFlag.ReadWrite)
                qimg.save(buff, "PNG")
                new_item["content"] = io.BytesIO(buff.data().data())
            pdf_items.append(new_item)
        try:
            generate_output_pdf(pdf_items, self.output_file, self.bg_image, self.bg_pattern)
            QMessageBox.information(self, "Success", f"PDF saved to {self.output_file}")
            sys.exit(0)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save PDF: {e}")

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.cut_selection(is_partial=True)
            else:
                self.cut_selection(is_partial=False)
        else:
            super().keyPressEvent(event)
