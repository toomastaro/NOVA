import json

with open('hello_bot/utils/lang/ru.json', 'r', encoding='utf-8') as r_f:
    ru_text = json.load(r_f)


languages = {
    'RU': ru_text,
}


def text(key, user_lang='RU') -> str | dict:
    return languages[user_lang][key]
