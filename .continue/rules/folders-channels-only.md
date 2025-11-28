---
globs: '["main_bot/handlers/**/*folder*", "main_bot/database/user_folder/**/*",
  "main_bot/keyboards/keyboards.py"]'
alwaysApply: true
---

Папки используются ТОЛЬКО для каналов. Убрать все упоминания FolderType.BOT и логику для ботов в папках. Всегда использовать FolderType.CHANNEL. Добавлять русские комментарии для новых функций папок.