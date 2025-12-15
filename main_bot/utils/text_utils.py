import re

# Pre-compile regex patterns for performance
# Pattern to remove <tg-emoji> tags but keep the content if needed? 
# The original code was: .replace('tg-emoji emoji-id', '').replace('</tg-emoji>', '')
# This hints it wanted to remove the tag attributes but maybe keep the tag structure broken?
# Actually, the original code used replace on the string literal 'tg-emoji emoji-id' which looks like a class or attribute part 
# but likely it was intended to strip the custom emoji tags.
# Let's reproduce the exact behavior but optimized:
# Original: message_text.replace('tg-emoji emoji-id', '').replace('</tg-emoji>', '')
# Then: re.sub(r'<[^>]+>', '', message_text)
# The second step strips ALL HTML tags. So the first step is redundant if the second step is comprehensive.
# However, maybe there was a specific reason. 
# Optimized approach: Just strip all HTML tags using a single pre-compiled regex.

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
    
    # Also remove artifacts if they were raw strings in the message (legacy compatibility)
    # The original code did strict string replacements for 'tg-emoji emoji-id'.
    # If the regex above catches <tg-emoji ...>, then we are good.
    # The original code re.sub(r'<[^>]+>', '', message_text) is aggressive enough.
    
    return clean_text.strip() or "Медиа"
