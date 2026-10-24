"""Cikti videosuna "yapay zeka ile dublajlandi / AI-dubbed" meta etiketi (AB Yapay Zeka Yasasi md. 50 seffaflik notu).

Yeniden kodlama yok: ffmpeg `-c copy` ile kap (container) meta alanlari yazilir, sonra dosya yerine konur.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict
from dublaj_hatti.bolum_00_omurga.runtime.arac_yolu import arac_bul

ETIKET_TR = "Bu videonun sesi yapay zeka ile dublajlandi (sentetik ses)."
ETIKET_EN = "AI-dubbed: the audio track of this video is AI-generated (synthetic speech)."
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def yapay_zeka_etiketi_ekle(video_yolu: str | os.PathLike, araci: str = "DubWorld") -> Dict[str, Any]:
    kaynak = Path(video_yolu)
    ffmpeg = arac_bul("ffmpeg")
    if not ffmpeg or not kaynak.is_file():
        return {"ai_label": False, "neden": "ffmpeg ya da video yok"}
    gecici = kaynak.with_name(kaynak.stem + ".etiket" + kaynak.suffix)
    komut = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(kaynak), "-map", "0", "-c", "copy",
        "-metadata", f"comment={ETIKET_EN} / {ETIKET_TR}",
        "-metadata", f"description={ETIKET_EN}",
        "-metadata", f"encoded_by={araci}",
        "-metadata:s:a:0", "title=AI-dubbed (synthetic speech)",
        str(gecici),
    ]
    sonuc = subprocess.run(komut, capture_output=True, text=True, errors="replace", creationflags=NO_WINDOW)
    if sonuc.returncode != 0 or not gecici.is_file():
        gecici.unlink(missing_ok=True)
        return {"ai_label": False, "neden": (sonuc.stderr or "")[-300:]}
    os.replace(gecici, kaynak)
    return {"ai_label": True, "ai_label_text": ETIKET_EN}
