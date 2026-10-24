"""Hedef dile bagli her sey tek yerde: dil adlari, istem sablonu isleme, konusma hizi, cikti dili denetimi.

Bu dosyanin iki kopyasi vardir (llm_kopru/scripts ve claude_code_cli/scripts; bayt esit, test denetler):
isciler betik olarak calistigi icin istem_guvenligi.py ve natural_blocks_chain_contract.py ile ayni duzen.
Orkestrator (engine.py) llm_kopru kopyasini paket yoluyla ice aktarir.

Istem sablonu (docs/adr/0014-language-independent-translation-prompts.md):
- Satir ici yer tutucular: {target_lang_name} (Turkce adi: Turkce, Fransizca), {target_lang_name+de} (Turkce ekli
  bicim; ek on unlu bicimiyle yazilir, ses uyumu kendiliginden: Turkcede / Fransizcada), {target_lang_name_ascii},
  {target_lang_name_en} (English name), {target_lang_code}.
- Blok: "<!-- dil:tr -->" ... ["<!-- dil:diger -->" ...] "<!-- /dil -->" (her isaret kendi satirinda).
  tr hedefinde yalniz tr bolumu kalir (isaret satirlari silinir; tr icin cikti eski istemle bayt bayt aynidir).
  Baska dilde tr bolumu atilir; yerine diger bolumu, ya da "<!-- dil:tr ek=ANAHTAR -->" ise dil_ekleri/<kod>.md
  icindeki "## ANAHTAR" bolumu (yoksa dil_ekleri/_genel.md), ikisi de yoksa hicbir sey gelir.
- tr disi hedefte istemin sonuna dil eki eklenir: _genel.md "## genel" + <kod>.md "## genel".
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

DIL_EKLERI_KOKU = Path(__file__).resolve().parents[2] / "dil_ekleri"
VARSAYILAN_DIL = "tr"

# kod -> (Turkce ad, Ingilizce ad). Ingilizce adlar dubber.py yaziya dokum tablosuyla ayni kumedir.
DIL_ADLARI: dict[str, tuple[str, str]] = {
    "tr": ("Türkçe", "Turkish"), "en": ("İngilizce", "English"), "fr": ("Fransızca", "French"),
    "de": ("Almanca", "German"), "es": ("İspanyolca", "Spanish"), "it": ("İtalyanca", "Italian"),
    "pt": ("Portekizce", "Portuguese"), "ru": ("Rusça", "Russian"), "ja": ("Japonca", "Japanese"),
    "ko": ("Korece", "Korean"), "zh": ("Çince", "Chinese"), "ar": ("Arapça", "Arabic"),
    "hi": ("Hintçe", "Hindi"), "nl": ("Felemenkçe", "Dutch"), "pl": ("Lehçe", "Polish"),
    "sv": ("İsveççe", "Swedish"), "da": ("Danca", "Danish"), "no": ("Norveççe", "Norwegian"),
    "fi": ("Fince", "Finnish"), "cs": ("Çekçe", "Czech"), "el": ("Yunanca", "Greek"),
    "he": ("İbranice", "Hebrew"), "hu": ("Macarca", "Hungarian"), "id": ("Endonezce", "Indonesian"),
    "ms": ("Malayca", "Malay"), "th": ("Tayca", "Thai"), "vi": ("Vietnamca", "Vietnamese"),
    "uk": ("Ukraynaca", "Ukrainian"), "ro": ("Rumence", "Romanian"), "bg": ("Bulgarca", "Bulgarian"),
    "hr": ("Hırvatça", "Croatian"), "sk": ("Slovakça", "Slovak"), "sl": ("Slovence", "Slovenian"),
    "sr": ("Sırpça", "Serbian"), "lt": ("Litvanca", "Lithuanian"), "lv": ("Letonca", "Latvian"),
    "et": ("Estonca", "Estonian"), "fa": ("Farsça", "Persian"), "bn": ("Bengalce", "Bengali"),
    "ta": ("Tamilce", "Tamil"), "te": ("Teluguca", "Telugu"), "mr": ("Marathice", "Marathi"),
    "gu": ("Güceratça", "Gujarati"), "kn": ("Kannadaca", "Kannada"), "ml": ("Malayalamca", "Malayalam"),
    "pa": ("Pencapça", "Punjabi"), "ur": ("Urduca", "Urdu"), "sw": ("Svahilice", "Swahili"),
    "af": ("Afrikaanca", "Afrikaans"), "ca": ("Katalanca", "Catalan"), "gl": ("Galiçyaca", "Galician"),
    "eu": ("Baskça", "Basque"), "cy": ("Galce", "Welsh"), "ga": ("İrlandaca", "Irish"),
    "mt": ("Maltaca", "Maltese"), "is": ("İzlandaca", "Icelandic"), "mk": ("Makedonca", "Macedonian"),
    "sq": ("Arnavutça", "Albanian"), "bs": ("Boşnakça", "Bosnian"), "az": ("Azerice", "Azerbaijani"),
    "ka": ("Gürcüce", "Georgian"), "hy": ("Ermenice", "Armenian"), "ne": ("Nepalce", "Nepali"),
    "si": ("Sinhalaca", "Sinhala"), "km": ("Khmerce", "Khmer"), "lo": ("Laoca", "Lao"),
    "my": ("Birmanca", "Burmese"), "mn": ("Moğolca", "Mongolian"), "kk": ("Kazakça", "Kazakh"),
    "uz": ("Özbekçe", "Uzbek"), "tg": ("Tacikçe", "Tajik"), "ky": ("Kırgızca", "Kyrgyz"),
    "tk": ("Türkmence", "Turkmen"), "am": ("Amharca", "Amharic"), "yo": ("Yorubaca", "Yoruba"),
    "zu": ("Zuluca", "Zulu"), "xh": ("Xhosaca", "Xhosa"), "so": ("Somalice", "Somali"),
    "ha": ("Hausaca", "Hausa"), "ig": ("İgboca", "Igbo"),
}
DIL_KODU_ESLERI = {"iw": "he", "nb": "no", "nn": "no", "in": "id", "jw": "jv", "zh_hans": "zh", "zh_hant": "zh"}


def dil_kodu(deger: Any) -> str:
    """'pt-BR' -> 'pt', 'ZH_cn' -> 'zh'; bos ise 'tr' (eski davranis: istemler Turkce hedefliydi)."""
    kod = str(deger or "").strip().lower().replace("_", "-")
    if not kod:
        return VARSAYILAN_DIL
    kod = kod.split("-", 1)[0]
    return DIL_KODU_ESLERI.get(kod, kod)


def is_hedef_dili(job: dict[str, Any] | None) -> str:
    return dil_kodu((job or {}).get("target_lang") if isinstance(job, dict) else "")


def is_kaynak_dili(job: dict[str, Any] | None) -> str:
    deger = (job or {}).get("source_lang") if isinstance(job, dict) else ""
    return dil_kodu(deger) if str(deger or "").strip() else "en"


_ON_UNLU = set("eiöüEİÖÜ")
_ARKA_UNLU = set("aıouAIOU")
_UNLU_DONUSUMU = str.maketrans({"e": "a", "i": "ı", "ö": "o", "ü": "u"})
_ASCII_DONUSUMU = str.maketrans({"ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ı": "i", "İ": "I", "ö": "o", "Ö": "O",
                                 "ş": "s", "Ş": "S", "ü": "u", "Ü": "U"})


def dil_adi(kod: str, ek: str = "") -> str:
    """Turkce dil adi + istege bagli ek (ek on unlu bicimiyle: 'de', 'yle', 'leştirme')."""
    kod = dil_kodu(kod)
    ad = DIL_ADLARI.get(kod, ("", ""))[0] or (DIL_ADLARI.get(kod, ("", ""))[1] or kod.upper())
    if not ek:
        return ad
    son_unlu = next((harf for harf in reversed(ad) if harf in _ON_UNLU or harf in _ARKA_UNLU), "e")
    return ad + (ek.translate(_UNLU_DONUSUMU) if son_unlu in _ARKA_UNLU else ek)


def dil_adi_en(kod: str) -> str:
    kod = dil_kodu(kod)
    return DIL_ADLARI.get(kod, ("", kod.upper()))[1] or kod.upper()


def dil_adi_ascii(kod: str, ek: str = "") -> str:
    return dil_adi(kod, ek).translate(_ASCII_DONUSUMU)


# ---------------------------------------------------------------- istem sablonu

YER_TUTUCU = re.compile(r"\{target_lang_(name_ascii|name_en|name|code)(?:\+([^\s{}]+))?\}")
_BLOK_BAS = re.compile(r"^<!-- dil:tr(?: ek=([a-z0-9_]+))? -->\s*$")
_BLOK_DIGER = re.compile(r"^<!-- dil:diger -->\s*$")
_BLOK_SON = re.compile(r"^<!-- /dil -->\s*$")


class IstemSablonuHatasi(ValueError):
    pass


def yer_tutuculari_doldur(metin: str, kod: str) -> str:
    kod = dil_kodu(kod)

    def degistir(eslesme: re.Match[str]) -> str:
        tur, ek = eslesme.group(1), eslesme.group(2) or ""
        if tur == "name":
            return dil_adi(kod, ek)
        if tur == "name_ascii":
            return dil_adi_ascii(kod, ek)
        if tur == "name_en":
            return dil_adi_en(kod)
        return kod

    return YER_TUTUCU.sub(degistir, metin)


def dil_eki_bolumleri(kod: str) -> dict[str, str]:
    """dil_ekleri/<kod>.md icindeki '## anahtar' bolumleri; ilk basliktan onceki giris (kaynak notlari) atilir."""
    yol = DIL_EKLERI_KOKU / f"{dil_kodu(kod) if not kod.startswith('_') else kod}.md"
    if not yol.is_file():
        return {}
    bolumler: dict[str, list[str]] = {}
    anahtar = ""
    for satir in yol.read_text(encoding="utf-8").splitlines():
        if satir.startswith("## "):
            anahtar = satir[3:].strip()
            bolumler[anahtar] = []
        elif anahtar:
            bolumler[anahtar].append(satir)
    return {ad: "\n".join(satirlar).strip("\n") for ad, satirlar in bolumler.items()}


def dil_eki_bolumu(kod: str, anahtar: str) -> str | None:
    ozel = dil_eki_bolumleri(kod)
    if anahtar in ozel:
        return ozel[anahtar]
    genel = dil_eki_bolumleri("_genel")
    return genel.get(anahtar)


def dil_eki_metni(kod: str) -> str:
    """tr disi hedefte istemin sonuna eklenen ek (_genel 'genel' + dile ozel 'genel')."""
    kod = dil_kodu(kod)
    if kod == "tr":
        return ""
    parcalar = [dil_eki_bolumleri("_genel").get("genel", ""), dil_eki_bolumleri(kod).get("genel", "")]
    return yer_tutuculari_doldur("\n\n".join(parca for parca in parcalar if parca.strip()), kod)


def istem_isle(sablon: str, kod: str) -> str:
    """Istem sablonunu hedef dile gore isler. tr icin cikti, sablonlastirma oncesi istemle bayt bayt aynidir."""
    kod = dil_kodu(kod)
    cikti: list[str] = []
    durum = ""  # "", "tr", "diger"
    anahtar = ""
    diger: list[str] = []
    for satir in sablon.splitlines(keepends=True):
        govde = satir.rstrip("\r\n")
        bas = _BLOK_BAS.match(govde)
        if bas:
            if durum:
                raise IstemSablonuHatasi("ic ice dil blogu")
            durum, anahtar, diger = "tr", bas.group(1) or "", []
            continue
        if _BLOK_DIGER.match(govde):
            if durum != "tr" or anahtar:
                raise IstemSablonuHatasi("dil:diger yalniz eksiz dil:tr blogunun icinde olur")
            durum = "diger"
            continue
        if _BLOK_SON.match(govde):
            if not durum:
                raise IstemSablonuHatasi("acilmamis dil blogu kapatildi")
            if kod != "tr":
                if anahtar:
                    bolum = dil_eki_bolumu(kod, anahtar)
                    if bolum is None:
                        raise IstemSablonuHatasi(f"dil_ekleri/_genel.md icinde '## {anahtar}' bolumu yok")
                    if bolum.strip():
                        cikti.append(bolum + "\n")
                else:
                    cikti.extend(diger)
            durum, anahtar, diger = "", "", []
            continue
        if durum == "tr":
            if kod == "tr":
                cikti.append(satir)
        elif durum == "diger":
            diger.append(satir)
        else:
            cikti.append(satir)
    if durum:
        raise IstemSablonuHatasi("kapanmamis dil blogu")
    metin = yer_tutuculari_doldur("".join(cikti), kod)
    ek = dil_eki_metni(kod)
    if ek:
        sonda_satir = metin.endswith("\n")
        govde = metin.rstrip("\n") + "\n\n" if metin.strip() else ""
        metin = govde + ek + ("\n" if sonda_satir else "")
    return metin


def sema_isle(deger: Any, kod: str) -> Any:
    """JSON semasindaki metinlerde yer tutuculari doldurur (aciklamalar dilden bagimsiz kalir)."""
    if isinstance(deger, str):
        return yer_tutuculari_doldur(deger, kod)
    if isinstance(deger, list):
        return [sema_isle(oge, kod) for oge in deger]
    if isinstance(deger, dict):
        return {anahtar: sema_isle(oge, kod) for anahtar, oge in deger.items()}
    return deger


def konusma_slug(kod: str) -> str:
    """'turkish', 'french': is JSON'undaki oncelik etiketi icin."""
    return re.sub(r"[^a-z]+", "_", dil_adi_en(kod).lower()).strip("_") or "target_language"


