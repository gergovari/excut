
# Modern Color Palette
COLORS = {
    "dark": {
        "bg_primary": "#1e1e1e",
        "bg_secondary": "#252526",
        "bg_tertiary": "#2d2d30",
        "fg_primary": "#d4d4d4",
        "fg_secondary": "#bbbbbb",
        "accent": "#007acc", # VS Code Blue
        "accent_hover": "#0062a3",
        "border": "#454545",
        "selection": "#264f78",
        "text_on_accent": "#ffffff",
        "success": "#28a745",
        "danger": "#e74c3c"
    },
    "light": {
        "bg_primary": "#ffffff",
        "bg_secondary": "#f3f3f3",
        "bg_tertiary": "#e5e5e5",
        "fg_primary": "#333333",
        "fg_secondary": "#555555",
        "accent": "#007acc",
        "accent_hover": "#005a9e",
        "border": "#cccccc",
        "selection": "#a6d6ff",
        "text_on_accent": "#ffffff",
        "success": "#28a745",
        "danger": "#e74c3c"
    }
}

def get_stylesheet(theme="dark"):
    c = COLORS[theme]
    
    return f"""
    /* Global Reset */
    QWidget {{
        color: {c['fg_primary']};
        background-color: {c['bg_primary']};
        font-family: "Segoe UI", "Roboto", "Helvetica Neue", sans-serif;
        font-size: 14px;
        selection-background-color: {c['selection']};
        selection-color: {c['text_on_accent']};
        outline: none;
    }}

    /* Main Window & Containers */
    QMainWindow, QDialog, QFrame {{
        background-color: {c['bg_primary']};
        border: none;
    }}
    
    /* Splitter */
    QSplitter::handle {{
        background-color: {c['bg_tertiary']};
        border: 1px solid {c['bg_primary']};
    }}
    QSplitter::handle:hover {{
        background-color: {c['accent']};
    }}

    /* Tree Widget (Sidebar) */
    QTreeWidget {{
        background-color: {c['bg_secondary']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 5px;
        alternate-background-color: {c['bg_primary']};
    }}
    QTreeWidget::item {{
        padding: 6px;
        margin: 2px;
        border-radius: 4px;
    }}
    QTreeWidget::item:selected {{
        background-color: {c['selection']};
        color: {c['text_on_accent']};
    }}
    QTreeWidget::item:hover:!selected {{
        background-color: {c['bg_tertiary']};
        border: 1px solid {c['border']};
    }}

    /* Buttons */
    QPushButton {{
        background-color: {c['bg_tertiary']};
        color: {c['fg_primary']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 6px 12px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {c['accent']};
        color: {c['text_on_accent']};
        border: 1px solid {c['accent']};
    }}
    QPushButton:pressed {{
        background-color: {c['accent_hover']};
    }}
    
    /* Special Classes */
    QPushButton.success-btn {{
        background-color: {c['success']};
        color: white;
        border: none;
    }}
    QPushButton.success-btn:hover {{
        background-color: #218838;
    }}
    
    QPushButton.danger-btn {{
        background-color: transparent;
        color: {c['danger']};
        border: 1px solid {c['danger']};
    }}
    QPushButton.danger-btn:hover {{
        background-color: {c['danger']};
        color: white;
    }}

    /* Inputs */
    QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox {{
        background-color: {c['bg_tertiary']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 4px;
        color: {c['fg_primary']};
    }}
    QLineEdit:focus, QAbstractSpinBox:focus {{
        border: 1px solid {c['accent']};
    }}

    /* Scrollbars (Modern Thin) */
    QScrollBar:vertical {{
        border: none;
        background: {c['bg_primary']};
        width: 10px;
        margin: 0px 0px 0px 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {c['border']};
        min-height: 20px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c['accent']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        border: none;
        background: {c['bg_primary']};
        height: 10px;
    }}
    QScrollBar::handle:horizontal {{
        background: {c['border']};
        min-width: 20px;
        border-radius: 5px;
    }}
    """
