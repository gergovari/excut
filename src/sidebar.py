from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel, 
    QPushButton, QHBoxLayout, QInputDialog, QLineEdit, QMenu, QDialog, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QIcon, QAction

class ImageViewerDialog(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Exercise Viewer")
        self.resize(800, 600)
        layout = QVBoxLayout(self)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        lbl = QLabel()
        lbl.setPixmap(pixmap)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setWidget(lbl)
        
        layout.addWidget(scroll)

class SidebarItemWidget(QWidget):
    delete_clicked = pyqtSignal()
    edit_clicked = pyqtSignal()
    copy_clicked = pyqtSignal()

    def __init__(self, text, icon=None, is_title=False):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # Drag Handle
        self.drag_label = QLabel("☰")
        self.drag_label.setStyleSheet("color: gray; font-size: 16px; cursor: move;")
        layout.addWidget(self.drag_label)
        
        # Thumbnail / Icon
        self.icon_label = QLabel()
        if icon:
            scaled = icon.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio)
            self.icon_label.setPixmap(scaled)
        elif is_title:
             self.icon_label.setText("T")
             self.icon_label.setStyleSheet("font-weight: bold; font-size: 20px; border: 1px solid #ccc; padding: 5px;")
        layout.addWidget(self.icon_label)
        
        # Title/Name
        self.name_label = QLabel(text)
        if is_title:
            self.name_label.setStyleSheet("font-weight: bold; font-size: 14px;") # Bigger title
        layout.addWidget(self.name_label, 1) # stretch
        
        # Copy Button
        self.copy_btn = QPushButton()
        self.copy_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon)) # Standard File Icon
        self.copy_btn.setToolTip("Copy")
        self.copy_btn.setFixedWidth(30)
        self.copy_btn.clicked.connect(self.copy_clicked.emit)
        layout.addWidget(self.copy_btn)

        # Edit Button (Pen)
        self.edit_btn = QPushButton("✎")
        self.edit_btn.setFixedWidth(30)
        self.edit_btn.clicked.connect(self.edit_clicked.emit)
        layout.addWidget(self.edit_btn)
        
        # Delete Button (Trash)
        self.del_btn = QPushButton()
        self.del_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_TrashIcon))
        self.del_btn.setFixedWidth(30)
        self.del_btn.setStyleSheet("color: red;") 
        self.del_btn.clicked.connect(self.delete_clicked.emit)
        layout.addWidget(self.del_btn)

    def set_text(self, text):
        self.name_label.setText(text)

