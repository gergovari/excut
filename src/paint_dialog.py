from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QColorDialog, QSlider, QWidget, QComboBox
)
from PyQt6.QtCore import Qt, QPoint, QPointF, QRect, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QPainterPath, QKeySequence, QImage

class PaintCanvas(QWidget):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.base_pixmap = pixmap
        self.setMinimumSize(300, 300)
        
        self.strokes = [] # List of (QPainterPath, dict)
        self.redo_stack = [] # List of (QPainterPath, dict)
        self.current_path = None
        self.current_points = []
        
        self.brush_color = QColor(255, 0, 0)
        self.brush_size = 5
        self.is_eraser = False
        self.color_mode = "color"
        self.scale_factor = 1.0
        self.offset = QPointF(0, 0)
        
    def load_strokes(self, existing_strokes):
        if not existing_strokes:
            return
            
        for s in existing_strokes:
            path = QPainterPath()
            pts = s.get("points", [])
            if pts:
                path.moveTo(QPointF(pts[0][0], pts[0][1]))
                for p in pts[1:]:
                    path.lineTo(QPointF(p[0], p[1]))
            
            self.strokes.append((path, s))
            
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
        
        w, h = self.width(), self.height()
        bw, bh = self.base_pixmap.width(), self.base_pixmap.height()
        
        scale_w = w / bw if bw > 0 else 1.0
        scale_h = h / bh if bh > 0 else 1.0
        self.scale_factor = min(scale_w, scale_h)
        
        draw_w = bw * self.scale_factor
        draw_h = bh * self.scale_factor
        
        self.offset = QPointF((w - draw_w) / 2.0, (h - draw_h) / 2.0)
        
        painter.translate(self.offset)
        painter.scale(self.scale_factor, self.scale_factor)
        
        if self.color_mode == "grayscale":
            img = self.base_pixmap.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
            pix = QPixmap.fromImage(img)
            painter.drawPixmap(0, 0, pix)
        elif self.color_mode == "bw":
            img = self.base_pixmap.toImage().convertToFormat(QImage.Format.Format_Mono)
            pix = QPixmap.fromImage(img)
            painter.drawPixmap(0, 0, pix)
        else:
            painter.drawPixmap(0, 0, self.base_pixmap)
        
        stroke_layer = QPixmap(self.base_pixmap.size())
        stroke_layer.fill(Qt.GlobalColor.transparent)
        
        layer_painter = QPainter(stroke_layer)
        layer_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        for path, stroke_dict in self.strokes:
            if stroke_dict.get("eraser"):
                layer_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            else:
                layer_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                
            pen = QPen(QColor(stroke_dict["color"]), stroke_dict["size"], Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            layer_painter.setPen(pen)
            layer_painter.drawPath(path)
            
        if self.current_path:
            if self.is_eraser:
                layer_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            else:
                layer_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(self.brush_color, self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            layer_painter.setPen(pen)
            layer_painter.drawPath(self.current_path)
            
        layer_painter.end()
        painter.drawPixmap(0, 0, stroke_layer)

    def _map_to_image(self, event):
        pos = event.position() if hasattr(event, 'position') else QPointF(event.pos())
        return (pos - self.offset) / self.scale_factor

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pt = self._map_to_image(event)
            self.current_path = QPainterPath()
            self.current_path.moveTo(pt)
            self.current_points = [[pt.x(), pt.y()]]
            self.redo_stack.clear()
            self.update()

    def mouseMoveEvent(self, event):
        if self.current_path:
            pt = self._map_to_image(event)
            self.current_path.lineTo(pt)
            self.current_points.append([pt.x(), pt.y()])
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.current_path:
            pt = self._map_to_image(event)
            self.current_path.lineTo(pt)
            self.current_points.append([pt.x(), pt.y()])
            
            stroke_dict = {
                "points": self.current_points,
                "color": self.brush_color.name(),
                "size": self.brush_size,
                "eraser": self.is_eraser
            }
            self.strokes.append((self.current_path, stroke_dict))
            self.current_path = None
            self.current_points = []
            self.update()

    def undo(self):
        if self.strokes:
            self.redo_stack.append(self.strokes.pop())
            self.update()
            
    def redo(self):
        if self.redo_stack:
            self.strokes.append(self.redo_stack.pop())
            self.update()

class PaintDialog(QDialog):
    def __init__(self, pixmap, existing_strokes=None, color_mode="color", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paint Cut")
        self.resize(800, 600)
        self.layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.color_btn = QPushButton("Brush Color")
        self.color_btn.clicked.connect(self.choose_color)
        toolbar.addWidget(self.color_btn)
        
        self.eraser_btn = QPushButton("Eraser")
        self.eraser_btn.setCheckable(True)
        self.eraser_btn.clicked.connect(self.toggle_eraser)
        toolbar.addWidget(self.eraser_btn)
        
        self.color_mode_combo = QComboBox()
        self.color_mode_combo.addItems(["Original Color", "Grayscale", "Black & White"])
        mode_index = {"color": 0, "grayscale": 1, "bw": 2}.get(color_mode, 0)
        self.color_mode_combo.setCurrentIndex(mode_index)
        self.color_mode_combo.currentIndexChanged.connect(self.color_mode_changed)
        toolbar.addWidget(self.color_mode_combo)
        
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(1, 50)
        self.size_slider.setValue(5)
        self.size_slider.valueChanged.connect(self.size_changed)
        toolbar.addWidget(QLabel("Size:"))
        toolbar.addWidget(self.size_slider)
        
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setShortcut(QKeySequence("Ctrl+Z"))
        self.undo_btn.clicked.connect(self.undo)
        toolbar.addWidget(self.undo_btn)
        
        self.redo_btn = QPushButton("Redo")
        self.redo_btn.setShortcut(QKeySequence("Ctrl+Y"))
        self.redo_btn.clicked.connect(self.redo)
        toolbar.addWidget(self.redo_btn)
        
        toolbar.addStretch()
        self.layout.addLayout(toolbar)
        
        # Canvas
        self.canvas = PaintCanvas(pixmap)
        self.canvas.color_mode = color_mode
        if hasattr(self.parent(), 'last_paint_color'):
            self.canvas.brush_color = QColor(self.parent().last_paint_color)
            self.canvas.brush_size = getattr(self.parent(), 'last_paint_size', 5)
        if existing_strokes:
            self.canvas.load_strokes(existing_strokes)
        self.layout.addWidget(self.canvas)
        self.size_slider.setValue(self.canvas.brush_size)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        self.layout.addLayout(btn_layout)
        self.update_color_btn()

    def choose_color(self):
        color = QColorDialog.getColor(self.canvas.brush_color, self, "Choose Color", QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if color.isValid():
            self.canvas.brush_color = color
            if hasattr(self.parent(), 'last_paint_color'):
                self.parent().last_paint_color = color.name()
            self.update_color_btn()

    def size_changed(self, value):
        self.canvas.brush_size = value
        if hasattr(self.parent(), 'last_paint_size'):
            self.parent().last_paint_size = value

    def update_color_btn(self):
        color = self.canvas.brush_color.name()
        self.color_btn.setStyleSheet(f"background-color: {color}; color: {'white' if self.canvas.brush_color.lightness() < 128 else 'black'};")

    def toggle_eraser(self, checked):
        self.canvas.is_eraser = checked

    def color_mode_changed(self, index):
        modes = ["color", "grayscale", "bw"]
        if 0 <= index < len(modes):
            self.canvas.color_mode = modes[index]
            self.canvas.update()

    def undo(self):
        self.canvas.undo()
        
    def redo(self):
        self.canvas.redo()

    def get_strokes(self):
        return [s[1] for s in self.canvas.strokes]

    def get_color_mode(self):
        return self.canvas.color_mode
