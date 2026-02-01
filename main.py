import sys
import argparse
from PyQt6.QtWidgets import QApplication
from src.gui import MainWindow

def main():
    parser = argparse.ArgumentParser(description="ExCut - Exercise Cutter Tool")
    parser.add_argument("input_files", nargs='+', help="Input PDF or Image files")
    parser.add_argument("--output", default="output.pdf", help="Output PDF filename (default: output.pdf)")
    parser.add_argument("--bg-image", help="Path to background image for output PDF pages (takes precedence over pattern)", default=None)
    parser.add_argument("--bg-pattern", help="Background pattern name (available: 'squared')", default=None)
    parser.add_argument("--page-size", default="A4", help="Page size (default: A4)")
    parser.add_argument("--theme", choices=["light", "dark"], default="dark", help="UI Theme (default: dark)")
    
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    
    window = MainWindow(args.input_files, args.output, args.bg_image, args.bg_pattern, args.theme)
    window.showMaximized()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
