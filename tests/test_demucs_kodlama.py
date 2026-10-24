"""Demucs alt sürecinin çıktısı Windows yerel kod sayfasından bağımsız okunur.

Temiz kurulumda (cp1254 konsol) ilerleme çubuğunun UTF-8 karakteri UnicodeDecodeError verip
preserve_background işini düşürüyordu. Bu test, gerçek bir Python alt sürecine UTF-8 blok
karakterleri yazdırır ve okuyucunun çökmediğini doğrular.
"""
import subprocess
import sys

import pytest

demucs_cleaner = pytest.importorskip(
    "dublaj_hatti.bolum_10_kaynak_edinme.adim_50_asr_sesi_hazirlama.demucs_cleaner"
)

COCUK = "import sys; sys.stdout.write('\\u258f\\u258e ilerleme 50%\\n\\u00e7\\u011f\\u0131 hata yok\\n')"


def test_demucs_cocuk_utf8_ciktisi_cokertmez(monkeypatch, tmp_path):
    gercek_popen = subprocess.Popen
    gorulen = {}

    def sahte_popen(cmd, **kw):
        gorulen.update(kw)
        return gercek_popen([sys.executable, "-c", COCUK], **kw)

    monkeypatch.setattr(demucs_cleaner.subprocess, "Popen", sahte_popen)
    ses = tmp_path / "girdi.wav"
    ses.write_bytes(b"")
    # Çocuk başarıyla biter ama çıktı dosyası üretmez: kod sonra kendi hatasını verebilir,
    # UnicodeDecodeError vermemeli.
    try:
        demucs_cleaner.clean_audio_with_demucs(str(ses), str(tmp_path), prefer_device="cpu")
    except UnicodeDecodeError as exc:  # pragma: no cover - hatanın kendisi
        pytest.fail(f"alt süreç çıktısı çözülemedi: {exc}")
    except Exception:
        pass
    assert gorulen.get("encoding") == "utf-8"
    assert gorulen["env"].get("PYTHONIOENCODING") == "utf-8"
