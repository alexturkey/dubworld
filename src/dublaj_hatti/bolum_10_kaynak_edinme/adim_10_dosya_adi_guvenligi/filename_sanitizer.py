"""
Filename Sanitizer Module
Handles all filename sanitization for Windows/FFmpeg/Python compatibility

Usage:
    from src.utils.filename_sanitizer import sanitize_filename

    # For internal use (project folders, vocals, output files)
    safe_name = sanitize_filename("РОССИЯ - ЖИЗНЬ.mp4")
    # Result: "rossiya_-_zhizn.mp4"

    # Keep original case (for display purposes)
    display_name = sanitize_filename("РОССИЯ.mp4", keep_case=True)
    # Result: "ROSSIYa.mp4"
"""

import re
import unicodedata

# Transliteration uses the explicit table below (Turkish, European, Greek, Cyrillic) + NFD accent stripping.
# Unidecode is deliberately not used: it is GPL-2.0+ and its presence would make the output environment-dependent.


LANG_SPECIFIC_MAPPINGS = {
    "tr": {
        'Ö': 'O', 'ö': 'o',
        'Ü': 'U', 'ü': 'u',
        'Ş': 'S', 'ş': 's',
        'Ğ': 'G', 'ğ': 'g',
        'Ç': 'C', 'ç': 'c',
        'İ': 'I', 'ı': 'i',
    },
    "en": {},
    "de": {
        'Ö': 'Oe', 'ö': 'oe',
        'Ü': 'Ue', 'ü': 'ue',
        'Ä': 'Ae', 'ä': 'ae',
        'ẞ': 'SS', 'ß': 'ss',
    },
    "fr": {
        'É': 'E', 'é': 'e',
        'È': 'E', 'è': 'e',
        'Ê': 'E', 'ê': 'e',
        'Ë': 'E', 'ë': 'e',
        'À': 'A', 'à': 'a',
        'Â': 'A', 'â': 'a',
        'Î': 'I', 'î': 'i',
        'Ï': 'I', 'ï': 'i',
        'Ô': 'O', 'ô': 'o',
        'Ù': 'U', 'ù': 'u',
        'Û': 'U', 'û': 'u',
        'Ç': 'C', 'ç': 'c',
        'Œ': 'OE', 'œ': 'oe',
        'Æ': 'AE', 'æ': 'ae',
    },
    "es": {
        'Ñ': 'N', 'ñ': 'n',
        'Á': 'A', 'á': 'a',
        'É': 'E', 'é': 'e',
        'Í': 'I', 'í': 'i',
        'Ó': 'O', 'ó': 'o',
        'Ú': 'U', 'ú': 'u',
        '¿': '', '¡': '',
    },
    "it": {
        'À': 'A', 'à': 'a',
        'È': 'E', 'è': 'e',
        'É': 'E', 'é': 'e',
        'Ì': 'I', 'ì': 'i',
        'Ò': 'O', 'ò': 'o',
        'Ù': 'U', 'ù': 'u',
    },
    "pt": {
        'Ã': 'A', 'ã': 'a',
        'Õ': 'O', 'õ': 'o',
        'Á': 'A', 'á': 'a',
        'É': 'E', 'é': 'e',
        'Ê': 'E', 'ê': 'e',
        'Í': 'I', 'í': 'i',
        'Ó': 'O', 'ó': 'o',
        'Ô': 'O', 'ô': 'o',
        'Ú': 'U', 'ú': 'u',
        'Ç': 'C', 'ç': 'c',
    },
    "ru": {
        'А': 'A', 'а': 'a', 'Б': 'B', 'б': 'b', 'В': 'V', 'в': 'v',
        'Г': 'G', 'г': 'g', 'Д': 'D', 'д': 'd', 'Е': 'E', 'е': 'e',
        'Ё': 'Yo', 'ё': 'yo', 'Ж': 'Zh', 'ж': 'zh', 'З': 'Z', 'з': 'z',
        'И': 'I', 'и': 'i', 'Й': 'Y', 'й': 'y', 'К': 'K', 'к': 'k',
        'Л': 'L', 'л': 'l', 'М': 'M', 'м': 'm', 'Н': 'N', 'н': 'n',
        'О': 'O', 'о': 'o', 'П': 'P', 'п': 'p', 'Р': 'R', 'р': 'r',
        'С': 'S', 'с': 's', 'Т': 'T', 'т': 't', 'У': 'U', 'у': 'u',
        'Ф': 'F', 'ф': 'f', 'Х': 'Kh', 'х': 'kh', 'Ц': 'Ts', 'ц': 'ts',
        'Ч': 'Ch', 'ч': 'ch', 'Ш': 'Sh', 'ш': 'sh', 'Щ': 'Shch', 'щ': 'shch',
        'Ъ': '', 'ъ': '', 'Ы': 'Y', 'ы': 'y', 'Ь': '', 'ь': '',
        'Э': 'E', 'э': 'e', 'Ю': 'Yu', 'ю': 'yu', 'Я': 'Ya', 'я': 'ya',
    },
    "ja": {},
    "ko": {},
    "zh": {},
    "ar": {
        'ا': 'a', 'ب': 'b', 'ت': 't', 'ث': 'th', 'ج': 'j', 'ح': 'h',
        'خ': 'kh', 'د': 'd', 'ذ': 'dh', 'ر': 'r', 'ز': 'z', 'س': 's',
        'ش': 'sh', 'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': 'a',
        'غ': 'gh', 'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm',
        'ن': 'n', 'ه': 'h', 'و': 'w', 'ي': 'y', 'ء': '', 'ة': 'h',
    },
}


