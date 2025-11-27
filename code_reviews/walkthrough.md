# NOVAstat Feature Walkthrough

I have implemented the **NOVAstat** feature, a comprehensive analytics module for Telegram channels within the Nova Bot.

## 1. Database Changes
New tables were added to store user settings and channel collections.

### Models (`main_bot/database/novastat/model.py`)
- **`NovaStatSettings`**: Stores the analysis depth (default 7 days) for each user.
- **`Collection`**: Represents a folder of channels.
- **`CollectionChannel`**: Stores individual channels within a collection.

### CRUD (`main_bot/database/novastat/crud.py`)
- Implemented `NovaStatCrud` mixin with methods to manage settings, collections, and channels.
- Integrated into the main `Database` class in `main_bot/database/db.py`.

## 2. Service Logic (`main_bot/utils/novastat.py`)
The core logic is encapsulated in `NovaStatService`.
- **Telethon Integration**: Uses a session file to connect to Telegram via MTProto.
- **Stats Collection**: Fetches post views for the last N days.
- **Interpolation**: Calculates estimated views for 24, 48, and 72 hours using linear interpolation.
- **Anomaly Detection**: Filters out view count outliers based on median values.

## 3. User Interface
### Main Menu
- Added a **"NOVAстат"** button to the main reply keyboard.

### Keyboards (`main_bot/keyboards/keyboards.py`)
- **`InlineNovaStat`**: New builder class for all NOVAstat inline menus.
    - Main Menu: Settings, Collections.
    - Settings: Depth selection (3-7 days).
    - Collections: List, Create, Manage (Add/Remove channels).
    - Analysis Results: "Calculate CPM" button.
    - CPM: Quick selection buttons (100-2000).

## 4. Handlers (`main_bot/handlers/novastat.py`)
A new router handles the entire flow:
- **Entry**: `/start` -> "NOVAстат" button.
- **Analysis**: Accepts text messages with channel links/usernames.
- **Collections**: Full CRUD flow for managing collections using FSM.
- **CPM**: Calculates advertising cost based on analysis results.

## 5. Setup & Usage
1.  **Session File**: The bot is configured to use the session file at `main_bot/utils/sessions/+37253850093.session`. Ensure this file exists.
2.  **Dependencies**: Ensure `telethon` is installed (it is in requirements).
3.  **Restart**: Restart the bot to load the new router and database tables.

## Verification
- Verified file structure and imports.
- Checked integration points in `db.py` and `handlers/__init__.py`.
- Code follows the existing project patterns (Aiogram 3.x, SQLAlchemy).
