import argparse
import hashlib
import importlib.metadata
import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import psutil
from moonshine_voice.moonshine_api import ModelArch
from moonshine_voice.transcriber import LineCompleted, Transcriber
from moonshine_voice.utils import load_wav_file


def zaman_damgasi_olustur():
    simdi = datetime.now()
    return simdi.strftime("%Y-%m-%d_%H-%M-%S-") + f"{simdi.microsecond // 1000:03d}"


def normalize_kelimeler(metin):
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", metin.lower())


def duzenleme_mesafesi(sol, sag):
    onceki = list(range(len(sag) + 1))
    for sol_indeks, sol_deger in enumerate(sol, 1):
        simdiki = [sol_indeks]
        for sag_indeks, sag_deger in enumerate(sag, 1):
            simdiki.append(
                min(
                    simdiki[-1] + 1,
                    onceki[sag_indeks] + 1,
                    onceki[sag_indeks - 1] + (sol_deger != sag_deger),
                )
            )
        onceki = simdiki
    return onceki[-1]


def dosya_sha256(dosya_yolu):
    ozet = hashlib.sha256()
    with open(dosya_yolu, "rb") as dosya:
        for parca in iter(lambda: dosya.read(1024 * 1024), b""):
            ozet.update(parca)
    return ozet.hexdigest().upper()


class BellekIzleyici:
    def __init__(self):
        self.islem = psutil.Process()
        self.dur = threading.Event()
        self.en_yuksek_rss = self.islem.memory_info().rss
        self.is_parcacigi = threading.Thread(target=self._izle, daemon=True)

    def _izle(self):
        while not self.dur.wait(0.02):
            try:
                self.en_yuksek_rss = max(
                    self.en_yuksek_rss,
                    self.islem.memory_info().rss,
                )
            except psutil.Error:
                return

    def baslat(self):
        self.is_parcacigi.start()

    def bitir(self):
        self.dur.set()
        self.is_parcacigi.join()
        try:
            self.en_yuksek_rss = max(
                self.en_yuksek_rss,
                self.islem.memory_info().rss,
            )
        except psutil.Error:
            pass


def ana():
    ayrac = argparse.ArgumentParser()
    ayrac.add_argument("--audio", required=True)
    ayrac.add_argument("--model-dir", required=True)
    ayrac.add_argument("--reference")
    ayrac.add_argument("--output-root", default="output")
    ayrac.add_argument("--chunk-seconds", type=float, default=0.1)
    ayrac.add_argument("--execution-mode", choices=("streaming", "offline"), default="streaming")
    argumanlar = ayrac.parse_args()

    ses_yolu = Path(argumanlar.audio).resolve()
    model_yolu = Path(argumanlar.model_dir).resolve()
    cikti_yolu = Path(argumanlar.output_root).resolve() / zaman_damgasi_olustur()
    cikti_yolu.mkdir(parents=True, exist_ok=False)

    ses_verisi, ornekleme_hizi = load_wav_file(str(ses_yolu))
    ses_suresi = len(ses_verisi) / ornekleme_hizi
    referans_metin = ""
    if argumanlar.reference:
        referans_metin = Path(argumanlar.reference).read_text(encoding="utf-8")

    bellek_izleyici = BellekIzleyici()
    bellek_izleyici.baslat()
    yukleme_baslangici = time.perf_counter()
    transcriber = Transcriber(
        model_path=model_yolu,
        model_arch=ModelArch.MEDIUM_STREAMING,
        options={"word_timestamps": "true"},
    )
    model_yukleme_suresi = time.perf_counter() - yukleme_baslangici

    tamamlanan_satirlar = []

    def satir_dinleyici(olay):
        if isinstance(olay, LineCompleted):
            tamamlanan_satirlar.append(olay.line)

    parca_boyutu = max(1, int(argumanlar.chunk_seconds * ornekleme_hizi))
    transkripsiyon_baslangici = time.perf_counter()
    if argumanlar.execution_mode == "offline":
        son_transkript = transcriber.transcribe_without_streaming(ses_verisi, ornekleme_hizi)
        tamamlanan_satirlar = son_transkript.lines
    else:
        transcriber.add_listener(satir_dinleyici)
        transcriber.start()
        for indeks in range(0, len(ses_verisi), parca_boyutu):
            transcriber.add_audio(
                ses_verisi[indeks : indeks + parca_boyutu],
                ornekleme_hizi,
            )
        son_transkript = transcriber.stop()
    transkripsiyon_suresi = time.perf_counter() - transkripsiyon_baslangici

    if not tamamlanan_satirlar and son_transkript is not None:
        tamamlanan_satirlar = son_transkript.lines
    transcriber.close()
    bellek_izleyici.bitir()

    metin = " ".join(
        satir.text.strip()
        for satir in tamamlanan_satirlar
        if satir.text and satir.text.strip()
    )
    kelimeler = normalize_kelimeler(metin)
    if not kelimeler:
        raise RuntimeError("No lexical transcript produced; run is not accepted")
    referans_kelimeler = normalize_kelimeler(referans_metin)
    mesafe = None
    if referans_kelimeler:
        mesafe = duzenleme_mesafesi(referans_kelimeler, kelimeler)

    kelime_zamanlari = []
    for satir in tamamlanan_satirlar:
        for kelime in satir.words or []:
            kelime_zamanlari.append(
                {
                    "word": kelime.word,
                    "start": kelime.start,
                    "end": kelime.end,
                    "confidence": kelime.confidence,
                }
            )

    sonuc = {
        "engine": "moonshine-voice",
        "package_version": importlib.metadata.version("moonshine-voice"),
        "model": "medium-streaming-en",
        "model_arch": "MEDIUM_STREAMING",
        "quantization": "official_quantized_ort",
        "device": "cpu",
        "audio_path": str(ses_yolu),
        "audio_sha256": dosya_sha256(ses_yolu),
        "audio_duration_seconds": ses_suresi,
        "sample_rate": ornekleme_hizi,
        "model_load_seconds": model_yukleme_suresi,
        "transcription_seconds": transkripsiyon_suresi,
        "real_time_factor": transkripsiyon_suresi / ses_suresi,
        "peak_process_rss_mb": bellek_izleyici.en_yuksek_rss / (1024 * 1024),
        "normalized_word_count": len(kelimeler),
        "reference_normalized_word_count": len(referans_kelimeler) if referans_kelimeler else None,
        "word_edit_distance": mesafe,
        "line_count": len(tamamlanan_satirlar),
        "word_timestamp_count": len(kelime_zamanlari),
        "execution_mode": argumanlar.execution_mode,
        "chunk_seconds": argumanlar.chunk_seconds if argumanlar.execution_mode == "streaming" else None,
        "transcript": metin,
        "normalized_words": kelimeler,
        "word_timestamps": kelime_zamanlari,
    }

    (cikti_yolu / "transcript.txt").write_text(metin + "\n", encoding="utf-8")
    (cikti_yolu / "result.json").write_text(
        json.dumps(sonuc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(cikti_yolu),
                "transcription_seconds": transkripsiyon_suresi,
                "normalized_word_count": len(kelimeler),
                "word_edit_distance": mesafe,
                "peak_process_rss_mb": sonuc["peak_process_rss_mb"],
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    ana()
