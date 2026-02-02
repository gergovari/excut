from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QRubberBand, QGraphicsRectItem, QGraphicsItem
from PyQt6.QtCore import Qt, QRectF, QPointF, QSize, pyqtSignal, QObject, QRect, QSizeF
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QBrush, QWheelEvent, QFont

class SignalProxy(QObject):
    geometry_changed = pyqtSignal()
    removed = pyqtSignal()
    about_to_change = pyqtSignal()

class ResizableRectItem(QGraphicsRectItem):
    def __init__(self, rect, parent=None):
        super().__init__(rect, parent)
        self.signals = SignalProxy()
        self.geometry_changed = self.signals.geometry_changed
        self.removed = self.signals.removed
        self.about_to_change = self.signals.about_to_change

        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | 
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setPen(QPen(QColor(255, 0, 0), 2, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(QColor(255, 0, 0, 50)))
        
        self.handle_size = 10
        self.current_handle = None
        self.is_resizing = False
        self.order_index = 1 # Display number

    def mouseDoubleClickEvent(self, event):
        self.removed.emit()
        super().mouseDoubleClickEvent(event)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        # Draw number
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.setBrush(QBrush(QColor(255, 0, 0)))
        
        # Small circle/box at top-left
        r = self.rect()
        radius = 12
        center = r.topLeft() + QPointF(radius, radius)
        painter.drawEllipse(center, radius, radius)
        
        painter.drawText(QRectF(center.x() - radius, center.y() - radius, radius*2, radius*2), 
                         Qt.AlignmentFlag.AlignCenter, str(self.order_index))
        
    def hoverMoveEvent(self, event):
        pos = event.pos()
        rect = self.rect()
        # Simple corner detection
        if (pos - rect.topLeft()).manhattanLength() < self.handle_size:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            self.current_handle = "TL"
        elif (pos - rect.bottomRight()).manhattanLength() < self.handle_size:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            self.current_handle = "BR"
        elif (pos - rect.topRight()).manhattanLength() < self.handle_size:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            self.current_handle = "TR"
        elif (pos - rect.bottomLeft()).manhattanLength() < self.handle_size:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            self.current_handle = "BL"
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor) # Move
            self.current_handle = None
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        self.about_to_change.emit()
        if self.current_handle:
            self.is_resizing = True
        else:
             super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_resizing:
            pos = event.pos()
            rect = self.rect()
            
            if self.current_handle == "TL":
                new_rect = QRectF(pos, rect.bottomRight())
            elif self.current_handle == "BR":
                new_rect = QRectF(rect.topLeft(), pos)
            elif self.current_handle == "TR":
                new_rect = QRectF(rect.bottomLeft().x(), pos.y(), pos.x() - rect.bottomLeft().x(), rect.bottomLeft().y() - pos.y())
                # QRectF init from top-left logic usually: QRectF(topLeft, bottomRight) or (x, y, w, h)
                # Let's use normalized later
                new_rect = QRectF(rect.topLeft().x(), pos.y(), pos.x() - rect.topLeft().x(), rect.height() + (rect.top() - pos.y()))
                # Actually simpler: just update coords
                new_rect = QRectF(
                   rect.left(), pos.y(),
                   pos.x() - rect.left(), rect.bottom() - pos.y() 
                )
            elif self.current_handle == "BL":
                new_rect = QRectF(
                   pos.x(), rect.top(),
                   rect.right() - pos.x(), pos.y() - rect.top()
                )
            
            self.setRect(new_rect.normalized())
            self.geometry_changed.emit()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.is_resizing = False
        self.geometry_changed.emit()
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.geometry_changed.emit()
        return super().itemChange(change, value)

class ImageCanvas(QGraphicsView):
    selection_finished = pyqtSignal(QRect)
    about_to_change = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        
        # Selection Item (Scene-based substitute for RubberBand)
        self.selection_item = QGraphicsRectItem()
        self.selection_item.setPen(QPen(QColor(255, 0, 0), 2, Qt.PenStyle.DashLine))
        self.selection_item.setBrush(QBrush(QColor(255, 0, 0, 50)))
        self.selection_item.setZValue(100) # Ensure on top
        self.selection_item.hide()
        self.scene.addItem(self.selection_item)
        
        self.origin = QPointF()
        self.selecting = False
        self.current_selection_rect = None # QRect (scene coords)
        
        # If True, selection is cleared/hidden immediately after mouse release
        self.auto_reset_selection = False

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def set_image(self, image_data):
        # Clear existing items except the pixmap_item itself if it's being reused
        # If we want to clear all items including rects, we'd need to manage that
        # For now, assume this just sets the background image.
        image = QImage.fromData(image_data)
        pixmap = QPixmap.fromImage(image)
        self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event: QWheelEvent):
        adj = (event.angleDelta().y() / 120) * 0.1
        self.scale(1 + adj, 1 + adj)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if we clicked on an item that is movable (like ResizeableRectItem)
            item = self.scene.itemAt(self.mapToScene(event.pos()), self.transform())
            if isinstance(item, ResizableRectItem):
                super().mousePressEvent(event) # Handled by item
                return

            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            # Map view pos to scene pos for origin
            self.origin = self.mapToScene(event.pos())
            
            self.selection_item.setRect(QRectF(self.origin, QSizeF()))
            self.selection_item.show()
            self.selecting = True
        else:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.selecting:
            if not self.origin.isNull():
                current_scene_pos = self.mapToScene(event.pos())
                rect = QRectF(self.origin, current_scene_pos).normalized()
                self.selection_item.setRect(rect)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.selecting:
            self.selecting = False
            
            # Get geometry from item (already in scene coords)
            scene_rect = self.selection_item.rect()
            
            # Clip to image bounds
            img_rect = self.pixmap_item.boundingRect()
            scene_rect = scene_rect.intersected(img_rect)
            
            self.current_selection_rect = scene_rect.toRect()
            
            # Update visual to match clipped rect
            self.selection_item.setRect(scene_rect)
            
            # Emit signal
            if not self.current_selection_rect.isEmpty():
                self.selection_finished.emit(self.current_selection_rect)
            
            # Hide the temporary selection ONLY if configured to auto-reset (e.g. RecropDialog)
            if self.auto_reset_selection:
                self.selection_item.hide() 
                self.current_selection_rect = None
                
        super().mouseReleaseEvent(event)


    def get_selection(self):
        if self.current_selection_rect and not self.current_selection_rect.isEmpty():
            return self.pixmap_item.pixmap().copy(self.current_selection_rect)
        return None

    def clear_selection(self):
        self.selection_item.hide()
        self.current_selection_rect = None
