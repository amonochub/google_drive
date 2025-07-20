def escape_markdown(text: str) -> str:
    """Экранирование спецсимволов для Telegram MarkdownV2."""
    escape_chars = r'_[]()~`>#+-=|{}.!'
    for ch in escape_chars:
        text = text.replace(ch, f'\\{ch}')
    return text 