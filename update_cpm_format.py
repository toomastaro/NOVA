import re

# Read the file
with open(r'c:\NOVA\main_bot\utils\schedulers.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to find text("cpm:report").format( with 7 parameters
pattern = r'(text\("cpm:report"\)\.format\(\s+post_id,\s+channels_text,\s+cpm_price,\s+total_views,\s+rub_price,\s+round\(rub_price / usd_rate, 2\),\s+round\(usd_rate, 2\),\s+\))'

# Replacement with 8 parameters (adding timestamp)
replacement = r'text("cpm:report").format(\n                    post_id,\n                    channels_text,\n                    cpm_price,\n                    total_views,\n                    rub_price,\n                    round(rub_price / usd_rate, 2),\n                    round(usd_rate, 2),\n                    exchange_rate_update_time.strftime("%H:%M %d.%m.%Y") if exchange_rate_update_time else "N/A"\n                )'

# Replace all occurrences
new_content = re.sub(pattern, replacement, content)

# Write back
with open(r'c:\NOVA\main_bot\utils\schedulers.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Updated CPM report format calls")
