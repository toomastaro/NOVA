import os

PROJECT_ROOT = r"C:\NOVA"
OLD_FILE = os.path.join(PROJECT_ROOT, "main_bot", "database", "types.py")
NEW_FILE = os.path.join(PROJECT_ROOT, "main_bot", "database", "db_types.py")

SEARCH_STR = "from main_bot.database.types import"
REPLACE_STR = "from main_bot.database.db_types import"

def main():
    # 1. Rename file
    if os.path.exists(OLD_FILE):
        try:
            os.rename(OLD_FILE, NEW_FILE)
            print(f"Renamed {OLD_FILE} -> {NEW_FILE}")
        except OSError as e:
            print(f"Error renaming file: {e}")
            return
    elif os.path.exists(NEW_FILE):
        print(f"File already renamed to {NEW_FILE}")
    else:
        print(f"Error: {OLD_FILE} not found!")

    # 2. Update imports
    count = 0
    for root, dirs, files in os.walk(PROJECT_ROOT):
        if "venv" in root or ".git" in root or "__pycache__" in root:
            continue
            
        for file in files:
            if file.endswith(".py") and file != "fix_types_naming.py":
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    if SEARCH_STR in content:
                        new_content = content.replace(SEARCH_STR, REPLACE_STR)
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        print(f"Updated imports in: {filepath}")
                        count += 1
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")

    print(f"Finished. Updated {count} files.")

if __name__ == "__main__":
    main()
