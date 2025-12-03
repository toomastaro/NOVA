#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для удаления channel_username из schedulers.py
"""

file_path = "main_bot/utils/schedulers.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Заменяем строку с channel_username
old_line = '                    channel_username=channel.username if channel else None,\r\n'
content = content.replace(old_line, '')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("File fixed!")
