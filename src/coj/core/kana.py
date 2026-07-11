"""phonemic_to_kana — shared Old Japanese romanisation → historical katakana."""

_KANA_RAW: list[tuple[str, str]] = [
    # Three-character syllables first
    ("pye", "ヘ"), ("pwi", "ヒ"),
    ("bye", "ベ"), ("bwi", "ビ"),
    ("kye", "ケ"), ("kwi", "キ"), ("kwo", "コ"),
    ("gye", "ゲ"), ("gwi", "ギ"), ("gwo", "ゴ"),
    ("mye", "メ"), ("mwi", "ミ"), ("mwo", "モ"),
    ("two", "ト"), ("dwo", "ド"),
    ("swo", "ソ"), ("zwo", "ゾ"),
    ("nwo", "ノ"), ("ywo", "ヨ"), ("rwo", "ロ"),
    # Two-character syllables
    ("pa", "ハ"), ("pi", "ヒ"), ("pu", "フ"), ("pe", "ヘ"), ("po", "ホ"),
    ("ba", "バ"), ("bi", "ビ"), ("bu", "ブ"), ("be", "ベ"), ("bo", "ボ"),
    ("ka", "カ"), ("ki", "キ"), ("ku", "ク"), ("ke", "ケ"), ("ko", "コ"),
    ("ga", "ガ"), ("gi", "ギ"), ("gu", "グ"), ("ge", "ゲ"), ("go", "ゴ"),
    ("ma", "マ"), ("mi", "ミ"), ("mu", "ム"), ("me", "メ"), ("mo", "モ"),
    ("ta", "タ"), ("ti", "チ"), ("tu", "ツ"), ("te", "テ"), ("to", "ト"),
    ("da", "ダ"), ("di", "ヂ"), ("du", "ヅ"), ("de", "デ"), ("do", "ド"),
    ("sa", "サ"), ("si", "シ"), ("su", "ス"), ("se", "セ"), ("so", "ソ"),
    ("za", "ザ"), ("zi", "ジ"), ("zu", "ズ"), ("ze", "ゼ"), ("zo", "ゾ"),
    ("na", "ナ"), ("ni", "ニ"), ("nu", "ヌ"), ("ne", "ネ"), ("no", "ノ"),
    ("ya", "ヤ"), ("yu", "ユ"), ("yo", "ヨ"),
    ("ra", "ラ"), ("ri", "リ"), ("ru", "ル"), ("re", "レ"), ("ro", "ロ"),
    ("wa", "ワ"), ("we", "ヱ"),
    # Two-vowel combinations
    ("ye", "エ"), ("wi", "ヰ"), ("wo", "ヲ"),
    # Bare vowels (shortest; must come last)
    ("a", "ア"), ("i", "イ"), ("u", "ウ"), ("o", "オ"), ("e", "エ"),
]

# Sorted longest-first for greedy left-to-right matching
_KANA_TABLE: list[tuple[str, str]] = sorted(_KANA_RAW, key=lambda x: -len(x[0]))


def phonemic_to_kana(form: str) -> str:
    """
    Convert romanised Old Japanese phonemic transcription to historical katakana.
    Uses greedy longest-match left-to-right. Unrecognised segments are wrapped
    in ⟨…⟩.
    """
    result: list[str] = []
    pos = 0
    low = form.lower()
    while pos < len(low):
        matched = False
        for phon, kana in _KANA_TABLE:
            if low.startswith(phon, pos):
                result.append(kana)
                pos += len(phon)
                matched = True
                break
        if not matched:
            result.append(f"⟨{low[pos]}⟩")
            pos += 1
    return "".join(result)
