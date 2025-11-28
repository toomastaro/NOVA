---
globs: '["**/keyboards.py", "**/posting*.py", "**/scheduler*.py"]'
description: Apply when working with button parsing in keyboards or message sending
alwaysApply: false
---

При парсинге кнопок всегда проверяй формат " - " (пробел-дефис-пробел) ПЕРВЫМ, так как это основной формат сохранения кнопок в системе. Порядок проверки: 1) " - " 2) "—" (em dash) 3) "-" (обычный дефис). Всегда используй .strip() для очистки текста и URL. Добавляй проверку if buttons: перед kb.row(*buttons) для предотвращения добавления пустых рядов.