# ---------------------------------------------------------------- konusma hizi ve sayim

# saniye_birim: kelime dillerinde sn/kelime, karakter dillerinde sn/karakter.
# karakter_kelime: karakter dillerinde bir 'kelime esdegeri' kac karakter (Latin ad ve kisaltmalar ayrica kelime sayilir).
# kaynak: olcum = proje olcumu; tahmin = dogrulanmadi (docs/adr/0014 tablo notu). Degerler yalniz tavsiye niteligindeki
# hedef kelime sayilarini uretir; gercek sure TTS olcumuyle belirlenir (ADR 0010).
KONUSMA_HIZI: dict[str, dict[str, Any]] = {
    "tr": {"birim": "kelime", "saniye_birim": 0.43, "kaynak": "olcum: Supertonic Turkce dublaj, proje varsayilani"},
    "en": {"birim": "kelime", "saniye_birim": 0.33, "kaynak": "tahmin: tr olcumu x ayni icerigin kelime orani"},
    "de": {"birim": "kelime", "saniye_birim": 0.38, "kaynak": "tahmin: bilesik kelimeler, tr'ye yakin"},
    "fr": {"birim": "kelime", "saniye_birim": 0.32, "kaynak": "tahmin: kisa islev sozcukleri bol"},
    "es": {"birim": "kelime", "saniye_birim": 0.32, "kaynak": "tahmin: kisa islev sozcukleri bol"},
    "it": {"birim": "kelime", "saniye_birim": 0.33, "kaynak": "tahmin"},
    "pt": {"birim": "kelime", "saniye_birim": 0.33, "kaynak": "tahmin"},
    "ru": {"birim": "kelime", "saniye_birim": 0.40, "kaynak": "tahmin: cekimli, uzun kelimeler"},
    "ar": {"birim": "kelime", "saniye_birim": 0.40, "kaynak": "tahmin: ekli yazim, uzun kelimeler"},
    "ja": {"birim": "karakter", "saniye_birim": 0.17, "karakter_kelime": 2.5,
           "kaynak": "tahmin: yayin okumasi icin anilan ~300-350 karakter/dk araligi"},
    "zh": {"birim": "karakter", "saniye_birim": 0.22, "karakter_kelime": 1.7,
           "kaynak": "tahmin: Pellegrino ve ark. 2011 (Language 87/3) Mandarin ~5,2 hece/sn, bir karakter bir hece, duraklar dahil"},
    "ko": {"birim": "karakter", "saniye_birim": 0.16, "karakter_kelime": 3.0,
           "kaynak": "tahmin: bir Hangul hecesi bir karakter, ~6 hece/sn"},
    "th": {"birim": "karakter", "saniye_birim": 0.10, "karakter_kelime": 5.0,
           "kaynak": "tahmin: bosluksuz yazim, unlu isaretleri sayilmaz"},
}
VARSAYILAN_SANIYE_KELIME = 0.43  # tabloda olmayan dil: eski davranis (tum diller icin 0.43) korunur


