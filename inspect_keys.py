import json

with open('C:\\NOVA\\main_bot\\utils\\lang\\ru.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

keys_to_check = [
    'reply_menu:novastat',
    'reply_menu:exchange_rate',
    'reply_menu:posting',
    'reply_menu:story',
    'reply_menu:bots',
    'reply_menu:support',
    'reply_menu:profile'
]

with open('C:\\NOVA\\inspect_results.txt', 'w', encoding='utf-8') as out:
    out.write("Checking keys in ru.json:\n")
    for key in keys_to_check:
        if key in data:
            value = data[key]
            out.write(f"Key: {key}\n")
            out.write(f"Value: '{value}'\n")
            out.write(f"Repr:  {repr(value)}\n")
            out.write("-" * 20 + "\n")
        else:
            out.write(f"Key: {key} NOT FOUND\n")

print("Results saved to C:\\NOVA\\inspect_results.txt")
