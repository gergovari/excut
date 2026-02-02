from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter, QMessageBox, QProgressDialog, 
    QDialog, QVBoxLayout, QPushButton, QApplication, QLabel, QFileDialog, QMenuBar, QMenu,
    QFormLayout, QLineEdit, QComboBox, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, QRect, QRectF
from PyQt6.QtGui import QAction, QPixmap, QPainter, QShortcut, QKeySequence, QColor, QPalette, QTransform, QImage, QPen, QBrush
from .canvas import ImageCanvas
from .sidebar import Sidebar
from .pdf_utils import load_input_files, generate_output_pdf
from .project_io import save_project, load_project
from .styles import get_stylesheet
from .preview import PreviewDialog
import sys
import io
import os
import tempfile

class RecropDialog(QDialog):
    def __init__(self, full_pages, initial_parts_meta, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Crop")
        self.resize(1000, 800)
        self.layout = QVBoxLayout(self)
        
        self.full_pages = full_pages
        self.parts_meta = initial_parts_meta
        self.current_parts_meta = initial_parts_meta
        
        first_part = initial_parts_meta[0]
        self.view_page_idx = first_part['page_idx']
        
        info_label = QLabel("Controls: Drag on empty space to ADD selection. Double-click selection to REMOVE. Drag red box to MOVE/RESIZE.\nNavigation: Left/Right Arrow or H/L Keys.")
        info_label.setStyleSheet("font-weight: bold; color: gray;")
        self.layout.addWidget(info_label)
        
        page_ctrl = QHBoxLayout()
        self.page_lbl = QLabel(f"Page {self.view_page_idx + 1}")
        page_ctrl.addWidget(self.page_lbl)
        self.layout.addLayout(page_ctrl)
        
        self.canvas = ImageCanvas()
        self.canvas.selection_finished.connect(self.add_from_selection)
        self.canvas.auto_reset_selection = True
        
        self.rect_items = []
        
        self.load_page(self.view_page_idx)
        
        self.layout.addWidget(self.canvas)
        
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Cut")
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(self.show_preview)
        btn_layout.addWidget(self.preview_btn)
        
        self.layout.addLayout(btn_layout)

        # Shortcuts
        QShortcut(QKeySequence(Qt.Key.Key_Left), self).activated.connect(self.prev_page)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self).activated.connect(self.next_page)
        QShortcut(QKeySequence(Qt.Key.Key_H), self).activated.connect(self.prev_page)
        QShortcut(QKeySequence(Qt.Key.Key_L), self).activated.connect(self.next_page)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.undo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self).activated.connect(self.redo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self.redo)
        
        self.undo_stack = []
        self.redo_stack = []

        # Connect canvas selection properly here to use save_state
        try:
             self.canvas.selection_finished.disconnect()
        except:
             pass
        self.canvas.selection_finished.connect(self._on_canvas_selection_added)

    def _on_canvas_selection_added(self, rect):
        self.save_state()
        self.add_from_selection(rect)

    def save_state(self):
        import copy
        self._commit_current_page_changes()
        state = copy.deepcopy(self.current_parts_meta)
        self.undo_stack.append(state)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return
        
        import copy
        # Save current state to redo stack before undoing
        # But we need to commit visible state first to be accurate??
        self._commit_current_page_changes() 
        current = copy.deepcopy(self.current_parts_meta)
        self.redo_stack.append(current)
            
        state = self.undo_stack.pop()
        self.current_parts_meta = state
        self.load_page(self.view_page_idx) 

    def redo(self):
        if not self.redo_stack:
            return

        import copy
        self._commit_current_page_changes()
        current = copy.deepcopy(self.current_parts_meta)
        self.undo_stack.append(current)

        state = self.redo_stack.pop()
        self.current_parts_meta = state
        self.load_page(self.view_page_idx)

    def show_preview(self):
        parts, _ = self.get_result()
        if not parts:
            QMessageBox.information(self, "Preview", "No parts to preview.")
            return

        # Combine
        total_h = sum(p.height() for p in parts)
        max_w = max(p.width() for p in parts) if parts else 0
        
        combined = QPixmap(max_w, total_h)
        combined.fill(Qt.GlobalColor.white) # or transparent?
        
        painter = QPainter(combined)
        y = 0
        for p in parts:
            painter.drawPixmap(0, y, p)
            y += p.height()
        painter.end()
        
        # Show
        dlg = QDialog(self)
        dlg.setWindowTitle("Exercise Preview")
        layout = QVBoxLayout(dlg)
        lbl = QLabel()
        lbl.setPixmap(combined)
        
        scroll = QScrollArea()
        scroll.setWidget(lbl)
        layout.addWidget(scroll)
        dlg.resize(600, 800)
        dlg.exec()
        
    def load_page(self, page_idx):
        if not (0 <= page_idx < len(self.full_pages)):
            return
            
        self.view_page_idx = page_idx
        self.page_lbl.setText(f"Page {page_idx + 1}")
        
        # Remove existing rects manually to preserve pixmap_item
        for item in self.rect_items:
            self.canvas.scene.removeItem(item)
        self.rect_items = []
        
        img_data, _, _ = self.full_pages[page_idx]
        self.canvas.set_image(img_data)
        
        from .canvas import ResizableRectItem
        current_page_rects = [p['rect'] for p in self.current_parts_meta if p['page_idx'] == page_idx]
        
        for r in current_page_rects:
            item = ResizableRectItem(QRectF(r))
            item.geometry_changed.connect(self.update_numbers)
            item.about_to_change.connect(self.save_state) # Snapshot before mod
            item.removed.connect(lambda i=item: self._on_rect_removed(i))
            self.canvas.scene.addItem(item)
            self.rect_items.append(item)
            
        self.update_numbers()

    def _on_rect_removed(self, item):
        self.save_state()
        self.remove_rect(item)

    def prev_page(self):
        self._commit_current_page_changes()
        if self.view_page_idx > 0:
            self.load_page(self.view_page_idx - 1)

    def next_page(self):
        self._commit_current_page_changes()
        if self.view_page_idx < len(self.full_pages) - 1:
            self.load_page(self.view_page_idx + 1)
            
    def _commit_current_page_changes(self):
        self.current_parts_meta = [p for p in self.current_parts_meta if p['page_idx'] != self.view_page_idx]
        
        for item in self.rect_items:
            top_left = item.mapToScene(item.rect().topLeft())
            bottom_right = item.mapToScene(item.rect().bottomRight())
            r = QRectF(top_left, bottom_right).toRect()
            
            img_rect = self.canvas.pixmap_item.boundingRect().toRect()
            r = r.intersected(img_rect)
            if not r.isEmpty():
                self.current_parts_meta.append({'page_idx': self.view_page_idx, 'rect': r})
                
    def update_numbers(self):
        # Calculate start index based on previous pages
        offset = 0
        # current_parts_meta holds items from OTHER pages (after commit/load cycle involved in page switching?)
        # Wait, inside load_page, we haven't filtered current_parts_meta yet? 
        # load_page: 
        #   current_page_rects = ... from self.current_parts_meta
        #   so self.current_parts_meta currently HAS this page's items.
        
        # When we are editing, current_parts_meta includes everything.
        # But we are modifying self.rect_items which are separate.
        # So we should count strictly items in current_parts_meta where page_idx < current
        
        for p in self.current_parts_meta:
            if p['page_idx'] < self.view_page_idx:
                offset += 1
                
        for i, item in enumerate(self.rect_items):
            item.order_index = offset + i + 1
            item.update()

    def add_from_selection(self, rect):
        from .canvas import ResizableRectItem
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
        self._commit_current_page_changes()
        parts_pixmaps = []
        sorted_meta = sorted(self.current_parts_meta, key=lambda x: x['page_idx'])
        
        for p in sorted_meta:
            pidx = p['page_idx']
            rect = p['rect']
            img_data, _, _ = self.full_pages[pidx]
            
            if isinstance(img_data, QPixmap):
                page_pix = img_data
            elif isinstance(img_data, QImage):
                page_pix = QPixmap.fromImage(img_data)
            else:
                # Assume bytes
                page_img = QImage.fromData(img_data)
                page_pix = QPixmap.fromImage(page_img)
                
            parts_pixmaps.append(page_pix.copy(rect))
        
        return parts_pixmaps, sorted_meta

