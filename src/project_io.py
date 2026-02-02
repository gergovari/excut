"""
Handles saving and loading of ExCut projects (.excu).
"""
import os
import json
import shutil
import tempfile
import zipfile
import re
from PyQt6.QtCore import QRect

def save_project(output_path, input_paths, sidebar_items, metadata=None):
    """
    Saves the current state to a .excu file (zip).
    
    Args:
        output_path (str): Destination .excu file path.
        input_paths (list): List of absolute paths to input files (images/pdfs).
        sidebar_items (list): List of dicts representing sidebar items.
                              Each dict should have: 'type', 'title', 'content' (if image, handled separately), 'parts' (if existing)
                              Note: 'content' (QPixmap) is not serialized directly. We rely on 'parts' metadata or re-generating from source.
        metadata (dict): Global project metadata (e.g. current settings).
    """
    
    # Create temp directory
    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = os.path.join(temp_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)
        
        # 1. Copy Input Files
        # We need to map original paths to relative paths in the zip
        # and store this mapping so we can resolve them on load.
        # But wait, if we load, we extract them to a temp dir.
        # So the manifest should rely on filenames or a mapping.
        
        input_map = {} # original_path -> asset_filename
        serialized_inputs = []
        
        for idx, path in enumerate(input_paths):
             if not os.path.exists(path):
                 continue
             
             # Create unique filename to avoid collisions
             ext = os.path.splitext(path)[1]
             # safe name
             base = os.path.basename(path)
             # just use index prefix to be sure
             asset_name = f"{idx}_{base}"
             
             dest = os.path.join(assets_dir, asset_name)
             shutil.copy2(path, dest)
             
             input_map[path] = asset_name
             serialized_inputs.append(asset_name)

        # 2. Serialize Sidebar Items
        # We need to ensure QRects are serialized to simple lists/dicts
        serialized_items = []
        
        for item in sidebar_items:
            s_item = item.copy()
            # Remove objects that can't be JSON serialized
            if "content" in s_item:
                del s_item["content"]
            
            # Serialize 'parts' logic
            if "parts" in s_item:
                new_parts = []
                for p in s_item["parts"]:
                    # p has 'page_idx', 'rect'
                    np = p.copy()
                    if "rect" in np:
                        r = np["rect"]
                        if isinstance(r, QRect):
                            np["rect"] = [r.x(), r.y(), r.width(), r.height()]
                    new_parts.append(np)
                s_item["parts"] = new_parts
            
            serialized_items.append(s_item)

        # 3. Create Manifest
        manifest = {
            "version": 1,
            "inputs": serialized_inputs,
            "items": serialized_items,
            "metadata": metadata or {}
        }
        
        with open(os.path.join(temp_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
            
        # 4. Zip it up
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, temp_dir)
                    zf.write(abs_path, rel_path)

def load_project(project_path, extract_root):
    """
    Loads a .excu file.
    
    Args:
        project_path (str): Path to .excu file.
        extract_root (str): Directory to extract assets to (controlled by caller, e.g. a temp dir).
        
    Returns:
        tuple: (input_paths, sidebar_items, metadata)
    """
    if not os.path.exists(project_path):
        raise FileNotFoundError(f"Project file not found: {project_path}")
        
    # Unzip
    with zipfile.ZipFile(project_path, 'r') as zf:
        zf.extractall(extract_root)
        
    manifest_path = os.path.join(extract_root, "manifest.json")
    if not os.path.exists(manifest_path):
        raise ValueError("Invalid project file: manifest.json missing")
        
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
        
    # Reconstruct inputs
    assets_dir = os.path.join(extract_root, "assets")
    input_paths = []
    
    # Check if 'inputs' is list of strings (filenames)
    # The manifest stores filenames relative to assets/
    for fname in manifest.get("inputs", []):
         full_path = os.path.join(assets_dir, fname)
         if os.path.exists(full_path):
             input_paths.append(full_path)
             
    # Reconstruct sidebar items
    items = []
    for s_item in manifest.get("items", []):
        # Deserialize Rects
        if "parts" in s_item:
            for p in s_item["parts"]:
                if "rect" in p and isinstance(p["rect"], list):
                    x, y, w, h = p["rect"]
                    p["rect"] = QRect(x, y, w, h)
        
        # Note: We do NOT reconstruct 'content' (pixmaps) here.
        # The main application must regenerate them from inputs + parts data.
        items.append(s_item)
        
    return input_paths, items, manifest.get("metadata", {})
