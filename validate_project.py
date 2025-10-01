import os
import py_compile
from pathlib import Path

def check_syntax(file_path):
    try:
        py_compile.compile(file_path, doraise=True)
        return True, ""
    except py_compile.PyCompileError as e:
        return False, str(e)

def scan_directory(path):
    print(f"🔍 Scanning Python files under: {path}")
    error_found = False
    for root, dirs, files in os.walk(path):
        for f in files:
            if f.endswith(".py"):
                full_path = os.path.join(root, f)
                ok, err = check_syntax(full_path)
                if ok:
                    print(f"✅ {full_path}")
                else:
                    error_found = True
                    print(f"❌ {full_path}")
                    print(err)
    if not error_found:
        print("\n🎉 All Python files passed syntax check!")

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent
    scan_directory(project_root)
