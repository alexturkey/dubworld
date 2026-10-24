"""RVC dönüştürücü: resmî RVC WebUI `infer/cli.py` komut satırını AYRI SÜREÇTE, kendi sanal ortamında çalıştırır.

Kurulum (kullanıcı yapar, docs/motorlar/rvc.md):
  DUBLAJ_RVC_KOK    = resmî depo klonu (github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI)
  DUBLAJ_RVC_PYTHON = o deponun sanal ortamının python'u (boşsa <kök>/.venv/... ya da <kök>/venv/... aranır)
Akış: karışım sesi wav → RVC → kaynağın sessiz aralıkları yeniden susturulur (RVC'nin nefes/uğultu üretmesini
önler) → hattın örnekleme hızına döner. Dönüştürme başarısızsa hata verir (sessizce orijinal sese düşmez).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
RVC_RESMI_DEPO = "https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI"
RVC_SINANAN_COMMIT = "81eed5e8f68b6bed1789f682fe78cdd324495afc"  # infer/cli.py argümanları bu commit'ten okundu
ZAMAN_ASIMI_SN = 7200
KURULUM_IPUCU = (
    "RVC kurulu değil: resmî RVC WebUI'yi kurup DUBLAJ_RVC_KOK (ve gerekirse DUBLAJ_RVC_PYTHON) ortam "
    "değişkenini verin; ayrıntı docs/motorlar/rvc.md"
)
RIZA_METNI = (
    "RVC rıza onayı yok: modelin sesi size ait değilse sesin sahibinin açık izni gerekir. Onaylıyorsanız "
    "ses.rvc_riza_onayi = true (ETHICS.md)."
)


class RvcHatasi(RuntimeError):
    pass


class RvcKuruluDegil(RvcHatasi):
    pass


class RvcRizaHatasi(RvcHatasi):
    pass


@dataclass(frozen=True)
class RvcAyar:
    model_yolu: str
    index_yolu: str = ""
    perde: int = 0  # yarım ton
    index_orani: float = 0.75
    rms_karisim: float = 0.25
    koruma: float = 0.33
    sessizlik_db: float = -45.0
    en_kisa_sessizlik_sn: float = 0.15
    yumusatma_ms: int = 40


def rvc_ayari_cfgden(cfg: Any) -> RvcAyar | None:
    """DubConfig'ten RVC ayarı; model yolu boşsa None (RVC kapalı). Rıza yoksa RvcRizaHatasi."""
    model = str(getattr(cfg, "rvc_model_yolu", "") or "").strip()
    if not model:
        return None
    if not bool(getattr(cfg, "rvc_riza_onayi", False)):
        raise RvcRizaHatasi(RIZA_METNI)
    return RvcAyar(model_yolu=model, index_yolu=str(getattr(cfg, "rvc_index_yolu", "") or "").strip(),
                   perde=int(getattr(cfg, "rvc_perde", 0) or 0))


def _rvc_kok() -> Path | None:
    deger = os.environ.get("DUBLAJ_RVC_KOK", "").strip()
    return Path(deger).expanduser() if deger else None


def _rvc_python(kok: Path | None) -> Path | None:
    deger = os.environ.get("DUBLAJ_RVC_PYTHON", "").strip()
    if deger:
        return Path(deger).expanduser()
    if kok is None:
        return None
    for aday in (".venv/Scripts/python.exe", "venv/Scripts/python.exe", ".venv/bin/python", "venv/bin/python"):
        if (kok / aday).is_file():
            return kok / aday
    return None


def rvc_durumu() -> dict[str, Any]:
    kok = _rvc_kok()
    python = _rvc_python(kok)
    cli = kok / "infer" / "cli.py" if kok else None
    kurulu = bool(kok and cli and cli.is_file() and python and python.is_file())
    return {"kurulu": kurulu, "kok": str(kok or ""), "python": str(python or ""), "cli": str(cli or "")}


def komut_olustur(python: str, cli: str, girdi: str, cikti: str, ayar: RvcAyar) -> list[str]:
    komut = [
        python, cli, "--model", ayar.model_yolu, "--input", girdi, "--output", cikti,
        "--pitch", str(int(ayar.perde)), "--f0-method", "rmvpe",
        "--index-rate", str(ayar.index_orani), "--rms-mix-rate", str(ayar.rms_karisim),
        "--protect", str(ayar.koruma), "--format", "wav", "--overwrite",
    ]
    if ayar.index_yolu:
        komut += ["--index", ayar.index_yolu]
    return komut


def sessizlik_araliklari(ses: np.ndarray, sr: int, esik_db: float, en_kisa_sn: float) -> list[tuple[float, float]]:
    import numpy as np
    """10 ms çerçeve RMS'i eşiğin altında kalan, en az `en_kisa_sn` süren aralıklar (saniye)."""
    if ses.ndim > 1:
        ses = ses.mean(axis=1)
    cerceve = max(1, int(sr * 0.01))
    sayi = len(ses) // cerceve
    if sayi <= 0:
        return []
    kareler = ses[: sayi * cerceve].reshape(sayi, cerceve)
    rms = np.sqrt(np.mean(kareler * kareler, axis=1) + 1e-12)
    sessiz = rms < 10 ** (esik_db / 20.0)
    en_az = max(1, int(en_kisa_sn / 0.01))
    araliklar: list[tuple[float, float]] = []
    bas: int | None = None
    for i, s in enumerate(sessiz):
        if s and bas is None:
            bas = i
        elif not s and bas is not None:
            if i - bas >= en_az:
                araliklar.append((bas * 0.01, i * 0.01))
            bas = None
    if bas is not None and sayi - bas >= en_az:
        araliklar.append((bas * 0.01, len(ses) / sr))
    return araliklar


