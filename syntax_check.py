import py_compile
import sys
import os

files = [
    "C:/NOVA/main_bot/database/user/crud.py",
    "C:/NOVA/main_bot/utils/schedulers/cleanup.py",
]

print("Running syntax check...")
has_errors = False

for file_path in files:
    try:
        py_compile.compile(file_path, doraise=True)
        print(f"OK: {os.path.basename(file_path)}")
    except py_compile.PyCompileError as e:
        print(f"ERROR: {os.path.basename(file_path)}")
        print(e)
        has_errors = True
    except Exception as e:
        print(f"ERROR: {os.path.basename(file_path)}: {e}")
        has_errors = True

if has_errors:
    sys.exit(1)
print("All files verified successfully.")
