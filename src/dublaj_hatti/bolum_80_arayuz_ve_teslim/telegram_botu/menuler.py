"""Ayar menüsü (saf işlevler): seçenekler ayar katmanının şemasından (`is_yurutucu.ayar_formu`) gelir, bot ayrı
bir seçenek listesi tutmaz. Yalnız seçimli ve evet/hayır ayarları menüde; serbest metin ayarları CLI/GUI/web'de.

Geri çağırma verisi Telegram sınırı (64 bayt) içinde kalsın diye sıra numarasıyla kodlanır: `b:<bölüm>`,
`a:<anahtar no>`, `d:<anahtar no>:<değer no>`, `s` (sıfırla), `k` (kapat).
"""

from __future__ import annotations

from typing import Any

MENUDE_TURLER = ("secim", "evet_hayir")


def menu_ogeleri(form: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [o for o in form if o["tur"] in MENUDE_TURLER]


def bolumler(ogeler: list[dict[str, Any]]) -> list[str]:
    gorulen: list[str] = []
    for o in ogeler:
        if o["bolum"] not in gorulen:
            gorulen.append(o["bolum"])
    return gorulen


def secenekler(oge: dict[str, Any]) -> list[Any]:
    return [True, False] if oge["tur"] == "evet_hayir" else list(oge["secenekler"])


def deger_metni(deger: Any) -> str:
    if isinstance(deger, bool):
        return "evet" if deger else "hayır"
    return str(deger)


def geri_cagirma_coz(veri: str, ogeler: list[dict[str, Any]]) -> tuple[str, Any]:
    """('bolum', ad) | ('anahtar', oge) | ('deger', (anahtar, değer)) | ('sifirla', None) | ('kapat', None)."""
    parcalar = (veri or "").split(":")
    try:
        if parcalar[0] == "b" and len(parcalar) == 2 and parcalar[1] in bolumler(ogeler):
            return "bolum", parcalar[1]
        if parcalar[0] == "a" and len(parcalar) == 2:
            return "anahtar", ogeler[int(parcalar[1])]
        if parcalar[0] == "d" and len(parcalar) == 3:
            oge = ogeler[int(parcalar[1])]
            return "deger", (oge["anahtar"], secenekler(oge)[int(parcalar[2])])
    except (ValueError, IndexError):
        pass
    if veri == "s":
        return "sifirla", None
    return "kapat", None


def bolum_dugmeleri(ogeler: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(b, f"b:{b}") for b in bolumler(ogeler)] + [("Varsayılana dön", "s"), ("Kapat", "k")]


def anahtar_dugmeleri(ogeler: list[dict[str, Any]], bolum: str, secimler: dict[str, Any]) -> list[tuple[str, str]]:
    cikti = []
    for i, o in enumerate(ogeler):
        if o["bolum"] == bolum:
            deger = secimler.get(o["anahtar"], o["deger"])
            cikti.append((f"{o['anahtar'].split('.', 1)[1]} = {deger_metni(deger)}", f"a:{i}"))
    return cikti


def deger_dugmeleri(ogeler: list[dict[str, Any]], oge: dict[str, Any]) -> list[tuple[str, str]]:
    i = ogeler.index(oge)
    return [(deger_metni(d), f"d:{i}:{j}") for j, d in enumerate(secenekler(oge))]
