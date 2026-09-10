from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QColorDialog, QSlider, QWidget
)
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QPainterPath

class PaintCanvas(QWidget):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.base_pixmap = pixmap
        self.setFixedSize(pixmap.size())
        
        self.strokes = [] # List of (QPainterPath, QColor, size)
        self.current_path = None
        
        self.brush_color = QColor(255, 0, 0)
        self.brush_size = 5

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.base_pixmap)
        
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        for path, color, size in self.strokes:
            pen = QPen(color, size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)
            
        if self.current_path:
            pen = QPen(self.brush_color, self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(self.current_path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.current_path = QPainterPath()
            self.current_path.moveTo(event.pos())
            self.update()

    def mouseMoveEvent(self, event):
        if self.current_path:
            self.current_path.lineTo(event.pos())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.current_path:
            self.current_path.lineTo(event.pos())
            self.strokes.append((self.current_path, self.brush_color, self.brush_size))
            self.current_path = None
            self.update()

    def undo(self):
        if self.strokes:
            self.strokes.pop()
            self.update()

class PaintDialog(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paint Cut")
        self.layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.color_btn = QPushButton("Color")
        self.color_btn.clicked.connect(self.choose_color)
        toolbar.addWidget(self.color_btn)
        
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(1, 50)
        self.size_slider.setValue(5)
        self.size_slider.valueChanged.connect(self.size_changed)
        toolbar.addWidget(QLabel("Size:"))
        toolbar.addWidget(self.size_slider)
        
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.clicked.connect(self.undo)
        toolbar.addWidget(self.undo_btn)
        
        toolbar.addStretch()
        self.layout.addLayout(toolbar)
        
        # Canvas
        self.canvas = PaintCanvas(pixmap)
        self.layout.addWidget(self.canvas)
        
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
        color = QColorDialog.getColor(self.canvas.brush_color, self)
        if color.isValid():
            self.canvas.brush_color = color
            self.update_color_btn()

    def size_changed(self, value):
        self.canvas.brush_size = value

    def update_color_btn(self):
        color = self.canvas.brush_color.name()
        self.color_btn.setStyleSheet(f"background-color: {color}; color: {'white' if self.canvas.brush_color.lightness() < 128 else 'black'};")

    def undo(self):
        self.canvas.undo()

    def get_strokes(self):
        return self.canvas.strokes
