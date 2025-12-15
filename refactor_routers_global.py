import os

# Target the main project directory
TARGET_DIR = r"C:\NOVA\main_bot"

def refactor_files():
    print(f"Starting refactoring in {TARGET_DIR}...")
    count = 0
    for root, dirs, files in os.walk(TARGET_DIR):
        # Scan all directories
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    if "hand_add" in content:
                        new_content = content.replace("hand_add", "get_router")
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        print(f"Updated: {file_path}")
                        count += 1
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
    
    print(f"Refactoring complete. {count} files updated.")

if __name__ == "__main__":
    refactor_files()
