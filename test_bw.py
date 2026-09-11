import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QColor, qRgb

app = QApplication(sys.argv)

img = QImage(100, 100, QImage.Format.Format_RGB32)
img.fill(QColor(255, 0, 0)) # Red

# Grayscale first
img_gray = img.convertToFormat(QImage.Format.Format_Grayscale8)

# Now increase contrast
table = []
for i in range(256):
    v = max(0, min(255, (i - 127) * 4 + 127))
    table.append(qRgb(v, v, v))

# Indexed 8
img_indexed = img_gray.convertToFormat(QImage.Format.Format_Indexed8, table)
print("Red pixel after contrast enhancement:", img_indexed.pixelColor(0, 0).name())

# Let's try to simulate red highlight over black text
img2 = QImage(100, 100, QImage.Format.Format_RGB32)
img2.fill(QColor(255, 255, 255))
# draw black
for i in range(50):
    img2.setPixelColor(i, i, QColor(0, 0, 0))
# draw red highlight
for i in range(50):
    img2.setPixelColor(i, i+1, QColor(255, 0, 0))

img2_gray = img2.convertToFormat(QImage.Format.Format_Grayscale8)
img2_indexed = img2_gray.convertToFormat(QImage.Format.Format_Indexed8, table)
print("White pixel after contrast enhancement:", img2_indexed.pixelColor(0, 99).name())
print("Black pixel after contrast enhancement:", img2_indexed.pixelColor(0, 0).name())
print("Red pixel after contrast enhancement:", img2_indexed.pixelColor(0, 1).name())