def karakter_tabanli(kod: str) -> bool:
    return KONUSMA_HIZI.get(dil_kodu(kod), {}).get("birim") == "karakter"


def saniye_per_kelime(kod: str) -> float:
    """Bir kelime (ya da kelime esdegeri) icin ortalama konusma suresi; tr = 0.43 (degismez)."""
    bilgi = KONUSMA_HIZI.get(dil_kodu(kod))
    if not bilgi:
        return VARSAYILAN_SANIYE_KELIME
    if bilgi["birim"] == "karakter":
        return float(bilgi["saniye_birim"]) * float(bilgi["karakter_kelime"])
    return float(bilgi["saniye_birim"])


def _bosluk_sayaci(metin: str) -> int:
    return len(str(metin or "").split())


_LATIN_PARCA = re.compile(r"[A-Za-z0-9À-ɏ]+(?:[.'’\-][A-Za-z0-9À-ɏ]+)*")


def kelime_esdegeri(metin: str, kod: str, kelime_sayaci: Callable[[str], int] | None = None) -> int:
    """Kelime dillerinde verilen sayac (varsayilan bosluk bolme; cagiranin eski sayaci aynen korunur).
    zh/ja/ko/th: yazi karakterleri / karakter_kelime + icindeki Latin/rakam parcalari (marka, kisaltma)."""
    metin = str(metin or "")
    if not karakter_tabanli(kod):
        return (kelime_sayaci or _bosluk_sayaci)(metin)
    latin = _LATIN_PARCA.findall(metin)
    kalan = _LATIN_PARCA.sub(" ", metin)
    yazi_karakteri = sum(1 for harf in kalan if harf.isalnum())
    deger = yazi_karakteri / float(KONUSMA_HIZI[dil_kodu(kod)]["karakter_kelime"]) + len(latin)
    if deger <= 0:
        return 0
    return max(1, int(deger + 0.5))


