"""Ayar menüsü (saf işlevler): seçenekler ayar katmanının şemasından (`is_yurutucu.ayar_formu`) gelir, bot ayrı
bir seçenek listesi tutmaz. Menüde: seçimli ve evet/hayır ayarları, ayrıca hazır değerli birkaç tam sayı ve metin
ayarı (kaynak uygulamanın Telegram menüsüyle aynı hazır değerler + "özel değer gir"). Diğer serbest metin / sayı
ayarları CLI/GUI/web'de.

Geri çağırma verisi Telegram sınırı (64 bayt) içinde kalsın diye sıra numarasıyla kodlanır: `b:<bölüm>`,
`a:<anahtar no>`, `d:<anahtar no>:<değer no>`, `o:<anahtar no>` (özel değer iste), `s` (sıfırla), `k` (kapat).
"""

from __future__ import annotations

from typing import Any

MENUDE_TURLER = ("secim", "evet_hayir")
# Hazır düğmeler ve "özel değer gir" aralığı (kaynak uygulama final video menüsü: CQ 23/26/30/40, 1-51;
# en çok boyut 100/179 (WhatsApp)/500/1000 MB, 1-2000).
HAZIR_DEGERLER: dict[str, list[int]] = {"video.cq": [23, 26, 30, 40], "video.max_mb": [100, 179, 500, 1000]}
HAZIR_ETIKETLER: dict[tuple[str, int], str] = {
    ("video.cq", 23): "yüksek kalite", ("video.cq", 26): "dengeli", ("video.cq", 30): "daha küçük",
    ("video.cq", 40): "agresif", ("video.max_mb", 179): "WhatsApp",
}
OZEL_ARALIK: dict[str, tuple[int, int]] = {"video.cq": (1, 51), "video.max_mb": (1, 2000)}
# Değer seçilince birlikte değişen ayar: kalite ya da boyut seçimi video politikasını da seçer (kaynakta da öyle).
BIRLIKTE: dict[str, dict[str, Any]] = {"video.cq": {"video.politika": "cq"}, "video.max_mb": {"video.politika": "max_mb"}}
# transkripsiyon.model yalnız faster-whisper ailesinde anlamlı (varsayilan.toml: diğer motorların modeli sabit).
MODEL_ANAHTARI = "transkripsiyon.model"
MOTOR_ANAHTARI = "transkripsiyon.motor"
MODELLI_MOTORLAR = frozenset({"auto", "faster-whisper", "faster_whisper_ctc", "whisperx"})
MODEL_SECENEKLERI = ["large-v3-turbo", "distil-large-v3", "distil-large-v3.5"]


def menu_ogeleri(form: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [o for o in form if o["tur"] in MENUDE_TURLER or o["anahtar"] in HAZIR_DEGERLER
            or o["anahtar"] == MODEL_ANAHTARI]


def _motor(ogeler: list[dict[str, Any]], secimler: dict[str, Any] | None) -> str:
    if secimler and MOTOR_ANAHTARI in secimler:
        return str(secimler[MOTOR_ANAHTARI])
    return str(next((o["deger"] for o in ogeler if o["anahtar"] == MOTOR_ANAHTARI), "auto"))


def gorunur_mu(oge: dict[str, Any], ogeler: list[dict[str, Any]], secimler: dict[str, Any] | None = None) -> bool:
    """Model ayarı yalnız modeli seçilebilen motorda gösterilir."""
    return oge["anahtar"] != MODEL_ANAHTARI or _motor(ogeler, secimler) in MODELLI_MOTORLAR


def bolumler(ogeler: list[dict[str, Any]]) -> list[str]:
    gorulen: list[str] = []
    for o in ogeler:
        if o["bolum"] not in gorulen:
            gorulen.append(o["bolum"])
    return gorulen


def secenekler(oge: dict[str, Any]) -> list[Any]:
    if oge["anahtar"] in HAZIR_DEGERLER:
        return list(HAZIR_DEGERLER[oge["anahtar"]])
    if oge["anahtar"] == MODEL_ANAHTARI:
        return list(MODEL_SECENEKLERI)
    return [True, False] if oge["tur"] == "evet_hayir" else list(oge["secenekler"])


def deger_metni(deger: Any) -> str:
    if isinstance(deger, bool):
        return "evet" if deger else "hayır"
    return str(deger)


def birlikte_degisen(anahtar: str) -> dict[str, Any]:
    return dict(BIRLIKTE.get(anahtar, {}))


def ozel_deger_coz(oge: dict[str, Any], metin: str) -> int:
    """Kullanıcının yazdığı özel değer: tam sayı ve aralıkta olmalı, yoksa ValueError (ne beklendiği yazılı)."""
    alt, ust = OZEL_ARALIK[oge["anahtar"]]
    temiz = (metin or "").strip().lower().removesuffix("mb").strip()
    if not temiz.isdigit():
        raise ValueError(f"{oge['anahtar']}: tam sayı girin ({alt}-{ust})")
    deger = int(temiz)
    if not alt <= deger <= ust:
        raise ValueError(f"{oge['anahtar']}: {alt}-{ust} aralığında olmalı (girilen {deger})")
    return deger


def ozel_istem_metni(oge: dict[str, Any]) -> str:
    alt, ust = OZEL_ARALIK[oge["anahtar"]]
    birim = " MB" if oge["anahtar"] == "video.max_mb" else ""
    return f"{oge['anahtar']}: özel değeri yazıp gönderin ({alt}-{ust}{birim}). Vazgeçmek için /ayarlar."


def geri_cagirma_coz(veri: str, ogeler: list[dict[str, Any]]) -> tuple[str, Any]:
    """('bolum', ad) | ('anahtar', oge) | ('deger', (anahtar, değer)) | ('ozel', oge) | ('sifirla', None) |
    ('kapat', None)."""
    parcalar = (veri or "").split(":")
    try:
        if parcalar[0] == "b" and len(parcalar) == 2 and parcalar[1] in bolumler(ogeler):
            return "bolum", parcalar[1]
        if parcalar[0] == "a" and len(parcalar) == 2:
            return "anahtar", ogeler[int(parcalar[1])]
        if parcalar[0] == "d" and len(parcalar) == 3:
            oge = ogeler[int(parcalar[1])]
            return "deger", (oge["anahtar"], secenekler(oge)[int(parcalar[2])])
        if parcalar[0] == "o" and len(parcalar) == 2:
            oge = ogeler[int(parcalar[1])]
            if oge["anahtar"] in OZEL_ARALIK:
                return "ozel", oge
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
        if o["bolum"] == bolum and gorunur_mu(o, ogeler, secimler):
            deger = secimler.get(o["anahtar"], o["deger"])
            cikti.append((f"{o['anahtar'].split('.', 1)[1]} = {deger_metni(deger)}", f"a:{i}"))
    return cikti


def deger_dugmeleri(ogeler: list[dict[str, Any]], oge: dict[str, Any]) -> list[tuple[str, str]]:
    i = ogeler.index(oge)
    dugmeler = []
    for j, d in enumerate(secenekler(oge)):
        etiket = HAZIR_ETIKETLER.get((oge["anahtar"], d))
        birim = " MB" if oge["anahtar"] == "video.max_mb" else ""
        dugmeler.append((f"{deger_metni(d)}{birim}" + (f" ({etiket})" if etiket else ""), f"d:{i}:{j}"))
    if oge["anahtar"] in OZEL_ARALIK:
        alt, ust = OZEL_ARALIK[oge["anahtar"]]
        dugmeler.append((f"Özel değer gir ({alt}-{ust})", f"o:{i}"))
    return dugmeler