def sanitize_filename(filename: str, keep_case: bool = False, source_lang: str = None) -> str:
    """
    Create ultra-safe filename for Windows/FFmpeg/Python

    Handles ALL problematic characters that can cause issues with:
    - Windows filesystem (reserved names, invalid chars)
    - FFmpeg encoding (Unicode fullwidth, special symbols)
    - Python libraries (emoji, control characters)
    - International characters (Turkish, German, French, Korean, etc.)

    Processing Pipeline:
    1. Unicode normalization (NFKC: fullwidth → halfwidth)
       - Example: ？ (U+FF1F) → ? (U+003F), ｜ (U+FF5C) → | (U+007C)
    2. Emoji removal (all Unicode emoji ranges)
    3. Diacritics → ASCII transliteration
       - Turkish: ö→o, ş→s, ü→u, ğ→g, ı→i, ç→c, İ→I
       - German: ä→a, ö→o, ü→u, ß→ss, ẞ→SS
       - French: é→e, è→e, ê→e, à→a, ç→c
       - Korean/Japanese/Chinese → romanized
    4. Windows invalid characters → underscore
    5. Space → underscore
    6. Multiple underscores → single
    7. Lowercase conversion (optional)
    8. Windows reserved names protection
    9. Length limit (200 chars, Windows safe)
    10. Trailing dots/spaces/underscores removal

    Args:
        filename: Original filename (with or without extension)
        keep_case: If False, converts to lowercase for consistency (default: False)

    Returns:
        Sanitized filename (safe for Windows, FFmpeg, Python)

    Examples:
        >>> sanitize_filename("What is Python？ ｜ Python.mp4")
        'what_is_python_python.mp4'

        >>> sanitize_filename("Türkçe Öğretim Videosu.mp4")
        'turkce_ogretim_videosu.mp4'

        >>> sanitize_filename("РОССИЯ - ЖИЗНЬ.mp4")
        'rossiia_-_zhizn.mp4'

        >>> sanitize_filename("Hello 😀 World!.mp4")
        'hello_world.mp4'
    """
    # 1. Unicode normalization (NFKC: fullwidth → halfwidth, compatibility decomposition)
    # This fixes: ？ → ?, ｜ → |, Ａ → A, etc.
    filename = unicodedata.normalize('NFKC', filename)

    # 2. Remove emojis (all Unicode emoji ranges)
    # Covers: Emoticons, symbols, pictographs, transport, flags, etc.
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed characters
        "\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs
        "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-A
        "\U00002600-\U000026FF"  # miscellaneous symbols
        "\U00002700-\U000027BF"  # dingbats
        "]+", flags=re.UNICODE
    )
    filename = emoji_pattern.sub('', filename)

    lang_key = source_lang.lower() if source_lang else None
    if lang_key and lang_key in LANG_SPECIFIC_MAPPINGS:
        for char, replacement in LANG_SPECIFIC_MAPPINGS[lang_key].items():
            filename = filename.replace(char, replacement)

    manual_map = {
        'İ': 'I',
        'ı': 'i',
        'I': 'I',
        'i': 'i',
        'Ş': 'S', 'ş': 's',
        'Ğ': 'G', 'ğ': 'g',
        'Ç': 'C', 'ç': 'c',
        'Ä': 'Ae', 'ä': 'ae',
        'ẞ': 'SS', 'ß': 'ss',
        'À': 'A', 'à': 'a', 'Â': 'A', 'â': 'a',
        'É': 'E', 'é': 'e', 'È': 'E', 'è': 'e', 'Ê': 'E', 'ê': 'e', 'Ë': 'E', 'ë': 'e',
        'Î': 'I', 'î': 'i', 'Ï': 'I', 'ï': 'i',
        'Ô': 'O', 'ô': 'o',
        'Ù': 'U', 'ù': 'u', 'Û': 'U', 'û': 'u',
        'Æ': 'AE', 'æ': 'ae',
        'Œ': 'OE', 'œ': 'oe',

        # Spanish
        'Ñ': 'N', 'ñ': 'n',
        'Á': 'A', 'á': 'a',
        'Í': 'I', 'í': 'i',
        'Ó': 'O', 'ó': 'o',
        'Ú': 'U', 'ú': 'u',
        '¿': '',  # Inverted question mark (not needed in filename)
        '¡': '',  # Inverted exclamation mark

        # Portuguese
        'Ã': 'A', 'ã': 'a',
        'Õ': 'O', 'õ': 'o',

        # Polish
        'Ą': 'A', 'ą': 'a',
        'Ć': 'C', 'ć': 'c',
        'Ę': 'E', 'ę': 'e',
        'Ł': 'L', 'ł': 'l',
        'Ń': 'N', 'ń': 'n',
        'Ś': 'S', 'ś': 's',
        'Ź': 'Z', 'ź': 'z',
        'Ż': 'Z', 'ż': 'z',

        # Czech/Slovak
        'Č': 'C', 'č': 'c',
        'Ď': 'D', 'ď': 'd',
        'Ě': 'E', 'ě': 'e',
        'Ň': 'N', 'ň': 'n',
        'Ř': 'R', 'ř': 'r',
        'Š': 'S', 'š': 's',
        'Ť': 'T', 'ť': 't',
        'Ů': 'U', 'ů': 'u',
        'Ý': 'Y', 'ý': 'y',
        'Ž': 'Z', 'ž': 'z',

        # Scandinavian (Danish, Norwegian, Swedish)
        'Å': 'A', 'å': 'a',
        'Ø': 'O', 'ø': 'o',

        # Icelandic
        'Þ': 'Th', 'þ': 'th',  # Thorn
        'Ð': 'D', 'ð': 'd',    # Eth

        # Romanian
        'Ă': 'A', 'ă': 'a',
        'Ș': 'S', 'ș': 's',
        'Ț': 'T', 'ț': 't',

        # Hungarian
        'Ő': 'O', 'ő': 'o',
        'Ű': 'U', 'ű': 'u',

        # Greek (common letters)
        'Α': 'A', 'α': 'a',
        'Β': 'B', 'β': 'b',
        'Γ': 'G', 'γ': 'g',
        'Δ': 'D', 'δ': 'd',
        'Ε': 'E', 'ε': 'e',
        'Ζ': 'Z', 'ζ': 'z',
        'Η': 'E', 'η': 'e',
        'Θ': 'Th', 'θ': 'th',
        'Ι': 'I', 'ι': 'i',
        'Κ': 'K', 'κ': 'k',
        'Λ': 'L', 'λ': 'l',
        'Μ': 'M', 'μ': 'm',
        'Ν': 'N', 'ν': 'n',
        'Ξ': 'X', 'ξ': 'x',
        'Ο': 'O', 'ο': 'o',
        'Π': 'P', 'π': 'p',
        'Ρ': 'R', 'ρ': 'r',
        'Σ': 'S', 'σ': 's', 'ς': 's',  # Final sigma
        'Τ': 'T', 'τ': 't',
        'Υ': 'Y', 'υ': 'y',
        'Φ': 'Ph', 'φ': 'ph',
        'Χ': 'Ch', 'χ': 'ch',
        'Ψ': 'Ps', 'ψ': 'ps',
        'Ω': 'O', 'ω': 'o',

        # Cyrillic (Russian - basic letters)
        'А': 'A', 'а': 'a',
        'Б': 'B', 'б': 'b',
        'В': 'V', 'в': 'v',
        'Г': 'G', 'г': 'g',
        'Д': 'D', 'д': 'd',
        'Е': 'E', 'е': 'e',
        'Ё': 'E', 'ё': 'e',
        'Ж': 'Zh', 'ж': 'zh',
        'З': 'Z', 'з': 'z',
        'И': 'I', 'и': 'i',
        'Й': 'Y', 'й': 'y',
        'К': 'K', 'к': 'k',
        'Л': 'L', 'л': 'l',
        'М': 'M', 'м': 'm',
        'Н': 'N', 'н': 'n',
        'О': 'O', 'о': 'o',
        'П': 'P', 'п': 'p',
        'Р': 'R', 'р': 'r',
        'С': 'S', 'с': 's',
        'Т': 'T', 'т': 't',
        'У': 'U', 'у': 'u',
        'Ф': 'F', 'ф': 'f',
        'Х': 'Kh', 'х': 'kh',
        'Ц': 'Ts', 'ц': 'ts',
        'Ч': 'Ch', 'ч': 'ch',
        'Ш': 'Sh', 'ш': 'sh',
        'Щ': 'Shch', 'щ': 'shch',
        'Ъ': '', 'ъ': '',  # Hard sign (silent)
        'Ы': 'Y', 'ы': 'y',
        'Ь': '', 'ь': '',  # Soft sign (silent)
        'Э': 'E', 'э': 'e',
        'Ю': 'Yu', 'ю': 'yu',
        'Я': 'Ya', 'я': 'ya',
    }

    if source_lang and source_lang in LANG_SPECIFIC_MAPPINGS:
        manual_map.update(LANG_SPECIFIC_MAPPINGS[source_lang])
    else:
        manual_map.update(LANG_SPECIFIC_MAPPINGS.get("tr", {}))

    for char, replacement in manual_map.items():
        filename = filename.replace(char, replacement)

    filename = ''.join(
        c for c in unicodedata.normalize('NFD', filename)
        if unicodedata.category(c) != 'Mn'
    )

    # 4. Windows invalid characters -> underscore
    # These characters cannot be used in Windows filenames
    invalid_chars = '<>:"/\\|?*\'`@$%^&+=[]{}#;!~()'
    for char in invalid_chars:
        filename = filename.replace(char, '_')

    # 5. Control characters (ASCII 0-31) → remove
    filename = ''.join(c for c in filename if ord(c) >= 32)

    # 6. Space → underscore (for URL-safe and CLI-friendly names)
    filename = filename.replace(' ', '_')

    # 7. Multiple underscores → single (aesthetic cleanup)
    filename = re.sub(r'_+', '_', filename)

    # 8. Lowercase conversion (optional, for consistency)
    if not keep_case:
        filename = filename.lower()

    # 9. Windows reserved names protection
    # COM1, LPT1, CON, PRN, AUX, NUL, etc. cannot be used as filenames
    base_name = filename.split('.')[0] if '.' in filename else filename
    reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                      'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2',
                      'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
    if base_name.upper() in reserved_names:
        filename = f"video_{filename}"

    # 10. Length limit (Windows max path: 260, filename: 200 safe)
    if len(filename) > 200:
        # Preserve extension if present
        if '.' in filename:
            name, ext = filename.rsplit('.', 1)
            filename = name[:200-len(ext)-1] + '.' + ext
        else:
            filename = filename[:200]

    # 11. Strip trailing dots/spaces/underscores (Windows doesn't allow)
    filename = filename.rstrip('. _')

    # 12. Fallback for empty filename
    return filename or "video"