# ---------------------------------------------------------------- cikti dili denetimi

_YAZILAR: tuple[tuple[str, tuple[tuple[int, int], ...]], ...] = (
    ("latin", ((0x41, 0x5A), (0x61, 0x7A), (0xC0, 0x24F), (0x1E00, 0x1EFF))),
    ("kiril", ((0x400, 0x52F),)),
    ("yunan", ((0x370, 0x3FF),)),
    ("ermeni", ((0x530, 0x58F),)),
    ("ibrani", ((0x590, 0x5FF),)),
    ("arap", ((0x600, 0x6FF), (0x750, 0x77F), (0x8A0, 0x8FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))),
    ("devanagari", ((0x900, 0x97F),)),
    ("bengal", ((0x980, 0x9FF),)),
    ("gurmukhi", ((0xA00, 0xA7F),)),
    ("gucerat", ((0xA80, 0xAFF),)),
    ("tamil", ((0xB80, 0xBFF),)),
    ("telugu", ((0xC00, 0xC7F),)),
    ("kannada", ((0xC80, 0xCFF),)),
    ("malayalam", ((0xD00, 0xD7F),)),
    ("sinhala", ((0xD80, 0xDFF),)),
    ("tay", ((0xE00, 0xE7F),)),
    ("lao", ((0xE80, 0xEFF),)),
    ("birman", ((0x1000, 0x109F),)),
    ("gurcu", ((0x10A0, 0x10FF),)),
    ("hangul", ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF))),
    ("etiyopya", ((0x1200, 0x137F),)),
    ("khmer", ((0x1780, 0x17FF),)),
    ("kana", ((0x3040, 0x30FF), (0x31F0, 0x31FF), (0xFF66, 0xFF9F))),
    ("han", ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF))),
)
DIL_YAZISI: dict[str, set[str]] = {
    "ru": {"kiril"}, "uk": {"kiril"}, "bg": {"kiril"}, "mk": {"kiril"}, "kk": {"kiril"}, "ky": {"kiril"},
    "tg": {"kiril"}, "mn": {"kiril"}, "sr": {"kiril", "latin"}, "el": {"yunan"}, "hy": {"ermeni"},
    "he": {"ibrani"}, "ar": {"arap"}, "fa": {"arap"}, "ur": {"arap"}, "hi": {"devanagari"},
    "mr": {"devanagari"}, "ne": {"devanagari"}, "bn": {"bengal"}, "pa": {"gurmukhi"}, "gu": {"gucerat"},
    "ta": {"tamil"}, "te": {"telugu"}, "kn": {"kannada"}, "ml": {"malayalam"}, "si": {"sinhala"},
    "th": {"tay"}, "lo": {"lao"}, "my": {"birman"}, "ka": {"gurcu"}, "ko": {"hangul", "han"},
    "am": {"etiyopya"}, "km": {"khmer"}, "ja": {"kana", "han"}, "zh": {"han"},
}

