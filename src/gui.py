from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter, QMessageBox, QProgressDialog, 
    QDialog, QVBoxLayout, QPushButton, QApplication, QLabel, QFileDialog, QMenuBar, QMenu,
    QFormLayout, QLineEdit, QComboBox, QScrollArea, QSlider, QColorDialog
)
from PyQt6.QtCore import Qt, QTimer, QRect, QRectF, QPointF
from PyQt6.QtGui import QAction, QPixmap, QPainter, QShortcut, QKeySequence, QColor, QPalette, QTransform, QImage, QPen, QBrush, QIcon, QPainterPath
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
        dlg.resize(600, 800)
        layout = QVBoxLayout(dlg)
        
        lbl = QLabel()
        # Scale to fit width while keeping aspect ratio
        max_w = dlg.width() - 40
        scaled = combined.scaled(max_w, combined.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        lbl.setPixmap(scaled)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(lbl)
        layout.addWidget(scroll)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)
        
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

from .paint_dialog import PaintCanvas

class FloatingPreviewWindow(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setWindowTitle("Cut Preview / Quick Edit")
        self.resize(400, 400)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.toolbar = QHBoxLayout()
        self.color_btn = QPushButton("Brush Color")
        self.color_btn.clicked.connect(self.choose_color)
        self.toolbar.addWidget(self.color_btn)
        
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(1, 50)
        self.size_slider.setValue(5)
        self.size_slider.valueChanged.connect(self.size_changed)
        self.toolbar.addWidget(QLabel("Size:"))
        self.toolbar.addWidget(self.size_slider)
        
        self.eraser_btn = QPushButton("Eraser")
        self.eraser_btn.setCheckable(True)
        self.eraser_btn.clicked.connect(self.toggle_eraser)
        self.toolbar.addWidget(self.eraser_btn)
        
        self.color_mode_combo = QComboBox()
        self.color_mode_combo.addItems(["Original Color", "Grayscale", "Hide Red"])
        self.color_mode_combo.currentIndexChanged.connect(self.color_mode_changed)
        self.toolbar.addWidget(self.color_mode_combo)
        
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setShortcut(QKeySequence("Ctrl+Z"))
        self.undo_btn.clicked.connect(self.undo)
        self.toolbar.addWidget(self.undo_btn)
        
        self.redo_btn = QPushButton("Redo")
        self.redo_btn.setShortcut(QKeySequence("Ctrl+Y"))
        self.redo_btn.clicked.connect(self.redo)
        self.toolbar.addWidget(self.redo_btn)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_strokes)
        self.toolbar.addWidget(self.save_btn)
        
        self.toolbar_widget = QWidget()
        self.toolbar_widget.setLayout(self.toolbar)
        self.layout.addWidget(self.toolbar_widget)
        
        self.canvas_container = QVBoxLayout()
        self.layout.addLayout(self.canvas_container)
        
        self.canvas = None
        self.current_item = None
        self.empty_label = QLabel("No cut selected")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas_container.addWidget(self.empty_label)

    def set_pixmap(self, pixmap, existing_strokes=None, item=None):
        self.current_item = item
        if self.canvas:
            self.canvas_container.removeWidget(self.canvas)
            self.canvas.deleteLater()
            self.canvas = None
            
        if pixmap:
            self.empty_label.hide()
            self.canvas = PaintCanvas(pixmap)
            
            if item:
                data = item.data(0, Qt.ItemDataRole.UserRole)
                # Backward compatibility: map grayscale bool to color_mode
                mode = data.get("color_mode", "grayscale" if data.get("grayscale") else "color")
                self.canvas.color_mode = mode
                
                self.color_mode_combo.blockSignals(True)
                mode_index = {"color": 0, "grayscale": 1, "hide_red": 2}.get(mode, 0)
                self.color_mode_combo.setCurrentIndex(mode_index)
                self.color_mode_combo.blockSignals(False)
                
            if hasattr(self.main_window, 'last_paint_color'):
                self.canvas.brush_color = QColor(self.main_window.last_paint_color)
                self.canvas.brush_size = getattr(self.main_window, 'last_paint_size', 5)
            if existing_strokes:
                self.canvas.load_strokes(existing_strokes)
            self.canvas_container.addWidget(self.canvas)
            self.update_color_btn()
            self.size_slider.setValue(self.canvas.brush_size)
        else:
            self.empty_label.show()

    def choose_color(self):
        if not self.canvas: return
        color = QColorDialog.getColor(self.canvas.brush_color, self, "Choose Color", QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if color.isValid():
            self.canvas.brush_color = color
            self.main_window.last_paint_color = color.name()
            self.update_color_btn()

    def size_changed(self, value):
        if self.canvas:
            self.canvas.brush_size = value
            self.main_window.last_paint_size = value

    def update_color_btn(self):
        if not self.canvas: return
        color = self.canvas.brush_color.name()
        self.color_btn.setStyleSheet(f"background-color: {color}; color: {'white' if self.canvas.brush_color.lightness() < 128 else 'black'};")

    def toggle_eraser(self, checked):
        if self.canvas:
            self.canvas.is_eraser = checked

    def color_mode_changed(self, index):
        if self.canvas:
            modes = ["color", "grayscale", "hide_red"]
            if 0 <= index < len(modes):
                self.canvas.color_mode = modes[index]
                self.canvas.update()

    def undo(self):
        if self.canvas:
            self.canvas.undo()

    def redo(self):
        if self.canvas:
            self.canvas.redo()

    def save_strokes(self):
        if not self.canvas or not self.current_item: return
        strokes = [s[1] for s in self.canvas.strokes]
        
        self.main_window.apply_strokes_to_item(self.current_item, strokes, self.canvas.color_mode)

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
        
        self.unsaved_changes = False
        
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
        self.original_pages = [] # List of unpainted pristine (img_data, filename, page_num)
        self.page_rotations = [] # List of cumulative rotation angles
        self.current_idx = 0
        self.pending_parts = []
        self.last_paint_color = "#ff0000"
        self.last_paint_size = 5
        
        # Undo/Redo State
        self.undo_stack = []
        self.redo_stack = []
        self.current_state_snapshot = []
        
        self.floating_preview_window = None
        
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
        
        replace_pdf_action = QAction("Replace Source PDF(s)...", self)
        replace_pdf_action.triggered.connect(self.replace_source_pdf)
        file_menu.addAction(replace_pdf_action)
        
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
        
        view_menu = menubar.addMenu("View")
        float_preview_action = QAction("Floating Cut Preview", self)
        float_preview_action.triggered.connect(self.toggle_floating_preview)
        view_menu.addAction(float_preview_action)
        
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
        self.sidebar.request_paint.connect(self.handle_paint)
        self.sidebar.state_changed.connect(self.on_sidebar_change)
        self.sidebar.set_color_mode_requested.connect(self.set_mode_for_items)
        self.sidebar.tree.itemSelectionChanged.connect(self.update_floating_preview)
        
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

    def toggle_floating_preview(self):
        if self.floating_preview_window is None:
            self.floating_preview_window = FloatingPreviewWindow(self, self)
        
        if self.floating_preview_window.isVisible():
            self.floating_preview_window.hide()
        else:
            self.floating_preview_window.show()
            self.update_floating_preview()

    def update_floating_preview(self):
        if self.floating_preview_window and self.floating_preview_window.isVisible():
            items = self.sidebar.tree.selectedItems()
            if items:
                item = items[0]
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if data and data.get("type") == "image":
                    parts = data.get("parts", [])
                    pixmap = self._reconstruct_pixmap(parts, strokes=None)
                    existing_strokes = data.get("strokes", [])
                    if pixmap:
                        self.floating_preview_window.set_pixmap(pixmap, existing_strokes=existing_strokes, item=item)
                        return
            self.floating_preview_window.set_pixmap(None, None)

    def discard_pending(self):
        self.pending_parts = []
        self.sidebar.remove_pending()
        self.set_unsaved_changes(True)

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
            
            self.set_unsaved_changes(True)
            QMessageBox.information(self, "Settings", "Settings updated.")

    def add_input_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add Files", "", "Images/PDFs (*.pdf *.png *.jpg *.jpeg *.bmp)")
        if files:
            self.input_paths.extend(files)
            self.set_unsaved_changes(True)
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
                    self.update_window_title()
                    
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
                "page_rotations": self.page_rotations,
                "last_paint_color": getattr(self, 'last_paint_color', "#ff0000"),
                "last_paint_size": getattr(self, 'last_paint_size', 5),
                "undo_stack": self._serialize_stack(self.undo_stack),
                "redo_stack": self._serialize_stack(self.redo_stack)
            }
            
            save_project(path, self.input_paths, items_state, metadata=meta)
            self.current_project_path = path
            self.set_unsaved_changes(False)
            QMessageBox.information(self, "Success", f"Project saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project: {e}")

    def _serialize_stack(self, stack):
        serialized = []
        for snapshot in stack:
            if isinstance(snapshot, list):
                serialized.append(self._clean_snapshot_for_json(snapshot))
            elif isinstance(snapshot, dict):
                if snapshot.get("type") == "rotate":
                     pass 
                else: 
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

        if "parts" in data:
            new_parts = []
            for p in data["parts"]:
                meta = p
                if isinstance(p, (list, tuple)) and len(p) > 1:
                    meta = p[1]
                
                if isinstance(meta, dict):
                    np = meta.copy()
                    if "rect" in np:
                        r = np["rect"]
                        if isinstance(r, QRect):
                            np["rect"] = [r.x(), r.y(), r.width(), r.height()]
                    new_parts.append(np)
                else:
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
            self.original_pages = []
            self.input_paths = []
            self.sidebar.tree.clear()
            self.sidebar.remove_pending()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                pass
                
            extract_dir = tempfile.mkdtemp()
            
            input_paths, items, metadata = load_project(path, extract_dir)
            self.input_paths = input_paths
            self.current_project_path = path
            
            if "theme" in metadata:
                self.theme = metadata["theme"]
                self.apply_theme(self.theme)
            if "page_size" in metadata:
                ps = metadata["page_size"]
                if isinstance(ps, list): ps = tuple(ps)
                self.page_size = ps
                
            if "output_file" in metadata:
                self.output_file = metadata["output_file"]
                
            if "bg_image" in metadata:
                 self.bg_image = metadata["bg_image"]
            if "bg_pattern" in metadata:
                 self.bg_pattern = metadata["bg_pattern"]
            if "page_rotations" in metadata:
                 self.page_rotations = metadata["page_rotations"]
            if "last_paint_color" in metadata:
                 self.last_paint_color = metadata["last_paint_color"]
            if "last_paint_size" in metadata:
                 self.last_paint_size = metadata["last_paint_size"]
                 
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
            
            def fix_snapshot_rects(snapshot):
                if isinstance(snapshot, dict):
                    return snapshot.copy()
                    
                fixed = []
                for item in snapshot:
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
            if "last_paint_color" in metadata:
                 self.last_paint_color = metadata["last_paint_color"]
            if "last_paint_size" in metadata:
                 self.last_paint_size = metadata["last_paint_size"]
                 
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
            
            self.current_state_snapshot = self._get_sidebar_state()
            self.undo_stack = []
            self.redo_stack = []
            self.set_unsaved_changes(False)

    def on_sidebar_change(self):
        new_state = self._get_sidebar_state()
        
        self.undo_stack.append(self.current_state_snapshot)
        self.current_state_snapshot = new_state
        self.redo_stack.clear()
        self.set_unsaved_changes(True)

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
            
        data = self.current_editing_item.data(0, Qt.ItemDataRole.UserRole)
        import copy
        current_state = copy.deepcopy(data.get("parts", []))
        self.canvas_redo_stack.append(current_state)
            
        state = self.canvas_undo_stack.pop()
        
        data["parts"] = state
        self.current_editing_item.setData(0, Qt.ItemDataRole.UserRole, data)
        
        self.handle_recrop(self.current_editing_item, push_state=False)
        return True

    def redo_canvas(self):
        if not self.canvas_redo_stack or not self.current_editing_item:
             return False

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
        if self.current_editing_item and self.undo_canvas():
             return

        if not self.undo_stack:
            return
            
        item = self.undo_stack.pop()
        
        if isinstance(item, dict) and item.get('type') == 'rotate':
             page_idx = item['page_idx']
             old_data = item['data']
             old_angle = item.get('prev_angle', 0)
             
             current_data = self.pages[page_idx]
             self.redo_stack.append({
                 'type': 'rotate', 
                 'page_idx': page_idx, 
                 'data': current_data,
                 'prev_angle': self.page_rotations[page_idx]
             })
             
             self.pages[page_idx] = old_data
             self.page_rotations[page_idx] = old_angle
             self._rebuild_page_paint(page_idx)
             if self.current_idx == page_idx:
                 self.show_current_page()
        else:
             state_to_restore = item
             
             self.redo_stack.append(self.current_state_snapshot)
             
             self.current_state_snapshot = state_to_restore
        
             self.sidebar.tree.blockSignals(True)
             self.sidebar.tree.clear()
             self._restore_sidebar_items(state_to_restore)
             self.sidebar.tree.blockSignals(False)
             self.sidebar.restore_widgets()
             self.update_floating_preview()

    def redo(self):
        if self.current_editing_item and self.redo_canvas():
             return

        if not self.redo_stack:
            return

        item = self.redo_stack.pop()
        
        if isinstance(item, dict) and item.get('type') == 'rotate':
             page_idx = item['page_idx']
             redo_data = item['data'] 
             redo_angle = item.get('prev_angle', 0)
             
             current_data = self.pages[page_idx]
             self.undo_stack.append({
                 'type': 'rotate', 
                 'page_idx': page_idx, 
                 'data': current_data,
                 'prev_angle': self.page_rotations[page_idx]
             })
             
             self.pages[page_idx] = redo_data
             self.page_rotations[page_idx] = redo_angle
             if self.current_idx == page_idx:
                 self.show_current_page()
        else:
             state_to_restore = item
             self.redo_stack.append(self.current_state_snapshot)
             
             self.sidebar.tree.blockSignals(True)
             self.sidebar.tree.clear()
             self._restore_sidebar_items(state_to_restore)
             self.sidebar.tree.blockSignals(False)
             self.sidebar.restore_widgets()
             self.update_floating_preview()
             
             self.current_state_snapshot = state_to_restore

    def _restore_sidebar_items(self, items, parent_item=None):
        import copy
        items_copy = copy.deepcopy(items)
        
        for idx, data in enumerate(items_copy):
            if "parts" in data:
                for p in data["parts"]:
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
                parts = data.get("parts", [])
                strokes = data.get("strokes")
                clean_parts = []
                for p in parts:
                    if isinstance(p, (list, tuple)):
                         pix_ref = p[0]
                         meta_copy = p[1].copy() if len(p) > 1 and isinstance(p[1], dict) else {}
                         clean_parts.append((pix_ref, meta_copy))
                    else:
                         clean_parts.append(copy.deepcopy(p))
                
                color_mode = data.get("color_mode", "color")
                pix = self._reconstruct_pixmap(clean_parts, strokes=strokes, color_mode=color_mode)
                if pix:
                    from PyQt6.QtWidgets import QTreeWidgetItem
                    item = QTreeWidgetItem()
                    item_data = {"type": "image", "content": pix, "title": data.get("title", ""), "parts": clean_parts}
                    if strokes:
                        item_data["strokes"] = strokes
                    if "color_mode" in data:
                        item_data["color_mode"] = data["color_mode"]
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

    def _reconstruct_pixmap(self, parts_data, strokes=None, color_mode="color"):
        if not parts_data: return None
        pixmaps = []
        for i, p in enumerate(parts_data):
            if isinstance(p, (list, tuple)) and len(p) >= 1 and isinstance(p[0], QPixmap):
                pixmaps.append(p[0])
                continue
                
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
                        page_img = QImage.fromData(img_data)
                        page_pix = QPixmap.fromImage(page_img)
                        
                    cropped = page_pix.copy(rect)
                    
                    pixmaps.append(cropped)
                    
        if not pixmaps:
            return None
            
        full_pix = self.combine_parts(pixmaps)
        
        if color_mode == "grayscale":
            img = full_pix.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
            full_pix = QPixmap.fromImage(img)
        elif color_mode == "hide_red":
            img = full_pix.toImage().convertToFormat(QImage.Format.Format_RGB32)
            
            # Isolate Green channel to map Red to Black and White to White
            green_mask = QImage(img.size(), QImage.Format.Format_RGB32)
            green_mask.fill(QColor(0, 255, 0))
            p = QPainter(img)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
            p.drawImage(0, 0, green_mask)
            p.end()
            
            # Determine Qt's exact grayscale coefficient for pure green
            test_img = QImage(1, 1, QImage.Format.Format_RGB32)
            test_img.fill(QColor(0, 255, 0))
            test_gray = test_img.convertToFormat(QImage.Format.Format_Grayscale8)
            green_gray_val = test_gray.pixelColor(0, 0).red()
            if green_gray_val == 0: green_gray_val = 150
            
            # Convert to grayscale and normalize so Green (which was White) becomes 255 (White)
            # Red (which has 0 Green) becomes 0 (Black)
            img = img.convertToFormat(QImage.Format.Format_Grayscale8)
            table = [0xff000000 | (min(255, int(i * 255.0 / green_gray_val)) * 0x010101) for i in range(256)]
            img = img.convertToFormat(QImage.Format.Format_Indexed8, table)
            img = img.convertToFormat(QImage.Format.Format_Grayscale8)
            
            full_pix = QPixmap.fromImage(img)
        
        if strokes:
            # MUST copy full_pix to avoid baking strokes into cached pixmaps!
            result_pix = full_pix.copy()
            layer = QPixmap(result_pix.size())
            layer.fill(Qt.GlobalColor.transparent)
            
            layer_painter = QPainter(layer)
            layer_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            for stroke_dict in strokes:
                if stroke_dict.get("eraser"):
                    layer_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                else:
                    layer_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                
                pen = QPen(QColor(stroke_dict["color"]), stroke_dict["size"], Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                layer_painter.setPen(pen)
                
                path = QPainterPath()
                pts = stroke_dict["points"]
                if pts:
                    path.moveTo(QPointF(pts[0][0], pts[0][1]))
                    for p in pts[1:]:
                        path.lineTo(QPointF(p[0], p[1]))
                layer_painter.drawPath(path)
                
            layer_painter.end()
            
            painter = QPainter(result_pix)
            painter.drawPixmap(0, 0, layer)
            painter.end()
            
            return result_pix
            
        return full_pix

    def load_data(self):
        if hasattr(self, 'current_project_path') and self.current_project_path and os.path.exists(self.current_project_path) and self.current_project_path.lower().endswith(".excu"):
             self._load_project_file(self.current_project_path)
             return

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
                self.original_pages.append((img_data, fname, pnum))
                if len(self.page_rotations) < len(self.pages):
                    self.page_rotations.append(0)
                QApplication.processEvents()
            
            restored_rotations = self.page_rotations[:]
            self.page_rotations = [0] * len(self.pages) 
            for i in range(len(self.pages)):
                if i < len(restored_rotations) and restored_rotations[i] != 0:
                    self._apply_rotation_to_page(i, restored_rotations[i], save_undo=False, sync_items=False)

            self.show_current_page()
            
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.current_state_snapshot = self._get_sidebar_state()
            self.set_unsaved_changes(False)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data: {e}")
        progress.close()

    def replace_source_pdf(self):
        if not self.input_paths:
            QMessageBox.information(self, "Info", "No input files to replace.")
            return

        from PyQt6.QtWidgets import QInputDialog
        file_to_replace, ok = QInputDialog.getItem(
            self, "Select File to Replace", "Choose the file you want to replace:", self.input_paths, 0, False
        )
        if not ok or not file_to_replace:
            return
            
        old_path_idx = self.input_paths.index(file_to_replace)

        new_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select New PDF/Images", "", "Supported Files (*.pdf *.png *.jpg *.jpeg *.bmp)"
        )
        if not new_paths:
            return
            
        progress = QProgressDialog("Extracting and Replacing Source Files...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        try:
            generator = load_input_files(new_paths)
            new_pages = []
            for img_data, fname, pnum in generator:
                new_pages.append((img_data, fname, pnum))
                QApplication.processEvents()
                
            if not new_pages:
                progress.close()
                QMessageBox.warning(self, "Error", "No pages were extracted from the selected files.")
                return
                
            progress.close()
            
            progress = QProgressDialog("Finalizing Replacement...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
                
            start_idx = -1
            end_idx = -1
            for i, p in enumerate(self.pages):
                if p[1] == file_to_replace:
                    if start_idx == -1:
                        start_idx = i
                    end_idx = i
                    
            if start_idx == -1:
                start_idx = len(self.pages)
                end_idx = len(self.pages) - 1
                
            old_count = end_idx - start_idx + 1
            new_count = len(new_pages)
            delta = new_count - old_count
            
            self.pages[start_idx:end_idx+1] = new_pages
            self.original_pages[start_idx:end_idx+1] = new_pages
            
            if start_idx < len(self.page_rotations):
                rot_start = start_idx
                rot_end = min(end_idx + 1, len(self.page_rotations))
                self.page_rotations[rot_start:rot_end] = [0] * new_count
                
            if len(self.page_rotations) < len(self.pages):
                self.page_rotations.extend([0] * (len(self.pages) - len(self.page_rotations)))
            elif len(self.page_rotations) > len(self.pages):
                self.page_rotations = self.page_rotations[:len(self.pages)]
                
            for item, data in self.sidebar.iter_all_items():
                if "parts" in data:
                    updated = False
                    new_parts = []
                    for p in data["parts"]:
                        meta = p[1] if isinstance(p, tuple) else p
                        c_meta = meta.copy()
                        pidx = c_meta.get("page_idx", -1)
                        
                        if pidx > end_idx:
                            c_meta["page_idx"] = pidx + delta
                            updated = True
                        elif start_idx <= pidx <= end_idx:
                            updated = True
                        
                        new_parts.append(c_meta)
                            
                    if updated:
                        data["parts"] = new_parts
                        item.setData(0, Qt.ItemDataRole.UserRole, data)
                            
            self.input_paths[old_path_idx:old_path_idx+1] = new_paths
            
            for i in range(len(self.pages)):
                self._rebuild_page_paint(i)
                
            if self.current_idx >= len(self.pages):
                self.current_idx = 0
            self.show_current_page()
            self.update_floating_preview()
            
            self.set_unsaved_changes(True)
            QMessageBox.information(self, "Success", "Source PDF successfully replaced! Cuts and paints were preserved and shifted appropriately.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to replace files: {e}")
            
        progress.close()

    def apply_theme(self, theme):
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
            self.update_window_title()
            self.canvas.clear_selection()
            self.canvas.setFocus()
        else:
            self.canvas.set_image(None)
            self.update_window_title()

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
            
        angle = 90 if direction == 'right' else -90
        self._apply_rotation_to_page(self.current_idx, angle, save_undo=True)
        self.set_unsaved_changes(True)

    def _apply_rotation_to_page(self, page_idx, angle, save_undo=True, sync_items=True):
        if not (0 <= page_idx < len(self.pages)):
            return

        current_data = self.pages[page_idx]
        if save_undo:
            self.undo_stack.append({
                'type': 'rotate', 
                'page_idx': page_idx, 
                'data': current_data,
                'prev_angle': self.page_rotations[page_idx]
            })
            self.redo_stack.clear()
        
        self.page_rotations[page_idx] = (self.page_rotations[page_idx] + angle) % 360
        
        img, fname, pnum = current_data
        
        qimg = img if not isinstance(img, (bytes, QPixmap)) else (QImage.fromData(img) if isinstance(img, bytes) else img.toImage())
            
        transform = QTransform().rotate(angle)
        new_qimg = qimg.transformed(transform, Qt.TransformationMode.SmoothTransformation)
        
        new_img = QPixmap.fromImage(new_qimg)
        
        self.pages[page_idx] = (new_img, fname, pnum)
        
        if sync_items:
            self._update_items_on_rotation(page_idx, angle)
        
        self.set_unsaved_changes(True)
        self.show_current_page()

    def _transform_rect(self, rect, page_w, page_h, angle):
        if angle == 0: return rect
        
        if angle == 90:
            return QRect(page_h - (rect.y() + rect.height()), rect.x(), rect.height(), rect.width())
        elif angle == -90 or angle == 270:
            return QRect(rect.y(), page_w - (rect.x() + rect.width()), rect.height(), rect.width())
        elif abs(angle) == 180:
            return QRect(page_w - (rect.x() + rect.width()), page_h - (rect.y() + rect.height()), rect.width(), rect.height())
        return rect

    def _update_items_on_rotation(self, page_idx, angle):
        new_img, _, _ = self.pages[page_idx]
        new_w, new_h = new_img.width(), new_img.height()
        
        if abs(angle) % 180 == 90:
            old_w, old_h = new_h, new_w
        else:
            old_w, old_h = new_w, new_h

        for item, data in self.sidebar.iter_all_items():
            if data.get("type") == "image" and "parts" in data:
                updated = False
                new_parts = []
                for p in data["parts"]:
                    if p.get("page_idx") == page_idx:
                        p["rect"] = self._transform_rect(p["rect"], old_w, old_h, angle)
                        updated = True
                    new_parts.append(p)
                
                if updated:
                    data["parts"] = new_parts
                    new_pix = self._reconstruct_pixmap(new_parts, strokes=data.get("strokes"))
                    data["content"] = new_pix
                    
                    item.setData(0, Qt.ItemDataRole.UserRole, data)
                    widget = self.sidebar.tree.itemWidget(item, 0)
                    if widget:
                        widget.set_icon(new_pix)
                    
                    item.setIcon(0, QIcon(new_pix))
            
    def handle_paint(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data.get("type") != "image": return
        
        parts = data.get("parts", [])
        if not parts: return
        
        # We must reconstruct the pixmap WITHOUT strokes so the dialog can render them cleanly
        pixmap = self._reconstruct_pixmap(parts, strokes=None)
        if not pixmap: return
        
        existing_strokes = data.get("strokes", [])
        color_mode = data.get("color_mode", "grayscale" if data.get("grayscale") else "color")
        
        from .paint_dialog import PaintDialog
        dlg = PaintDialog(pixmap, existing_strokes=existing_strokes, color_mode=color_mode, parent=self)
        if dlg.exec():
            strokes = dlg.get_strokes()
            new_color_mode = dlg.get_color_mode()
            self.apply_strokes_to_item(item, strokes, new_color_mode)
            
    def apply_strokes_to_item(self, item, strokes, color_mode=None, add_undo=True):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data: return
        
        if add_undo:
            self.undo_stack.append(self.current_state_snapshot)
        
        data["strokes"] = strokes
        if color_mode is not None:
            data["color_mode"] = color_mode
        else:
            color_mode = data.get("color_mode", "grayscale" if data.get("grayscale") else "color")
        
        new_pix = self._reconstruct_pixmap(data.get("parts", []), strokes=strokes, color_mode=color_mode)
        data["content"] = new_pix
        item.setData(0, Qt.ItemDataRole.UserRole, data)
        widget = self.sidebar.tree.itemWidget(item, 0)
        if widget:
            widget.set_icon(new_pix)
            
        item.setIcon(0, QIcon(new_pix))
            
        if add_undo:
            self.current_state_snapshot = self._get_sidebar_state()
            self.redo_stack.clear()
            self.set_unsaved_changes(True)
            self.update_floating_preview()

    def set_mode_for_items(self, items, mode_to_set):
        image_items = []
        def _collect(item):
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data["type"] == "image":
                if item not in image_items:
                    image_items.append(item)
            elif data and data["type"] == "group":
                for i in range(item.childCount()):
                    _collect(item.child(i))

        for it in items:
            _collect(it)

        if not image_items: return
        
        self.undo_stack.append(self.current_state_snapshot)

        for item in image_items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            strokes = data.get("strokes", [])
            self.apply_strokes_to_item(item, strokes, color_mode=mode_to_set, add_undo=False)
            
        self.current_state_snapshot = self._get_sidebar_state()
        self.redo_stack.clear()
        self.set_unsaved_changes(True)
        self.update_floating_preview()

    def _rebuild_page_paint(self, page_idx):
        if page_idx < 0 or page_idx >= len(self.pages) or page_idx >= len(self.original_pages):
            return
            
        img_data, fname, pnum = self.original_pages[page_idx]
        
        if isinstance(img_data, QImage):
            full_pix = QPixmap.fromImage(img_data)
        elif isinstance(img_data, QPixmap):
            full_pix = QPixmap(img_data)
        else:
            img = QImage.fromData(img_data)
            full_pix = QPixmap.fromImage(img)
            
        angle = self.page_rotations[page_idx] if page_idx < len(self.page_rotations) else 0
        if angle != 0:
            transform = QTransform().rotate(angle)
            full_pix = full_pix.transformed(transform, Qt.TransformationMode.SmoothTransformation)
            
        self.pages[page_idx] = (full_pix, fname, pnum)


    def cut_selection(self, is_partial):
        selection = self.canvas.get_selection()
        rect = self.canvas.current_selection_rect
        
        if not selection and not is_partial and not self.pending_parts:
            return
            
        self.set_unsaved_changes(True)

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
                parts = item.get("parts", [])
                strokes = item.get("strokes")
                color_mode = item.get("color_mode", "color")
                
                if parts:
                    pix = self._reconstruct_pixmap(parts, strokes=strokes, color_mode=color_mode)
                else:
                    pix = item["content"]
                    
                if not pix:
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

    def set_unsaved_changes(self, dirty=True):
        if self.unsaved_changes != dirty:
            self.unsaved_changes = dirty
            self.update_window_title()

    def update_window_title(self):
        title = "ExCut"
        
        if 0 <= self.current_idx < len(self.pages):
            _, fname, pnum = self.pages[self.current_idx]
            title = f"ExCut - {fname} (Page {pnum}) [{self.current_idx + 1}/{len(self.pages)}]"
            if hasattr(self, 'current_project_path') and self.current_project_path:
                 pass # Could append project name if desired, but sticking to file focus for now
        elif self.pages:
             # Should not happen if filtered correctly but fallback
             title = f"ExCut - {len(self.pages)} Pages Loaded"
        else:
             title = "ExCut - No Files Loaded"

        if self.unsaved_changes:
            title += " *"
            
        self.setWindowTitle(title)

    def closeEvent(self, event):
        if self.unsaved_changes:
            reply = QMessageBox.question(
                self, 
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save them before quitting?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )
            
            if reply == QMessageBox.StandardButton.Save:
                # Save
                self.save_current_project()
                # Check if save was successful? save_current_project handles UI but doesn't return success/fail clearly
                # But it updates current_project_path and presumably unsaved_changes if we hook it up.
                # Let's verify if unsaved_changes is cleared.
                if self.unsaved_changes: 
                    # Save failed or cancelled inside save dialog
                    event.ignore()
                    return
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