class Sidebar(QWidget):
    finish_clicked = pyqtSignal()
    request_recrop = pyqtSignal(object) # param: item (to get data)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Guide Label
        # Guide Label
        self.guide_label = QLabel(
            "<b>Controls:</b><br>"
            "Page Switch: Arrows or H/L<br>"
            "Zoom: Mouse Wheel<br>"
            "Select: Drag Mouse<br>"
            "Cut: Enter | Append: Shift+Enter<br>"
            "Sidebar: Drag to Reorder<br>"
            "Double Click: Inspect Image"
        )
        # Default style, will be updated by set_theme
        self.guide_label.setTextFormat(Qt.TextFormat.RichText)
        self.layout.addWidget(self.guide_label)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list_widget.setSpacing(2)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_click)
        self.layout.addWidget(self.list_widget)
        
        # Pending Label
        self.pending_label = QLabel()
        self.pending_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pending_label.hide()
        self.layout.addWidget(self.pending_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.add_title_btn = QPushButton("Add Title Page")
        self.add_title_btn.clicked.connect(self.add_title_page)
        btn_layout.addWidget(self.add_title_btn)
        
        self.finish_btn = QPushButton("Finish")
        self.finish_btn.clicked.connect(self.finish_clicked.emit)
        btn_layout.addWidget(self.finish_btn)
        
        self.layout.addLayout(btn_layout)

    def get_insert_row(self):
        # If selection, return row + 1, else count
        rows = [self.list_widget.row(x) for x in self.list_widget.selectedItems()]
        if rows:
            return rows[0] + 1
        return self.list_widget.count()

    def add_exercise(self, pixmap, name=None, metadata=None):
        if name is None:
            name = ""
            
        item = QListWidgetItem()
        # metadata: {'page_idx': int, 'rect': QRect} for basic items
        data = {"type": "image", "content": pixmap, "title": name}
        if metadata:
            data.update(metadata)
            
        item.setData(Qt.ItemDataRole.UserRole, data)
        item.setSizeHint(QSize(0, 60))
        
        row = self.get_insert_row()
        self.list_widget.insertItem(row, item)
        
        widget = SidebarItemWidget(name, icon=pixmap)
        widget.delete_clicked.connect(lambda: self.delete_item(item))
        widget.edit_clicked.connect(lambda: self.edit_item(item, widget))
        widget.copy_clicked.connect(lambda: self.copy_item(item))
        
        self.list_widget.setItemWidget(item, widget)
        # Select new item for continuous insertion flow
        self.list_widget.setCurrentItem(item)
        self.list_widget.scrollToItem(item)

    def add_title_page(self):
        text, ok = QInputDialog.getText(self, "Add Title Page", "Enter title:")
        if ok and text:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, {"type": "title", "content": None, "title": text})
            item.setSizeHint(QSize(0, 60))
            
            row = self.get_insert_row()
            self.list_widget.insertItem(row, item)
            
            widget = SidebarItemWidget(text, is_title=True)
            widget.delete_clicked.connect(lambda: self.delete_item(item))
            widget.edit_clicked.connect(lambda: self.edit_item(item, widget))
            widget.copy_clicked.connect(lambda: self.copy_item(item))
            
            self.list_widget.setItemWidget(item, widget)
            self.list_widget.setCurrentItem(item)
            self.list_widget.scrollToItem(item)

    def delete_item(self, item):
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)

    def edit_item(self, item, widget):
        data = item.data(Qt.ItemDataRole.UserRole)
        current_title = data["title"]
        text, ok = QInputDialog.getText(self, "Rename", "New name:", text=current_title)
        if ok and text:
            data["title"] = text
            item.setData(Qt.ItemDataRole.UserRole, data)
            widget.set_text(text)
            
    def copy_item(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        new_data = data.copy()
        
        # Create new item
        new_item = QListWidgetItem()
        new_item.setData(Qt.ItemDataRole.UserRole, new_data)
        new_item.setSizeHint(QSize(0, 60))
        
        row = self.list_widget.row(item) + 1
        self.list_widget.insertItem(row, new_item)
        
        # Widget logic
        icon = new_data["content"] if new_data["type"] == "image" else None
        is_title = (new_data["type"] == "title")
        
        widget = SidebarItemWidget(new_data["title"], icon=icon, is_title=is_title)
        widget.delete_clicked.connect(lambda: self.delete_item(new_item))
        widget.edit_clicked.connect(lambda: self.edit_item(new_item, widget))
        widget.copy_clicked.connect(lambda: self.copy_item(new_item))
        
        self.list_widget.setItemWidget(new_item, widget)
        self.list_widget.setCurrentItem(new_item)

    def on_item_double_click(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data["type"] == "image":
            # Emit signal for main window to handle re-cropping
            self.request_recrop.emit(item)

    def update_pending_exercise(self, pixmap):
        if not self.pending_label.isVisible():
            self.pending_label.show()
            self.pending_label.setStyleSheet("border: 2px dashed #f39c12; padding: 5px; background-color: #fcf3cf;")
            
        w = self.width() - 40
        scaled = pixmap.scaled(w, w, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.pending_label.setPixmap(scaled)

    def remove_pending(self):
        self.pending_label.clear()
        self.pending_label.hide()

    def get_items(self):
        items = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            items.append(data)
        return items

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            items = self.list_widget.selectedItems()
            if items:
                self.delete_item(items[0])
        else:
            super().keyPressEvent(event)

    def set_theme(self, theme):
        if theme == "dark":
            # Dark mode: Dark background for guide, white text (handled by palette, but background needs opacity or color)
            self.guide_label.setStyleSheet("background: #444; color: white; padding: 5px; border-radius: 4px;")
        else:
            # Light mode: Light background
            self.guide_label.setStyleSheet("background: #eee; color: black; padding: 5px; border-radius: 4px;")