def sessizligi_maskele(ses: np.ndarray, sr: int, araliklar: list[tuple[float, float]], yumusatma_ms: int) -> np.ndarray:
    import numpy as np
    cikti = np.array(ses, dtype=np.float32, copy=True)
    tek = cikti.ndim == 1
    if tek:
        cikti = cikti[:, None]
    yumusak = max(1, int(sr * yumusatma_ms / 1000.0))
    for bas_sn, son_sn in araliklar:
        bas = max(0, min(len(cikti), int(bas_sn * sr)))
        son = max(0, min(len(cikti), int(son_sn * sr)))
        if son <= bas:
            continue
        sol = max(0, bas - yumusak)
        if bas > sol:
            cikti[sol:bas] *= np.linspace(1.0, 0.0, bas - sol, endpoint=False, dtype=np.float32)[:, None]
        cikti[bas:son] = 0.0
        sag = min(len(cikti), son + yumusak)
        if sag > son:
            cikti[son:sag] *= np.linspace(0.0, 1.0, sag - son, endpoint=False, dtype=np.float32)[:, None]
    return cikti[:, 0] if tek else cikti


def _yeniden_ornekle(ses: np.ndarray, kaynak_sr: int, hedef_sr: int) -> np.ndarray:
    import numpy as np
    if kaynak_sr == hedef_sr or len(ses) == 0:
        return ses.astype(np.float32)
    from math import gcd

    from scipy.signal import resample_poly

    bolen = gcd(int(kaynak_sr), int(hedef_sr))
    return resample_poly(ses, hedef_sr // bolen, kaynak_sr // bolen).astype(np.float32)


def rvc_karisima_uygula(karisim: np.ndarray, sr: int, ayar: RvcAyar, calisma: str | Path, logger: Any = None) -> np.ndarray:
    """Tek kanallı karışım sesini RVC'den geçirir; aynı uzunlukta, aynı örnekleme hızında ses döndürür."""
    import numpy as np
    import soundfile as sf

    durum = rvc_durumu()
    if not durum["kurulu"]:
        raise RvcKuruluDegil(KURULUM_IPUCU)
    if not Path(ayar.model_yolu).is_file():
        raise RvcHatasi(f"RVC modeli bulunamadı: {Path(ayar.model_yolu).name}")
    if ayar.index_yolu and not Path(ayar.index_yolu).is_file():
        raise RvcHatasi(f"RVC index dosyası bulunamadı: {Path(ayar.index_yolu).name}")
    klasor = Path(calisma) / "rvc"
    klasor.mkdir(parents=True, exist_ok=True)
    girdi, cikti = klasor / "rvc_girdi.wav", klasor / "rvc_cikti.wav"
    tek = np.asarray(karisim, dtype=np.float32)
    if tek.ndim > 1:
        tek = tek.mean(axis=1)
    sf.write(str(girdi), tek, sr, subtype="PCM_16")
    araliklar = sessizlik_araliklari(tek, sr, ayar.sessizlik_db, ayar.en_kisa_sessizlik_sn)
    basla = time.perf_counter()
    tamam = subprocess.run(
        komut_olustur(durum["python"], durum["cli"], str(girdi), str(cikti), ayar),
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=ZAMAN_ASIMI_SN,
        stdin=subprocess.DEVNULL, creationflags=NO_WINDOW, cwd=durum["kok"],
    )
    sure = round(time.perf_counter() - basla, 3)
    if tamam.returncode != 0 or not cikti.is_file():
        son = (tamam.stderr or tamam.stdout or "").strip()[-1200:]
        raise RvcHatasi(f"RVC dönüştürme başarısız (çıkış {tamam.returncode}): {son}")
    donmus, donmus_sr = sf.read(str(cikti), dtype="float32", always_2d=False)
    if donmus.ndim > 1:
        donmus = donmus.mean(axis=1)
    donmus = _yeniden_ornekle(donmus, int(donmus_sr), sr)
    if len(donmus) < len(tek):
        donmus = np.pad(donmus, (0, len(tek) - len(donmus)))
    donmus = sessizligi_maskele(donmus[: len(tek)], sr, araliklar, ayar.yumusatma_ms)
    rapor = {**asdict(ayar), "model_yolu": Path(ayar.model_yolu).name, "index_yolu": Path(ayar.index_yolu).name,
             "sure_sn": sure, "sessiz_aralik": len(araliklar), "rvc_commit_sinanan": RVC_SINANAN_COMMIT}
    (klasor / "rvc_rapor.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")
    for gecici in (girdi, cikti):
        gecici.unlink(missing_ok=True)
    if logger:
        logger.info("[RVC] dönüştürüldü: %.1f sn ses, %.1f sn sürdü, %d sessiz aralık korundu",
                    len(tek) / sr, sure, len(araliklar))
    return donmus.astype(np.float32)
