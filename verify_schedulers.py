import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from main_bot.utils import schedulers
    print("Successfully imported schedulers")
except ImportError as e:
    print(f"ImportError: {e}")
except SyntaxError as e:
    print(f"SyntaxError: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
