#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скрипт для объединения файлов локализации"""

import json

# Читаем старый файл (валидный JSON)
with open('C:\\NOVA\\old_ru.json', 'r', encoding='utf-8') as f:
    old_data = json.load(f)

# Читаем текущий файл (теперь валидный JSON)
with open('C:\\NOVA\\main_bot\\utils\\lang\\ru.json', 'r', encoding='utf-8') as f:
    current_data = json.load(f)


# Объединяем: сначала старые ключи, потом перезаписываем текущими
merged_data = {**old_data, **current_data}

# Сохраняем объединенный файл
with open('C:\\NOVA\\main_bot\\utils\\lang\\ru.json', 'w', encoding='utf-8') as f:
    json.dump(merged_data, f, ensure_ascii=False, indent=2)

print("OK: File updated successfully!")
print(f"Total keys: {len(merged_data)}")
print(f"From old_ru.json: {len(old_data)}")
print(f"From current ru.json: {len(current_data)}")
