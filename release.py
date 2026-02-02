#!/usr/bin/env python3
import os
import re
import subprocess
import sys

APPIMAGE_SCRIPT = "packaging/build/appimage.sh"
WINDOWS_SCRIPT = "packaging/build/windows.sh"

def get_current_version(file_path):
    with open(file_path, "r") as f:
        content = f.read()
    match = re.search(r'VERSION="v(\d+)\.(\d+)"', content)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None

def update_version_in_file(file_path, major, minor):
    new_version = f"v{major}.{minor}"
    with open(file_path, "r") as f:
        content = f.read()
    
    new_content = re.sub(r'VERSION="v\d+\.\d+"', f'VERSION="{new_version}"', content)
    
    with open(file_path, "w") as f:
        f.write(new_content)
    return new_version

def run_command(cmd, shell=False, env=None):
    print(f"🚀 Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        if env is None:
            env = os.environ.copy()
        subprocess.run(cmd, check=True, shell=shell, env=env)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running command: {e}")
        sys.exit(1)

def main():
    # 1. Determine current version and increment
    current = get_current_version(APPIMAGE_SCRIPT)
    if not current:
        print("❌ Could not find version in scripts.")
        sys.exit(1)
    
    major, minor = current
    new_minor = minor + 1
    new_version_str = f"v{major}.{new_minor}"
    
    print(f"ℹ️  Current Version: v{major}.{minor}")
    print(f"ℹ️  New Version:     {new_version_str}")
    
    # 2. Update files
    print("📝 Updating version in build scripts...")
    update_version_in_file(APPIMAGE_SCRIPT, major, new_minor)
    # update_version_in_file(WINDOWS_SCRIPT, major, new_minor)
    
    # 3. Git commit and tag (Optional but recommended for releases)
    # Checking if we are in a git repo
    if os.path.isdir(".git"):
        print("commit changes...")
        run_command(["git", "add", APPIMAGE_SCRIPT])
        run_command(["git", "commit", "-m", f"Bump version to {new_version_str}"])
    
    # Setup Environment with VENV
    env = os.environ.copy()
    venv_bin = os.path.abspath("venv/bin")
    env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"

    # 4. Run Build Scripts
    print("🔨 Running AppImage Build...")
    run_command(["./packaging/build/appimage.sh"], env=env)
    
    # print("🔨 Running Windows Build...")
    # run_command(["./packaging/build/windows.sh"], env=env)
    
    # 5. Create GitHub Release
    print(f"📦 Creating GitHub Release {new_version_str}...")
    
    dist_files = [
        f"dist/ExCut-x86_64-{new_version_str}.AppImage",
        # f"dist/ExCut-x86_64-{new_version_str}.exe"
    ]
    
    # Verify files exist
    for f in dist_files:
        if not os.path.exists(f):
            print(f"❌ Error: Expected build artifact not found: {f}")
            # Identify what IS there if expected name is wrong
            print("Contents of dist/:")
            run_command(["ls", "-l", "dist"])
            sys.exit(1)

    cmd = [
        "gh", "release", "create", new_version_str,
        "--title", f"Release {new_version_str}",
        "--notes", f"Automated release of version {new_version_str}.",
    ] + dist_files
    
    run_command(cmd)
    
    print("✅ Release automation execution complete!")

if __name__ == "__main__":
    main()
