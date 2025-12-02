#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка добавленных ключей"""

import json

# Читаем оба файла
with open('C:\\NOVA\\old_ru.json', 'r', encoding='utf-8') as f:
    old_data = json.load(f)

with open('C:\\NOVA\\main_bot\\utils\\lang\\ru.json', 'r', encoding='utf-8') as f:
    merged_data = json.load(f)

# Находим ключи, которые были в old но отсутствовали в merged
old_keys = set(old_data.keys())
merged_keys = set(merged_data.keys())

# Ключи из old_ru.json
keys_from_old = old_keys - (merged_keys - old_keys)

print(f"Keys in old_ru.json: {len(old_keys)}")
print(f"Keys in merged ru.json: {len(merged_keys)}")
print(f"New keys added from old_ru.json: {len(keys_from_old)}")

# Показываем первые 20 добавленных ключей
added = sorted(list(old_keys))[:20]
print("\nFirst 20 keys from old_ru.json:")
for key in added:
    print(f"  - {key}")
