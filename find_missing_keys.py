#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Поиск всех используемых ключей локализации в коде"""

import json
import re
import os
from pathlib import Path

# Читаем ru.json
with open('C:\\NOVA\\main_bot\\utils\\lang\\ru.json', 'r', encoding='utf-8') as f:
    ru_keys = set(json.load(f).keys())

# Паттерн для поиска text('key') или text("key")
pattern = r"text\(['\"]([^'\"]+)['\"]\)"

# Собираем все используемые ключи
used_keys = set()
files_with_text = []

# Ищем во всех Python файлах
for py_file in Path('C:\\NOVA\\main_bot').rglob('*.py'):
    try:
        content = py_file.read_text(encoding='utf-8')
        matches = re.findall(pattern, content)
        if matches:
            files_with_text.append(str(py_file))
            for match in matches:
                # Пропускаем динамические ключи с {}
                if '{}' not in match and '{' not in match:
                    used_keys.add(match)
    except Exception as e:
        print(f"Error reading {py_file}: {e}")

# Находим недостающие ключи
missing_keys = used_keys - ru_keys

print(f"Total keys in ru.json: {len(ru_keys)}")
print(f"Total unique keys used in code: {len(used_keys)}")
print(f"Missing keys: {len(missing_keys)}")
print()

# Сохраняем в файл
with open('C:\\NOVA\\missing_keys.txt', 'w', encoding='utf-8') as f:
    f.write(f"Missing keys ({len(missing_keys)}):\n")
    for key in sorted(missing_keys):
        f.write(f"{key}\n")

if missing_keys:
    print("Missing keys saved to: C:\\NOVA\\missing_keys.txt")
    for key in sorted(missing_keys)[:10]:  # Показываем только первые 10
        print(f"  {key}")
else:
    print("All keys are present!")

print(f"\nResults saved to: C:\\NOVA\\missing_keys.txt")