# Latin yazili diller icin islev sozcukleri (kucuk harf) ve ayirt edici harfler. Kaynak: genel dil bilgisi, elle
# secildi; yalniz 'hedef dilde hic iz yok, baska dilde guclu iz var' karari icin kullanilir.
ISLEV_SOZCUKLERI: dict[str, set[str]] = {
    "tr": set("bir bu ve için ile çok ne şu ama gibi daha var yok mi mı mu mü değil kadar sonra her hiç olarak olan "
              "ben sen biz siz onlar şey diye ki ya veya ise çünkü şimdi işte bunu şunu onu bana sana bize size "
              "nasıl neden niye artık hem bile sadece yani evet hayır oldu olur burada orada".split()),
    "en": set("the and is are was were this that with for you your it's of to in on not have has be will would "
              "can could what which who they them there here just very about from but or an".split()),
    "de": set("der die das und ist nicht ein eine mit für auf ich sie wir ihr es zu den dem des von sich auch "
              "noch wie aber oder wenn dass hier jetzt sehr".split()),
    "fr": set("le la les et est une des du pour avec dans sur pas que qui vous nous ce cette il elle ils sont "
              "mais ou au aux très ici c'est je tu".split()),
    "es": set("el la los las y es una del para con por que qué no se lo como pero muy está esto este esta "
              "usted ustedes aquí ahora también yo".split()),
    "it": set("il lo la gli le e è una del della per con che non si come ma molto questo questa sono qui ora "
              "anche io voi noi".split()),
    "pt": set("o a os as e é um uma do da dos das para com que não se como mas muito isso este esta você vocês "
              "aqui agora também eu nós".split()),
    "nl": set("de het een en is niet van voor met op dat die dit zijn wij jij u ook maar heel hier nu".split()),
    "pl": set("i w na nie jest to się że z do jak ale tak co ten ta czy być bardzo tutaj teraz".split()),
    "id": set("dan yang di ini itu tidak dengan untuk dari ke ada akan saya kami kita anda juga sangat".split()),
}
AYIRT_EDICI_HARFLER: dict[str, str] = {
    "tr": "ğış", "de": "ßä", "es": "ñ¿¡", "pt": "ãõ", "fr": "èêœù", "pl": "ąęłńśźż", "it": "",
}
CIKTI_DILI_MIN_SOZCUK = 4      # Latin-Latin karari icin en az sozcuk (kisa segmentte yanlis alarm yok)
CIKTI_DILI_MIN_HARF = 8        # yazi karari icin, kaynakta gecen ozel adlar cikarildiktan sonra en az harf
CIKTI_DILI_GUCLU_IZ = 3        # baska dilin en az bu kadar izi olmali
CIKTI_DILI_YAZI_ORANI = 0.5    # beklenen yazinin harf payi bunun altindaysa yanlis dil
CIKTI_DILI_TURKCE_HARF = 3     # Turkce disi Latin hedefte kaynakta olmayan ı/ğ/ş sayisi esigi
TURKCE_HARFLI_DILLER = {"tr", "az", "tk"}


