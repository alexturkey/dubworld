"""XTTS için Türkçe metin hazırlama: kısaltma/sıra sayısı/tırnak koruma, nokta-soru-ünlem → virgül, 150 karakterlik parçalar."""
import re
import unicodedata

KISALTMALAR = [
    'Dr.', 'Prof.', 'Doc.', 'Yrd.', 'Ogr.', 'Gor.',
    'vb.', 'vs.', 'vd.', 'bkz.', 'orn.', 'yy.',
    'Ltd.', 'Sti.', 'A.S.', 'T.C.', 'ABD.',
    'M.O.', 'M.S.', 'I.O.', 'I.S.',
    'No.', 'Tel.', 'Fax.', 'E-posta.',
]


def unicode_temizle(text):
    text = text.replace('\u0130', '<<BUYUK_I_NOKTA>>')
    text = unicodedata.normalize('NFD', text)
    text = text.replace('i\u0307', 'i')
    text = text.replace('I\u0307', '<<BUYUK_I_NOKTA>>')
    text = unicodedata.normalize('NFC', text)
    text = text.replace('<<BUYUK_I_NOKTA>>', '\u0130')
    return text


def kisaltmalari_koru(text):
    for kisaltma in KISALTMALAR:
        if kisaltma in text:
            korumali = kisaltma.replace('.', '\u00a7')
            text = text.replace(kisaltma, korumali)
    return text


def kisaltmalari_geri_al(text):
    text = text.replace('\u00a7', '.')
    return text


def sira_sayilarini_koru(text):
    pattern = r'(\d+)\.\s+([a-z\u00e7\u011f\u0131\u00f6\u015f\u00fc])'
    text = re.sub(pattern, '\\1\u00b6 \\2', text)
    pattern2 = r'(\d+)\.\s+(Y\u00fczy\u0131l|Madde|B\u00f6l\u00fcm|K\u0131s\u0131m|Say\u0131)'
    text = re.sub(pattern2, '\\1\u00b6 \\2', text, flags=re.IGNORECASE)
    return text


def sira_sayilarini_geri_al(text):
    text = text.replace('\u00b6', '.')
    return text


def tirnak_icini_koru(text):
    def replace_inside_quotes(match):
        content = match.group(1)
        content = content.replace('.', '\u25cf')
        content = content.replace('?', '\u25c6')
        content = content.replace('!', '\u25b2')
        return '"' + content + '"'
    text = re.sub(r'"([^"]*)"', replace_inside_quotes, text)
    return text


def tirnak_icini_geri_al(text):
    text = text.replace('\u25cf', '.')
    text = text.replace('\u25c6', '?')
    text = text.replace('\u25b2', '!')
    return text


def yazidan_konusmaya(text):
    text = unicode_temizle(text)
    text = ' '.join(text.split())
    text = kisaltmalari_koru(text)
    text = sira_sayilarini_koru(text)
    text = tirnak_icini_koru(text)
    text = text.replace('...', '\u2026')
    text = text.replace('\u2026', ',')
    text = text.replace(';', ',')
    text = re.sub(r'\?\s+', ', ', text)
    text = text.rstrip('?')
    text = re.sub(r'!\s+', ', ', text)
    text = text.rstrip('!')
    text = re.sub(r'\.\s+([A-Z\u00c7\u011e\u0130\u00d6\u015e\u00dc])', r', \1', text)
    text = re.sub(r'\.\s+([a-z\u00e7\u011f\u0131\u00f6\u015f\u00fc])', r', \1', text)
    text = re.sub(r'\.\s+(\d)', r', \1', text)
    text = re.sub(r'\.\s+"', ', "', text)
    text = text.rstrip('.')
    text = kisaltmalari_geri_al(text)
    text = sira_sayilarini_geri_al(text)
    text = tirnak_icini_geri_al(text)

    if len(text) > 1:
        def kucult(match):
            virgul = match.group(1)
            harf = match.group(2)
            kelime_devami = match.group(3) if match.lastindex >= 3 else ''
            return virgul + harf.lower() + kelime_devami
        text = re.sub(
            r'(,\s+)([A-Z\u00c7\u011e\u0130\u00d6\u015e\u00dc])([a-z\u00e7\u011f\u0131\u00f6\u015f\u00fc])',
            kucult, text
        )

    text = re.sub(r',\s*,', ',', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    text = re.sub(r',([^\s])', r', \1', text)
    text = unicode_temizle(text)
    return text


def xtts_metin_hazirla(text):
    konusma = yazidan_konusmaya(text)
    if not konusma.endswith(','):
        konusma = konusma + ','
    return konusma


def _bosluktan_bol(text, max_chars=150):
    parcalar = []
    while len(text) > max_chars:
        kesim = text[:max_chars].rfind(' ')
        if kesim <= 0:
            kesim = max_chars
        parcalar.append(text[:kesim].strip())
        text = text[kesim:].strip()
    if text:
        parcalar.append(text)
    return parcalar


def _merge_short_segments(segmentler, min_chars=50, max_chars=150):
    birlesik = []
    i = 0
    while i < len(segmentler):
        current = segmentler[i]

        while i + 1 < len(segmentler):
            sonraki = segmentler[i + 1]
            birlesik_text = current + ", " + sonraki

            if len(birlesik_text) <= max_chars:
                current = birlesik_text
                i += 1
            else:
                break

        birlesik.append(current)
        i += 1

    if len(birlesik) >= 2 and len(birlesik[-1]) < min_chars:
        birlesim = birlesik[-2] + ", " + birlesik[-1]
        if len(birlesim) <= max_chars:
            birlesik.pop()
            birlesik[-1] = birlesim

    sonuc = []
    for parca in birlesik:
        if len(parca) > max_chars:
            sonuc.extend(_bosluktan_bol(parca, max_chars))
        else:
            sonuc.append(parca)

    return sonuc


def xtts_metin_parcala(text, max_chars=150, min_chars=50):
    konusma = yazidan_konusmaya(text)

    if len(konusma) <= max_chars:
        if not konusma.endswith(','):
            konusma = konusma + ','
        return [konusma]

    segmentler = [s.strip() for s in konusma.split(',') if s.strip()]

    birlesik = _merge_short_segments(segmentler, min_chars, max_chars)

    parcalar = []
    for parca in birlesik:
        if not parca.endswith(','):
            parca = parca + ','
        parcalar.append(parca)

    return parcalar
