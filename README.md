<p align="center">
  <img src="packaging/icon.png" alt="ExCut Logo" width="200"/>
</p>

# ExCut

<p align="center">
  <b>Exercise Cutter Tool</b><br>
  Cut, Organize, and Export Exercises from Images and PDFs.<br>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python Version">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/status-active-success" alt="Status">
</p>

---

## 📖 Overview

**ExCut** is a powerful Python GUI application designed for students and educators to streamline the process of digitizing exercises. Whether you have photos of textbook pages or PDF documents, ExCut allows you to easily select specific questions ("cuts"), organize them into groups, and export a clean, professional PDF ready for printing or sharing.

## ✨ Features

### 🎯 Precision Cutting
- **Rectangular Selection**: Easily drag-and-drop to select exercises.
- **Smart Recrop**: Edit existing cuts to adjust boundaries or add/remove parts.
- **Append Mode**: Combine multiple disjoint areas into a single exercise using `Shift+Enter`.

### 📂 File Support
- **Multi-Format**: Load PDFs (`.pdf`) and Images (`.png`, `.jpg`, `.jpeg`, `.bmp`).
- **Batch Loading**: Import multiple files at once.
- **Page Navigation**: Seamlessly browse through multi-page documents.

### 🛠️ Organization & Workflow
- **Sidebar Management**: Reorder items via drag-and-drop.
- **Grouping**: Organize exercises into logic groups or chapters.
- **Sticky Mode**: Keep specific selections active for repeated actions.
- **Undo/Redo System**: Full history support for both Canvas edits and Sidebar organization.
- **Project Persistence**: Save your work as `.excu` files and resume anytime.

### 🎨 Customization & Export
- **Themes**: Toggle between **Light** and **Dark** modes for comfortable usage.
- **PDF Export**: Generate high-quality PDFs.
- **Custom Settings**: Configure Page Size (A4, A3, etc.), Background Patterns (Squared, Blank), and Background Images.

## 🚀 Installation

Ensure you have Python 3.10+ installed.

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/excut.git
    cd excut
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## 💻 Usage

### Launching the App
You can start the application using the command line:

```bash
# Basic launch
python3 main.py

# Launch with input files
python3 main.py data/math_exam.pdf data/photo.jpg
```

### Keyboard Shortcuts

Efficiency is key. Master these shortcuts to speed up your workflow:

| Context        | Shortcut                        | Action                               |
| :------------- | :------------------------------ | :----------------------------------- |
| **Project**    | `Ctrl + O`                      | Open Project                         |
|                | `Ctrl + S`                      | Save Project                         |
|                | `Ctrl + I`                      | Add Input Files                      |
|                | `Ctrl + P`                      | Preview PDF                          |
| **Editing**    | `Ctrl + Z`                      | Undo                                 |
|                | `Ctrl + Shift + Z` / `Ctrl + Y` | Redo                                 |
| **Navigation** | `Right Arrow` / `L`             | Next Page                            |
|                | `Left Arrow` / `H`              | Previous Page                        |
|                | `J` / `K`                       | Select Next/Previous Item in Sidebar |
| **Action**     | `Enter`                         | **Cut Selection** (Create Exercise)  |
|                | `Shift + Enter`                 | **Append Selection** (Combine parts) |
|                | `F2`                            | Rename Sidebar Item                  |
|                | `Del`                           | Delete Sidebar Item                  |
