from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QLabel, 
    QPushButton, QHBoxLayout, QInputDialog, QMenu, QDialog, QScrollArea,
    QAbstractItemView, QFrame, QApplication, QCheckBox, QDialogButtonBox,
    QLineEdit, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import QPixmap, QIcon, QAction, QDrag, QPainter, QColor, QPen

def draw_pen_icon():
    pix = QPixmap(24, 24)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Draw simple pen
    painter.setPen(QPen(QColor("#d4d4d4"), 2))
    painter.translate(12, 12)
    painter.rotate(45)
    # Body
    painter.drawRect(-3, -8, 6, 12)
    # Tip
    painter.drawLine(-3, 4, 0, 8)
    painter.drawLine(3, 4, 0, 8)
    
    painter.end()
    return QIcon(pix)

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

class GroupEditDialog(QDialog):
    def __init__(self, current_name, show_title, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Group")
        self.layout = QVBoxLayout(self)
        
        self.name_label = QLabel("Group Name:")
        self.layout.addWidget(self.name_label)
        
        self.name_input = QInputDialog() # We just use a line edit
        from PyQt6.QtWidgets import QLineEdit
        self.name_edit = QLineEdit(current_name)
        self.layout.addWidget(self.name_edit)
        
        self.show_title_chk = QCheckBox("Render as Title in PDF")
        self.show_title_chk.setChecked(show_title)
        self.layout.addWidget(self.show_title_chk)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def get_data(self):
        return self.name_edit.text(), self.show_title_chk.isChecked()

class DragHandle(QLabel):
    def __init__(self, tree, item, parent=None):
        super().__init__("☰", parent)
        self.tree = tree
        self.item = item
        self.setStyleSheet("color: #888; font-size: 16px; font-weight: bold; margin-right: 2px; margin-left: 0px;")
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.drag_start_pos:
            return
            
        if (event.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
            
        drag = QDrag(self.tree)
        mime_data = self.tree.mimeData([self.item])
        drag.setMimeData(mime_data)
        
        widget = self.parent()
        if widget:
            pixmap = widget.grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())
            
        drag.exec(Qt.DropAction.MoveAction)

class SidebarItemWidget(QWidget):
    delete_clicked = pyqtSignal()
    edit_clicked = pyqtSignal()
    copy_clicked = pyqtSignal()
    
    def __init__(self, text, tree, item, icon=None, is_title=False, is_group=False):
        super().__init__()
        self.tree = tree
        self.item = item
        self.is_title = is_title
        self.is_group = is_group
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2) # Zero horizontal, slight vertical
        layout.setSpacing(4)
        
        self.setMinimumHeight(40) # Ensure enough height for text

        
        # Drag Handle
        self.drag_label = DragHandle(tree, item, self)
        layout.addWidget(self.drag_label)
        
        self.icon_label = None
        
        if icon:
            self.icon_label = QLabel()
            self.icon_label.setPixmap(icon.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(self.icon_label)
        elif is_group:
             self.icon_label = QLabel("📁")
             self.icon_label.setStyleSheet("font-size: 16px;")
             layout.addWidget(self.icon_label)
        elif is_title:
             self.icon_label = QLabel("T")
             self.icon_label.setStyleSheet("font-weight: bold; font-size: 20px; border: 1px solid #ccc; padding: 5px;")
             layout.addWidget(self.icon_label)
            
        self.label = QLineEdit(text)
        self.label.setReadOnly(True)
        self.label.setFrame(False)
        self.label.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) # Pass clicks/drags to Tree
        
        # Initial Theme
        self.update_style()
             
        layout.addWidget(self.label)
        
        # Buttons (always visible)
        self.btn_container = QWidget()
        btn_layout = QHBoxLayout(self.btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)
        
        style = QApplication.style()
        
        btn_edit = QPushButton()
        btn_edit.setIcon(draw_pen_icon())
        
        edit_tooltip = "Edit (Double-click)"
        if self.is_title or self.is_group:
            edit_tooltip = "Rename (F2)"
            
        btn_edit.setToolTip(edit_tooltip)
        btn_edit.setFixedSize(24, 24)
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.clicked.connect(self.edit_clicked.emit)
        
        btn_copy = QPushButton()
        btn_copy.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)) # File look
        btn_copy.setToolTip("Duplicate")
        btn_copy.setFixedSize(24, 24)
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.clicked.connect(self.copy_clicked.emit)
        
        btn_del = QPushButton()
        btn_del.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon)) # Trash
        btn_del.setToolTip("Delete (Del)")
        btn_del.setFixedSize(24, 24)
        btn_del.setProperty("class", "danger-btn")
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.clicked.connect(self.delete_clicked.emit)
        
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_copy)
        btn_layout.addWidget(btn_del)
        
        layout.addWidget(self.btn_container)
        # Buttons always visible
        
    def update_theme(self, theme):
        self._current_theme = theme
        self.update_style(theme)

    def update_style(self, theme=None):
        if theme is None:
            theme = getattr(self, "_current_theme", "dark")
            
        color = "black" if theme == "light" else "white"
        
        # Explicitly matching QLineEdit selector to ensure specificity
        base_style = "QLineEdit { border: none; background: transparent;"
        
        style = ""
        if self.is_title:
             style = f"{base_style} font-weight: bold; font-size: 14px; color: {color}; }}"
        elif self.is_group:
             style = f"{base_style} font-weight: bold; font-size: 14px; text-decoration: underline; color: {color}; }}"
        else:
             style = f"{base_style} color: {color}; }}"
             
        self.label.setStyleSheet(style)

    # Removed enterEvent/leaveEvent to keep buttons visible
    def enterEvent(self, event):
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        super().leaveEvent(event)
        
    def set_text(self, text):
        self.label.setText(text)
        self.label.setCursorPosition(0)

    def set_icon(self, icon):
        if self.icon_label:
            self.icon_label.setPixmap(icon.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            # If no icon label existed (should only happen if created without icon/group/title which shouldn't happen for images)
            # Create one insert it? For now assume it exists if we are calling set_icon (image type)
            self.icon_label = QLabel()
            self.icon_label.setPixmap(icon.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            # Insert after drag handle (index 1)
            self.layout().insertWidget(1, self.icon_label)

class SidebarTree(QTreeWidget):
    widgets_refreshed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setIndentation(20)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dragMoveEvent(self, event):
        target = self.itemAt(event.position().toPoint())
        is_group = False
        if target:
            data = target.data(0, Qt.ItemDataRole.UserRole)
            is_group = (data and data.get("type") == "group")
            
        pos = self.dropIndicatorPosition()
        
        # Strict Rule: Only Groups can accept "OnItem" drops (nesting)
        # We REJECT (ignore) the event if user strictly tries to drop ON a non-group.
        # This hints the view to look for other options (like Above/Below).
        # However, if this makes "between" dropping impossible, we might need to rely on default behavior.
        # Default behavior of QTreeWidget usually allows dropping ON anything.
        if pos == QAbstractItemView.DropIndicatorPosition.OnItem and not is_group:
            event.ignore() 
            return

        super().dragMoveEvent(event)

    def dropEvent(self, event):
        # We must call super to handle the data move
        super().dropEvent(event)
        self.widgets_refreshed.emit()


class Sidebar(QWidget):
    finish_clicked = pyqtSignal()
    request_recrop = pyqtSignal(object) 
    request_discard = pyqtSignal()
    state_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        self.sticky_mode = False
        
        # Guide
        self.guide_label = QLabel(
            "<b>Controls:</b><br>"
            "Page: Arrows, H/L<br>"
            "Nav: J/K/Arrows<br>"
            "Cut: Enter | Append: Shift+Enter<br>"
            "Edit Group: Dbl Click/Pencil<br>"
            "Sticky: Dbl Click Preview<br>"
            "Undo/Redo: Ctrl+Z/Y"
        )
        self.guide_label.setTextFormat(Qt.TextFormat.RichText)
        self.layout.addWidget(self.guide_label)

        # Tree
        self.tree = SidebarTree()
        self.tree.itemDoubleClicked.connect(self.on_item_double_click)
        self.tree.widgets_refreshed.connect(self.restore_widgets)
        self.tree.widgets_refreshed.connect(self.state_changed.emit)
        self.layout.addWidget(self.tree)
        
        self.pending_container = QWidget()
        self.pending_layout = QVBoxLayout(self.pending_container)
        self.pending_layout.setContentsMargins(0, 5, 0, 5)
        
        self.pending_label = QLabel()
        self.pending_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pending_label.setToolTip("Double-click to toggle Sticky Mode")
        self.pending_label.mouseDoubleClickEvent = self.toggle_sticky_mode
        self.pending_layout.addWidget(self.pending_label)
        
        self.discard_btn = QPushButton("Discard Pending")
        self.discard_btn.setProperty("class", "danger-btn")
        self.discard_btn.clicked.connect(self.request_discard.emit)
        self.discard_btn.hide()
        self.pending_layout.addWidget(self.discard_btn)
        
        self.pending_container.hide()
        self.layout.addWidget(self.pending_container)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.add_group_btn = QPushButton("Add Group")
        self.add_group_btn.clicked.connect(self.add_group)
        btn_layout.addWidget(self.add_group_btn)
        
        self.add_title_btn = QPushButton("Add Title")
        self.add_title_btn.clicked.connect(self.add_title_page)
        btn_layout.addWidget(self.add_title_btn)
        
        self.layout.addLayout(btn_layout)
        
        self.finish_btn = QPushButton("Finish && Save PDF")
        self.finish_btn = QPushButton("Finish && Save PDF")
        self.finish_btn.setProperty("class", "success-btn")
        self.finish_btn.clicked.connect(self.finish_clicked.emit)
        self.layout.addWidget(self.finish_btn)

    def restore_widgets(self):
        root = self.tree.invisibleRootItem()
        self._recursive_restore(root)
        
    def _recursive_restore(self, parent_item):
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            # Check if widget exists
            if not self.tree.itemWidget(item, 0):
                # Restore
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if data:
                    is_group = (data["type"] == "group")
                    is_title = (data["type"] == "title")
                    icon = data.get("content") if data["type"] == "image" else None
                    self._setup_item_widget(item, data["title"], icon, is_group, is_title)
            
            # Recurse
            self._recursive_restore(item)

    def toggle_sticky_mode(self, event):
        self.sticky_mode = not self.sticky_mode
        border = "3px solid #e74c3c" if self.sticky_mode else "2px dashed #f39c12"
        self.pending_label.setStyleSheet(f"border: {border}; padding: 5px; background-color: #fcf3cf;")

    def get_insert_location(self):
        selected = self.tree.selectedItems()
        if not selected:
            root = self.tree.invisibleRootItem()
            return root, root.childCount()
        
        item = selected[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if data and data.get("type") == "group":
            return item, item.childCount()
        else:
            parent = item.parent() or self.tree.invisibleRootItem()
            idx = parent.indexOfChild(item)
            return parent, idx + 1

    def add_group(self):
        items_to_move = self.tree.selectedItems()
        
        dlg = GroupEditDialog("", show_title=False, parent=self)
        if dlg.exec():
            text, show_title = dlg.get_data()
            
            group_item = QTreeWidgetItem()
            group_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "group", "title": text, "show_title": show_title})
            
            parent, idx = self.get_insert_location()
            if items_to_move:
                first = items_to_move[0]
                parent = first.parent() or self.tree.invisibleRootItem()
                idx = parent.indexOfChild(first)
            
            parent.insertChild(idx, group_item)
            group_item.setExpanded(True)
            self._setup_item_widget(group_item, text, is_group=True)
            
            if items_to_move:
                for item in items_to_move:
                    old_parent = item.parent() or self.tree.invisibleRootItem()
                    ix = old_parent.indexOfChild(item)
                    if ix >= 0:
                        taken = old_parent.takeChild(ix)
                        group_item.addChild(taken)
                        
                        data = taken.data(0, Qt.ItemDataRole.UserRole)
                        icon = data.get("content") if data["type"] == "image" else None
                        is_grp = (data["type"] == "group")
                        is_ttl = (data["type"] == "title")
                        self._setup_item_widget(taken, data["title"], icon, is_grp, is_ttl)
            
            self.tree.setCurrentItem(group_item)
            self.state_changed.emit()

    def add_exercise(self, pixmap, name=None, metadata=None):
        if name is None:
            name = ""
        
        item = QTreeWidgetItem()
        data = {"type": "image", "content": pixmap, "title": name}
        if metadata:
            data.update(metadata)
        item.setData(0, Qt.ItemDataRole.UserRole, data)
        
        parent, idx = self.get_insert_location()
        parent.insertChild(idx, item)
        
        if parent != self.tree.invisibleRootItem():
            parent.setExpanded(True)

        self._setup_item_widget(item, name, icon=pixmap)
        
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        self.state_changed.emit()

    def add_title_page(self):
        text, ok = QInputDialog.getText(self, "Add Title Page", "Enter title:")
        if ok and text:
            item = QTreeWidgetItem()
            item.setData(0, Qt.ItemDataRole.UserRole, {"type": "title", "content": None, "title": text})
            
            parent, idx = self.get_insert_location()
            parent.insertChild(idx, item)
            
            self._setup_item_widget(item, text, is_title=True)
            self.tree.setCurrentItem(item)
            self.state_changed.emit()

    def _setup_item_widget(self, item, text, icon=None, is_group=False, is_title=False):
        # Set Flags correcty for Drag/Drop
        flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDragEnabled
        
        # Only Groups should allow "Drop On" (nesting)
        # All items allow "Drop Between" (reordering) implied by View properties
        if is_group:
            flags |= Qt.ItemFlag.ItemIsDropEnabled
        else:
            # Explicitly disable dropping ON a title/exercise
            # This forces the indicator to be Above or Below
             flags &= ~Qt.ItemFlag.ItemIsDropEnabled
             
        item.setFlags(flags)
        
        widget = SidebarItemWidget(text, self.tree, item, icon, is_title=is_title, is_group=is_group)
        widget.delete_clicked.connect(lambda: self.delete_item(item))
        widget.edit_clicked.connect(lambda: self.edit_item(item, widget))
        widget.copy_clicked.connect(lambda: self.copy_item(item))
        self.tree.setItemWidget(item, 0, widget)

    def delete_item(self, item, emit_signal=True):
        parent = item.parent() or self.tree.invisibleRootItem()
        parent.removeChild(item)
        if emit_signal:
            self.state_changed.emit()

    def edit_item(self, item, widget):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        # Check type
        if data.get("type") == "image":
            self.request_recrop.emit(item)
        elif data.get("type") == "group":
            # Group Edit Dialog
            dlg = GroupEditDialog(data["title"], data.get("show_title", False), self)
            if dlg.exec():
                text, show_title = dlg.get_data()
                data["title"] = text
                data["show_title"] = show_title
                item.setData(0, Qt.ItemDataRole.UserRole, data)
                widget.set_text(text)
                self.state_changed.emit()
        else:
            # Title Rename
            current_title = data["title"]
            text, ok = QInputDialog.getText(self, "Rename", "New name:", text=current_title)
            if ok and text:
                data["title"] = text
                item.setData(0, Qt.ItemDataRole.UserRole, data)
                widget.set_text(text)
                self.state_changed.emit()
                self.state_changed.emit()

    def copy_item(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        # Deep copy data structure manually to ensure control over types
        new_data = data.copy()
        
        if "parts" in new_data:
            # Manually copy parts to ensure proper structure (list of dicts or compatible tuples)
            new_parts = []
            for part in new_data["parts"]:
                # Handle Tuple (Pixmap, Meta)
                if isinstance(part, (list, tuple)) and len(part) >= 2:
                    pix = part[0]
                    meta = part[1].copy() if isinstance(part[1], dict) else {}
                    
                    if isinstance(pix, QPixmap):
                        new_parts.append((QPixmap(pix), meta)) # Copy QPixmap
                    else:
                        new_parts.append((pix, meta))
                        
                # Handle Dict (Metadata only)
                elif isinstance(part, dict):
                    new_parts.append(part.copy())
                
                # Fallback
                else:
                    import copy
                    new_parts.append(copy.deepcopy(part))
                    
            new_data["parts"] = new_parts
            
        new_item = QTreeWidgetItem()
        new_item.setData(0, Qt.ItemDataRole.UserRole, new_data)
        
        parent = item.parent() or self.tree.invisibleRootItem()
        idx = parent.indexOfChild(item)
        parent.insertChild(idx + 1, new_item)
        
        is_group = (new_data["type"] == "group")
        is_title = (new_data["type"] == "title")
        icon = new_data.get("content")
        
        self._setup_item_widget(new_item, new_data["title"], icon, is_group, is_title)
        self.tree.setCurrentItem(new_item)
        self.state_changed.emit()

    def on_item_double_click(self, item, column):
        # Determine type
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data.get("type") == "image":
            # Exercise -> Recrop
            self.request_recrop.emit(item)
        else:
            # Title/Group -> Rename/Edit
            widget = self.tree.itemWidget(item, 0)
            self.edit_item(item, widget)

    def rename_selected(self):
        items = self.tree.selectedItems()
        if not items: return
        
        changed = False
        if len(items) == 1:
            item = items[0]
            data = item.data(0, Qt.ItemDataRole.UserRole)
            
            widget = self.tree.itemWidget(item, 0)
            
            current_title = data["title"]
            text, ok = QInputDialog.getText(self, "Rename", "New name:", text=current_title)
            if ok and text:
                data["title"] = text
                item.setData(0, Qt.ItemDataRole.UserRole, data)
                widget.set_text(text)
                changed = True
        else:
            text, ok = QInputDialog.getText(self, "Mass Rename", "New Title Template (use %d for number):")
            if ok and text:
                for i, item in enumerate(items):
                    new_title = text.replace("%d", str(i+1)) if "%d" in text else f"{text} {i+1}"
                    data = item.data(0, Qt.ItemDataRole.UserRole)
                    data["title"] = new_title
                    item.setData(0, Qt.ItemDataRole.UserRole, data)
                    widget = self.tree.itemWidget(item, 0)
                    if widget: widget.set_text(new_title)
                changed = True
        
        if changed:
            self.state_changed.emit()

    def update_pending_exercise(self, pixmap):
        if not self.pending_container.isVisible():
            self.pending_container.show()
            self.discard_btn.show()
            border = "3px solid #e74c3c" if self.sticky_mode else "2px dashed #f39c12"
            self.pending_label.setStyleSheet(f"border: {border}; padding: 5px; background-color: #fcf3cf;")
            
        w = self.width() - 40
        scaled = pixmap.scaled(w, w, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.pending_label.setPixmap(scaled)

    def remove_pending(self):
        if not self.sticky_mode:
            self.pending_label.clear()
            self.pending_container.hide()
            self.discard_btn.hide()

    def get_items(self):
        items = []
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            self._collect_items(root.child(i), items)
        return items

    def _collect_items(self, item, items_list):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if data["type"] == "group":
            # Check flag
            if data.get("show_title", False):
                items_list.append({"type": "title", "title": data["title"], "content": None})
            
            for i in range(item.childCount()):
                self._collect_items(item.child(i), items_list)
        else:
            items_list.append(data)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_J:
            items = self.tree.selectedItems()
            if not items:
                top = self.tree.topLevelItem(0)
                if top:
                    self.tree.setCurrentItem(top)
            else:
                current = self.tree.currentItem()
                if current:
                    next_item = self.tree.itemBelow(current)
                    if next_item:
                        self.tree.setCurrentItem(next_item)
        elif event.key() == Qt.Key.Key_K:
            # Prev item
            items = self.tree.selectedItems()
            if not items:
                top = self.tree.topLevelItem(0)
                if top:
                    self.tree.setCurrentItem(top)
            else:
                current = self.tree.currentItem()
                if current:
                    prev_item = self.tree.itemAbove(current)
                    if prev_item:
                        self.tree.setCurrentItem(prev_item)
        elif event.key() == Qt.Key.Key_Delete:
            items = self.tree.selectedItems()
            if items:
                for item in items:
                    self.delete_item(item, emit_signal=False)
                self.state_changed.emit()
        elif event.key() == Qt.Key.Key_F2:
            self.rename_selected()
        else:
            super().keyPressEvent(event)
            
    def update_theme(self, theme):
        self._current_theme = theme
        # Guide Label Styling to match theme
        if theme == "dark":
            self.guide_label.setStyleSheet("background: #252526; color: #d4d4d4; padding: 8px; border-radius: 4px; border: 1px solid #454545;")
        else:
            self.guide_label.setStyleSheet("background: #f3f3f3; color: #333; padding: 8px; border-radius: 4px; border: 1px solid #ccc;")
            
        # Recursive update
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            self._update_item_style(root.child(i), theme)

    def _update_item_style(self, item, theme):
        widget = self.tree.itemWidget(item, 0)
        if widget and hasattr(widget, "update_theme"):
             widget.update_theme(theme)
         
        # Recursion
        for i in range(item.childCount()):
            self._update_item_style(item.child(i), theme)
