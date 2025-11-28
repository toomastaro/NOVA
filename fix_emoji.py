import json
import re

# Читаем файл локализации
with open('c:/NOVA/NOVA/main_bot/utils/lang/ru.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Функция для замены тегов tg-emoji на обычные эмодзи
def replace_tg_emoji(text):
    # Паттерн для поиска <tg-emoji emoji-id="...">эмодзи</tg-emoji>
    pattern = r'<tg-emoji emoji-id="[^"]*">([^<]+)</tg-emoji>'
    # Заменяем на просто эмодзи
    return re.sub(pattern, r'\1', text)

# Обрабатываем все значения в словаре
def process_dict(d):
    for key, value in d.items():
        if isinstance(value, str):
            d[key] = replace_tg_emoji(value)
        elif isinstance(value, dict):
            process_dict(value)
    return d

# Применяем замену
data = process_dict(data)

# Сохраняем обратно
with open('c:/NOVA/NOVA/main_bot/utils/lang/ru.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print("Done! All <tg-emoji> tags replaced with Unicode emoji")
