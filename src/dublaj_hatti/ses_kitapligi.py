"""Ses kitaplığı: kullanıcının kendi (ya da sahibinin izin verdiği) referans sesleri, yalnız bu bilgisayarda.

Her ses bir klasör: `ayarlar/ses_kitapligi/<kimlik>/ses.wav` (24 kHz mono, ffmpeg ile dönüştürülür) +
`kimlik.json` (ad, kategori, süre, isteğe bağlı kayıt metni, sabit tohum, rıza kaydı). Klasör git dışıdır; yer
`DUBLAJ_SES_KITAPLIGI` ile değişir. Rıza kaydı olmadan ses eklenmez: tür ("kendi" = benim sesim, "izinli" = sahibinin
açık izni), tarih ve "gerçek kişiyi izinsiz taklit etmeyeceğim" onayı (ETHICS.md).

Kitaplıktaki ses varsayılan olarak VoxCPM2'ye referans olur: ses kimliği `kitaplik/<kimlik>` (ses.voxcpm2_ses,
ses.voxcpm2_kadin_sesleri / erkek_sesleri, ses.konusmaci_sesleri). VoxCPM2 yalnız sesten klonlar, metin gerekmez
(Apache-2.0, lisans kapısı yok); kayıtta ne söylendiği yazıldıysa (`metin`) referans metin olarak verilir ve benzerlik
artar. Her kayıtta eklenirken bir `tohum` saklanır: aynı ses her okumada aynı tohumla çalışır (tutarlılık).
XTTS v2 yalnız kuruluysa isteğe bağlı bir seçenektir (ses.motor = xtts, ses.xtts_referans_ses = <ses.wav>; ticari
olmayan lisans, onay gerekir; kullanımdan kalkıyor).
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dublaj_hatti.yapilandirma import PROJE_KOKU

KITAPLIK_ORTAM = "DUBLAJ_SES_KITAPLIGI"
KATEGORILER = ("kadin", "erkek", "cocuk", "genc", "yasli", "diger")
RIZA_TURLERI = ("kendi", "izinli")
SES_UZANTILARI = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".webm"}
EN_KISA_SN, EN_UZUN_SN = 3.0, 30.0  # önerilen 6-15 sn; bu sınırlar yalnız açık hatayı yakalar
AD_SINIRI = 60
METIN_SINIRI = 600  # kaydın metni (isteğe bağlı): VoxCPM2 referans metni
KITAPLIK_ONEKI = "kitaplik/"  # ses kimliği biçimi: kitaplik/<kimlik>
RIZA_SURUMU = 1  # rıza metni değişirse artar; eski kayıtlar hangi metne onay verildiğini korur
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_KIMLIK = re.compile(r"[0-9a-f]{32}")
_DENETIM_KARAKTERI = re.compile(r"[\x00-\x1f\x7f]")


class SesKitapligiHatasi(ValueError):
    """Kullanıcıya gösterilecek açık hata (geçersiz ad, rıza yok, kısa kayıt ...).

    `anahtar` arayüzün kendi dilinde göstermesi için sabit bir kimliktir (web yanıtında "anahtar").
    """

    def __init__(self, mesaj: str, anahtar: str = "") -> None:
        super().__init__(mesaj)
        self.anahtar = anahtar


def kok() -> Path:
    acik = os.environ.get(KITAPLIK_ORTAM, "").strip()
    return Path(acik).expanduser().resolve() if acik else PROJE_KOKU / "ayarlar" / "ses_kitapligi"


def _klasor(kimlik: str) -> Path:
    if not _KIMLIK.fullmatch(str(kimlik or "")):
        raise SesKitapligiHatasi("geçersiz ses kimliği", "kimlik_gecersiz")
    klasor = kok() / kimlik
    if not (klasor / "kimlik.json").is_file():
        raise SesKitapligiHatasi("ses bulunamadı: Sesler sekmesinden ekleyin ya da başka bir ses seçin", "ses_yok")
    return klasor


def _ad(ad: Any) -> str:
    temiz = " ".join(str(ad or "").split())
    if not temiz or len(temiz) > AD_SINIRI or _DENETIM_KARAKTERI.search(temiz):
        raise SesKitapligiHatasi(f"ad 1-{AD_SINIRI} karakter olmalı", "ad_gecersiz")
    return temiz


def _kategori(kategori: Any) -> str:
    if kategori not in KATEGORILER:
        raise SesKitapligiHatasi("kategori: " + ", ".join(KATEGORILER), "kategori_gecersiz")
    return str(kategori)


def _metin(metin: Any) -> str:
    """Kaydın metni: denetim karakterleri ve art arda boşluklar temizlenir; boş olabilir, en çok 600 karakter."""
    temiz = " ".join(_DENETIM_KARAKTERI.sub(" ", str(metin or "")).split())
    if len(temiz) > METIN_SINIRI:
        raise SesKitapligiHatasi(f"kaydın metni en çok {METIN_SINIRI} karakter olabilir; bu {len(temiz)}", "metin_uzun")
    return temiz


def _kaydi_oku(klasor: Path) -> dict[str, Any]:
    kayit = json.loads((klasor / "kimlik.json").read_text(encoding="utf-8"))
    kayit["yol"] = str(klasor / "ses.wav")
    return kayit


def _kaydi_yaz(klasor: Path, kayit: dict[str, Any]) -> None:
    veri = {k: v for k, v in kayit.items() if k != "yol"}
    gecici = klasor / "kimlik.json.tmp"
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")
    gecici.replace(klasor / "kimlik.json")


def listele() -> list[dict[str, Any]]:
    """Kitaplıktaki sesler, son eklenen önce. Bozuk kayıt atlanır (liste hiçbir zaman düşmez)."""
    if not kok().is_dir():
        return []
    sesler = []
    for klasor in kok().iterdir():
        if _KIMLIK.fullmatch(klasor.name) and (klasor / "kimlik.json").is_file() and (klasor / "ses.wav").is_file():
            try:
                sesler.append(_kaydi_oku(klasor))
            except (OSError, ValueError):
                continue
    return sorted(sesler, key=lambda s: (str(s.get("eklendi", "")), str(s.get("kimlik", ""))), reverse=True)


def _sure(yol: Path) -> float:
    with wave.open(str(yol), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def ekle(kaynak: str | Path, ad: str, kategori: str, riza: str, taklit_yok: bool, dosya_adi: str = "",
         metin: str = "") -> dict:
    """Ses dosyasını kitaplığa ekler (24 kHz mono wav). Rıza türü ve taklit onayı zorunlu; `metin` isteğe bağlı."""
    ad, kategori, metin = _ad(ad), _kategori(kategori), _metin(metin)
    if riza not in RIZA_TURLERI:
        raise SesKitapligiHatasi("rıza gerekli: kendi sesiniz ya da sahibinin açık izni", "riza_yok")
    if taklit_yok is not True:
        raise SesKitapligiHatasi("gerçek bir kişiyi izinsiz taklit etmeme onayı gerekli (ETHICS.md)", "taklit_yok")
    uzanti = Path(dosya_adi or str(kaynak)).suffix.lower()
    if uzanti not in SES_UZANTILARI:
        raise SesKitapligiHatasi("desteklenen ses dosyaları: " + ", ".join(sorted(SES_UZANTILARI)), "uzanti_gecersiz")
    from dublaj_hatti.bolum_00_omurga.runtime.arac_yolu import arac_bul

    ffmpeg = arac_bul("ffmpeg")
    if not ffmpeg:
        raise SesKitapligiHatasi("ffmpeg bulunamadı: scripts/kur.ps1 -Adim modeller", "ffmpeg_yok")
    kok().mkdir(parents=True, exist_ok=True)
    kimlik = uuid.uuid4().hex
    gecici = Path(tempfile.mkdtemp(prefix=".ekle_", dir=kok()))
    try:
        wav = gecici / "ses.wav"
        sonuc = subprocess.run([ffmpeg, "-nostdin", "-y", "-v", "error", "-i", str(kaynak), "-vn", "-ac", "1",
                                "-ar", "24000", "-c:a", "pcm_s16le", str(wav)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               creationflags=NO_WINDOW)
        if sonuc.returncode != 0 or not wav.is_file():
            raise SesKitapligiHatasi("ses dosyası okunamadı", "okunamadi")
        try:
            sure = round(_sure(wav), 2)
        except (EOFError, OSError, ValueError, ZeroDivisionError, wave.Error) as sorun:
            raise SesKitapligiHatasi("ses dosyası okunamadı", "okunamadi") from sorun
        if not EN_KISA_SN <= sure <= EN_UZUN_SN:
            raise SesKitapligiHatasi(f"kayıt {EN_KISA_SN:g}-{EN_UZUN_SN:g} sn olmalı (önerilen 6-15 sn); bu {sure:g} sn",
                                     "sure_disi")
        kayit = {"kimlik": kimlik, "ad": ad, "kategori": kategori, "sure_sn": sure,
                 "eklendi": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                 "metin": metin, "tohum": random.randrange(1, 2**31),  # sabit tohum: aynı ses hep aynı tohumla okunur
                 "riza": {"tur": riza, "taklit_yok": True, "surum": RIZA_SURUMU}}
        _kaydi_yaz(gecici, kayit)
        hedef = kok() / kimlik
        gecici.replace(hedef)
        return _kaydi_oku(hedef)
    finally:
        shutil.rmtree(gecici, ignore_errors=True)


def guncelle(kimlik: str, ad: str | None = None, kategori: str | None = None, metin: str | None = None) -> dict:
    """Ad, kategori ve kaydın metnini değiştirir (None = dokunma; metin "" = metni sil)."""
    klasor = _klasor(kimlik)
    kayit = _kaydi_oku(klasor)
    if ad is not None:
        kayit["ad"] = _ad(ad)
    if kategori is not None:
        kayit["kategori"] = _kategori(kategori)
    if metin is not None:
        kayit["metin"] = _metin(metin)
    _kaydi_yaz(klasor, kayit)
    return _kaydi_oku(klasor)


def sil(kimlik: str) -> None:
    """Sesi ve kaydını kalıcı siler (yalnız kitaplığın kendi klasörü)."""
    klasor = _klasor(kimlik)
    shutil.rmtree(klasor)


def bul(yol: str | Path) -> dict | None:
    """Ayardaki referans ses yolu kitaplıktaki bir sesse onun kaydı (arayüz seçili sesi adıyla gösterir)."""
    try:
        hedef = Path(yol).resolve()
    except (OSError, ValueError):
        return None
    return next((s for s in listele() if Path(s["yol"]).resolve() == hedef), None)


def kitaplik_mi(ses: Any) -> bool:
    return str(ses or "").startswith(KITAPLIK_ONEKI)


def coz(ses: str) -> dict[str, Any]:
    """`kitaplik/<kimlik>` → VoxCPM2'ye verilecek referans: {yol, metin, tohum, ad}. Yoksa yol gösteren hata.

    `metin` boşsa yalnız sesten klonlanır. Eski kayıtta tohum yoksa kimlikten türetilir (yine sabit).
    """
    kimlik = str(ses or "")[len(KITAPLIK_ONEKI):] if kitaplik_mi(ses) else ""
    if not _KIMLIK.fullmatch(kimlik) or not (kok() / kimlik / "kimlik.json").is_file():
        raise SesKitapligiHatasi(
            f"ses kitaplığında '{ses}' yok: Sesler sekmesinden ekleyin ya da ayarda başka bir ses seçin "
            f"(biçim kitaplik/<kimlik>)", "ses_yok")
    kayit = _kaydi_oku(kok() / kimlik)
    if not Path(kayit["yol"]).is_file():
        raise SesKitapligiHatasi(f"'{kayit.get('ad', kimlik)}' sesinin ses dosyası eksik: sesi silip yeniden ekleyin",
                                 "ses_dosyasi_yok")
    tohum = kayit.get("tohum")
    return {"yol": kayit["yol"], "metin": str(kayit.get("metin") or ""), "ad": str(kayit.get("ad") or kimlik),
            "tohum": tohum if isinstance(tohum, int) and tohum > 0 else int(kimlik[:8], 16) % (2**31 - 1) + 1}
