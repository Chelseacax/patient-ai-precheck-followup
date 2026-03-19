"""
Supported languages and dialect configuration for Singapore / Southeast Asia.
"""

SUPPORTED_LANGUAGES = {
    # --- Singapore Official Languages ---
    "English": {
        "dialects": ["Standard Singapore English", "Singlish"],
        "code": "en",
        "group": "Singapore Official Languages",
    },
    "华语 (Mandarin)": {
        "dialects": ["新加坡华语 (Singapore Mandarin)", "标准普通话 (Standard Mandarin)"],
        "code": "zh",
        "group": "Singapore Official Languages",
    },
    "Malay (Bahasa Melayu)": {
        "dialects": ["Standard Bahasa Melayu", "Bazaar Melayu / Pasar Melayu", "Informal / Colloquial Malay"],
        "code": "ms",
        "group": "Singapore Official Languages",
    },
    "Tamil (தமிழ்)": {
        "dialects": ["Singapore Tamil (சிங்கப்பூர் தமிழ்)", "Standard Tamil (நிலைத்தமிழ்)"],
        "code": "ta",
        "group": "Singapore Official Languages",
    },
    # --- Singapore Chinese Dialects ---
    "广东话 (Cantonese)": {
        "dialects": ["新加坡广东话 (Singapore Cantonese)", "香港广东话 (Hong Kong Cantonese)"],
        "code": "zh-cantonese",
        "group": "Singapore Chinese Dialects",
    },
    # --- Southeast Asian Languages ---
    "Hindi (हिन्दी)": {
        "dialects": ["Standard Hindi", "Colloquial Hindi"],
        "code": "hi",
        "group": "Southeast Asian Languages",
    },
    "Tagalog (Filipino)": {
        "dialects": ["Standard Filipino", "Taglish"],
        "code": "tl",
        "group": "Southeast Asian Languages",
    },
    "Vietnamese (Tiếng Việt)": {
        "dialects": ["Northern Vietnamese", "Southern Vietnamese"],
        "code": "vi",
        "group": "Southeast Asian Languages",
    },
    "Thai (ภาษาไทย)": {
        "dialects": ["Central Thai", "Informal Thai"],
        "code": "th",
        "group": "Southeast Asian Languages",
    },
    "Bahasa Indonesia": {
        "dialects": ["Formal Indonesian", "Informal / Colloquial"],
        "code": "id",
        "group": "Southeast Asian Languages",
    },
    "Burmese (မြန်မာဘာသာ)": {
        "dialects": ["Standard Burmese", "Colloquial Burmese"],
        "code": "my",
        "group": "Southeast Asian Languages",
    },
    "Bengali (বাংলা)": {
        "dialects": ["Standard Bengali", "Bangladeshi Bengali"],
        "code": "bn",
        "group": "Southeast Asian Languages",
    },
    "Khmer (ភាសាខ្មែរ)": {
        "dialects": ["Standard Khmer", "Colloquial Khmer"],
        "code": "km",
        "group": "Southeast Asian Languages",
    },
}

LANGUAGES_SKIP_ENGLISH_TRANSLATION: frozenset = frozenset()