class SettingsDialog(QDialog):
    def __init__(self, output_file, page_size, theme, bg_image, bg_pattern, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Project Settings")
        self.resize(500, 300)
        
        self.layout = QFormLayout(self)
        
        self.output_edit = QLineEdit(output_file)
        self.layout.addRow("Output Filename:", self.output_edit)
        
        self.page_size_edit = QLineEdit(page_size)
        self.page_size_edit.setToolTip("e.g. A4, A3, letter, or widthxheight")
        self.layout.addRow("Page Size:", self.page_size_edit)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setCurrentText(theme)
        self.layout.addRow("Theme:", self.theme_combo)
        
        self.pattern_combo = QComboBox()
        self.pattern_combo.addItems(["", "squared"])
        self.pattern_combo.setCurrentText(bg_pattern or "")
        self.layout.addRow("Background Pattern:", self.pattern_combo)
        
        bg_layout = QHBoxLayout()
        self.bg_edit = QLineEdit(bg_image or "")
        self.bg_btn = QPushButton("Browse...")
        self.bg_btn.clicked.connect(self.browse_bg)
        bg_layout.addWidget(self.bg_edit)
        bg_layout.addWidget(self.bg_btn)
        self.layout.addRow("Background Image:", bg_layout)
        
        btn_box = QHBoxLayout()
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self.accept)
        btn_box.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.cancel_btn)
        
        self.layout.addRow(btn_box)

    def browse_bg(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Background Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.bg_edit.setText(path)

    def get_values(self):
        return {
            "output": self.output_edit.text(),
            "page_size": self.page_size_edit.text(),
            "theme": self.theme_combo.currentText(),
            "bg_pattern": self.pattern_combo.currentText(),
            "bg_image": self.bg_edit.text()
        }

class MainWindow(QMainWindow):
    def __init__(self, input_paths, output_file, bg_image=None, bg_pattern=None, theme="dark", page_size="A4", default_save_path=None):
        super().__init__()
        self.rect_pen = QPen(QColor("#e74c3c"), 2)
        self.rect_brush = QBrush(QColor(231, 76, 60, 50))
        self.undo_stack = []
        self.redo_stack = []
        self.canvas_undo_stack = []
        self.canvas_redo_stack = []
        self.resize_handle_size = 10
        self.current_editing_item = None
        
        self.setWindowTitle("ExCut")
        self.resize(1200, 800)
        
        self.input_paths = [os.path.abspath(f) for f in input_paths] if input_paths else []
        self.output_file = output_file
        self.bg_image = bg_image
        self.bg_pattern = bg_pattern
        self.theme = theme
        self.page_size = page_size
        self.current_project_path = default_save_path
        
        # Temp dir for processing
        self.temp_dir = tempfile.mkdtemp()
        
        self._init_ui()
        
        self.pages = [] # List of (img_data, filename, page_num)
        self.current_idx = 0
        self.pending_parts = []
        
        # Undo/Redo State
        self.undo_stack = []
        self.redo_stack = []
        self.current_state_snapshot = []
        
        QTimer.singleShot(0, self.load_data)

    def _init_ui(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        
        open_action = QAction("Open Project...", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self.browse_load_project)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save Project", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self.save_current_project)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save Project As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self.browse_save_project)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        add_files_action = QAction("Add Input Files...", self)
        add_files_action.setShortcut(QKeySequence("Ctrl+I"))
        add_files_action.triggered.connect(self.add_input_files)
        file_menu.addAction(add_files_action)
        
        file_menu.addSeparator()
        
        preview_action = QAction("Preview PDF", self)
        preview_action.setShortcut(QKeySequence("Ctrl+P"))
        preview_action.triggered.connect(self.show_preview)
        file_menu.addAction(preview_action)
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Undo/Redo Actions
        edit_menu = menubar.addMenu("Edit")
        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        undo_action.triggered.connect(self.undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("Redo", self)
        redo_action.setShortcuts([QKeySequence("Ctrl+Shift+Z"), QKeySequence("Ctrl+Y")])
        redo_action.triggered.connect(self.redo)
        edit_menu.addAction(redo_action)
        
        proj_menu = menubar.addMenu("Project")
        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self.open_settings)
        proj_menu.addAction(settings_action)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.splitter)
        
        self.canvas_container = QWidget()
        self.canvas_layout = QVBoxLayout(self.canvas_container)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        
        self.canvas = ImageCanvas()
        self.canvas_layout.addWidget(self.canvas)
        
        rotation_layout = QHBoxLayout()
        rotation_layout.setContentsMargins(5, 5, 5, 5)
        
        self.btn_rotate_left = QPushButton("↶ Rotate Left")
        self.btn_rotate_left.clicked.connect(lambda: self.rotate_page('left'))
        rotation_layout.addWidget(self.btn_rotate_left)
        
        self.btn_rotate_right = QPushButton("Rotate Right ↷")
        self.btn_rotate_right.clicked.connect(lambda: self.rotate_page('right'))
        rotation_layout.addWidget(self.btn_rotate_right)
        
        self.canvas_layout.addLayout(rotation_layout)
        
        self.splitter.addWidget(self.canvas_container)
        
        self.sidebar = Sidebar()
        self.splitter.addWidget(self.sidebar)
        self.sidebar.finish_clicked.connect(self.finish_process)
        self.sidebar.request_recrop.connect(self.handle_recrop)
        self.sidebar.request_discard.connect(self.discard_pending)
        self.sidebar.state_changed.connect(self.on_sidebar_change)
        
        self.splitter.setSizes([900, 300])
        
        self.theme_btn = QPushButton("Toggle Theme", self.sidebar)
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.sidebar.layout.insertWidget(0, self.theme_btn) 
        
        self.shortcut_prev_arrow = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self.shortcut_prev_arrow.activated.connect(self.prev_page)
        self.shortcut_next_arrow = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self.shortcut_next_arrow.activated.connect(self.next_page)
        self.shortcut_prev_h = QShortcut(QKeySequence(Qt.Key.Key_H), self)
        self.shortcut_prev_h.activated.connect(self.prev_page)
        self.shortcut_next_l = QShortcut(QKeySequence(Qt.Key.Key_L), self)
        self.shortcut_next_l.activated.connect(self.next_page)
        
        self.shortcut_f2 = QShortcut(QKeySequence(Qt.Key.Key_F2), self)
        self.shortcut_f2.activated.connect(self.sidebar.rename_selected)
        
        self.shortcut_j = QShortcut(QKeySequence(Qt.Key.Key_J), self)
        self.shortcut_j.activated.connect(self.sidebar.tree.navigate_next)
        self.shortcut_k = QShortcut(QKeySequence(Qt.Key.Key_K), self)
        self.shortcut_k.activated.connect(self.sidebar.tree.navigate_prev)

        self.apply_theme(self.theme)

    def discard_pending(self):
        self.pending_parts = []
        self.sidebar.remove_pending()

    def open_settings(self):
        dlg = SettingsDialog(self.output_file, str(self.page_size), self.theme, self.bg_image, self.bg_pattern, self)
        if dlg.exec():
            vals = dlg.get_values()
            self.output_file = vals["output"]
            self.page_size = vals["page_size"]
            self.bg_image = vals["bg_image"]
            self.bg_pattern = vals["bg_pattern"]
            
            new_theme = vals["theme"]
            if new_theme != self.theme:
                self.theme = new_theme
                self.apply_theme(self.theme)
            
            QMessageBox.information(self, "Settings", "Settings updated.")

    def add_input_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add Files", "", "Images/PDFs (*.pdf *.png *.jpg *.jpeg *.bmp)")
        if files:
            self.input_paths.extend(files)
            progress = QProgressDialog("Loading files...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            try:
                generator = load_input_files(files)
                for img_data, fname, pnum in generator:
                    self.pages.append((img_data, fname, pnum))
                    QApplication.processEvents()
                
                if len(self.pages) > 0 and self.canvas.pixmap_item.pixmap().isNull():
                    self.show_current_page()
                else:
                    self.setWindowTitle(f"ExCut - {self.pages[self.current_idx][1]} (Page {self.pages[self.current_idx][2]}) [{self.current_idx + 1}/{len(self.pages)}]")
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load files: {e}")
            progress.close()

    def save_current_project(self):
        if self.current_project_path:
            self._save_to_path(self.current_project_path)
        else:
            self.browse_save_project()

    def browse_save_project(self):
        default = self.current_project_path if self.current_project_path else ""
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", default, "ExCut Project (*.excu)")
        if path:
            if not path.endswith(".excu"):
                path += ".excu"
            self._save_to_path(path)

    def _save_to_path(self, path):
        try:
            items_state = self._get_sidebar_state()
            
            # Serialize Pending Parts
            pending_state = []
            for p, meta in self.pending_parts:
                # meta: {'page_idx', 'rect'}
                # Need to convert rect
                pmeta = meta.copy()
                if 'rect' in pmeta:
                    r = pmeta['rect']
                    if isinstance(r, QRect):
                        pmeta['rect'] = [r.x(), r.y(), r.width(), r.height()]
                pending_state.append(pmeta)
            
            meta = {
                "theme": self.theme, 
                "page_size": self.page_size, 
                "output_file": self.output_file,
                "bg_image": self.bg_image,
                "bg_pattern": self.bg_pattern,
                "current_idx": self.current_idx,
                "sticky_mode": self.sidebar.sticky_mode,
                "pending_parts": pending_state,
                "undo_stack": self._serialize_stack(self.undo_stack),
                "redo_stack": self._serialize_stack(self.redo_stack)
            }
            
            save_project(path, self.input_paths, items_state, metadata=meta)
            self.current_project_path = path
            QMessageBox.information(self, "Success", f"Project saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project: {e}")

    def _serialize_stack(self, stack):
        # Recursively convert QRects to lists for JSON serialization
        serialized = []
        for snapshot in stack:
            if isinstance(snapshot, list):
                serialized.append(self._clean_snapshot_for_json(snapshot))
            elif isinstance(snapshot, dict):
                # Handle rotation dicts
                if snapshot.get("type") == "rotate":
                     # data is tuple (img_data, fname, pnum)
                     # img_data is bytes. json can't serialize bytes directly?
                     # But save_project handles bytes for main pages?
                     # No, save_project calls json.dump. Bytes are NOT json serializable.
                     # We must skip saving rotation undo steps or serialize them properly?
                     # Rotation steps contain FULL PAGE DATA. This is heavy.
                     # But current implementation uses pickle-like behavior?
                     # No, project_io uses json + zip.
                     # For rotation, we should probably NOT save it to disk in undo stack, 
                     # or we must encode it.
                     # Given the complexity, let's filter out 'rotate' actions from saved stack 
                     # OR properly encode. 
                     # For now, let's just save sidebar states (lists).
                     # If we encounter a dict (rotation), we skip it to avoid crash/bloat?
                     # Or we can try to save it. But bytes must be base64.
                     pass 
                else: 
                     # Should be list for sidebar state
                     serialized.append(self._clean_snapshot_for_json([snapshot])[0])
        return serialized

    def _clean_snapshot_for_json(self, items):
        cleaned = []
        for item in items:
            c_item = item.copy()
            
            if "parts" in c_item:
                new_parts = []
                for p in c_item["parts"]:
                    np = p.copy()
                    if "rect" in np:
                        r = np["rect"]
                        if isinstance(r, QRect):
                            np["rect"] = [r.x(), r.y(), r.width(), r.height()]
                    new_parts.append(np)
                c_item["parts"] = new_parts
            
            if "children" in c_item:
                c_item["children"] = self._clean_snapshot_for_json(c_item["children"])
            
            cleaned.append(c_item)
        return cleaned

    def _get_sidebar_state(self):
        state = []
        root = self.sidebar.tree.invisibleRootItem()
        for i in range(root.childCount()):
            state.append(self._item_to_dict(root.child(i)))
        return state

    def _item_to_dict(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole).copy()
        if "content" in data: del data["content"]

        
        
        # Recursively convert QRects in parts
        if "parts" in data:
            new_parts = []
            for p in data["parts"]:
                # p can be dict or tuple (pixmap, meta_dict)
                meta = p
                if isinstance(p, (list, tuple)) and len(p) > 1:
                    # If it's a tuple, we only care about metadata for snapshotting/saving
                    # The content is usually ignored or reconstructed
                    # Wait, for Undo/Redo IN MEMORY, we want to KEEP the Pixmap if possible?
                    # The undo stack uses these snapshots. 
                    # If we discard the pixmap here, _restore_sidebar_items must RECONSTRUCT it.
                    # _restore_sidebar_items calls _reconstruct_pixmap which is expensive but correct.
                    # AND _reconstruct_pixmap handles both tuples and dicts.
                    # BUT `_get_sidebar_state` is ALSO used for `save_project` (disk). 
                    # `_save_to_path` helper CALLS `_get_sidebar_state`.
                    # So `_item_to_dict` MUST return something JSON-serializable-friendly OR be cleaned later.
                    # `_save_to_path` calls `save_project`. `save_project` iterates items.
                    # `save_project` EXPECTS `parts` to be a list of dicts with 'rect'.
                    # It copies the item and does `np.copy()`. If `np` is a tuple inside `save_project`, it will CRASH there too!
                    # Checked project_io.py:
                    # line 69: for p in s_item["parts"]: np = p.copy()
                    # YES, `save_project` will crash if `parts` contains tuples because tuples don't have .copy().
                    
                    # So `_item_to_dict` acts as a sanitizer for the sidebar's "complex" state into "simple" state (dicts).
                    # Ideally, `_item_to_dict` should STRIP the pixmap from the tuple and return just the metadata dict.
                    meta = p[1]
                
                # Check for dict type before copying
                if isinstance(meta, dict):
                    np = meta.copy()
                    if "rect" in np:
                        r = np["rect"]
                        if isinstance(r, QRect):
                            np["rect"] = [r.x(), r.y(), r.width(), r.height()]
                    new_parts.append(np)
                else:
                     # Fallback? Should not happen if data is valid
                     pass

            data["parts"] = new_parts
        
        children = []
        for i in range(item.childCount()):
            children.append(self._item_to_dict(item.child(i)))
        if children:
            data['children'] = children
            
        return data

    def browse_load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "ExCut Project (*.excu)")
        if path:
            self._load_project_file(path)

    def _load_project_file(self, path):
         try:
            self.pages = []
            self.input_paths = []
            self.sidebar.tree.clear()
            self.sidebar.remove_pending()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # We need to Keep the temp dir alive? 
                # No, we load images into memory.
                pass
                
            # Actually load_project helper does extraction. 
            # We need a persistent location for assets if we want to reload them later?
            # Current implementation loads all into memory.
            
            # Create a dedicated extract dir that persists or clean up?
            # ExCut loads everything to memory (self.pages).
            
            extract_dir = tempfile.mkdtemp()
            # Clean up old extract_dir if exists?
            
            input_paths, items, metadata = load_project(path, extract_dir)
            self.input_paths = input_paths
            self.current_project_path = path
            
            if "theme" in metadata:
                self.theme = metadata["theme"]
                self.apply_theme(self.theme)
            if "page_size" in metadata:
                # Handle tuple vs list
                ps = metadata["page_size"]
                if isinstance(ps, list): ps = tuple(ps)
                self.page_size = ps
                
            if "output_file" in metadata:
                self.output_file = metadata["output_file"]
                
            if "bg_image" in metadata:
                 self.bg_image = metadata["bg_image"]
            if "bg_pattern" in metadata:
                 self.bg_pattern = metadata["bg_pattern"]
                 
            self.load_images_from_paths(self.input_paths)
            self._restore_sidebar_items(items)
            
            if "current_idx" in metadata:
                self.current_idx = metadata["current_idx"]
            
            if "sticky_mode" in metadata:
                self.sidebar.set_sticky_mode(metadata["sticky_mode"])
                
            self.show_current_page()
            
            # Restore Pending
            if "pending_parts" in metadata:
                for pmeta in metadata["pending_parts"]:
                    if "rect" in pmeta and isinstance(pmeta["rect"], list):
                        x, y, w, h = pmeta["rect"]
                        pmeta["rect"] = QRect(x, y, w, h)
                    parts = [pmeta]
                    pix = self._reconstruct_pixmap(parts)
                    if pix:
                        self.pending_parts.append((pix, pmeta))
                if self.pending_parts:
                    parts_visuals = [p[0] for p in self.pending_parts]
                    preview = self.combine_parts(parts_visuals)
                    self.sidebar.update_pending_exercise(preview)
            
            # Restore Undo/Redo Stacks
            # They are lists of snapshots.
            # Snapshots are lists of items (dicts).
            # The items have 'rect' lists that need to be QRects?
            # actually _restore_sidebar_items handles dict->item creation BUT relies on gui helper for QRect?
            # No, _restore_sidebar_items iterates a list.
            # We need to recursively fix QRects in the stacks if we want them to be "ready to restore".
            
            def fix_snapshot_rects(snapshot):
                fixed = []
                for item in snapshot:
                    # Shallow copy item
                    c_item = item.copy()
                    if "parts" in c_item:
                         new_parts = []
                         for p in c_item["parts"]:
                             np = p.copy()
                             if "rect" in np and isinstance(np["rect"], list):
                                 x,y,w,h = np["rect"]
                                 np["rect"] = QRect(x,y,w,h)
                             new_parts.append(np)
                         c_item["parts"] = new_parts
                    
                    if "children" in c_item:
                        c_item["children"] = fix_snapshot_rects(c_item["children"])
                    fixed.append(c_item)
                return fixed

            self.undo_stack = []
            if "undo_stack" in metadata:
                for s in metadata["undo_stack"]:
                    self.undo_stack.append(fix_snapshot_rects(s))
                    
            self.redo_stack = []
            if "redo_stack" in metadata:
                for s in metadata["redo_stack"]:
                    self.redo_stack.append(fix_snapshot_rects(s))

            self.current_state_snapshot = self._get_sidebar_state()
            
         except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load project: {e}")
            self.current_idx = 0
            self.pending_parts = []
            self.sidebar.tree.clear()
            self.sidebar.remove_pending()
            self.canvas.clear_selection()
            self.canvas.set_image(None)

            input_paths, items, metadata = load_project(path, self.temp_dir)
            
            self.input_paths = input_paths
            self.current_project_path = path
            
            if "theme" in metadata:
                self.theme = metadata["theme"]
                self.apply_theme(self.theme)
            if "page_size" in metadata:
                 self.page_size = metadata["page_size"]
            if "output_file" in metadata:
                 self.output_file = metadata["output_file"]
            if "bg_image" in metadata:
                 self.bg_image = metadata["bg_image"]
            if "bg_pattern" in metadata:
                 self.bg_pattern = metadata["bg_pattern"]
                 
            self.load_images_from_paths(self.input_paths)
            self._restore_sidebar_items(items)
            
            if "current_idx" in metadata:
                self.current_idx = metadata["current_idx"]
            
            if "sticky_mode" in metadata:
                self.sidebar.set_sticky_mode(metadata["sticky_mode"])
                
            self.show_current_page()
            
            self.show_current_page()
            
            # Restore Pending
            if "pending_parts" in metadata:
                for pmeta in metadata["pending_parts"]:
                    # Deserialize rect
                    if "rect" in pmeta and isinstance(pmeta["rect"], list):
                        x, y, w, h = pmeta["rect"]
                        pmeta["rect"] = QRect(x, y, w, h)
                        
                    # Reconstruct pixmap
                    parts = [pmeta] # combine takes list
                    pix = self._reconstruct_pixmap(parts)
                    if pix:
                        self.pending_parts.append((pix, pmeta))
                
                # Update visual
                if self.pending_parts:
                    parts_visuals = [p[0] for p in self.pending_parts]
                    preview = self.combine_parts(parts_visuals)
                    self.sidebar.update_pending_exercise(preview)
            
            # Init Snapshot
            self.current_state_snapshot = self._get_sidebar_state()
            self.undo_stack = []
            self.redo_stack = []
            
         except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load project: {e}")

    def on_sidebar_change(self):
        # Capture new state
        new_state = self._get_sidebar_state()
        
        # Push OLD state to undo
        self.undo_stack.append(self.current_state_snapshot)
        self.current_state_snapshot = new_state
        self.redo_stack.clear() # Invalidated

    def push_canvas_state(self):
        if not self.current_editing_item:
            return
        
        data = self.current_editing_item.data(0, Qt.ItemDataRole.UserRole)
        import copy
        state = copy.deepcopy(data.get("parts", []))
        self.canvas_undo_stack.append(state)
        self.canvas_redo_stack.clear()

    def undo_canvas(self):
        if not self.canvas_undo_stack or not self.current_editing_item:
            return False
            
        # Push current to redo
        data = self.current_editing_item.data(0, Qt.ItemDataRole.UserRole)
        import copy
        current_state = copy.deepcopy(data.get("parts", []))
        self.canvas_redo_stack.append(current_state)
            
        state = self.canvas_undo_stack.pop()
        
        # Restore logic
        data["parts"] = state
        self.current_editing_item.setData(0, Qt.ItemDataRole.UserRole, data)
        
        # Refresh Canvas
        self.handle_recrop(self.current_editing_item, push_state=False)
        return True

    def redo_canvas(self):
        if not self.canvas_redo_stack or not self.current_editing_item:
             return False

        # Push current to undo
        data = self.current_editing_item.data(0, Qt.ItemDataRole.UserRole)
        import copy
        current_state = copy.deepcopy(data.get("parts", []))
        self.canvas_undo_stack.append(current_state)
        
        state = self.canvas_redo_stack.pop()
        
        data["parts"] = state
        self.current_editing_item.setData(0, Qt.ItemDataRole.UserRole, data)
        
        self.handle_recrop(self.current_editing_item, push_state=False)
        return True

    def undo(self):
        # Try Canvas Undo first if active
        if self.current_editing_item and self.undo_canvas():
             return

        if not self.undo_stack:
            return
            
        item = self.undo_stack.pop()
        
        if isinstance(item, dict) and item.get('type') == 'rotate':
             page_idx = item['page_idx']
             old_data = item['data']
             
             # Save current for Redo
             current_data = self.pages[page_idx]
             self.redo_stack.append({'type': 'rotate', 'page_idx': page_idx, 'data': current_data})
             
             self.pages[page_idx] = old_data
             if self.current_idx == page_idx:
                 self.show_current_page()
        else:
             state_to_restore = item
             
             # Save CURRENT state to Redo Stack BEFORE restoring old state
             self.redo_stack.append(self.current_state_snapshot)
             
             # Now Update Current to be the Restored state
             self.current_state_snapshot = state_to_restore
        
             self.sidebar.tree.blockSignals(True)
             self.sidebar.tree.clear()
             self._restore_sidebar_items(state_to_restore)
             self.sidebar.tree.blockSignals(False)
             self.sidebar.restore_widgets()

    def redo(self):
        if self.current_editing_item and self.redo_canvas():
             return

        if not self.redo_stack:
            return

        item = self.redo_stack.pop()
        
        if isinstance(item, dict) and item.get('type') == 'rotate':
             page_idx = item['page_idx']
             redo_data = item['data'] 
             
             # Save current to Undo
             current_data = self.pages[page_idx]
             self.undo_stack.append({'type': 'rotate', 'page_idx': page_idx, 'data': current_data})
             
             self.pages[page_idx] = redo_data
             if self.current_idx == page_idx:
                 self.show_current_page()
        else:
             state_to_restore = item
             self.undo_stack.append(self.current_state_snapshot)
             
             self.sidebar.tree.blockSignals(True)
             self.sidebar.tree.clear()
             self._restore_sidebar_items(state_to_restore)
             self.sidebar.tree.blockSignals(False)
             self.sidebar.restore_widgets()
             
             self.current_state_snapshot = state_to_restore

    def _restore_sidebar_items(self, items, parent_item=None):
        import copy
        # Deep copy the items list to prevent mutation of the undo stack
        # This is critical because we might modify 'rect' types in place below if we aren't careful,
        # or if previous logic did. But strictly, we should work on a copy.
        items_copy = copy.deepcopy(items)
        
        for idx, data in enumerate(items_copy):
            # FIX: Ensure nested rects are deserialized if gui.py handles it
            if "parts" in data:
                for p in data["parts"]:
                    # Handle both Dict and Tuple cases for safety
                    meta = None
                    if isinstance(p, dict):
                         meta = p
                    elif isinstance(p, (list, tuple)) and len(p) > 1 and isinstance(p[1], dict):
                         meta = p[1]
                         
                    if meta and "rect" in meta and isinstance(meta["rect"], list):
                        x,y,w,h = meta["rect"]
                        meta["rect"] = QRect(x,y,w,h)

            if data["type"] == "group":
                from PyQt6.QtWidgets import QTreeWidgetItem
                item = QTreeWidgetItem()
                item.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "group", 
                    "title": data["title"], 
                    "show_title": data.get("show_title", False)
                })
                
                if parent_item:
                    parent_item.addChild(item)
                else:
                    self.sidebar.tree.invisibleRootItem().addChild(item)
                item.setExpanded(True)
                self.sidebar._setup_item_widget(item, data["title"], is_group=True)
                
                if "children" in data:
                    self._restore_sidebar_items(data["children"], item)
                    
            elif data["type"] == "image":
                # Ensure rects in parts are QRects (snapshots store them as lists)
                parts = data.get("parts", [])
                clean_parts = []
                for p in parts:
                    # Deep copy the part data to ensure independence
                    if isinstance(p, (list, tuple)):
                         # Reconstruct tuple (pix, meta)
                         pix_ref = p[0]
                         meta_copy = p[1].copy() if len(p) > 1 and isinstance(p[1], dict) else {}
                         # We don't necessarily need to clone the QPixmap here if reconstruction handles it
                         clean_parts.append((pix_ref, meta_copy))
                    else:
                         # Full deepcopy for dicts
                         clean_parts.append(copy.deepcopy(p))
                
                pix = self._reconstruct_pixmap(clean_parts)
                if pix:
                    from PyQt6.QtWidgets import QTreeWidgetItem
                    item = QTreeWidgetItem()
                    # Store completely FRESH data dict
                    item_data = {"type": "image", "content": pix, "title": data.get("title", ""), "parts": clean_parts}
                    item.setData(0, Qt.ItemDataRole.UserRole, item_data)
                    
                    if parent_item:
                        parent_item.addChild(item)
                    else:
                        root = self.sidebar.tree.invisibleRootItem()
                        root.addChild(item)
                        
                    self.sidebar._setup_item_widget(item, data.get("title", ""), icon=pix)
                else:
                     print(f"WARNING: Failed to restore item '{data.get('title', 'Unknown')}'. invalid parts data.")
                    
            elif data["type"] == "title":
                 from PyQt6.QtWidgets import QTreeWidgetItem
                 item = QTreeWidgetItem()
                 item.setData(0, Qt.ItemDataRole.UserRole, {"type": "title", "content": None, "title": data["title"]})
                 
                 if parent_item:
                     parent_item.addChild(item)
                 else:
                     self.sidebar.tree.invisibleRootItem().addChild(item)
                     
                 self.sidebar._setup_item_widget(item, data["title"], is_title=True)

    def _reconstruct_pixmap(self, parts_data):
        if not parts_data: return None
        pixmaps = []
        for i, p in enumerate(parts_data):
            # Check if it's a tuple (Pixmap, Meta) - from Clone/Manual Copy
            if isinstance(p, (list, tuple)) and len(p) >= 1 and isinstance(p[0], QPixmap):
                pixmaps.append(p[0])
                continue
                
            # Otherwise assume it's a Metadata Dict - from Load/Undo
            meta = p
            if isinstance(p, (list, tuple)) and len(p) > 1:
                meta = p[1]
            
            if isinstance(meta, dict):
                pidx = meta.get('page_idx', -1)
                rect = meta.get('rect')
                
                if 0 <= pidx < len(self.pages) and rect:
                    img_data, _, _ = self.pages[pidx]
                    
                    if isinstance(img_data, QPixmap):
                        page_pix = img_data
                    elif isinstance(img_data, QImage):
                        page_pix = QPixmap.fromImage(img_data)
                    else:
                        # Assume bytes
                        page_img = QImage.fromData(img_data)
                        page_pix = QPixmap.fromImage(page_img)
                        
                    cropped = page_pix.copy(rect)
                    
                    pixmaps.append(cropped)
                    
        if not pixmaps:
            return None
            
        return self.combine_parts(pixmaps)

    def load_data(self):
        if not self.input_paths:
            return

        if len(self.input_paths) == 1 and self.input_paths[0].lower().endswith(".excu"):
            self._load_project_file(self.input_paths[0])
            return

        self.load_images_from_paths(self.input_paths)

    def load_images_from_paths(self, paths):
        progress = QProgressDialog("Loading files...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        try:
            generator = load_input_files(paths)
            for img_data, fname, pnum in generator:
                self.pages.append((img_data, fname, pnum))
                QApplication.processEvents()
            self.show_current_page()
            
            # Reset Undo History after initial load
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.current_state_snapshot = self._get_sidebar_state()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data: {e}")
        progress.close()

    def apply_theme(self, theme):
        # Use Modern QSS
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_stylesheet(theme))
            
        self.sidebar.update_theme(theme)
            
    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply_theme(self.theme)

    def show_current_page(self):
        if 0 <= self.current_idx < len(self.pages):
            img_data, fname, pnum = self.pages[self.current_idx]
            self.canvas.set_image(img_data)
            self.setWindowTitle(f"ExCut - {fname} (Page {pnum}) [{self.current_idx + 1}/{len(self.pages)}]")
            self.canvas.clear_selection()
            self.canvas.setFocus()
        else:
            self.canvas.set_image(None)
            self.setWindowTitle("ExCut - No Files Loaded")

    def prev_page(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self.show_current_page()

    def next_page(self):
        if self.current_idx < len(self.pages) - 1:
            self.current_idx += 1
            self.show_current_page()
            
    def rotate_page(self, direction):
        if not (0 <= self.current_idx < len(self.pages)):
            return
            
        # 1. Save state for Undo
        current_data = self.pages[self.current_idx] # (img_data, fname, pnum)
        self.undo_stack.append({
            'type': 'rotate', 
            'page_idx': self.current_idx, 
            'data': current_data
        })
        self.redo_stack.clear()
        
        # 2. Rotate
        img, fname, pnum = current_data
        
        # Handle bytes vs QPixmap/QImage
        if isinstance(img, bytes):
            qimg = QImage.fromData(img)
        elif isinstance(img, QPixmap):
            qimg = img.toImage()
        else:
            qimg = img
            
        angle = 90 if direction == 'right' else -90
        transform = QTransform().rotate(angle)
        new_qimg = qimg.transformed(transform, Qt.TransformationMode.SmoothTransformation)
        
        # Convert back to bytes? Or keep as QImage?
        # Canvas accepts QImage/QPixmap. Keeping as QPixmap is efficient for display.
        # But if anything else expects bytes (e.g. deepcopying?), it might be tricky.
        # Let's check if we should convert back to bytes for consistency.
        # Converting QImage to bytes (PNG) is expensive.
        # Let's store as QPixmap for performance.
        new_img = QPixmap.fromImage(new_qimg)
        
        # 3. Update
        self.pages[self.current_idx] = (new_img, fname, pnum)
        self.show_current_page()
            


    def cut_selection(self, is_partial):
        selection = self.canvas.get_selection()
        rect = self.canvas.current_selection_rect
        
        if not selection and not is_partial and not self.pending_parts:
            return

        metadata = None
        if selection:
            metadata = {'page_idx': self.current_idx, 'rect': rect}
            self.pending_parts.append((selection, metadata))
            self.canvas.clear_selection()
        
        if self.pending_parts:
            parts_visuals = [p[0] for p in self.pending_parts]
            preview = self.combine_parts(parts_visuals)
            self.sidebar.update_pending_exercise(preview)
        
        should_finalize = False
        is_sticky = self.sidebar.sticky_mode
        
        if not is_partial:
             should_finalize = True
             
        if should_finalize and self.pending_parts:
             parts_visuals = [p[0] for p in self.pending_parts]
             final_exercise = self.combine_parts(parts_visuals)
             
             all_metadata = [p[1] for p in self.pending_parts if p[1]]
             final_meta = {'parts': all_metadata}
             
             self.sidebar.add_exercise(final_exercise, metadata=final_meta)
             
             if is_sticky:
                 if selection:
                     self.pending_parts.pop() 
                 
                 if self.pending_parts:
                     parts_visuals = [p[0] for p in self.pending_parts]
                     preview = self.combine_parts(parts_visuals)
                     self.sidebar.update_pending_exercise(preview)
                 
             else:
                 self.sidebar.remove_pending()
                 self.pending_parts = []

    def combine_parts(self, parts):
        if not parts: return None
        if len(parts) == 1: return parts[0]
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

    def _on_canvas_selection_added(self, rect):
        self.push_canvas_state()
        self.add_new_rect_to_item(rect)

    def _on_rect_removed(self, item_gfx):
        self.push_canvas_state()
        self.remove_rect_from_item(item_gfx)
        
    def handle_recrop(self, item, push_state=True):
        self.current_editing_item = item
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if push_state:
            self.canvas_undo_stack.clear()
            # Push initial empty/current state?
            # Actually push only BEFORE change.
            # But the first change needs a base state.
            # Let's push current state as "base" if stack is empty?
            # No, standard Undo:
            # 1. State A.
            # 2. Action -> Push A. State B.
            pass
            

        if 'parts' in data and data['parts']:
            dlg = RecropDialog(self.pages, data['parts'], self)
            
            if dlg.exec():
                new_pixmaps, new_meta = dlg.get_result()
                if new_pixmaps:
                    combined_pix = self.combine_parts(new_pixmaps)
                    
                    data['content'] = combined_pix
                    data['parts'] = new_meta 
                    item.setData(0, Qt.ItemDataRole.UserRole, data)
                    
                    widget = self.sidebar.tree.itemWidget(item, 0)
                    if widget:
                        widget.set_icon(combined_pix)
                    
                    self.sidebar.state_changed.emit()
        else:
             QMessageBox.information(self, "Info", "Cannot edit this item (missing metadata).")

    def show_preview(self):
        items = self.sidebar.get_items() 
        dlg = PreviewDialog(items, self.bg_image, self.bg_pattern, self.page_size, self)
        dlg.exec()

    def finish_process(self):
        # Auto-save before finishing
        self.save_current_project()
        
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
                
                from PyQt6.QtCore import QBuffer, QIODevice
                buff = QBuffer()
                buff.open(QIODevice.OpenModeFlag.ReadWrite)
                qimg.save(buff, "PNG")
                new_item["content"] = io.BytesIO(buff.data().data())
            pdf_items.append(new_item)
            
        try:
            generate_output_pdf(pdf_items, self.output_file, self.bg_image, self.bg_pattern, self.page_size)
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