def _yazi(harf: str) -> str:
    kod = ord(harf)
    for ad, araliklar in _YAZILAR:
        for bas, son in araliklar:
            if bas <= kod <= son:
                return ad
    return ""


def _sozcukler(metin: str) -> list[str]:
    return [sozcuk.lower() for sozcuk in re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", metin)]


def _latin_izleri(metin: str) -> dict[str, int]:
    sozcukler = _sozcukler(metin)
    kucuk = unicodedata.normalize("NFC", metin.lower())
    izler = {}
    for dil, kume in ISLEV_SOZCUKLERI.items():
        puan = sum(1 for sozcuk in sozcukler if sozcuk in kume)
        puan += sum(1 for harf in AYIRT_EDICI_HARFLER.get(dil, "") if harf in kucuk)
        izler[dil] = puan
    return izler


def metin_dili_sorunu(metin: str, kod: str, kaynak_metni: str = "", korunan: list[str] | None = None) -> str:
    """Metin hedef dilde degilse kisa aciklama, degilse ''. Emin olunmayan her durumda '' (yanlis alarm yok)."""
    kod = dil_kodu(kod)
    metin = unicodedata.normalize("NFC", str(metin or ""))
    if not metin.strip():
        return ""
    beklenen = DIL_YAZISI.get(kod, {"latin"} if kod in DIL_ADLARI else set())
    if not beklenen:
        return ""
    # Kaynakta ya da korunan terimlerde gecen sozcukler (marka, ad, kisaltma) yazi hesabindan cikarilir.
    kaynak_sozcukleri = set(_sozcukler(kaynak_metni))
    for terim in korunan or []:
        kaynak_sozcukleri.update(_sozcukler(str(terim)))
    temiz = re.sub(r"[^\W\d_]+(?:['’][^\W\d_]+)?",
                   lambda e: " " if e.group(0).lower() in kaynak_sozcukleri else e.group(0), metin)
    sayac: dict[str, int] = {}
    for harf in temiz:
        if harf.isalpha():
            yazi = _yazi(harf)
            if yazi:
                sayac[yazi] = sayac.get(yazi, 0) + 1
    toplam = sum(sayac.values())
    if toplam >= CIKTI_DILI_MIN_HARF:
        pay = sum(sayac.get(yazi, 0) for yazi in beklenen) / toplam
        if pay < CIKTI_DILI_YAZI_ORANI:
            baskin = max(sayac, key=lambda ad: sayac[ad])
            return f"beklenen yazi {'/'.join(sorted(beklenen))}, metin {baskin} yazisinda (pay {pay:.2f})"
    if kod == "ja" and sayac.get("han", 0) >= CIKTI_DILI_MIN_HARF and sayac.get("kana", 0) == 0:
        return "Japonca beklendi, metinde hic kana yok (Cince olabilir)"
    if kod == "zh":
        kana, han = sayac.get("kana", 0), sayac.get("han", 0)
        if kana >= 2 and kana >= 0.2 * (kana + han):
            return "Cince beklendi, metinde kana var (Japonca olabilir)"
    if beklenen == {"latin"} and kod not in TURKCE_HARFLI_DILLER:
        # Istemler Turkce yazildigi icin en olasi sizinti Turkcedir: kaynakta gecmeyen sozcuklerde ı/ğ/ş sayilir.
        harfler = "ığİĞ" if kod == "ro" else "ığşİĞŞ"  # Rumencede cedilla'li ş eski yazimda yaygin
        turkce_harf = sum(1 for harf in temiz if harf in harfler)
        if turkce_harf >= CIKTI_DILI_TURKCE_HARF:
            return f"{dil_adi_en(kod)} beklendi, metinde {turkce_harf} Turkceye ozgu harf (ı/ğ/ş) var"
    if beklenen == {"latin"} and kod in ISLEV_SOZCUKLERI and len(_sozcukler(metin)) >= CIKTI_DILI_MIN_SOZCUK:
        izler = _latin_izleri(metin)
        if izler.get(kod, 0) == 0:
            digeri = max((dil for dil in izler if dil != kod), key=lambda dil: izler[dil])
            if izler[digeri] >= CIKTI_DILI_GUCLU_IZ:
                return f"{dil_adi_en(kod)} beklendi, metin {dil_adi_en(digeri)} gibi (iz {digeri}={izler[digeri]}, {kod}=0)"
    return ""


def cikti_dili_ihlalleri(job: dict[str, Any], result: dict[str, Any]) -> list[str]:
    """Her aday (ya da tam metin) hedef dilde mi? Ihlal listesi; bos liste = gecti."""
    kod = is_hedef_dili(job)
    ihlaller: list[str] = []
    if job.get("task_type") == "full_text_translation":
        sorun = metin_dili_sorunu(str(result.get("translated_text") or ""), kod, str(job.get("source_text") or ""))
        return [f"tam metin: {sorun}"] if sorun else []
    kaynaklar: dict[str, str] = {}
    for anahtar in ("segments", "context_before", "context_after", "discourse_segments"):
        for segment in job.get(anahtar) or []:
            if isinstance(segment, dict):
                parca = " ".join(str(segment.get(alan) or "") for alan in ("text", "original_source_text"))
                kaynaklar[str(segment.get("id"))] = kaynaklar.get(str(segment.get("id")), "") + " " + parca
    tum_kaynak = " ".join(kaynaklar.values())
    for item in result.get("translations") or []:
        if not isinstance(item, dict):
            continue
        korunan = [str(terim.get("text") if isinstance(terim, dict) else terim) for terim in item.get("kept_terms") or []]
        for sira, aday in enumerate(item.get("candidates") or []):
            sorun = metin_dili_sorunu(str(aday or ""), kod, tum_kaynak, korunan)
            if sorun:
                ihlaller.append(f"segment {item.get('id')} aday {sira}: {sorun}")
    return ihlaller
