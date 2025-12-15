import re
from typing import Any

# Pre-compile regex patterns for performance
_HTML_TAGS_PATTERN = re.compile(r'<[^>]+>')

def clean_html_text(text: str | None) -> str:
    """
    Cleans HTML tags from the text efficiently.
    Returns 'Медиа' if text is None or empty after cleaning.
    """
    if not text:
        return "Медиа"
    
    # Remove HTML tags
    clean_text = _HTML_TAGS_PATTERN.sub('', text)
    
    return clean_text.strip() or "Медиа"

def get_protect_tag(protect: Any) -> str:
    """
    Returns the protection tag based on the protect object settings.
    Ported from hello_bot/utils/functions.py
    """
    if protect.arab and protect.china:
        protect_tag = "all"
    elif protect.arab:
        protect_tag = "arab"
    elif protect.china:
        protect_tag = "china"
    else:
        protect_tag = ""

    return protect_tag
